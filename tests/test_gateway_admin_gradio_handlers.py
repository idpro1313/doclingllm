# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): ConnectionTester; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging

import httpx

from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded
from doclingllm.gateway.admin.connection_tester import run_all_connection_tests
from doclingllm.gateway.admin.gradio_handlers import handle_save_config, handle_test_connection

pytest_plugins = ["tests.conftest_admin"]


def test_connection_tester_all_probes_ok(admin_config_paths, admin_settings, caplog):
    caplog.set_level(logging.INFO)
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=30.0)
    report = run_all_connection_tests(runtime, http_client=client)
    client.close()
    assert report.ok
    assert any(probe.name.startswith("stage:") for probe in report.probes)
    found = any("[IMP:9][run_all_connection_tests][RESULT]" in r.message for r in caplog.records)
    print(report.to_markdown())
    assert found


def test_save_blocked_without_test(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    result = handle_save_config(runtime, last_test_ok=False, paths=admin_config_paths)
    assert result.ok is False
    assert "blocked" in result.message.lower()


def test_save_after_successful_test(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    result = handle_save_config(runtime, last_test_ok=True, paths=admin_config_paths)
    assert result.ok is True
    assert admin_config_paths.docling_serve_output.is_file()
