# region MODULE_CONTRACT [DOMAIN(9): KServe; CONCEPT(9): ProtocolAdapter, TensorEncode; TECH(9): numpy, json]
## @modulecontract
## @purpose Translate KServe v2 HTTP infer requests into vision API calls and encode parsed results as KServe tensors per docling engine contracts.
## @scope Protocol layer only; delegates HTTP to ExternalApiClient and parsing to parser registry.
## @links [USES_API(9): doclingllm.gateway.client.ExternalApiClient]
## @links [USES_API(8): doclingllm.gateway.parsers.get_parser]
## @changes
## LAST_CHANGE: [v0.2.8 – stage-specific KServe metadata and tensor encode/decode for layout OD, OCR, picture_classifier.]
## @modulemap
## FUNC 10[Handle KServe infer request] => handle_kserve_infer
## FUNC 8[Build model metadata by name] => build_kserve_model_metadata
## FUNC 8[Decode image tensor from KServe body] => decode_image_from_kserve_request
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: KServe v2, infer, tensor, object detection, layout, OCR, picture_classifier, metadata
# STRUCTURE: ▶ model_name → ◇ metadata|infer branch → ⚡ vision_inference → ◇ parser → ⊕ tensor encode → ⎋ KServe JSON

import base64
import json
import logging
from io import BytesIO
from typing import Any, Optional

import numpy as np

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.parsers import get_parser
from doclingllm.gateway.routing import RoutingTable, resolve_stage_route

logger = logging.getLogger(__name__)

KSERVE_MODEL_TO_STAGE: dict[str, str] = {
    "ocr": "ocr",
    "layout": "layout",
    "table": "table",
    "picture_classifier": "picture_classification",
}

KSERVE_MODEL_VERSION = "1"
KSERVE_MODEL_PLATFORM = "doclingllm"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)

LAYOUT_HERON_LABEL2ID: dict[str, int] = {
    "caption": 0,
    "footnote": 1,
    "formula": 2,
    "list-item": 3,
    "list_item": 3,
    "page-footer": 4,
    "page_footer": 4,
    "page-header": 5,
    "page_header": 5,
    "picture": 6,
    "section-header": 7,
    "section_header": 7,
    "table": 8,
    "text": 9,
    "title": 10,
    "document index": 11,
    "document_index": 11,
    "code": 12,
    "checkbox-selected": 13,
    "checkbox_selected": 13,
    "checkbox-unselected": 14,
    "checkbox_unselected": 14,
    "form": 15,
    "key-value region": 16,
    "key_value_region": 16,
}

PICTURE_CLASSIFIER_LABEL2ID: dict[str, int] = {
    "logo": 0,
    "photograph": 1,
    "icon": 2,
    "engineering_drawing": 3,
    "line_chart": 4,
    "bar_chart": 5,
    "other": 6,
    "table": 7,
    "flow_chart": 8,
    "screenshot_from_computer": 9,
    "signature": 10,
    "screenshot_from_manual": 11,
    "geographical_map": 12,
    "pie_chart": 13,
    "page_thumbnail": 14,
    "stamp": 15,
    "music": 16,
    "calendar": 17,
    "qr_code": 18,
    "bar_code": 19,
    "full_page_image": 20,
    "scatter_plot": 21,
    "chemistry_structure": 22,
    "topographical_map": 23,
    "crossword_puzzle": 24,
    "box_plot": 25,
}

PICTURE_CLASSIFIER_NUM_CLASSES = 26
DEFAULT_DETECTION_SCORE = 0.9


