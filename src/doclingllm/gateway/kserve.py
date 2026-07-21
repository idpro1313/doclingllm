# region MODULE_CONTRACT [DOMAIN(9): KServe; CONCEPT(9): ProtocolAdapter, TensorEncode; TECH(9): numpy, json]
## @modulecontract
## @purpose Translate KServe v2 HTTP infer requests into vision API calls and encode parsed results as KServe BYTES outputs.
## @scope Protocol layer only; delegates HTTP to ExternalApiClient and parsing to parser registry.
## @links [USES_API(9): doclingllm.gateway.client.ExternalApiClient]
## @links [USES_API(8): doclingllm.gateway.parsers.get_parser]
## @changes
## LAST_CHANGE: [v0.2.0 Slice S4 – KServe decode/infer/encode pipeline.]
## @modulemap
## FUNC 10[Handle KServe infer request] => handle_kserve_infer
## FUNC 8[Decode image tensor from KServe body] => decode_image_from_kserve_request
## FUNC 8[Encode parsed dict to KServe response] => encode_kserve_response
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: KServe v2, infer, tensor, image decode, OCR layout table
# STRUCTURE: ▶ KServe JSON → ◇ decode image → ⚡ vision_inference → ◇ parser → ⊕ encode → ⎋ KServe JSON

import base64
import json
import logging
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


# region FUNC_build_kserve_model_metadata [DOMAIN(7): KServe; CONCEPT(7): Metadata; TECH(7): json]
## @purpose Return KServe v2 model metadata for GET /v2/models/{name} used by docling api_kserve_v2 engines.
## @complexity 2
def build_kserve_model_metadata(model_name: str) -> dict[str, Any]:
    if model_name not in KSERVE_MODEL_TO_STAGE:
        raise KeyError(f"Unsupported KServe model name: {model_name}")
    return {
        "name": model_name,
        "versions": [KSERVE_MODEL_VERSION],
        "platform": KSERVE_MODEL_PLATFORM,
        "inputs": [
            {
                "name": "image",
                "datatype": "BYTES",
                "shape": [1],
            }
        ],
        "outputs": [
            {
                "name": "output",
                "datatype": "BYTES",
                "shape": [1],
            }
        ],
    }


# endregion FUNC_build_kserve_model_metadata


# region FUNC_decode_image_from_kserve_request [DOMAIN(8): KServe; CONCEPT(8): TensorDecode; TECH(8): numpy]
## @purpose Extract raw image bytes from KServe v2 infer request inputs array.
## @complexity 6
def decode_image_from_kserve_request(request_body: dict[str, Any]) -> bytes:
    inputs = request_body.get("inputs", [])
    if not inputs:
        raise ValueError("KServe request missing inputs")

    for tensor in inputs:
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

        if datatype in {"UINT8", "INT8", "FP32", "FP64"} and data is not None:
            array = np.array(data, dtype=np.uint8 if datatype == "UINT8" else np.float32)
            shape = tensor.get("shape")
            if shape and len(shape) >= 3:
                array = array.reshape(shape)
                if array.ndim == 3 and array.shape[-1] in (1, 3, 4):
                    from io import BytesIO

                    try:
                        from PIL import Image

                        mode = "L" if array.shape[-1] == 1 else "RGBA" if array.shape[-1] == 4 else "RGB"
                        if array.dtype != np.uint8:
                            array = (array * 255).clip(0, 255).astype(np.uint8)
                        image = Image.fromarray(array.squeeze(0) if array.shape[0] == 1 else array, mode=mode)
                        buffer = BytesIO()
                        image.save(buffer, format="PNG")
                        return buffer.getvalue()
                    except ImportError:
                        pass
            return array.astype(np.uint8).tobytes()

        if name.lower() in {"image", "input", "images"} and data is not None:
            if isinstance(data, str):
                return base64.b64decode(data)
            if isinstance(data, list):
                return np.array(data, dtype=np.uint8).tobytes()

    raise ValueError("No decodable image tensor found in KServe request")


# endregion FUNC_decode_image_from_kserve_request


# region FUNC_encode_kserve_response [DOMAIN(8): KServe; CONCEPT(8): TensorEncode; TECH(8): json]
## @purpose Wrap parsed inference dict as KServe v2 infer response with BYTES JSON output tensor.
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


# region FUNC_request_model_version [DOMAIN(5): KServe; CONCEPT(5): Metadata; TECH(5): str]
## @purpose Return static model version label for KServe response metadata.
def request_model_version(model_name: str) -> str:
    return KSERVE_MODEL_VERSION


# endregion FUNC_request_model_version


# region FUNC_handle_kserve_infer [DOMAIN(9): KServe; CONCEPT(9): InferPipeline; TECH(9): orchestration]
## @purpose Execute full KServe infer pipeline for a named model (ocr/layout/table/picture_classifier).
## @complexity 7
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
        f"parser={route.response_parser} keys={list(parsed.keys())} [VALUE]"
    )
    return response


# endregion FUNC_handle_kserve_infer
