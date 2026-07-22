# region MODULE_CONTRACT [DOMAIN(9): Testing; CONCEPT(9): KServeRelay; TECH(9): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import httpx
from fastapi.testclient import TestClient

from doclingllm.gateway.app import create_app
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.kserve_relay import handle_kserve_relay
from doclingllm.gateway.routing import load_routing_table, resolve_stage_route

pytest_plugins = ["tests.conftest_gateway", "tests.conftest_admin"]


def _relay_routing_yaml(tmp_path):
    yaml_path = tmp_path / "gateway-models-relay.yaml"
    yaml_path.write_text(
        """
endpoints:
  kserve_native:
    base_url: "http://triton.local:8000"
    api_key_env: VISION_API_KEY
    default_model: ""
  vision:
    base_url: "${VISION_API_BASE_URL}"
    api_key_env: VISION_API_KEY
    default_model: "${VISION_MODEL}"

stages:
  ocr:
    endpoint: kserve_native
    mode: kserve_relay
    model: ocr
    relay_model: docling-ocr-v1
  layout:
    endpoint: vision
    mode: openai_vision
    model: "${VISION_MODEL}"
    path: /chat/completions
    response_parser: layout_boxes_json
""",
        encoding="utf-8",
    )
    return yaml_path


def test_resolve_stage_route_kserve_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen-test")
    monkeypatch.setenv("VISION_API_KEY", "secret")
    yaml_path = _relay_routing_yaml(tmp_path)
    monkeypatch.setenv("GATEWAY_MODELS_CONFIG_PATH", str(yaml_path))
    settings = GatewaySettings()
    table = load_routing_table(yaml_path, settings)
    route = resolve_stage_route("ocr", table, settings)
    assert route.mode == "kserve_relay"
    assert route.model == "docling-ocr-v1"
    assert route.request_url == "http://triton.local:8000/v2/models/docling-ocr-v1/infer"
    assert route.relay_model == "docling-ocr-v1"


def test_handle_kserve_relay_forwards_raw_body(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen-test")
    monkeypatch.setenv("VISION_API_KEY", "relay-key")
    yaml_path = _relay_routing_yaml(tmp_path)
    monkeypatch.setenv("GATEWAY_MODELS_CONFIG_PATH", str(yaml_path))
    settings = GatewaySettings()
    table = load_routing_table(yaml_path, settings)
    raw_payload = b'{"inputs":[{"name":"image","datatype":"BYTES","data":["abc"]}]}'
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={"model_name": "docling-ocr-v1", "outputs": []},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(settings, client=httpx.Client(transport=transport))
    response = handle_kserve_relay(
        "ocr",
        raw_payload,
        {"content-type": "application/json", "accept": "application/json"},
        client,
        table,
        settings,
    )
    assert response.status_code == 200
    assert captured["url"] == "http://triton.local:8000/v2/models/docling-ocr-v1/infer"
    assert captured["body"] == raw_payload
    assert captured["headers"]["authorization"] == "Bearer relay-key"
    client.close()


def test_kserve_infer_relay_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen-test")
    monkeypatch.setenv("VISION_API_KEY", "relay-key")
    yaml_path = _relay_routing_yaml(tmp_path)
    monkeypatch.setenv("GATEWAY_MODELS_CONFIG_PATH", str(yaml_path))
    settings = GatewaySettings()
    table = load_routing_table(yaml_path, settings)
    assert table.stages["ocr"].mode == "kserve_relay"
    upstream_body = {"model_name": "docling-ocr-v1", "outputs": [{"name": "boxes", "data": [1]}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.content == b'{"relay":true}'
        return httpx.Response(200, json=upstream_body)

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(settings, client=httpx.Client(transport=transport))
    app = create_app(settings=settings, routing_table=table, client=client, enable_admin_ui=False)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/v2/models/ocr/infer",
            content=b'{"relay":true}',
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == upstream_body

    client.close()


def test_routing_merge_preserves_relay_model(admin_config_paths, admin_settings, tmp_path):
    from dataclasses import replace

    from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded
    from doclingllm.gateway.admin.routing_merge import build_merged_routing_dict

    relay_template = tmp_path / "gateway-models.template.yaml"
    relay_template.write_text(
        """
endpoints:
  vision:
    base_url: "${VISION_API_BASE_URL}"
    api_key_env: VISION_API_KEY
    default_model: "${VISION_MODEL}"
  kserve_native:
    base_url: "http://triton:8000"
    default_model: ""

stages:
  ocr:
    endpoint: kserve_native
    mode: kserve_relay
    model: ocr
    relay_model: native-ocr
""",
        encoding="utf-8",
    )
    paths = replace(admin_config_paths, models_template=relay_template)
    runtime = ensure_runtime_config_seeded(paths, admin_settings)
    runtime.stages["ocr"].model = "admin-vision-model"
    merged = build_merged_routing_dict(runtime, paths)
    assert merged["stages"]["ocr"]["model"] == "ocr"
    assert merged["stages"]["ocr"]["relay_model"] == "native-ocr"
