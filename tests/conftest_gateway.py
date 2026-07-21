# Gateway test fixtures and constants.

import base64
from pathlib import Path

import pytest

from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.routing import load_routing_table

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
TINY_PNG_BYTES = base64.standard_b64decode(TINY_PNG_B64)


@pytest.fixture
def gateway_settings(sample_routing_yaml, monkeypatch) -> GatewaySettings:
    monkeypatch.setenv("VISION_API_BASE_URL", "https://foundation-models.api.cloud.ru/v1")
    monkeypatch.setenv("VISION_MODEL", "deepseek-ai/DeepSeek-OCR-2")
    monkeypatch.setenv("VISION_API_KEY", "test-vision-key")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://192.168.101.15:8111/v1")
    monkeypatch.setenv("TEXT_MODEL", "minimax-m2.7")
    return GatewaySettings(gateway_models_config_path=sample_routing_yaml)


@pytest.fixture
def routing_table(gateway_settings) -> "RoutingTable":
    from doclingllm.gateway.routing import RoutingTable

    return load_routing_table(gateway_settings.gateway_models_config_path, gateway_settings)


@pytest.fixture
def full_routing_yaml(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "deploy" / "config" / "gateway-models.yaml"
    target = tmp_path / "gateway-models.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


@pytest.fixture
def kserve_image_request() -> dict:
    return {
        "inputs": [
            {
                "name": "image",
                "shape": [1],
                "datatype": "BYTES",
                "data": [TINY_PNG_B64],
            }
        ]
    }
