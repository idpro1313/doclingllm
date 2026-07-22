# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): ConfigExport; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

from doclingllm.gateway.admin.config_export import load_config_export_bundle
from doclingllm.gateway.admin.config_store import (
    ensure_runtime_config_seeded,
    load_runtime_config,
)
from doclingllm.gateway.admin.gradio_handlers import handle_refresh_config_export
from doclingllm.gateway.admin.routing_merge import build_merged_routing_dict

pytest_plugins = ["tests.conftest_admin"]


def test_config_export_bundle_contains_runtime_and_effective(admin_config_paths, admin_settings):
    ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    bundle = load_config_export_bundle(admin_config_paths, admin_settings)
    assert "gateway-runtime.yaml" in bundle.paths_summary
    assert "docker cp doclingllm-gateway" in bundle.paths_summary
    assert bundle.runtime_yaml.startswith("version:")
    assert "enable_remote_services" in bundle.docling_serve_yaml
    assert "stages:" in bundle.models_template_yaml
    assert "request_params" in bundle.effective_routing_yaml
    runtime = load_runtime_config(admin_config_paths, admin_settings)
    merged = build_merged_routing_dict(runtime, admin_config_paths)
    assert merged["stages"]["ocr"]["request_params"]["max_tokens"] == 512


def test_build_merged_routing_dict_applies_stage_override(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    from doclingllm.gateway.admin.runtime_models import StageOverride

    stages = dict(runtime.stages)
    stages["ocr"] = StageOverride(endpoint="vision", model="custom-vision-model")
    runtime = runtime.model_copy(update={"stages": stages})
    merged = build_merged_routing_dict(runtime, admin_config_paths)
    assert merged["stages"]["ocr"]["model"] == "custom-vision-model"


def test_handle_refresh_config_export_returns_five_fields(admin_config_paths, admin_settings):
    ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    result = handle_refresh_config_export(admin_config_paths, admin_settings)
    assert len(result) == 5
    paths_summary, runtime_yaml, docling_yaml, template_yaml, effective_yaml = result
    assert "volume dir:" in paths_summary
    assert "version:" in runtime_yaml
    assert "model-gateway:8080" in docling_yaml
    assert "ocr:" in template_yaml
    assert "Effective routing" in effective_yaml or "stages:" in effective_yaml
