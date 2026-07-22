# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): DoclingGenerator; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import yaml

from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded
from doclingllm.gateway.admin.docling_generator import (
    DOCLING_RESTART_HINT,
    render_docling_serve_yaml,
    write_docling_serve_yaml,
)

pytest_plugins = ["tests.conftest_admin"]


def test_docling_generator_points_to_gateway(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    text = render_docling_serve_yaml(runtime)
    assert DOCLING_RESTART_HINT in text
    data = yaml.safe_load(text.split("\n", 2)[2])
    assert data["enable_remote_services"] is True
    assert "http://model-gateway:8080" in yaml.dump(data)
    assert data["custom_code_formula_presets"]["remote_code_formula"]["engine_options"]["params"]["model"] == runtime.backends["text"].model


def test_write_docling_serve_yaml_to_volume(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    path = write_docling_serve_yaml(runtime, admin_config_paths)
    assert path == admin_config_paths.docling_serve_output
    assert path.is_file()


def test_docling_generator_kserve_timeouts_follow_gateway_request_timeout(
    admin_config_paths,
    admin_settings,
):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    runtime = runtime.model_copy(
        update={
            "gateway": runtime.gateway.model_copy(update={"request_timeout": 600.0}),
        }
    )
    data = yaml.safe_load(render_docling_serve_yaml(runtime).split("\n", 2)[2])
    assert data["custom_ocr_presets"]["auto"]["timeout"] == 600.0
    assert (
        data["custom_layout_presets"]["default"]["engine_options"]["timeout"] == 600.0
    )
    assert (
        data["custom_picture_classification_presets"]["default"]["engine_options"][
            "timeout"
        ]
        == 600.0
    )
