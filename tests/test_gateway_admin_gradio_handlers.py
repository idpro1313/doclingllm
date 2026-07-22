# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): ConnectionTester; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging

import httpx

from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded
from doclingllm.gateway.admin.connection_tester import (
    _format_chat_failure_detail,
    run_all_connection_tests,
)
from doclingllm.gateway.admin.gradio_handlers import (
    form_to_runtime,
    handle_save_config,
    handle_test_connection,
    parse_stage_inputs_from_form_tail,
    sync_stage_models_from_backends,
    validate_stage_routing,
)
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig, StageOverride

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


def test_gradio_stage_form_tail_order_matches_common_inputs():
    stage_names = ["ocr", "layout", "code_formula"]
    tail = [
        "openai_vision",
        "kserve_relay",
        "openai_text",
        "vision",
        "kserve_native",
        "text",
        "kimi-k2-6",
        "ocr",
        "minimax-m2.7",
        "",
        "docling-ocr-v1",
        "",
    ]
    stage_modes, stage_endpoints, stage_models, stage_relay_models = (
        parse_stage_inputs_from_form_tail(stage_names, tail)
    )
    assert stage_modes == {
        "ocr": "openai_vision",
        "layout": "kserve_relay",
        "code_formula": "openai_text",
    }
    assert stage_endpoints == {
        "ocr": "vision",
        "layout": "kserve_native",
        "code_formula": "text",
    }
    assert stage_models == {
        "ocr": "kimi-k2-6",
        "layout": "ocr",
        "code_formula": "minimax-m2.7",
    }
    assert stage_relay_models == {
        "ocr": "",
        "layout": "docling-ocr-v1",
        "code_formula": "",
    }


def test_sync_stage_models_from_backends():
    stage_names = ["code_formula", "layout", "ocr"]
    synced = sync_stage_models_from_backends(
        stage_names,
        vision_model="kimi-k2-6",
        text_model="minimax-m2.7",
        stage_endpoints={
            "code_formula": "text",
            "layout": "kserve_native",
            "ocr": "vision",
        },
        stage_modes={
            "code_formula": "openai_text",
            "layout": "kserve_relay",
            "ocr": "openai_vision",
        },
        current_models={
            "code_formula": "minimax-m2.7",
            "layout": "layout",
            "ocr": "kimi-k2-6",
        },
    )
    assert synced == ["minimax-m2.7", "layout", "kimi-k2-6"]


def test_form_to_runtime_kserve_relay(admin_settings):
    runtime = form_to_runtime(
        "https://vision/v1",
        "v-key",
        "vision-model",
        "http://text/v1",
        "",
        "text-model",
        "http://triton:8000",
        "native-key",
        300,
        "",
        "",
        "localhost",
        {"ocr": "kserve_relay"},
        {"ocr": "kserve_native"},
        {"ocr": "ocr"},
        {"ocr": "docling-ocr-v1"},
    )
    assert runtime.backends["kserve_native"].base_url == "http://triton:8000"
    assert runtime.stages["ocr"].mode == "kserve_relay"
    assert runtime.stages["ocr"].relay_model == "docling-ocr-v1"


def test_validate_stage_routing_requires_native_url():
    from doclingllm.gateway.admin.runtime_models import BackendConfig

    runtime = GatewayRuntimeConfig(
        backends={
            "vision": BackendConfig(base_url="https://v/v1", model="v"),
            "text": BackendConfig(base_url="http://t/v1", model="t"),
            "kserve_native": BackendConfig(base_url="", api_key=""),
        }
    )
    stages = {
        "ocr": StageOverride(
            endpoint="kserve_native",
            model="ocr",
            mode="kserve_relay",
            relay_model="docling-ocr-v1",
        )
    }
    try:
        validate_stage_routing(runtime, stages)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "KServe Native base URL" in str(exc)


def test_chat_failure_detail_includes_available_models():
    detail = _format_chat_failure_detail(
        status_code=404,
        model="minimax-m2.7",
        response_text='{"error":"model not found"}',
        available_models=["MiniMaxAI/MiniMax-M2", "other-model"],
    )
    assert "HTTP 404" in detail
    assert "model='minimax-m2.7'" in detail
    assert "MiniMaxAI/MiniMax-M2" in detail
