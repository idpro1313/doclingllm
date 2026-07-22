# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): ConnectionTest; TECH(9): httpx]
## @purpose Probe vision/text backends and per-stage routes before admin Save.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: connection tester, models list, chat ping, vision ping, per-stage
# STRUCTURE: ▶ runtime → ○ probe backends → ○ per-stage route → ∑ TestReport

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from doclingllm.gateway.admin.config_store import runtime_to_settings
from doclingllm.gateway.admin.routing_merge import load_merged_routing_table
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig, mask_api_key
from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.routing import KNOWN_STAGE_NAMES, resolve_stage_route

logger = logging.getLogger(__name__)

_ONE_BY_ONE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_ms: float
    detail: str = ""


@dataclass
class TestReport:
    probes: list[ProbeResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(probe.ok for probe in self.probes)

    def to_markdown(self) -> str:
        lines = ["| Probe | Status | ms | Detail |", "|---|---|---:|---|"]
        for probe in self.probes:
            status = "OK" if probe.ok else "FAIL"
            lines.append(
                f"| {probe.name} | {status} | {probe.latency_ms:.0f} | {probe.detail} |"
            )
        return "\n".join(lines)


def _auth_headers(api_key: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_model_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id:
                ids.append(model_id)
    return ids


def _format_chat_failure_detail(
    *,
    status_code: int | None,
    model: str,
    response_text: str = "",
    available_models: list[str] | None = None,
    error: str = "",
) -> str:
    parts: list[str] = []
    if status_code is not None:
        parts.append(f"HTTP {status_code}")
    if error:
        parts.append(error)
    parts.append(f"model={model!r}")
    if response_text:
        snippet = response_text.strip().replace("\n", " ")
        if len(snippet) > 160:
            snippet = snippet[:157] + "..."
        parts.append(f"body={snippet}")
    if available_models:
        preview = ", ".join(available_models[:8])
        suffix = "..." if len(available_models) > 8 else ""
        parts.append(f"available_models=[{preview}{suffix}]")
    return "; ".join(parts)


def _probe_models_list(
    client: httpx.Client,
    backend_name: str,
    base_url: str,
    api_key: str,
) -> tuple[ProbeResult, list[str]]:
    url = f"{base_url.rstrip('/')}/models"
    start = time.perf_counter()
    try:
        response = client.get(url, headers=_auth_headers(api_key), timeout=30.0)
        latency = (time.perf_counter() - start) * 1000
        model_ids = _extract_model_ids(response.json()) if response.status_code < 400 else []
        if response.status_code >= 400:
            return (
                ProbeResult(
                    name=f"{backend_name}:models",
                    ok=False,
                    latency_ms=latency,
                    detail=f"HTTP {response.status_code}",
                ),
                model_ids,
            )
        return (
            ProbeResult(
                name=f"{backend_name}:models",
                ok=True,
                latency_ms=latency,
                detail=f"HTTP {response.status_code}",
            ),
            model_ids,
        )
    except httpx.RequestError as exc:
        latency = (time.perf_counter() - start) * 1000
        return (
            ProbeResult(
                name=f"{backend_name}:models",
                ok=False,
                latency_ms=latency,
                detail=str(exc),
            ),
            [],
        )


def _probe_chat_ping(
    client: httpx.Client,
    backend_name: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    available_models: list[str] | None = None,
) -> ProbeResult:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {"model": model, "messages": messages, "max_tokens": 8}
    start = time.perf_counter()
    try:
        response = client.post(
            url,
            headers={**_auth_headers(api_key), "Content-Type": "application/json"},
            json=payload,
            timeout=60.0,
        )
        latency = (time.perf_counter() - start) * 1000
        if response.status_code >= 400:
            return ProbeResult(
                name=f"{backend_name}:chat",
                ok=False,
                latency_ms=latency,
                detail=_format_chat_failure_detail(
                    status_code=response.status_code,
                    model=model,
                    response_text=response.text,
                    available_models=available_models,
                ),
            )
        return ProbeResult(
            name=f"{backend_name}:chat",
            ok=True,
            latency_ms=latency,
            detail=f"HTTP {response.status_code}",
        )
    except httpx.RequestError as exc:
        latency = (time.perf_counter() - start) * 1000
        return ProbeResult(
            name=f"{backend_name}:chat",
            ok=False,
            latency_ms=latency,
            detail=_format_chat_failure_detail(
                model=model,
                error=str(exc),
                available_models=available_models,
            ),
        )


def _vision_ping_messages() -> list[dict[str, Any]]:
    encoded = base64.b64encode(_ONE_BY_ONE_PNG).decode("ascii")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "ping"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                },
            ],
        }
    ]


def run_all_connection_tests(
    runtime: GatewayRuntimeConfig,
    http_client: Optional[httpx.Client] = None,
) -> TestReport:
    report = TestReport()
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=runtime.gateway.request_timeout, trust_env=True)
    settings = runtime_to_settings(runtime)
    table = load_merged_routing_table(runtime, settings=settings)
    try:
        for backend_name in ("vision", "text"):
            backend = runtime.backends[backend_name]
            logger.info(
                f"[IMP:7][test_all_connections][BACKEND] {backend_name} "
                f"url={backend.base_url} key={mask_api_key(backend.api_key)} [PROBE]"
            )
            models_probe, available_models = _probe_models_list(
                client, backend_name, backend.base_url, backend.api_key
            )
            report.probes.append(models_probe)
            report.probes.append(
                _probe_chat_ping(
                    client,
                    backend_name,
                    backend.base_url,
                    backend.api_key,
                    backend.model,
                    [{"role": "user", "content": "ping"}],
                    available_models=available_models,
                )
            )
            if backend_name == "vision":
                report.probes.append(
                    _probe_chat_ping(
                        client,
                        f"{backend_name}:vision",
                        backend.base_url,
                        backend.api_key,
                        backend.model,
                        _vision_ping_messages(),
                        available_models=available_models,
                    )
                )
        api_client = ExternalApiClient(settings, client=client)
        for stage_name in sorted(KNOWN_STAGE_NAMES):
            if stage_name not in runtime.stages:
                continue
            route = resolve_stage_route(stage_name, table, settings)
            messages = [{"role": "user", "content": f"ping stage {stage_name}"}]
            if route.mode == "openai_vision":
                messages = _vision_ping_messages()
            start = time.perf_counter()
            try:
                api_client.chat_completions(route, messages, extra_params={"max_tokens": 8})
                latency = (time.perf_counter() - start) * 1000
                report.probes.append(
                    ProbeResult(
                        name=f"stage:{stage_name}",
                        ok=True,
                        latency_ms=latency,
                        detail=route.mode,
                    )
                )
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000
                report.probes.append(
                    ProbeResult(
                        name=f"stage:{stage_name}",
                        ok=False,
                        latency_ms=latency,
                        detail=str(exc),
                    )
                )
    finally:
        if owns_client:
            client.close()
    logger.info(
        f"[IMP:9][run_all_connection_tests][RESULT] ok={report.ok} probes={len(report.probes)} [VALUE]"
    )
    return report