# region FUNC_build_kserve_model_metadata [DOMAIN(8): KServe; CONCEPT(8): Metadata; TECH(8): json]
## @purpose Return KServe v2 model metadata matching docling engine expectations per model name.
## @complexity 4
def build_kserve_model_metadata(model_name: str) -> dict[str, Any]:
    if model_name not in KSERVE_MODEL_TO_STAGE:
        raise KeyError(f"Unsupported KServe model name: {model_name}")

    base = {
        "name": model_name,
        "versions": [KSERVE_MODEL_VERSION],
        "platform": KSERVE_MODEL_PLATFORM,
    }

    if model_name == "layout":
        return {
            **base,
            "inputs": [
                {"name": "images", "datatype": "FP32", "shape": [-1, 3, -1, -1]},
                {"name": "orig_target_sizes", "datatype": "INT64", "shape": [-1, 2]},
            ],
            "outputs": [
                {"name": "labels", "datatype": "INT64", "shape": [-1, -1]},
                {"name": "boxes", "datatype": "FP32", "shape": [-1, -1, 4]},
                {"name": "scores", "datatype": "FP32", "shape": [-1, -1]},
            ],
        }

    if model_name == "ocr":
        return {
            **base,
            "inputs": [
                {"name": "lang_type", "datatype": "BYTES", "shape": [1, 1]},
                {"name": "image", "datatype": "UINT8", "shape": [-1, -1, -1, 3]},
            ],
            "outputs": [
                {"name": "boxes", "datatype": "FP32", "shape": [-1, -1, 4, 2]},
                {"name": "txts", "datatype": "BYTES", "shape": [-1, -1]},
                {"name": "scores", "datatype": "FP32", "shape": [-1, -1]},
            ],
        }

    if model_name == "picture_classifier":
        return {
            **base,
            "inputs": [
                {"name": "pixel_values", "datatype": "FP32", "shape": [-1, 3, -1, -1]},
            ],
            "outputs": [
                {
                    "name": "logits",
                    "datatype": "FP32",
                    "shape": [-1, PICTURE_CLASSIFIER_NUM_CLASSES],
                },
            ],
        }

    return {
        **base,
        "inputs": [{"name": "image", "datatype": "BYTES", "shape": [1]}],
        "outputs": [{"name": "output", "datatype": "BYTES", "shape": [1]}],
    }


# endregion FUNC_build_kserve_model_metadata


# region FUNC_request_model_version [DOMAIN(5): KServe; CONCEPT(5): Metadata; TECH(5): str]
## @purpose Return static model version label for KServe response metadata.
def request_model_version(model_name: str) -> str:
    return KSERVE_MODEL_VERSION


# endregion FUNC_request_model_version


# region FUNC_decode_kserve_input_tensors [DOMAIN(8): KServe; CONCEPT(8): TensorDecode; TECH(8): numpy]
## @purpose Parse all input tensors from KServe infer JSON body into a name→ndarray map.
## @complexity 5
def decode_kserve_input_tensors(request_body: dict[str, Any]) -> dict[str, np.ndarray]:
    inputs = request_body.get("inputs", [])
    if not inputs:
        raise ValueError("KServe request missing inputs")

    decoded: dict[str, np.ndarray] = {}
    for tensor in inputs:
        name = str(tensor.get("name", ""))
        datatype = str(tensor.get("datatype", "")).upper()
        data = tensor.get("data")
        shape = tensor.get("shape")
        if data is None:
            continue

        np_dtype = {
            "FP32": np.float32,
            "FP64": np.float64,
            "INT64": np.int64,
            "INT32": np.int32,
            "UINT8": np.uint8,
            "INT8": np.int8,
            "BYTES": object,
        }.get(datatype, np.float32)

        if datatype == "BYTES":
            if isinstance(data, list):
                decoded[name] = np.array(data, dtype=object)
            else:
                decoded[name] = np.array([data], dtype=object)
            continue

        array = np.array(data, dtype=np_dtype)
        if shape:
            decoded[name] = array.reshape(shape)
        else:
            decoded[name] = array

    if not decoded:
        raise ValueError("KServe request inputs could not be decoded")
    return decoded


# endregion FUNC_decode_kserve_input_tensors


