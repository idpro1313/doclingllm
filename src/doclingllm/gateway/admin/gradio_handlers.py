# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): GradioHandlers; TECH(8): headless]
## @purpose Headless controller functions for Gradio admin UI (Pattern 4 testing).
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: gradio handlers, test save, admin UI, runtime form, kserve_relay, stage mode
# STRUCTURE: ▶ form → GatewayRuntimeConfig → ◇ test → ⊕ save → ⎋ reload hint

import logging
from dataclasses import dataclass
from typing import Any, Optional

from doclingllm.gateway.admin.config_store import load_runtime_config, save_runtime_config
from doclingllm.gateway.admin.connection_tester import TestReport, run_all_connection_tests
from doclingllm.gateway.admin.docling_generator import (
    DOCLING_RESTART_HINT,
    render_docling_serve_yaml,
    write_docling_serve_yaml,
)
from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.reload import reload_gateway_state
from doclingllm.gateway.admin.runtime_models import (
    BackendConfig,
    GatewayRuntimeConfig,
    GatewaySection,
    ProxySection,
    StageOverride,
    mask_api_key,
)
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings
from doclingllm.gateway.routing import KNOWN_MODES, KNOWN_STAGE_NAMES

logger = logging.getLogger(__name__)

STAGE_MODE_CHOICES = sorted(KNOWN_MODES)
STAGE_ENDPOINT_CHOICES = ["vision", "text", "kserve_native"]


@dataclass
class SaveResult:
    ok: bool
    message: str
    docling_preview: str = ""


def runtime_to_form(runtime: GatewayRuntimeConfig) -> dict[str, Any]:
    vision = runtime.backends["vision"]
    text = runtime.backends["text"]
    kserve_native = runtime.backends.get("kserve_native", BackendConfig())
    stage_models: dict[str, str] = {}
    stage_endpoints: dict[str, str] = {}
    stage_modes: dict[str, str] = {}
    stage_relay_models: dict[str, str] = {}
    for stage in KNOWN_STAGE_NAMES:
        if stage not in runtime.stages:
            continue
        entry = runtime.stages[stage]
        stage_models[stage] = entry.model
        stage_endpoints[stage] = entry.endpoint
        stage_modes[stage] = entry.resolved_mode(stage)
        stage_relay_models[stage] = entry.relay_model
    return {
        "vision_base_url": vision.base_url,
        "vision_api_key": vision.api_key,
        "vision_model": vision.model,
        "text_base_url": text.base_url,
        "text_api_key": text.api_key,
        "text_model": text.model,
        "kserve_native_base_url": kserve_native.base_url,
        "kserve_native_api_key": kserve_native.api_key,
        "request_timeout": runtime.gateway.request_timeout,
        "http_proxy": runtime.proxy.http_proxy,
        "https_proxy": runtime.proxy.https_proxy,
        "no_proxy": runtime.proxy.no_proxy,
        "stage_models": stage_models,
        "stage_endpoints": stage_endpoints,
        "stage_modes": stage_modes,
        "stage_relay_models": stage_relay_models,
        "last_test_ok": runtime.meta.last_test_ok,
    }


