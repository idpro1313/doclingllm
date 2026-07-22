# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): RoutingMerge; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging

from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded, runtime_to_settings
from doclingllm.gateway.admin.routing_merge import load_merged_routing_table
from doclingllm.gateway.routing import resolve_stage_route

pytest_plugins = ["tests.conftest_admin"]


def test_merged_routing_uses_runtime_models(admin_config_paths, admin_settings, caplog):
    caplog.set_level(logging.INFO)
    runtime = ensure_runtime_config_seeded(admin_config_paths, admin_settings)
    runtime.stages["ocr"].model = "ocr-special"
    settings = runtime_to_settings(runtime, admin_settings)
    table = load_merged_routing_table(runtime, admin_config_paths, settings)
    route = resolve_stage_route("ocr", table, settings)
    assert route.model == "ocr-special"
    assert route.request_url.startswith("https://")
    found = any("[IMP:9][load_merged_routing_table][READY]" in r.message for r in caplog.records)
    print("\n--- LDD TRAJECTORY ---")
    for record in caplog.records:
        if "[IMP:" in record.message and int(record.message.split("[IMP:")[1][0]) >= 7:
            print(record.message)
    assert found