# region FUNC_decode_image_from_kserve_request [DOMAIN(8): KServe; CONCEPT(8): TensorDecode; TECH(8): numpy]
## @purpose Extract raw image bytes from KServe v2 infer request inputs array.
## @complexity 6
def decode_image_from_kserve_request(request_body: dict[str, Any]) -> bytes:
    tensors = decode_kserve_input_tensors(request_body)

    for name, array in tensors.items():
        if name.lower() in {"image", "input", "images"}:
            return _tensor_to_png_bytes(array, name=name)

    for tensor in request_body.get("inputs", []):
        name = tensor.get("name", "")
        datatype = str(tensor.get("datatype", "")).upper()
        data = tensor.get("data")

        if datatype == "BYTES":
            if isinstance(data, list) and data:
                raw = data[0]
                if isinstance(raw, str):
                    return base64.b64decode(raw)
                return bytes(raw)
            if isinstance(data, str):
                return base64.b64decode(data)

    raise ValueError("No decodable image tensor found in KServe request")


# endregion FUNC_decode_image_from_kserve_request


# region FUNC__tensor_to_png_bytes [DOMAIN(7): KServe; CONCEPT(7): ImageDecode; TECH(7): PIL]
## @purpose Convert UINT8/FP32 image tensors to PNG bytes for vision API calls.
## @complexity 6
def _tensor_to_png_bytes(array: np.ndarray, name: str = "image") -> bytes:
    array = np.asarray(array)

    if array.dtype == object:
        raw = array.reshape(-1)[0]
        if isinstance(raw, str):
            return base64.b64decode(raw)
        return bytes(raw)

    if array.ndim == 4 and array.shape[-1] in (1, 3, 4):
        if array.dtype != np.uint8:
            if array.max() <= 1.0:
                array = (array * 255).clip(0, 255).astype(np.uint8)
            else:
                array = array.clip(0, 255).astype(np.uint8)
        frame = array[0] if array.shape[0] == 1 else array.squeeze(0)
    elif array.ndim == 3 and array.shape[0] in (1, 3, 4):
        frame = _denormalize_nchw(array)
    else:
        frame = array.astype(np.uint8)

    from PIL import Image

    if frame.ndim == 3 and frame.shape[0] in (1, 3, 4):
        chw = frame
        if chw.shape[0] in (1, 3):
            hwc = np.transpose(chw, (1, 2, 0))
        else:
            hwc = chw
        if hwc.shape[-1] == 1:
            image = Image.fromarray(hwc.squeeze(-1), mode="L")
        else:
            image = Image.fromarray(hwc.astype(np.uint8), mode="RGB")
    else:
        image = Image.fromarray(frame.astype(np.uint8))

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# endregion FUNC__tensor_to_png_bytes


# region FUNC__denormalize_nchw [DOMAIN(7): Vision; CONCEPT(7): Preprocess; TECH(7): numpy]
## @purpose Inverse ImageNet normalization for HF preprocessor pixel_values tensors.
## @complexity 4
def _denormalize_nchw(pixel_values: np.ndarray) -> np.ndarray:
    values = np.asarray(pixel_values, dtype=np.float32)
    if values.ndim == 3:
        values = values[np.newaxis, ...]
    if values.max() <= 1.0 and values.min() >= 0.0:
        denorm = values
    else:
        denorm = values * IMAGENET_STD + IMAGENET_MEAN
    denorm = np.clip(denorm, 0.0, 1.0)
    rgb = (denorm[0].transpose(1, 2, 0) * 255.0).astype(np.uint8)
    return rgb


# endregion FUNC__denormalize_nchw


# region FUNC__pixel_values_batch_to_png_list [DOMAIN(8): Layout; CONCEPT(8): BatchDecode; TECH(8): PIL]
## @purpose Convert layout OD pixel_values batch and orig sizes into PNG bytes per batch item.
## @complexity 6
def _pixel_values_batch_to_png_list(
    pixel_values: np.ndarray,
    orig_target_sizes: np.ndarray,
) -> list[bytes]:
    from PIL import Image

    pixel_values = np.asarray(pixel_values, dtype=np.float32)
    orig_target_sizes = np.asarray(orig_target_sizes, dtype=np.int64)
    batch_size = pixel_values.shape[0]
    images: list[bytes] = []

    for index in range(batch_size):
        rgb = _denormalize_nchw(pixel_values[index])
        image = Image.fromarray(rgb, mode="RGB")
        width = int(orig_target_sizes[index][0])
        height = int(orig_target_sizes[index][1])
        if width > 0 and height > 0 and image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        images.append(buffer.getvalue())

    return images


