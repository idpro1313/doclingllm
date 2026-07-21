# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): OpenAIProxy; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json

import httpx

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.openai_proxy import handle_openai_proxy, select_openai_route
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_gateway"]


def test_select_openai_route_vlm(gateway_settings, routing_table):
    body = {"model": "deepseek-ai/DeepSeek-OCR-2", "messages": [{"role": "user", "content": "hi"}]}
    route = select_openai_route(body, routing_table, gateway_settings)
    assert route.stage == "vlm"


def test_select_openai_route_text(gateway_settings, routing_table):
    body = {"model": "minimax-m2.7", "messages": [{"role": "user", "content": "formula"}]}
    route = select_openai_route(body, routing_table, gateway_settings)
    assert route.stage == "code_formula"


def test_handle_openai_proxy_passthrough(gateway_settings, routing_table):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "model": "x"})

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    body = {"model": "deepseek-ai/DeepSeek-OCR-2", "messages": [{"role": "user", "content": "test"}]}

    result = handle_openai_proxy(body, client, routing_table, gateway_settings)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert "chat/completions" in captured["url"]
    client.close()
