# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): Reload; TECH(8): FastAPI]
## @purpose Hot-reload gateway routing and HTTP client from volume runtime config.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: reload gateway state, admin reload, runtime config, routing table
# STRUCTURE: ▶ load runtime → ⊕ merge routing → ⊕ new client → ⎋ GatewayState

import logging
from typing import TYPE_CHECKING

from doclingllm.gateway.admin.config_store import (
    apply_proxy_env,
    ensure_runtime_config_seeded,
    load_runtime_config,
    runtime_to_settings,
)
from doclingllm.gateway.admin.docling_generator import write_docling_serve_yaml
from doclingllm.gateway.admin.paths import resolve_config_paths
from doclingllm.gateway.admin.routing_merge import load_merged_routing_table
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

    from doclingllm.gateway.app import GatewayState

logger = logging.getLogger(__name__)


def bootstrap_runtime_config(
    settings: GatewaySettings | None = None,
) -> GatewayRuntimeConfig:
    resolved_settings = settings or load_gateway_settings()
    paths = resolve_config_paths()
    runtime = ensure_runtime_config_seeded(paths, resolved_settings)
    if not paths.docling_serve_output.is_file():
        write_docling_serve_yaml(runtime, paths=paths)
    return runtime


def build_gateway_state(
    settings: GatewaySettings | None = None,
    client: ExternalApiClient | None = None,
) -> "GatewayState":
    from doclingllm.gateway.app import GatewayState

    resolved_settings = settings or load_gateway_settings()
    runtime = bootstrap_runtime_config(resolved_settings)
    apply_proxy_env(runtime)
    effective_settings = runtime_to_settings(runtime, resolved_settings)
    table = load_merged_routing_table(runtime, settings=effective_settings)
    resolved_client = client or ExternalApiClient(effective_settings)
    return GatewayState(effective_settings, table, resolved_client)


def reload_gateway_state(app: "FastAPI") -> "GatewayState":
    from doclingllm.gateway.app import GatewayState

    base_settings = load_gateway_settings()
    paths = resolve_config_paths()
    runtime = load_runtime_config(paths, base_settings)
    apply_proxy_env(runtime)
    effective_settings = runtime_to_settings(runtime, base_settings)
    table = load_merged_routing_table(runtime, paths, effective_settings)
    previous: GatewayState = app.state.gateway
    previous.client.close()
    new_state = GatewayState(effective_settings, table, ExternalApiClient(effective_settings))
    app.state.gateway = new_state
    logger.info(
        f"[IMP:9][reload_gateway_state][RELOAD] vision_model={effective_settings.vision_model} [OK]"
    )
    return new_state
