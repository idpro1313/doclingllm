# region MODULE_CONTRACT [DOMAIN(9): Testing; CONCEPT(9): KServe; TECH(9): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import base64
import json
import logging

import httpx

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.kserve import (
    decode_image_from_kserve_request,
    encode_kserve_response,
    handle_kserve_infer,
)
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_gateway"]


def test_decode_image_bytes_tensor(kserve_image_request):
    image = decode_image_from_kserve_request(kserve_image_request)
    assert image.startswith(b"\x89PNG")


def test_encode_kserve_response_roundtrip():
    parsed = {"text_regions": [{"text": "A", "bbox": [0, 0, 1, 1]}]}
    response = encode_kserve_response("ocr", parsed)
    encoded = response["outputs"][0]["data"][0]
    decoded = json.loads(base64.b64decode(encoded))
    assert decoded["text_regions"][0]["text"] == "A"


def test_handle_kserve_infer_ocr(gateway_settings, kserve_image_request, caplog):
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
        kserve_image_request,
        client,
        table,
        gateway_settings,
    )
    payload = json.loads(base64.b64decode(result["outputs"][0]["data"][0]))
    assert payload["text_regions"][0]["text"] == "Doc"
    assert any("[IMP:9][handle_kserve_infer][OK]" in r.message for r in caplog.records)
    client.close()
