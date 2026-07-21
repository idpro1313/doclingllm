# region MODULE_CONTRACT [DOMAIN(9): Testing; CONCEPT(9): KServe; TECH(9): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
import logging

import httpx

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.kserve import (
    build_kserve_model_metadata,
    coerce_xyxy_bbox,
    decode_image_from_kserve_request,
    encode_kserve_response,
    encode_object_detection_response,
    encode_ocr_kserve_response,
    handle_kserve_infer,
)
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_gateway"]


def test_encode_ocr_kserve_response_shape_without_batch_axis():
    result = encode_ocr_kserve_response(
        "ocr",
        {
            "text_regions": [
                {"text": "A", "bbox": [0, 0, 10, 5], "score": 0.9},
                {"text": "B", "bbox": [1, 1, 11, 6], "score": 0.8},
            ]
        },
    )
    boxes = next(item for item in result["outputs"] if item["name"] == "boxes")
    txts = next(item for item in result["outputs"] if item["name"] == "txts")
    scores = next(item for item in result["outputs"] if item["name"] == "scores")
    assert boxes["shape"] == [2, 4, 2]
    assert txts["shape"] == [2]
    assert scores["shape"] == [2]
    assert txts["data"] == ["A", "B"]


def test_encode_ocr_keeps_plain_text_without_bbox():
    result = encode_ocr_kserve_response(
        "ocr",
        {
            "text_regions": [
                {"text": "line one", "score": 0.5},
                {"text": "line two", "score": 0.5},
                {"text": "", "score": 0.5},
            ]
        },
        image_size=(200, 400),
    )
    boxes = next(item for item in result["outputs"] if item["name"] == "boxes")
    txts = next(item for item in result["outputs"] if item["name"] == "txts")
    assert boxes["shape"] == [2, 4, 2]
    assert txts["data"] == ["line one", "line two"]
    # quads flattened: [x1,y1, x2,y1, x2,y2, x1,y2] per region
    assert boxes["data"][0:8] == [0.0, 0.0, 200.0, 0.0, 200.0, 200.0, 0.0, 200.0]
    assert boxes["data"][8:16] == [0.0, 200.0, 200.0, 200.0, 200.0, 400.0, 0.0, 400.0]


def test_coerce_xyxy_bbox_nested_and_inverted():
    assert coerce_xyxy_bbox([[10, 20], [30, 40]]) == [10.0, 20.0, 30.0, 40.0]
    assert coerce_xyxy_bbox([30, 40, 10, 20]) == [10.0, 20.0, 30.0, 40.0]
    assert coerce_xyxy_bbox({"x1": 5, "y1": 6, "x2": 1, "y2": 2}) == [1.0, 2.0, 5.0, 6.0]
    assert coerce_xyxy_bbox([1, 1, 1, 1]) is None
    assert coerce_xyxy_bbox([[1, 2]]) is None


def test_encode_object_detection_per_batch_item():
    result = encode_object_detection_response(
        "layout",
        [
            [{"label": "title", "bbox": [10, 20, 80, 60], "score": 0.9}],
            [{"label": "text", "bbox": [15, 25, 90, 70], "score": 0.7}],
        ],
    )
    labels = next(item for item in result["outputs"] if item["name"] == "labels")
    boxes = next(item for item in result["outputs"] if item["name"] == "boxes")
    assert labels["shape"] == [2, 1]
    assert boxes["shape"] == [2, 1, 4]
    assert boxes["data"][0:4] == [10.0, 20.0, 80.0, 60.0]
    assert boxes["data"][4:8] == [15.0, 25.0, 90.0, 70.0]


def test_encode_object_detection_nested_bbox_and_scale():
    result = encode_object_detection_response(
        "layout",
        [
            [
                {"label": "text", "bbox": [[0.1, 0.2], [0.5, 0.8]], "score": 0.9},
                {"label": "bad", "bbox": [[1, 2]], "score": 0.1},
            ]
        ],
        image_sizes=[(100, 200)],
    )
    boxes = next(item for item in result["outputs"] if item["name"] == "boxes")
    assert boxes["shape"] == [1, 1, 4]
    assert boxes["data"] == [10.0, 40.0, 50.0, 160.0]


