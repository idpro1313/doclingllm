# region MODULE_CONTRACT [DOMAIN(8): Admin; CONCEPT(8): Package; TECH(8): Python]
## @purpose Gateway admin UI package: runtime config store, connection tests, Gradio handlers.
def _module_contract():
    pass
# endregion MODULE_CONTRACT

from doclingllm.gateway.admin.config_store import (
    ensure_runtime_config_seeded,
    load_runtime_config,
    save_runtime_config,
)
from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.reload import reload_gateway_state

__all__ = [
    "ConfigPaths",
    "ensure_runtime_config_seeded",
    "load_runtime_config",
    "reload_gateway_state",
    "resolve_config_paths",
    "save_runtime_config",
]