# endregion FUNC__pixel_values_batch_to_png_list


# region FUNC__layout_label_to_id [DOMAIN(6): Layout; CONCEPT(6): LabelMap; TECH(6): dict]
## @purpose Map free-form layout label strings to docling-layout-heron class ids.
## @complexity 3
def _layout_label_to_id(label: Any) -> int:
    if isinstance(label, (int, np.integer)):
        return int(label)
    normalized = str(label).strip().lower().replace("_", "-")
    normalized = normalized.replace(" ", "-")
    if normalized in LAYOUT_HERON_LABEL2ID:
        return LAYOUT_HERON_LABEL2ID[normalized]
    compact = normalized.replace("-", "_")
    if compact in LAYOUT_HERON_LABEL2ID:
        return LAYOUT_HERON_LABEL2ID[compact]
    return LAYOUT_HERON_LABEL2ID["text"]


# endregion FUNC__layout_label_to_id


# region FUNC__picture_label_to_id [DOMAIN(6): Classification; CONCEPT(6): LabelMap; TECH(6): dict]
## @purpose Map picture classifier label strings to DocumentFigureClassifier-v2.5 ids.
## @complexity 3
def _picture_label_to_id(label: Any) -> int:
    if isinstance(label, (int, np.integer)):
        return int(label)
    normalized = str(label).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in PICTURE_CLASSIFIER_LABEL2ID:
        return PICTURE_CLASSIFIER_LABEL2ID[normalized]
    return PICTURE_CLASSIFIER_LABEL2ID["other"]


# endregion FUNC__picture_label_to_id


# region FUNC_encode_kserve_response [DOMAIN(8): KServe; CONCEPT(8): TensorEncode; TECH(8): json]
## @purpose Wrap parsed inference dict as legacy KServe BYTES JSON output (table and fallback).
## @complexity 3
def encode_kserve_response(model_name: str, parsed: dict[str, Any]) -> dict[str, Any]:
    json_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
    encoded = base64.b64encode(json_bytes).decode("ascii")
    return {
        "model_name": model_name,
        "model_version": request_model_version(model_name),
        "outputs": [
            {
                "name": "output",
                "shape": [1],
                "datatype": "BYTES",
                "data": [encoded],
            }
        ],
    }


# endregion FUNC_encode_kserve_response


