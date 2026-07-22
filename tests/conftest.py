# region MODULE_CONTRACT [DOMAIN(7): Testing; CONCEPT(8): AntiLoop, PytestHooks; TECH(8): pytest]
## @purpose Provide pytest session hooks and shared fixtures for doclingllm gateway tests with Anti-Loop attempt tracking.
## @invariants
## - .test_counter.json increments only on session failure.
## - load_gateway_settings cache is cleared per test via fixture.
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from pathlib import Path

import pytest

from doclingllm.gateway.config import load_gateway_settings

COUNTER_FILE = Path(".test_counter.json")


def _read_counter() -> int:
    if not COUNTER_FILE.exists():
        return 0
    try:
        data = json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
        return int(data.get("failed_attempts", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def _write_counter(value: int) -> None:
    COUNTER_FILE.write_text(
        json.dumps({"failed_attempts": value}, indent=2),
        encoding="utf-8",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    attempts = _read_counter()
    if attempts > 0:
        print(f"\n[Anti-Loop] Previous failed attempts: {attempts}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if exitstatus == 0:
        _write_counter(0)
    else:
        _write_counter(_read_counter() + 1)


@pytest.fixture
def clear_settings_cache():
    load_gateway_settings.cache_clear()
    yield
    load_gateway_settings.cache_clear()


@pytest.fixture
def sample_routing_yaml(tmp_path: Path) -> Path:
    yaml_path = tmp_path / "gateway-models.yaml"
    yaml_path.write_text(
        """
endpoints:
  vision:
    base_url: "${VISION_API_BASE_URL}"
    api_key_env: VISION_API_KEY
    default_model: "${VISION_MODEL}"
  text:
    base_url: "${TEXT_API_BASE_URL}"
    api_key_env: TEXT_API_KEY
    default_model: "${TEXT_MODEL}"

stages:
  ocr:
    endpoint: vision
    mode: openai_vision
    model: "${VISION_MODEL}"
    path: /chat/completions
    response_parser: deepseek_ocr_json
    request_params:
      max_tokens: 512
      temperature: 0
  layout:
    endpoint: vision
    mode: openai_vision
    model: "${VISION_MODEL}"
    path: /chat/completions
    response_parser: layout_boxes_json
    request_params:
      max_tokens: 512
      temperature: 0
  code_formula:
    endpoint: text
    mode: openai_text
    model: minimax-m2.7
    path: /chat/completions
  vlm:
    endpoint: vision
    mode: openai_proxy
    model: "${VISION_MODEL}"
    path: /chat/completions
""",
        encoding="utf-8",
    )
    return yaml_path
