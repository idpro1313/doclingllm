# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): FastAPI; TECH(8): TestClient]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import base64
import json

import httpx
from fastapi.testclient import TestClient

from doclingllm.gateway.app import create_app
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_gateway"]


def test_health_endpoint(gateway_settings, full_routing_yaml):
    table = load_routing_table(full_routing_yaml, gateway_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    transport = httpx.MockTransport(handler)
    client = ExternalApiClient(gateway_settings, client=httpx.Client(transport=transport))
    app = create_app(settings=gateway_settings, routing_table=table, client=client)

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
    app = create_app(settings=gateway_settings, routing_table=table, client=client)

    with TestClient(app) as test_client:
        response = test_client.get("/v2/models/layout")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "layout"
        assert body["inputs"][0]["datatype"] == "BYTES"

        ready = test_client.get("/v2/models/layout/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True

        unknown = test_client.get("/v2/models/unknown")
        assert unknown.status_code == 404

    client.close()


def test_kserve_infer_endpoint(gateway_settings, full_routing_yaml, kserve_image_request):
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
    app = create_app(settings=gateway_settings, routing_table=table, client=client)

    with TestClient(app) as test_client:
        response = test_client.post("/v2/models/ocr/infer", json=kserve_image_request)
        assert response.status_code == 200
        body = response.json()
        decoded = json.loads(base64.b64decode(body["outputs"][0]["data"][0]))
        assert decoded["text_regions"][0]["text"] == "API"

    client.close()
