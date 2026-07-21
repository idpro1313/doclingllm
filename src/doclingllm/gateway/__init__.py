"""Model Gateway — протокольный адаптер KServe v2 / OpenAI для docling-serve."""

from doclingllm.gateway.app import create_app, run_gateway
from doclingllm.gateway.client import ExternalApiClient, extract_assistant_content
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings
from doclingllm.gateway.kserve import handle_kserve_infer
from doclingllm.gateway.openai_proxy import handle_openai_proxy
from doclingllm.gateway.routing import (
    RoutingTable,
    StageRoute,
    load_routing_table,
    resolve_stage_route,
)

__all__ = [
    "create_app",
    "run_gateway",
    "ExternalApiClient",
    "extract_assistant_content",
    "GatewaySettings",
    "load_gateway_settings",
    "handle_kserve_infer",
    "handle_openai_proxy",
    "RoutingTable",
    "StageRoute",
    "load_routing_table",
    "resolve_stage_route",
]
