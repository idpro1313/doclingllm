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
## LAST_CHANGE: [v0.4.0 – kserve_relay_infer raw-byte POST to native KServe backends.]
## @modulemap
## CLASS 10[Outbound HTTP client] => ExternalApiClient
## CLASS 8[Upstream transport/HTTP failure] => UpstreamApiError
## @usecases
## - [ExternalApiClient.chat_completions]: Gateway handler → POST external API → JSON response
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: httpx, client, OpenAI, chat completions, Bearer, vision, external API, UpstreamApiError, proxy
# STRUCTURE: ▶ StageRoute ┌build headers/body┐ → ⚡ POST → ◇ RequestError? UpstreamApiError : json → ⎋ dict

import base64
import logging
from typing import Any, Optional

import httpx

from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.request_logging import (
    log_model_inbound_response,
    log_model_outbound_request,
)
from doclingllm.gateway.routing import StageRoute

logger = logging.getLogger(__name__)

_RETRYABLE_TRANSPORT_ERRORS = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


# region CLASS_UpstreamApiError [DOMAIN(8): HTTPClient; CONCEPT(9): UpstreamFailure; TECH(8): Exception]
## @purpose Signal gateway handlers that the external vision/text API is unreachable or failed transport.
class UpstreamApiError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


# endregion CLASS_UpstreamApiError


