# region MODULE_CONTRACT [DOMAIN(7): Testing; CONCEPT(7): DeployConfig; TECH(7): yaml]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

from pathlib import Path

import yaml


def test_docker_compose_declares_remote_services():
    repo_root = Path(__file__).resolve().parents[1]
    compose_path = repo_root / "deploy" / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")
    assert "DOCLING_SERVE_ENABLE_REMOTE_SERVICES" in text
    assert "DOCLING_SERVE_LOAD_MODELS_AT_BOOT" in text
    assert 'DOCLING_SERVE_LOAD_MODELS_AT_BOOT: "false"' in text
    assert 'DOCLING_SERVE_ENABLE_UI: "true"' in text
    assert "model-gateway" in text
    assert "docling-serve" in text


def test_docling_serve_yaml_points_to_gateway():
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "deploy" / "config" / "docling-serve.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["enable_remote_services"] is True
    assert data["load_models_at_boot"] is False
    assert "http://model-gateway:8080" in yaml.dump(data)
    assert data.get("allowed_ocr_presets") is None
    assert data["default_ocr_preset"] == "remote_ocr"
    layout_default = data["custom_layout_presets"]["default"]
    assert layout_default["kind"] == "layout_object_detection"
    assert layout_default["engine_options"]["engine_type"] == "api_kserve_v2"
    assert layout_default["engine_options"]["model_name"] == "layout"
    ocr_auto = data["custom_ocr_presets"]["auto"]
    assert ocr_auto["kind"] == "kserve_v2_ocr"
    assert ocr_auto["model_name"] == "ocr"
    assert data["default_table_structure_preset"] == "tableformer_v1_accurate"
    assert "custom_table_structure_presets" not in data
    pic_default = data["custom_picture_classification_presets"]["default"]
    assert pic_default["engine_options"]["engine_type"] == "api_kserve_v2"
    assert "kind" not in pic_default


def test_env_defaults_has_required_keys():
    repo_root = Path(__file__).resolve().parents[1]
    defaults_path = repo_root / "deploy" / ".env.defaults"
    text = defaults_path.read_text(encoding="utf-8")
    for key in (
        "VISION_API_BASE_URL",
        "VISION_API_KEY=",
        "DOCLING_SERVE_ENABLE_UI=true",
        "TEXT_API_BASE_URL",
    ):
        assert key in text
    for line in text.splitlines():
        if line.startswith("VISION_API_KEY="):
            assert line == "VISION_API_KEY="
            break
    else:
        raise AssertionError("VISION_API_KEY line missing in .env.defaults")


def test_start_sh_creates_env_from_defaults():
    repo_root = Path(__file__).resolve().parents[1]
    start_sh = repo_root / "scripts" / "start.sh"
    text = start_sh.read_text(encoding="utf-8")
    assert ".env.defaults" in text
    assert "prompt_for_vision_api_key" in text


def test_gateway_models_yaml_has_all_stages():
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "deploy" / "config" / "gateway-models.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    stages = data["stages"]
    for stage in ("ocr", "layout", "table", "vlm", "code_formula"):
        assert stage in stages
