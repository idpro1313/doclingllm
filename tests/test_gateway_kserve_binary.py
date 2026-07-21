# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): KServeBinary; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import numpy as np

pytest_plugins = ["tests.conftest_gateway"]

from doclingllm.gateway.kserve import decode_kserve_input_tensors
from doclingllm.gateway.kserve_binary import (
    build_binary_kserve_request,
    encode_bytes_tensor,
    parse_kserve_infer_request,
)


def test_parse_binary_layout_request():
    pixel_values = np.zeros((1, 3, 4, 4), dtype=np.float32)
    orig_target_sizes = np.array([[640, 480]], dtype=np.int64)
    header = {
        "inputs": [
            {
                "name": "images",
                "shape": [1, 3, 4, 4],
                "datatype": "FP32",
                "parameters": {"binary_data_size": pixel_values.nbytes},
            },
            {
                "name": "orig_target_sizes",
                "shape": [1, 2],
                "datatype": "INT64",
                "parameters": {"binary_data_size": orig_target_sizes.nbytes},
            },
        ],
        "outputs": [
            {"name": "labels", "parameters": {"binary_data": True}},
            {"name": "boxes", "parameters": {"binary_data": True}},
            {"name": "scores", "parameters": {"binary_data": True}},
        ],
    }
    raw_body, headers = build_binary_kserve_request(
        header,
        [pixel_values.tobytes(), orig_target_sizes.tobytes()],
    )
    parsed = parse_kserve_infer_request(raw_body, headers)
    tensors = decode_kserve_input_tensors(parsed)
    assert tensors["images"].shape == (1, 3, 4, 4)
    assert tensors["orig_target_sizes"].tolist() == [[640, 480]]


def test_parse_binary_ocr_request():
    image = np.zeros((1, 4, 4, 3), dtype=np.uint8)
    lang_type = np.array([["en"]], dtype=object)
    header = {
        "inputs": [
            {
                "name": "lang_type",
                "shape": [1, 1],
                "datatype": "BYTES",
                "parameters": {"binary_data_size": len(encode_bytes_tensor(lang_type))},
            },
            {
                "name": "image",
                "shape": [1, 4, 4, 3],
                "datatype": "UINT8",
                "parameters": {"binary_data_size": image.nbytes},
            },
        ],
        "outputs": [
            {"name": "boxes", "parameters": {"binary_data": True}},
            {"name": "txts", "parameters": {"binary_data": True}},
            {"name": "scores", "parameters": {"binary_data": True}},
        ],
    }
    raw_body, headers = build_binary_kserve_request(
        header,
        [encode_bytes_tensor(lang_type), image.tobytes()],
    )
    parsed = parse_kserve_infer_request(raw_body, headers)
    tensors = decode_kserve_input_tensors(parsed)
    assert tensors["image"].shape == (1, 4, 4, 3)
    assert tensors["lang_type"].reshape(-1)[0] == "en"


def test_kserve_infer_endpoint_binary_layout(gateway_settings, full_routing_yaml):
    import httpx
    from fastapi.testclient import TestClient

    from doclingllm.gateway.app import create_app
    from doclingllm.gateway.client import ExternalApiClient
    from doclingllm.gateway.routing import load_routing_table

    table = load_routing_table(full_routing_yaml, gateway_settings)

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
    app = create_app(settings=gateway_settings, routing_table=table, client=client)

    pixel_values = np.zeros((1, 3, 8, 8), dtype=np.float32)
    orig_target_sizes = np.array([[8, 8]], dtype=np.int64)
    header = {
        "inputs": [
            {
                "name": "images",
                "shape": [1, 3, 8, 8],
                "datatype": "FP32",
                "parameters": {"binary_data_size": pixel_values.nbytes},
            },
            {
                "name": "orig_target_sizes",
                "shape": [1, 2],
                "datatype": "INT64",
                "parameters": {"binary_data_size": orig_target_sizes.nbytes},
            },
        ],
        "outputs": [
            {"name": "labels", "parameters": {"binary_data": True}},
            {"name": "boxes", "parameters": {"binary_data": True}},
            {"name": "scores", "parameters": {"binary_data": True}},
        ],
    }
    raw_body, binary_headers = build_binary_kserve_request(
        header,
        [pixel_values.tobytes(), orig_target_sizes.tobytes()],
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            "/v2/models/layout/infer",
            content=raw_body,
            headers=binary_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outputs"][0]["name"] == "labels"

    client.close()
