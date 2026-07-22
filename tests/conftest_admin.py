# Admin test fixtures.

from pathlib import Path

import pytest

from doclingllm.gateway.admin.paths import ConfigPaths
from doclingllm.gateway.config import GatewaySettings


@pytest.fixture
def admin_config_paths(tmp_path: Path, monkeypatch) -> ConfigPaths:
    repo_root = Path(__file__).resolve().parents[1]
    config_dir = tmp_path / "volume"
    config_dir.mkdir(parents=True, exist_ok=True)
    models_template = repo_root / "deploy" / "config" / "gateway-models.template.yaml"
    runtime_defaults = repo_root / "deploy" / "config" / "gateway-runtime.defaults.yaml"
    paths = ConfigPaths(
        config_dir=config_dir,
        runtime_config=config_dir / "gateway-runtime.yaml",
        docling_serve_output=config_dir / "docling-serve.yaml",
        models_template=models_template,
        runtime_defaults=runtime_defaults,
    )
    monkeypatch.setenv("DOCLINGLLM_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("GATEWAY_RUNTIME_CONFIG", str(paths.runtime_config))
    monkeypatch.setenv("GATEWAY_MODELS_TEMPLATE", str(models_template))
    monkeypatch.setenv("GATEWAY_RUNTIME_DEFAULTS", str(runtime_defaults))
    return paths


@pytest.fixture
def admin_settings(admin_config_paths, monkeypatch) -> GatewaySettings:
    monkeypatch.setenv("VISION_API_BASE_URL", "https://vision.example/v1")
    monkeypatch.setenv("VISION_MODEL", "vision-model")
    monkeypatch.setenv("VISION_API_KEY", "vision-secret")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://text.example/v1")
    monkeypatch.setenv("TEXT_MODEL", "text-model")
    monkeypatch.setenv("TEXT_API_KEY", "")
    return GatewaySettings()
