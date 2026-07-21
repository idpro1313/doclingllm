# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): HTTPClient; TECH(8): httpx, pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
import logging
import re

import httpx

from doclingllm.gateway.client import ExternalApiClient, extract_assistant_content
from doclingllm.gateway.routing import load_routing_table, resolve_stage_route

pytest_plugins = ["tests.conftest_gateway"]

IMP_LOG_PATTERN = re.compile(r"\[IMP:(\d+)\]")


def _print_ldd(records, needle: str) -> bool:
    found = False
    print("\n--- LDD TRAJECTORY (IMP:7-10) ---")
    for record in records:
        match = IMP_LOG_PATTERN.search(record.message)
        if match and int(match.group(1)) >= 7:
            print(record.message)
        if needle in record.message and "[IMP:9]" in record.message:
            found = True
    return found


def test_extract_assistant_content_openai_shape():
    data = {"choices": [{"message": {"content": "hello ocr"}}]}
    assert extract_assistant_content(data) == "hello ocr"


def test_external_api_client_vision_call(gateway_settings, caplog):
    caplog.set_level(logging.INFO)
    table = load_routing_table(gateway_settings.gateway_models_config_path, gateway_settings)
    route = resolve_stage_route("ocr", table, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "qwen3.6-35b-a3b"
        assert "Authorization" in request.headers
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"text_regions":[{"text":"Hi","bbox":[0,0,1,1]}]}'}}]},
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))

    text = client.vision_inference(route, b"\x89PNG", user_prompt="OCR this")
    assert "text_regions" in text
    assert _print_ldd(caplog.records, "chat_completions")
    client.close()


def test_external_api_client_text_route(gateway_settings, caplog):
    caplog.set_level(logging.INFO)
    table = load_routing_table(gateway_settings.gateway_models_config_path, gateway_settings)
    route = resolve_stage_route("code_formula", table, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "E=mc^2"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    data = client.chat_completions(route, [{"role": "user", "content": "formula?"}])
    assert extract_assistant_content(data) == "E=mc^2"
    client.close()