def test_encode_object_detection_clamps_and_drops_tiny_table():
    result = encode_object_detection_response(
        "layout",
        [
            [
                {"label": "table", "bbox": [-10, -5, 5, 10], "score": 0.9},
                {"label": "table", "bbox": [10, 10, 200, 180], "score": 0.8},
                {"label": "text", "bbox": [0, 0, 50, 40], "score": 0.7},
            ]
        ],
        image_sizes=[(100, 200)],
    )
    labels = next(item for item in result["outputs"] if item["name"] == "labels")
    boxes = next(item for item in result["outputs"] if item["name"] == "boxes")
    assert labels["shape"] == [1, 2]
    assert boxes["shape"] == [1, 2, 4]
    assert boxes["data"][0:4] == [10.0, 10.0, 100.0, 180.0]
    assert boxes["data"][4:8] == [0.0, 0.0, 50.0, 40.0]


def test_build_kserve_model_metadata_layout():
    metadata = build_kserve_model_metadata("layout")
    assert metadata["name"] == "layout"
    assert len(metadata["inputs"]) == 2
    assert metadata["inputs"][0]["name"] == "images"
    assert metadata["inputs"][1]["name"] == "orig_target_sizes"
    assert len(metadata["outputs"]) == 3
    assert metadata["outputs"][0]["name"] == "labels"


def test_build_kserve_model_metadata_ocr():
    metadata = build_kserve_model_metadata("ocr")
    assert metadata["inputs"][1]["name"] == "image"
    assert metadata["outputs"][0]["name"] == "boxes"


def test_decode_image_bytes_tensor(kserve_image_request):
    image = decode_image_from_kserve_request(kserve_image_request)
    assert image.startswith(b"\x89PNG")


def test_encode_kserve_response_roundtrip():
    parsed = {"text_regions": [{"text": "A", "bbox": [0, 0, 1, 1]}]}
    response = encode_kserve_response("table", parsed)
    encoded = response["outputs"][0]["data"][0]
    decoded = json.loads(__import__("base64").b64decode(encoded))
    assert decoded["text_regions"][0]["text"] == "A"


def test_handle_kserve_infer_ocr(gateway_settings, kserve_ocr_request, caplog):
    caplog.set_level(logging.INFO)
    table = load_routing_table(gateway_settings.gateway_models_config_path, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"text_regions":[{"text":"Doc","bbox":[0,0,100,20]}]}',
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))

    result = handle_kserve_infer(
        "ocr",
        kserve_ocr_request,
        client,
        table,
        gateway_settings,
    )
    output_names = {item["name"] for item in result["outputs"]}
    assert output_names == {"boxes", "txts", "scores"}
    boxes_output = next(item for item in result["outputs"] if item["name"] == "boxes")
    assert boxes_output["datatype"] == "FP32"
    assert boxes_output["shape"] == [1, 4, 2]
    txts_output = next(item for item in result["outputs"] if item["name"] == "txts")
    assert txts_output["shape"] == [1]
    scores_output = next(item for item in result["outputs"] if item["name"] == "scores")
    assert scores_output["shape"] == [1]
    assert any("[IMP:9][handle_kserve_infer][OK]" in r.message for r in caplog.records)
    client.close()


def test_handle_kserve_infer_layout(gateway_settings, kserve_layout_request, caplog):
    caplog.set_level(logging.INFO)
    table = load_routing_table(gateway_settings.gateway_models_config_path, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"boxes":[{"label":"Title","bbox":[0,0,6,6]}]}',
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))

    result = handle_kserve_infer(
        "layout",
        kserve_layout_request,
        client,
        table,
        gateway_settings,
    )
    output_names = [item["name"] for item in result["outputs"]]
    assert output_names == ["labels", "boxes", "scores"]
    labels_output = result["outputs"][0]
    assert labels_output["datatype"] == "INT64"
    assert labels_output["data"][0] == 10
    client.close()
