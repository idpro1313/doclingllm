# region MODULE_CONTRACT [DOMAIN(8): OpenAIProxy; CONCEPT(8): PassThrough, RouteSelection; TECH(8): httpx]
## @modulecontract
## @purpose Proxy OpenAI-compatible /v1/chat/completions requests from docling-serve to Cloud.ru or LAN minimax backends.
## @changes
## LAST_CHANGE: [v0.2.20 – image chat → vlm stage; always rewrite model to route.model.]
## @modulemap
## FUNC 9[Proxy chat/completions body] => handle_openai_proxy
## FUNC 7[Select route from request body] => select_openai_route
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: OpenAI proxy, chat completions, pass-through, vlm, code_formula, model rewrite
# STRUCTURE: ▶ JSON body → ◇ select route → ⚡ proxy/post → ⎋ OpenAI JSON

import logging
from typing import Any

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.routing import RoutingTable, StageRoute, resolve_stage_route

logger = logging.getLogger(__name__)


# region FUNC_message_has_image [DOMAIN(6): OpenAIProxy; CONCEPT(6): Multimodal; TECH(6): dict]
## @purpose Detect multimodal image content in OpenAI messages list.
## @complexity 4
def message_has_image(messages: list[Any]) -> bool:
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


# endregion FUNC_message_has_image


# region FUNC_select_openai_route [DOMAIN(8): OpenAIProxy; CONCEPT(8): Routing; TECH(8): routing]
## @purpose Choose gateway stage route based on OpenAI request model and message content.
## @complexity 5
def select_openai_route(
    body: dict[str, Any],
    table: RoutingTable,
    settings: GatewaySettings,
) -> StageRoute:
    model = str(body.get("model", "")).lower()
    messages = body.get("messages", [])

    if settings.text_model.lower() in model or "minimax" in model:
        return resolve_stage_route("code_formula", table, settings)

    # BUG_FIX_CONTEXT: previously any image → picture_description, so VlmPipeline
    # "Convert this page to docling" never hit the vlm stage. Prefer vlm for page
    # convert; picture_description only when prompt clearly asks to describe a figure.
    if message_has_image(messages):
        joined = " ".join(
            part.get("text", "")
            for message in messages
            if isinstance(message, dict)
            for part in (
                message.get("content")
                if isinstance(message.get("content"), list)
                else [{"type": "text", "text": str(message.get("content", ""))}]
            )
            if isinstance(part, dict) and part.get("type") == "text"
        ).lower()
        if "describe" in joined and "picture" in joined:
            return resolve_stage_route("picture_description", table, settings)
        return resolve_stage_route("vlm", table, settings)

    return resolve_stage_route("vlm", table, settings)


# endregion FUNC_select_openai_route


# region FUNC_handle_openai_proxy [DOMAIN(9): OpenAIProxy; CONCEPT(9): Proxy; TECH(9): httpx]
## @purpose Forward OpenAI chat/completions request to resolved external backend.
## @complexity 4
def handle_openai_proxy(
    body: dict[str, Any],
    client: ExternalApiClient,
    table: RoutingTable,
    settings: GatewaySettings,
) -> dict[str, Any]:
    route = select_openai_route(body, table, settings)
    logger.info(
        f"[IMP:8][handle_openai_proxy][ROUTE] stage={route.stage} url={route.request_url} [PROXY]"
    )
    if route.mode == "openai_proxy":
        return client.proxy_chat_completions(route, body)

    messages = body.get("messages", [])
    response = client.chat_completions(route, messages, extra_params={
        k: v for k, v in body.items() if k not in {"model", "messages"}
    })
    logger.info(
        f"[IMP:9][handle_openai_proxy][OK] stage={route.stage} [VALUE]"
    )
    return response


# endregion FUNC_handle_openai_proxy
