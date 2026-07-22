# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): RoutingMerge; TECH(9): PyYAML]
## @purpose Merge gateway-runtime.yaml with gateway-models.template.yaml into RoutingTable.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: routing merge, runtime, template, load_merged_routing_table
# STRUCTURE: ▶ runtime+template → ⊕ env_map → ◇ stage overrides → ⎋ RoutingTable

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from doclingllm.gateway.admin.config_store import runtime_to_settings
from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig
from doclingllm.gateway.config import GatewaySettings
from doclingllm.gateway.routing import (
    RoutingTable,
    load_routing_table_from_dict,
    substitute_in_object,
)

logger = logging.getLogger(__name__)


def build_env_map_from_runtime(runtime: GatewayRuntimeConfig) -> dict[str, str]:
    vision = runtime.backends["vision"]
    text = runtime.backends["text"]
    return {
        "VISION_API_BASE_URL": vision.base_url,
        "VISION_API_KEY": vision.api_key,
        "VISION_MODEL": vision.model,
        "TEXT_API_BASE_URL": text.base_url,
        "TEXT_API_KEY": text.api_key,
        "TEXT_MODEL": text.model,
    }


def apply_stage_overrides(
    substituted: dict[str, Any],
    runtime: GatewayRuntimeConfig,
) -> dict[str, Any]:
    stages_raw = substituted.get("stages", {})
    if not isinstance(stages_raw, dict):
        return substituted
    for stage_name, override in runtime.stages.items():
        if stage_name not in stages_raw or not isinstance(stages_raw[stage_name], dict):
            continue
        stage_entry = dict(stages_raw[stage_name])
        stage_entry["endpoint"] = override.endpoint
        # BUG_FIX_CONTEXT: kserve_relay stages keep template model/relay_model names for KServe URL, not admin VLM model.
        if stage_entry.get("mode") != "kserve_relay":
            stage_entry["model"] = override.model
        stages_raw[stage_name] = stage_entry
    substituted["stages"] = stages_raw
    return substituted


def build_merged_routing_dict(
    runtime: GatewayRuntimeConfig,
    paths: Optional[ConfigPaths] = None,
) -> dict[str, Any]:
    resolved_paths = paths or resolve_config_paths()
    if not resolved_paths.models_template.is_file():
        raise FileNotFoundError(
            f"Models template not found: {resolved_paths.models_template}"
        )
    template = yaml.safe_load(
        resolved_paths.models_template.read_text(encoding="utf-8")
    )
    if not isinstance(template, dict):
        raise ValueError("gateway-models.template.yaml must be a mapping")
    env_map = build_env_map_from_runtime(runtime)
    substituted = substitute_in_object(template, env_map)
    return apply_stage_overrides(substituted, runtime)


def load_merged_routing_table(
    runtime: GatewayRuntimeConfig,
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> RoutingTable:
    resolved_paths = paths or resolve_config_paths()
    resolved_settings = settings or runtime_to_settings(runtime)
    substituted = build_merged_routing_dict(runtime, resolved_paths)
    table = load_routing_table_from_dict(
        substituted,
        resolved_settings,
        source_path=resolved_paths.models_template,
    )
    logger.info(
        f"[IMP:9][load_merged_routing_table][READY] "
        f"template={resolved_paths.models_template} stages={sorted(table.stages)} [OK]"
    )
    return table
