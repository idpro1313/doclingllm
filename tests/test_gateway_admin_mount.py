# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): AdminMount; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import httpx
from fastapi.testclient import TestClient

from doclingllm.gateway.app import create_app
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_admin", "tests.conftest_gateway"]


def test_root_manifest_redirects_to_admin(admin_config_paths, admin_settings, full_routing_yaml):
    table = load_routing_table(full_routing_yaml, admin_settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )
    client = ExternalApiClient(admin_settings, client=httpx.Client(transport=transport))
    app = create_app(
        settings=admin_settings,
        routing_table=table,
        client=client,
        enable_admin_ui=True,
    )
    with TestClient(app) as test_client:
        response = test_client.get("/manifest.json", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/admin/manifest.json"
        admin_manifest = test_client.get("/admin/manifest.json")
        assert admin_manifest.status_code == 200
        assert admin_manifest.headers["content-type"].startswith("application/manifest+json")
    client.close()
