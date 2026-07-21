# region MODULE_CONTRACT [DOMAIN(9): HTTPClient; CONCEPT(9): OpenAIAPI, ExternalInference; TECH(9): httpx]
## @modulecontract
## @purpose Execute outbound OpenAI-compatible chat/completions calls to Cloud.ru and LAN backends with auth, timeouts, and structured logging.
## @scope HTTP transport only; no KServe parsing.
## @input StageRoute, message payloads.
## @output Parsed JSON response dict from external API.
## @links [USES_API(9): httpx]
## @links_to_spec plans/Architecture.md L4 Integration
## @invariants
## - Authorization header is NEVER logged.
## - chat_completions raises httpx.HTTPStatusError on 4xx/5xx after logging IMP:10.
## @changes
## LAST_CHANGE: [v0.2.0 Slice S2 – ExternalApiClient with vision and proxy modes.]
## @modulemap
## CLASS 10[Outbound HTTP client] => ExternalApiClient
## @usecases
## - [ExternalApiClient.chat_completions]: Gateway handler → POST external API → JSON response
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: httpx, client, OpenAI, chat completions, Bearer, vision, external API
# STRUCTURE: ▶ StageRoute ┌build headers/body┐ → ⚡ POST → ◇ json → ⎋ dict

import base64
import logging
from typing import Any, Optional

import httpx

from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.routing import StageRoute

logger = logging.getLogger(__name__)


# region CLASS_ExternalApiClient [DOMAIN(9): HTTPClient; CONCEPT(9): Integration; TECH(9): httpx]
## @purpose Centralize outbound HTTP to vision and text backends with consistent headers and error handling.
class ExternalApiClient:
    def __init__(self, settings: GatewaySettings, client: Optional[httpx.Client] = None):
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=settings.gateway_request_timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "ExternalApiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _build_headers(self, route: StageRoute) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if route.api_key:
            headers["Authorization"] = f"Bearer {route.api_key}"
        return headers

    def chat_completions(
        self,
        route: StageRoute,
        messages: list[dict[str, Any]],
        extra_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """POST OpenAI-compatible chat/completions to resolved route URL."""
        payload: dict[str, Any] = {
            "model": route.model,
            "messages": messages,
        }
        if extra_params:
            payload.update(extra_params)

        logger.info(
            f"[IMP:7][ExternalApiClient.chat_completions][REQUEST] "
            f"stage={route.stage} url={route.request_url} model={route.model} [HTTP]"
        )
        response = self._client.post(
            route.request_url,
            headers=self._build_headers(route),
            json=payload,
        )
        if response.status_code >= 400:
            logger.critical(
                f"[IMP:10][ExternalApiClient.chat_completions][HTTP_ERROR] "
                f"status={response.status_code} stage={route.stage} body={response.text[:500]} [FATAL]"
            )
            response.raise_for_status()

        data = response.json()
        logger.info(
            f"[IMP:9][ExternalApiClient.chat_completions][OK] "
            f"stage={route.stage} status={response.status_code} [VALUE]"
        )
        return data

    def vision_inference(
        self,
        route: StageRoute,
        image_bytes: bytes,
        user_prompt: str = "Extract structured data from this document image.",
    ) -> str:
        """Call vision backend and return assistant message content string."""
        image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        messages: list[dict[str, Any]] = []
        if route.system_prompt:
            messages.append({"role": "system", "content": route.system_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        )
        response_data = self.chat_completions(route, messages)
        return extract_assistant_content(response_data)

    def proxy_chat_completions(
        self,
        route: StageRoute,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass-through OpenAI request body to external backend."""
        if "model" not in body:
            body = {**body, "model": route.model}
        logger.info(
            f"[IMP:7][ExternalApiClient.proxy_chat_completions][PROXY] "
            f"url={route.request_url} model={body.get('model')} [HTTP]"
        )
        response = self._client.post(
            route.request_url,
            headers=self._build_headers(route),
            json=body,
        )
        if response.status_code >= 400:
            logger.critical(
                f"[IMP:10][ExternalApiClient.proxy_chat_completions][HTTP_ERROR] "
                f"status={response.status_code} [FATAL]"
            )
            response.raise_for_status()
        data = response.json()
        logger.info(
            f"[IMP:9][ExternalApiClient.proxy_chat_completions][OK] status={response.status_code} [VALUE]"
        )
        return data


# endregion CLASS_ExternalApiClient


# region FUNC_extract_assistant_content [DOMAIN(7): HTTPClient; CONCEPT(7): OpenAIResponse; TECH(7): dict]
## @purpose Extract first assistant message string from OpenAI chat/completions JSON response.
## @complexity 3
def extract_assistant_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(text_parts)
    return str(content)


# endregion FUNC_extract_assistant_content