# region CLASS_ExternalApiClient [DOMAIN(9): HTTPClient; CONCEPT(9): Integration; TECH(9): httpx]
## @purpose Centralize outbound HTTP to vision and text backends with consistent headers and error handling.
class ExternalApiClient:
    def __init__(self, settings: GatewaySettings, client: Optional[httpx.Client] = None):
        self._settings = settings
        self._owns_client = client is None
        # BUG_FIX_CONTEXT: trust_env=True so HTTP_PROXY/HTTPS_PROXY from container env are honored for Cloud.ru TLS egress.
        self._client = client or httpx.Client(
            timeout=settings.gateway_request_timeout,
            trust_env=True,
        )

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

    def _post_json_with_retry(
        self,
        route: StageRoute,
        *,
        payload: dict[str, Any],
        log_prefix: str,
    ) -> httpx.Response:
        max_attempts = 1 + max(0, self._settings.gateway_upstream_retries)
        last_error: httpx.RequestError | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._client.post(
                    route.request_url,
                    headers=self._build_headers(route),
                    json=payload,
                )
            except httpx.RequestError as exc:
                last_error = exc
                retryable = isinstance(exc, _RETRYABLE_TRANSPORT_ERRORS)
                if retryable and attempt < max_attempts:
                    logger.warning(
                        f"[IMP:8][ExternalApiClient.{log_prefix}][RETRY] "
                        f"stage={route.stage} attempt={attempt}/{max_attempts} "
                        f"url={route.request_url} error={exc} [FLOW]"
                    )
                    continue
                logger.critical(
                    f"[IMP:10][ExternalApiClient.{log_prefix}][TRANSPORT] "
                    f"stage={route.stage} url={route.request_url} error={exc} [FATAL]"
                )
                raise UpstreamApiError(
                    f"Upstream transport failure for {route.request_url}: {exc}"
                ) from exc
        if last_error is not None:
            raise UpstreamApiError(
                f"Upstream transport failure for {route.request_url}: {last_error}"
            ) from last_error
        raise UpstreamApiError(f"Upstream transport failure for {route.request_url}")

    def _merge_chat_payload(
        self,
        route: StageRoute,
        messages: list[dict[str, Any]],
        extra_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": route.model,
            "messages": messages,
        }
        if route.request_params:
            payload.update(route.request_params)
        if extra_params:
            payload.update(extra_params)
        return payload

    def _log_token_usage(self, route: StageRoute, response_data: dict[str, Any]) -> None:
        usage = response_data.get("usage")
        if not isinstance(usage, dict):
            return
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        reasoning_tokens: int | None = None
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            raw_reasoning = details.get("reasoning_tokens")
            if isinstance(raw_reasoning, int):
                reasoning_tokens = raw_reasoning
        metric_parts = [
            f"prompt={prompt_tokens}",
            f"completion={completion_tokens}",
            f"total={total_tokens}",
        ]
        if reasoning_tokens is not None:
            metric_parts.append(f"reasoning={reasoning_tokens}")
        logger.info(
            f"[IMP:8][ExternalApiClient.chat_completions][USAGE] "
            f"stage={route.stage} model={route.model} {' '.join(metric_parts)} [METRICS]"
        )

    def chat_completions(
        self,
        route: StageRoute,
        messages: list[dict[str, Any]],
        extra_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """POST OpenAI-compatible chat/completions to resolved route URL."""
        payload = self._merge_chat_payload(route, messages, extra_params)

        logger.info(
            f"[IMP:7][ExternalApiClient.chat_completions][REQUEST] "
            f"stage={route.stage} url={route.request_url} model={route.model} [HTTP]"
        )
        log_model_outbound_request(
            logger,
            stage=route.stage,
            request_url=route.request_url,
            payload=payload,
            call_kind="chat_completions",
        )
        response = self._post_json_with_retry(
            route,
            payload=payload,
            log_prefix="chat_completions",
        )
        if response.status_code >= 400:
            logger.critical(
                f"[IMP:10][ExternalApiClient.chat_completions][HTTP_ERROR] "
                f"status={response.status_code} stage={route.stage} body={response.text[:500]} [FATAL]"
            )
            response.raise_for_status()

        data = response.json()
        self._log_token_usage(route, data)
        log_model_inbound_response(
            logger,
            stage=route.stage,
            request_url=route.request_url,
            response_data=data,
            call_kind="chat_completions",
        )
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

    def kserve_relay_infer(
        self,
        route: StageRoute,
        *,
        upstream_url: str,
        raw_body: bytes,
        request_headers: dict[str, str],
        relay_model: str,
    ) -> httpx.Response:
        """POST raw KServe infer body to upstream without JSON re-encoding."""
        headers = dict(request_headers)
        if route.api_key:
            headers["Authorization"] = f"Bearer {route.api_key}"
        if "content-type" not in headers:
            headers["content-type"] = "application/json"

        logger.info(
            f"[IMP:7][ExternalApiClient.kserve_relay_infer][REQUEST] "
            f"stage={route.stage} url={upstream_url} model={relay_model} "
            f"bytes={len(raw_body)} [HTTP]"
        )
        try:
            response = self._client.post(
                upstream_url,
                headers=headers,
                content=raw_body,
            )
        except httpx.RequestError as exc:
            logger.critical(
                f"[IMP:10][ExternalApiClient.kserve_relay_infer][TRANSPORT] "
                f"stage={route.stage} url={upstream_url} error={exc} [FATAL]"
            )
            raise UpstreamApiError(
                f"Upstream transport failure for {upstream_url}: {exc}"
            ) from exc
        logger.info(
            f"[IMP:9][ExternalApiClient.kserve_relay_infer][OK] "
            f"stage={route.stage} status={response.status_code} [VALUE]"
        )
        return response

    def proxy_chat_completions(
        self,
        route: StageRoute,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass-through OpenAI request body to external backend."""
        # BUG_FIX_CONTEXT: docling-serve.yaml may send placeholder model (remote-vision);
        # always force the env-resolved route.model (VISION_MODEL / TEXT_MODEL).
        body = {**body, "model": route.model}
        logger.info(
            f"[IMP:7][ExternalApiClient.proxy_chat_completions][PROXY] "
            f"url={route.request_url} model={body.get('model')} [HTTP]"
        )
        log_model_outbound_request(
            logger,
            stage=route.stage,
            request_url=route.request_url,
            payload=body,
            call_kind="openai_proxy",
        )
        response = self._post_json_with_retry(
            route,
            payload=body,
            log_prefix="proxy_chat_completions",
        )
        if response.status_code >= 400:
            logger.critical(
                f"[IMP:10][ExternalApiClient.proxy_chat_completions][HTTP_ERROR] "
                f"status={response.status_code} [FATAL]"
            )
            response.raise_for_status()
        data = response.json()
        self._log_token_usage(route, data)
        log_model_inbound_response(
            logger,
            stage=route.stage,
            request_url=route.request_url,
            response_data=data,
            call_kind="openai_proxy",
        )
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