# region FUNC_encode_object_detection_response [DOMAIN(9): Layout; CONCEPT(9): ObjectDetection; TECH(9): numpy]
## @purpose Encode layout parser output as KServe labels/boxes/scores tensors for docling OD engine.
## @complexity 6
def encode_object_detection_response(
    model_name: str,
    parsed: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    boxes_raw = parsed.get("boxes", [])
    labels_list: list[int] = []
    boxes_list: list[list[float]] = []
    scores_list: list[float] = []

    for item in boxes_raw:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox", item.get("box", [0, 0, 0, 0]))
        if len(bbox) < 4:
            continue
        labels_list.append(_layout_label_to_id(item.get("label", "text")))
        boxes_list.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
        scores_list.append(float(item.get("score", DEFAULT_DETECTION_SCORE)))

    count = len(labels_list)
    labels = np.array([labels_list], dtype=np.int64) if count else np.zeros((batch_size, 0), dtype=np.int64)
    boxes = np.array([boxes_list], dtype=np.float32) if count else np.zeros((batch_size, 0, 4), dtype=np.float32)
    scores = np.array([scores_list], dtype=np.float32) if count else np.zeros((batch_size, 0), dtype=np.float32)

    if labels.shape[0] != batch_size:
        labels = np.repeat(labels, batch_size, axis=0) if batch_size > 1 else labels
        boxes = np.repeat(boxes, batch_size, axis=0) if batch_size > 1 else boxes
        scores = np.repeat(scores, batch_size, axis=0) if batch_size > 1 else scores

    return {
        "model_name": model_name,
        "model_version": request_model_version(model_name),
        "outputs": [
            {
                "name": "labels",
                "shape": list(labels.shape),
                "datatype": "INT64",
                "data": labels.reshape(-1).tolist(),
            },
            {
                "name": "boxes",
                "shape": list(boxes.shape),
                "datatype": "FP32",
                "data": boxes.reshape(-1).tolist(),
            },
            {
                "name": "scores",
                "shape": list(scores.shape),
                "datatype": "FP32",
                "data": scores.reshape(-1).tolist(),
            },
        ],
    }


# endregion FUNC_encode_object_detection_response


# region FUNC_encode_ocr_kserve_response [DOMAIN(9): OCR; CONCEPT(9): OCRTensor; TECH(9): numpy]
## @purpose Encode OCR parser output as KServe boxes/txts/scores tensors for kserve_v2_ocr model.
## @complexity 7
def encode_ocr_kserve_response(model_name: str, parsed: dict[str, Any]) -> dict[str, Any]:
    regions = parsed.get("text_regions", [])
    box_tensors: list[list[list[float]]] = []
    texts: list[str] = []
    scores: list[float] = []

    for region in regions:
        if not isinstance(region, dict):
            continue
        bbox = region.get("bbox", [0, 0, 0, 0])
        if len(bbox) < 4:
            continue
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        quad = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        box_tensors.append(quad)
        texts.append(str(region.get("text", "")))
        scores.append(float(region.get("score", DEFAULT_DETECTION_SCORE)))

    count = len(box_tensors)
    if count == 0:
        boxes = np.zeros((1, 0, 4, 2), dtype=np.float32)
        txts = np.array([[]], dtype=object)
        score_arr = np.zeros((1, 0), dtype=np.float32)
    else:
        boxes = np.array([box_tensors], dtype=np.float32)
        txts = np.array([texts], dtype=object)
        score_arr = np.array([scores], dtype=np.float32)

    txt_payload = [str(value) for value in txts.reshape(-1).tolist()]

    return {
        "model_name": model_name,
        "model_version": request_model_version(model_name),
        "outputs": [
            {
                "name": "boxes",
                "shape": list(boxes.shape),
                "datatype": "FP32",
                "data": boxes.reshape(-1).tolist(),
            },
            {
                "name": "txts",
                "shape": list(txts.shape),
                "datatype": "BYTES",
                "data": txt_payload,
            },
            {
                "name": "scores",
                "shape": list(score_arr.shape),
                "datatype": "FP32",
                "data": score_arr.reshape(-1).tolist(),
            },
        ],
    }


# endregion FUNC_encode_ocr_kserve_response


# region FUNC_encode_classification_logits_response [DOMAIN(8): Classification; CONCEPT(8): Logits; TECH(8): numpy]
## @purpose Encode picture classification parser output as KServe logits tensor batch.
## @complexity 5
def encode_classification_logits_response(
    model_name: str,
    parsed: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    label_id = _picture_label_to_id(parsed.get("label", "other"))
    score = float(parsed.get("score", DEFAULT_DETECTION_SCORE))
    logits = np.full((batch_size, PICTURE_CLASSIFIER_NUM_CLASSES), -20.0, dtype=np.float32)
    logits[:, label_id] = score * 10.0

    return {
        "model_name": model_name,
        "model_version": request_model_version(model_name),
        "outputs": [
            {
                "name": "logits",
                "shape": list(logits.shape),
                "datatype": "FP32",
                "data": logits.reshape(-1).tolist(),
            }
        ],
    }


# endregion FUNC_encode_classification_logits_response


# region FUNC_handle_kserve_infer [DOMAIN(9): KServe; CONCEPT(9): InferPipeline; TECH(9): orchestration]
## @purpose Execute full KServe infer pipeline for a named model with stage-specific tensor contracts.
## @complexity 8
def handle_kserve_infer(
    model_name: str,
    request_body: dict[str, Any],
    client: ExternalApiClient,
    table: RoutingTable,
    settings: GatewaySettings,
    user_prompt: Optional[str] = None,
) -> dict[str, Any]:
    stage = KSERVE_MODEL_TO_STAGE.get(model_name)
    if not stage:
        logger.critical(
            f"[IMP:10][handle_kserve_infer][UNKNOWN_MODEL] model={model_name} [FATAL]"
        )
        raise KeyError(f"Unsupported KServe model name: {model_name}")

    route = resolve_stage_route(stage, table, settings)

    if model_name == "layout":
        tensors = decode_kserve_input_tensors(request_body)
        pixel_values = tensors.get("images")
        orig_target_sizes = tensors.get("orig_target_sizes")
        if pixel_values is None or orig_target_sizes is None:
            raise ValueError("Layout infer requires images and orig_target_sizes tensors")
        batch_size = int(pixel_values.shape[0])
        png_list = _pixel_values_batch_to_png_list(pixel_values, orig_target_sizes)
        merged_boxes: list[dict[str, Any]] = []
        for index, image_bytes in enumerate(png_list):
            logger.info(
                f"[IMP:7][handle_kserve_infer][LAYOUT_BATCH] item={index} bytes={len(image_bytes)} [IO]"
            )
            assistant_text = client.vision_inference(
                route,
                image_bytes,
                user_prompt=user_prompt or route.system_prompt or f"Process document stage: {stage}",
            )
            parser = get_parser(route.response_parser)
            parsed = parser(assistant_text)
            merged_boxes.extend(parsed.get("boxes", []))
        response = encode_object_detection_response(
            model_name,
            {"boxes": merged_boxes},
            batch_size=batch_size,
        )
    elif model_name == "ocr":
        image_bytes = decode_image_from_kserve_request(request_body)
        logger.info(
            f"[IMP:7][handle_kserve_infer][DECODED] model={model_name} stage={stage} "
            f"bytes={len(image_bytes)} [IO]"
        )
        assistant_text = client.vision_inference(
            route,
            image_bytes,
            user_prompt=user_prompt or f"Process document stage: {stage}",
        )
        parser = get_parser(route.response_parser)
        parsed = parser(assistant_text)
        response = encode_ocr_kserve_response(model_name, parsed)
    elif model_name == "picture_classifier":
        tensors = decode_kserve_input_tensors(request_body)
        pixel_values = tensors.get("pixel_values") or tensors.get("images")
        if pixel_values is None:
            image_bytes = decode_image_from_kserve_request(request_body)
            batch_size = 1
        else:
            batch_size = int(pixel_values.shape[0])
            image_bytes = _tensor_to_png_bytes(np.asarray(pixel_values)[0:1])
        logger.info(
            f"[IMP:7][handle_kserve_infer][CLASSIFIER] model={model_name} bytes={len(image_bytes)} [IO]"
        )
        assistant_text = client.vision_inference(
            route,
            image_bytes,
            user_prompt=user_prompt or f"Process document stage: {stage}",
        )
        parser = get_parser(route.response_parser)
        parsed = parser(assistant_text)
        response = encode_classification_logits_response(model_name, parsed, batch_size)
    else:
        image_bytes = decode_image_from_kserve_request(request_body)
        logger.info(
            f"[IMP:7][handle_kserve_infer][DECODED] model={model_name} stage={stage} "
            f"bytes={len(image_bytes)} [IO]"
        )
        assistant_text = client.vision_inference(
            route,
            image_bytes,
            user_prompt=user_prompt or f"Process document stage: {stage}",
        )
        parser = get_parser(route.response_parser)
        parsed = parser(assistant_text)
        response = encode_kserve_response(model_name, parsed)

    logger.info(
        f"[IMP:9][handle_kserve_infer][OK] model={model_name} stage={stage} "
        f"parser={route.response_parser} outputs={[o['name'] for o in response['outputs']]} [VALUE]"
    )
    return response


# endregion FUNC_handle_kserve_infer
