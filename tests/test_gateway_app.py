# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): FastAPI; TECH(8): TestClient]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import httpx
from fastapi.testclient import TestClient

from doclingllm.gateway.app import create_app
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_gateway"]


def test_kserve_infer_upstream_connect_error_returns_502(
    gateway_settings, full_routing_yaml, kserve_ocr_request
):
    table = load_routing_table(full_routing_yaml, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("SSL: UNEXPECTED_EOF_WHILE_READING", request=request)

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    app = create_app(settings=gateway_settings, routing_table=table, client=client, enable_admin_ui=False)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post("/v2/models/ocr/infer", json=kserve_ocr_request)
        assert response.status_code == 502
        assert "Upstream" in response.json()["detail"]

    client.close()


def test_health_endpoint(gateway_settings, full_routing_yaml):
    table = load_routing_table(full_routing_yaml, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    app = create_app(settings=gateway_settings, routing_table=table, client=client, enable_admin_ui=False)

    with TestClient(app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    client.close()


def test_kserve_model_metadata_endpoint(gateway_settings, full_routing_yaml):
    table = load_routing_table(full_routing_yaml, gateway_settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    app = create_app(settings=gateway_settings, routing_table=table, client=client, enable_admin_ui=False)

    with TestClient(app) as test_client:
        response = test_client.get("/v2/models/layout")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "layout"
        assert body["inputs"][0]["name"] == "images"
        assert body["inputs"][0]["datatype"] == "FP32"
        assert body["outputs"][0]["name"] == "labels"

        ready = test_client.get("/v2/models/layout/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True

        unknown = test_client.get("/v2/models/unknown")
        assert unknown.status_code == 404

    client.close()


def test_kserve_infer_endpoint(gateway_settings, full_routing_yaml, kserve_ocr_request):
    table = load_routing_table(full_routing_yaml, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"text_regions":[{"text":"API","bbox":[0,0,1,1]}]}'}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    app = create_app(settings=gateway_settings, routing_table=table, client=client, enable_admin_ui=False)

    with TestClient(app) as test_client:
        response = test_client.post("/v2/models/ocr/infer", json=kserve_ocr_request)
        assert response.status_code == 200
        body = response.json()
        boxes_output = next(item for item in body["outputs"] if item["name"] == "boxes")
        assert boxes_output["datatype"] == "FP32"
        assert len(boxes_output["data"]) > 0

    client.close()
