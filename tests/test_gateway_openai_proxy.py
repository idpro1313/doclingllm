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
    body = {"model": "qwen3.6-35b-a3b", "messages": [{"role": "user", "content": "hi"}]}
    route = select_openai_route(body, routing_table, gateway_settings)
    assert route.stage == "vlm"


def test_select_openai_route_image_convert_uses_vlm(gateway_settings, routing_table):
    body = {
        "model": "remote-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Convert this page to docling."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,xx"},
                    },
                ],
            }
        ],
    }
    route = select_openai_route(body, routing_table, gateway_settings)
    assert route.stage == "vlm"


def test_select_openai_route_picture_description(gateway_settings, routing_table):
    body = {
        "model": "remote-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this picture from a document.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,xx"},
                    },
                ],
            }
        ],
    }
    route = select_openai_route(body, routing_table, gateway_settings)
    assert route.stage == "picture_description"


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
    body = {"model": "remote-vision", "messages": [{"role": "user", "content": "test"}]}

    result = handle_openai_proxy(body, client, routing_table, gateway_settings)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert "chat/completions" in captured["url"]
    assert captured["body"]["model"] == gateway_settings.vision_model
    client.close()