def split_stage_form_values(
    stage_names: list[str],
    stage_mode_values: list[str],
    stage_endpoint_values: list[str],
    stage_model_values: list[str],
    stage_relay_model_values: list[str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Map parallel Gradio stage inputs to dicts (modes, endpoints, models, relay_models)."""
    stage_modes = dict(zip(stage_names, stage_mode_values, strict=True))
    stage_endpoints = dict(zip(stage_names, stage_endpoint_values, strict=True))
    stage_models = dict(zip(stage_names, stage_model_values, strict=True))
    stage_relay_models = dict(zip(stage_names, stage_relay_model_values, strict=True))
    return stage_modes, stage_endpoints, stage_models, stage_relay_models


def parse_stage_inputs_from_form_tail(
    stage_names: list[str],
    tail: list[Any],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Parse flat form tail: [*modes, *endpoints, *models, *relay_models]."""
    count = len(stage_names)
    stage_mode_values = tail[:count]
    stage_endpoint_values = tail[count : 2 * count]
    stage_model_values = tail[2 * count : 3 * count]
    stage_relay_model_values = tail[3 * count : 4 * count]
    return split_stage_form_values(
        stage_names,
        stage_mode_values,
        stage_endpoint_values,
        stage_model_values,
        stage_relay_model_values,
    )


def sync_stage_models_from_backends(
    stage_names: list[str],
    vision_model: str,
    text_model: str,
    stage_endpoints: dict[str, str],
    stage_modes: dict[str, str],
    current_models: dict[str, str],
) -> list[str]:
    """Return model names per stage row; preserve relay gateway aliases."""
    models: list[str] = []
    for stage in stage_names:
        mode = stage_modes.get(stage, "openai_vision")
        if mode == "kserve_relay":
            models.append(current_models.get(stage, stage))
            continue
        endpoint = stage_endpoints.get(
            stage,
            "text" if stage == "code_formula" else "vision",
        )
        models.append(text_model if endpoint == "text" else vision_model)
    return models


def validate_stage_routing(
    runtime: GatewayRuntimeConfig,
    stages: dict[str, StageOverride],
) -> None:
    kserve_backend = runtime.backends.get("kserve_native", BackendConfig())
    for stage_name, override in stages.items():
        mode = override.resolved_mode(stage_name)
        if mode != "kserve_relay":
            continue
        if override.endpoint != "kserve_native":
            raise ValueError(
                f"Stage {stage_name}: kserve_relay requires endpoint kserve_native"
            )
        if not override.relay_model.strip():
            raise ValueError(
                f"Stage {stage_name}: kserve_relay requires relay_model (upstream KServe name)"
            )
        if not kserve_backend.base_url.strip():
            raise ValueError(
                f"Stage {stage_name}: kserve_relay requires KServe Native base URL"
            )


def form_to_runtime(
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    text_base_url: str,
    text_api_key: str,
    text_model: str,
    kserve_native_base_url: str,
    kserve_native_api_key: str,
    request_timeout: float,
    http_proxy: str,
    https_proxy: str,
    no_proxy: str,
    stage_modes: dict[str, str],
    stage_endpoints: dict[str, str],
    stage_models: dict[str, str],
    stage_relay_models: dict[str, str],
    previous: Optional[GatewayRuntimeConfig] = None,
) -> GatewayRuntimeConfig:
    base = previous or GatewayRuntimeConfig()
    stages: dict[str, StageOverride] = {}
    for stage in KNOWN_STAGE_NAMES:
        endpoint = stage_endpoints.get(stage, "vision" if stage != "code_formula" else "text")
        mode = stage_modes.get(stage, "openai_vision")
        model = stage_models.get(
            stage,
            stage if mode == "kserve_relay" else (text_model if endpoint == "text" else vision_model),
        )
        relay_model = stage_relay_models.get(stage, "")
        stages[stage] = StageOverride(
            endpoint=endpoint,
            model=model.strip(),
            mode=mode,
            relay_model=relay_model.strip(),
        )
    runtime = GatewayRuntimeConfig(
        version=base.version,
        backends={
            "vision": BackendConfig(
                base_url=vision_base_url.strip(),
                api_key=vision_api_key,
                model=vision_model.strip(),
            ),
            "text": BackendConfig(
                base_url=text_base_url.strip(),
                api_key=text_api_key,
                model=text_model.strip(),
            ),
            "kserve_native": BackendConfig(
                base_url=kserve_native_base_url.strip(),
                api_key=kserve_native_api_key,
                model="",
            ),
        },
        gateway=GatewaySection(
            request_timeout=float(request_timeout),
            log_level=base.gateway.log_level,
        ),
        proxy=ProxySection(
            http_proxy=http_proxy.strip(),
            https_proxy=https_proxy.strip(),
            no_proxy=no_proxy.strip(),
        ),
        stages=stages,
        meta=base.meta,
    )
    validate_stage_routing(runtime, stages)
    return runtime


def handle_test_connection(
    runtime: GatewayRuntimeConfig,
) -> tuple[TestReport, GatewayRuntimeConfig]:
    report = run_all_connection_tests(runtime)
    updated = runtime.mark_test_result(report.ok)
    logger.info(
        f"[IMP:9][handle_test_connection][RESULT] ok={report.ok} [VALUE]"
    )
    return report, updated


def handle_save_config(
    runtime: GatewayRuntimeConfig,
    *,
    last_test_ok: bool,
    paths: Optional[ConfigPaths] = None,
    app: Any = None,
) -> SaveResult:
    if not last_test_ok:
        return SaveResult(
            ok=False,
            message="Save blocked: run Test connection successfully before Save.",
        )
    resolved_paths = paths or resolve_config_paths()
    save_runtime_config(runtime, resolved_paths)
    write_docling_serve_yaml(runtime, paths=resolved_paths)
    preview = render_docling_serve_yaml(runtime, paths=resolved_paths)
    if app is not None:
        reload_gateway_state(app)
    message = (
        "Saved to config volume. Gateway reloaded. "
        f"{DOCLING_RESTART_HINT}"
    )
    logger.info(f"[IMP:9][handle_save_config][SAVE] ok=True [OK]")
    return SaveResult(ok=True, message=message, docling_preview=preview)


def handle_refresh_config_export(
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> tuple[str, str, str, str, str]:
    from doclingllm.gateway.admin.config_export import load_config_export_bundle

    bundle = load_config_export_bundle(paths, settings)
    return (
        bundle.paths_summary,
        bundle.runtime_yaml,
        bundle.docling_serve_yaml,
        bundle.models_template_yaml,
        bundle.effective_routing_yaml,
    )


def load_admin_runtime(
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> GatewayRuntimeConfig:
    resolved_paths = paths or resolve_config_paths()
    resolved_settings = settings or load_gateway_settings()
    from doclingllm.gateway.admin.config_store import ensure_runtime_config_seeded

    ensure_runtime_config_seeded(resolved_paths, resolved_settings)
    return load_runtime_config(resolved_paths, resolved_settings)


def masked_key_display(api_key: str) -> str:
    return mask_api_key(api_key) or "(empty)"
