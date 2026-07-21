# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): ConfigRouting; TECH(9): pytest, caplog]
## @purpose Verify GatewaySettings and RoutingTable load/resolution for Slice S1 with LDD telemetry.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: test gateway config routing settings yaml stage resolve
# STRUCTURE: ▶ fixtures → ◇ load settings/table → ⊕ resolve → ∑ assert + LDD print

import logging
import re
from pathlib import Path

import pytest

from doclingllm.gateway.config import GatewaySettings, load_gateway_settings
from doclingllm.gateway.routing import (
    load_routing_table,
    resolve_stage_route,
    substitute_env_placeholders,
)

IMP_LOG_PATTERN = re.compile(r"\[IMP:(\d+)\]")


def _print_ldd_trajectory(records, min_imp: int = 7) -> bool:
    found_high_imp = False
    print("\n--- LDD TRAJECTORY (IMP:7-10) ---")
    for record in records:
        match = IMP_LOG_PATTERN.search(record.message)
        if not match:
            continue
        imp_level = int(match.group(1))
        if imp_level >= min_imp:
            print(record.message)
        if imp_level >= 9 and "load_routing_table" in record.message:
            found_high_imp = True
    return found_high_imp


# region FUNC_test_substitute_env_placeholders [DOMAIN(7): Testing; TECH(7): pytest]
## @purpose Ensure ${VAR} expansion replaces known keys and leaves unknown keys empty.
def test_substitute_env_placeholders():
    env_map = {
        "VISION_API_BASE_URL": "https://ai-billing.develonica.group/v1",
        "VISION_MODEL": "qwen3.6-35b-a3b",
    }
    raw = "${VISION_API_BASE_URL}/chat/completions model=${VISION_MODEL} missing=${UNKNOWN}"
    result = substitute_env_placeholders(raw, env_map)
    assert "https://ai-billing.develonica.group/v1" in result
    assert "qwen3.6-35b-a3b" in result
    assert "${UNKNOWN}" not in result


# endregion FUNC_test_substitute_env_placeholders


# region FUNC_test_load_gateway_settings_from_env [DOMAIN(8): Testing; TECH(8): pytest, caplog]
## @purpose Validate GatewaySettings reads env overrides and emits IMP:9 readiness log.
def test_load_gateway_settings_from_env(clear_settings_cache, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("VISION_API_BASE_URL", "https://test-cloud.example/v1")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://10.0.0.5:8111/v1")
    monkeypatch.setenv("VISION_API_KEY", "test-vision-key")
    monkeypatch.setenv("TEXT_MODEL", "minimax-test")

    settings = load_gateway_settings()

    assert settings.vision_api_base_url == "https://test-cloud.example/v1"
    assert settings.text_api_base_url == "http://10.0.0.5:8111/v1"
    assert settings.vision_api_key == "test-vision-key"
    assert settings.text_model == "minimax-test"

    found_ready = any(
        "[IMP:9][load_gateway_settings][READY]" in record.message
        for record in caplog.records
    )
    print(f"\nSettings vision_model={settings.vision_model}")
    assert found_ready, "Missing IMP:9 readiness log from load_gateway_settings"


# endregion FUNC_test_load_gateway_settings_from_env


# region FUNC_test_load_routing_table [DOMAIN(9): Testing; TECH(9): pytest, caplog]
## @purpose Verify YAML routing table loads with env substitution and resolves OCR to vision route.
def test_load_routing_table(sample_routing_yaml, clear_settings_cache, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("VISION_API_BASE_URL", "https://ai-billing.develonica.group/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen3.6-35b-a3b")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://192.168.101.15:8111/v1")
    monkeypatch.setenv("TEXT_MODEL", "minimax-m2.7")
    monkeypatch.setenv("VISION_API_KEY", "secret-vision-token")

    settings = GatewaySettings(
        gateway_models_config_path=sample_routing_yaml,
    )
    table = load_routing_table(sample_routing_yaml, settings)

    assert "vision" in table.endpoints
    assert table.endpoints["vision"].base_url == "https://ai-billing.develonica.group/v1"
    assert "ocr" in table.stages
    assert len(table.stages) == 3

    ocr_route = resolve_stage_route("ocr", table, settings)
    assert ocr_route.mode == "openai_vision"
    assert ocr_route.model == "qwen3.6-35b-a3b"
    assert ocr_route.request_url == "https://ai-billing.develonica.group/v1/chat/completions"
    assert ocr_route.api_key == "secret-vision-token"
    assert ocr_route.response_parser == "deepseek_ocr_json"

    text_route = resolve_stage_route("code_formula", table, settings)
    assert text_route.endpoint_name == "text"
    assert text_route.mode == "openai_text"
    assert text_route.model == "minimax-m2.7"
    assert text_route.request_url == "http://192.168.101.15:8111/v1/chat/completions"
    assert text_route.api_key == ""

    found_routing_ready = _print_ldd_trajectory(caplog.records)
    assert found_routing_ready, "Missing IMP:9 log from load_routing_table"


# endregion FUNC_test_load_routing_table


# region FUNC_test_resolve_unknown_stage_raises [DOMAIN(7): Testing; TECH(7): pytest]
## @purpose Ensure misconfigured stage names fail fast with KeyError.
def test_resolve_unknown_stage_raises(sample_routing_yaml, clear_settings_cache, monkeypatch):
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_MODEL", "model-a")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://localhost/v1")
    monkeypatch.setenv("TEXT_MODEL", "model-b")

    settings = GatewaySettings(gateway_models_config_path=sample_routing_yaml)
    table = load_routing_table(sample_routing_yaml, settings)

    with pytest.raises(KeyError, match="Unknown pipeline stage"):
        resolve_stage_route("nonexistent_stage", table, settings)


# endregion FUNC_test_resolve_unknown_stage_raises


# region FUNC_test_load_production_routing_yaml [DOMAIN(8): Testing; TECH(8): pytest]
## @purpose Integration check against committed deploy/config/gateway-models.yaml.
def test_load_production_routing_yaml(clear_settings_cache, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    yaml_path = repo_root / "deploy" / "config" / "gateway-models.yaml"
    if not yaml_path.is_file():
        pytest.skip("Production gateway-models.yaml not present")

    monkeypatch.setenv("VISION_API_BASE_URL", "https://ai-billing.develonica.group/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen3.6-35b-a3b")
    monkeypatch.setenv("TEXT_API_BASE_URL", "http://192.168.101.15:8111/v1")
    monkeypatch.setenv("TEXT_MODEL", "minimax-m2.7")

    settings = GatewaySettings(gateway_models_config_path=yaml_path)
    table = load_routing_table(yaml_path, settings)

    assert len(table.stages) >= 7
    vlm_route = resolve_stage_route("vlm", table, settings)
    assert vlm_route.mode == "openai_proxy"
    assert "ai-billing.develonica.group" in vlm_route.request_url
    assert vlm_route.model == "qwen3.6-35b-a3b"


# endregion FUNC_test_load_production_routing_yaml
