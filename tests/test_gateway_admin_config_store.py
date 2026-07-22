# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): AdminConfigStore; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging

import yaml

from doclingllm.gateway.admin.config_store import (
    ensure_runtime_config_seeded,
    load_runtime_config,
    save_runtime_config,
)
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig

pytest_plugins = ["tests.conftest_admin"]


def test_seed_runtime_config_on_empty_volume(admin_config_paths, admin_settings, caplog):
    caplog.set_level(logging.INFO)
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    assert admin_config_paths.runtime_config.is_file()
    assert runtime.backends["vision"].api_key == "vision-secret"
    assert runtime.backends["vision"].model == "qwen3.6-35b-a3b"
    assert "ocr" in runtime.stages
    found = any("[IMP:9][ensure_runtime_config_seeded][SEED]" in r.message for r in caplog.records)
    print("\n--- LDD TRAJECTORY ---")
    for record in caplog.records:
        if "[IMP:" in record.message:
            print(record.message)
    assert found


def test_save_runtime_config_atomic(admin_config_paths, admin_settings):
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    runtime.backends["vision"].model = "updated-model"
    save_runtime_config(runtime, admin_config_paths)
    loaded = load_runtime_config(admin_config_paths, admin_settings)
    assert loaded.backends["vision"].model == "updated-model"
    raw = yaml.safe_load(admin_config_paths.runtime_config.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert raw["backends"]["vision"]["model"] == "updated-model"
