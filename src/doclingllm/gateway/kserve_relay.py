# region MODULE_CONTRACT [DOMAIN(9): KServeRelay; CONCEPT(9): Passthrough, NativeBackend; TECH(9): httpx]
## @modulecontract
## @purpose Forward docling KServe v2 infer requests byte-for-byte to a native KServe/Triton backend without VLM prompts or parsers.
## @scope Transport relay only; preserves binary framing and response content type.
## @input Raw infer body, incoming HTTP headers, resolved StageRoute.
## @output Upstream httpx.Response (JSON or octet-stream).
## @links [USES_API(9): doclingllm.gateway.client.ExternalApiClient]
## @invariants
## - Relay NEVER mutates raw_body before POST to upstream.
## - Authorization from route.api_key is added; incoming Authorization is not forwarded.
## @rationale
## Q: Why separate module from kserve.py?
## A: openai_vision path decodes tensors and synthesizes prompts; relay must stay a thin proxy.
## @changes
## LAST_CHANGE: [v0.4.0 – Initial kserve_relay passthrough for native KServe backends.]
## @modulemap
## FUNC 10[Relay infer to upstream KServe] => handle_kserve_relay
## FUNC 8[Resolve upstream model name] => resolve_relay_model_name
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: kserve relay, passthrough, native backend, triton, infer proxy, raw body
# STRUCTURE: ▶ raw_body+headers → ◇ resolve relay_model → ⚡ POST upstream → ⎋ httpx.Response

import logging
from typing import Any

import httpx

from doclingllm.gateway.client import ExternalApiClient, UpstreamApiError
from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.kserve import KSERVE_MODEL_TO_STAGE
from doclingllm.gateway.routing import RoutingTable, StageRoute, resolve_stage_route

logger = logging.getLogger(__name__)

_FORWARD_REQUEST_HEADERS = frozenset(
    {
        "content-type",
        "inference-header-content-length",
        "accept",
    }
)


# region FUNC_resolve_relay_model_name [DOMAIN(8): KServeRelay; CONCEPT(8): ModelMapping; TECH(8): str]
## @purpose Choose upstream KServe model name for relay (template relay_model or gateway model alias).
## @io str + StageRoute -> str
## @complexity 2
def resolve_relay_model_name(gateway_model_name: str, route: StageRoute) -> str:
    if route.relay_model:
        return route.relay_model
    return gateway_model_name


# endregion FUNC_resolve_relay_model_name


# region FUNC_build_relay_upstream_url [DOMAIN(8): KServeRelay; CONCEPT(8): URL; TECH(8): str]
## @purpose Build upstream KServe infer URL for a resolved relay model name.
## @complexity 2
def build_relay_upstream_url(route: StageRoute, relay_model: str) -> str:
    base = route.base_url.rstrip("/")
    return f"{base}/v2/models/{relay_model}/infer"


# endregion FUNC_build_relay_upstream_url


# region FUNC_filter_relay_request_headers [DOMAIN(7): KServeRelay; CONCEPT(7): HTTP; TECH(7): dict]
## @purpose Copy safe incoming headers for upstream KServe POST (lowercase keys).
## @complexity 3
def filter_relay_request_headers(incoming_headers: dict[str, str]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key, value in incoming_headers.items():
        normalized = key.lower()
        if normalized in _FORWARD_REQUEST_HEADERS and value:
            forwarded[normalized] = value
    return forwarded


# endregion FUNC_filter_relay_request_headers


# region FUNC_handle_kserve_relay [DOMAIN(9): KServeRelay; CONCEPT(9): Passthrough; TECH(9): httpx]
## @purpose POST raw KServe infer body to native backend and return upstream response unchanged.
## @uses ExternalApiClient.kserve_relay_infer, resolve_stage_route
## @complexity 5
def handle_kserve_relay(
    gateway_model_name: str,
    raw_body: bytes,
    incoming_headers: dict[str, str],
    client: ExternalApiClient,
    table: RoutingTable,
    settings: GatewaySettings,
) -> httpx.Response:
    stage = KSERVE_MODEL_TO_STAGE.get(gateway_model_name)
    if not stage:
        logger.critical(
            f"[IMP:10][handle_kserve_relay][UNKNOWN_MODEL] model={gateway_model_name} [FATAL]"
        )
        raise KeyError(f"Unsupported KServe model name: {gateway_model_name}")

    route = resolve_stage_route(stage, table, settings)
    if route.mode != "kserve_relay":
        logger.critical(
            f"[IMP:10][handle_kserve_relay][MODE] stage={stage} expected=kserve_relay got={route.mode} [FATAL]"
        )
        raise ValueError(f"Stage {stage} is not configured for kserve_relay")

    relay_model = resolve_relay_model_name(gateway_model_name, route)
    upstream_url = build_relay_upstream_url(route, relay_model)
    logger.info(
        f"[IMP:8][handle_kserve_relay][RELAY] gateway_model={gateway_model_name} "
        f"upstream_model={relay_model} url={upstream_url} bytes={len(raw_body)} [ROUTE]"
    )
    response = client.kserve_relay_infer(
        route,
        upstream_url=upstream_url,
        raw_body=raw_body,
        request_headers=filter_relay_request_headers(incoming_headers),
        relay_model=relay_model,
    )
    if response.status_code >= 400:
        logger.critical(
            f"[IMP:10][handle_kserve_relay][UPSTREAM_HTTP] status={response.status_code} "
            f"model={relay_model} body={response.text[:500]} [FATAL]"
        )
        raise UpstreamApiError(
            f"Upstream KServe relay failed ({response.status_code}) for {upstream_url}: "
            f"{response.text[:500]}",
            status_code=502 if response.status_code >= 500 else response.status_code,
        )
    logger.info(
        f"[IMP:9][handle_kserve_relay][OK] gateway_model={gateway_model_name} "
        f"upstream_model={relay_model} status={response.status_code} [VALUE]"
    )
    return response


# endregion FUNC_handle_kserve_relay
