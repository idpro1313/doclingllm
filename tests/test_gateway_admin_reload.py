# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): AdminReload; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import httpx
from fastapi.testclient import TestClient

from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded, save_runtime_config
from doclingllm.gateway.app import create_app
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.routing import load_routing_table

pytest_plugins = ["tests.conftest_admin", "tests.conftest_gateway"]


def test_admin_reload_endpoint(admin_config_paths, admin_settings, full_routing_yaml):
    ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    table = load_routing_table(full_routing_yaml, admin_settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    )
    client = ExternalApiClient(admin_settings, client=httpx.Client(transport=transport))
    app = create_app(
        settings=admin_settings,
        routing_table=table,
        client=client,
        enable_admin_ui=False,
    )
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    runtime.backends["vision"].model = "reload-model"
    save_runtime_config(runtime, admin_config_paths)
    with TestClient(app) as test_client:
        response = test_client.post("/admin/reload")
        assert response.status_code == 200
        state = app.state.gateway
        assert state.settings.vision_model == "reload-model"
    client.close()
