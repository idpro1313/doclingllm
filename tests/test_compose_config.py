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


def test_gateway_models_yaml_has_all_stages():
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "deploy" / "config" / "gateway-models.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    stages = data["stages"]
    for stage in ("ocr", "layout", "table", "vlm", "code_formula"):
        assert stage in stages
