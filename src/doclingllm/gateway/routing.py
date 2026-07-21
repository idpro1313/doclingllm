# region MODULE_CONTRACT [DOMAIN(9): Routing; CONCEPT(9): StageMapping, YAMLConfig; TECH(9): PyYAML, pydantic]
## @modulecontract
## @purpose Map docling pipeline stages to resolved external API endpoints using declarative gateway-models.yaml and environment substitution.
## @scope YAML load, ${ENV} expansion, stage→endpoint/mode/model/parser resolution.
## @input Path to gateway-models.yaml, GatewaySettings env map.
## @output RoutingTable, StageRoute for each pipeline stage.
## @links [READS_DATA_FROM(9): deploy/config/gateway-models.yaml]
## @links [USES_API(8): doclingllm.gateway.config.GatewaySettings]
## @links_to_spec plans/Architecture.md L3 Adaptation
## @invariants
## - load_routing_table ALWAYS returns RoutingTable with at least one stage when YAML is valid.
## - resolve_stage_route raises KeyError for unknown stage names.
## - Resolved base_url NEVER contains unresolved ${PLACEHOLDER} tokens.
## @rationale
## Q: Why separate routing from config.py?
## A: L3 Adaptation layer must not depend on pydantic-settings directly; tests inject YAML via tmp_path.
## @changes
## LAST_CHANGE: [v0.2.0 Slice S1 – RoutingTable, YAML loader, stage resolver.]
## @modulemap
## FUNC 10[Load YAML routing table] => load_routing_table
## FUNC 9[Resolve stage to outbound route] => resolve_stage_route
## CLASS 8[Loaded routing configuration] => RoutingTable
## CLASS 8[Resolved route for one stage] => StageRoute
## @usecases
## - [resolve_stage_route]: KServe handler → LookupStage → OutboundUrlAndAuth
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: routing, stage, gateway-models, yaml, endpoint, vision, text, parser, openai_vision
# STRUCTURE: ▶ YAML ┌substitute env┐ → ◇ parse → ⊕ RoutingTable → ◇ stage lookup → ⎋ StageRoute

import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from doclingllm.gateway.config import GatewaySettings

logger = logging.getLogger(__name__)

_ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

KNOWN_STAGE_NAMES = frozenset(
    {
        "ocr",
        "layout",
        "table",
        "picture_classification",
        "picture_description",
        "vlm",
        "code_formula",
    }
)

KNOWN_MODES = frozenset({"openai_vision", "openai_proxy", "openai_text"})


# region CLASS_EndpointConfig [DOMAIN(8): Routing; CONCEPT(8): Endpoint; TECH(8): pydantic]
## @purpose Describe one named backend (vision or text) after env substitution.
class EndpointConfig(BaseModel):
    name: str
    base_url: str
    api_key_env: Optional[str] = None
    default_model: str = ""

    @field_validator("base_url")
    @classmethod
    def validate_no_unresolved_placeholders(cls, value: str) -> str:
        if _ENV_PLACEHOLDER_PATTERN.search(value):
            raise ValueError(f"Unresolved env placeholder in base_url: {value}")
        return value.rstrip("/")


# endregion CLASS_EndpointConfig


# region CLASS_StageConfig [DOMAIN(8): Routing; CONCEPT(8): Stage; TECH(8): pydantic]
## @purpose Hold raw stage definition from gateway-models.yaml before endpoint resolution.
class StageConfig(BaseModel):
    name: str
    endpoint: str
    mode: str
    model: str
    path: str = "/chat/completions"
    response_parser: Optional[str] = None
    system_prompt: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in KNOWN_MODES:
            raise ValueError(f"Unknown routing mode: {value}. Expected one of {sorted(KNOWN_MODES)}")
        return value


# endregion CLASS_StageConfig


# region CLASS_StageRoute [DOMAIN(9): Routing; CONCEPT(9): ResolvedRoute; TECH(8): pydantic]
## @purpose Provide fully resolved outbound call parameters for a docling pipeline stage.
class StageRoute(BaseModel):
    stage: str
    mode: str
    model: str
    base_url: str
    request_path: str
    request_url: str
    api_key: str = ""
    response_parser: Optional[str] = None
    system_prompt: Optional[str] = None
    endpoint_name: str = ""


# endregion CLASS_StageRoute


# region CLASS_RoutingTable [DOMAIN(9): Routing; CONCEPT(9): RoutingTable; TECH(8): pydantic]
## @purpose Aggregate endpoints and stages loaded from gateway-models.yaml.
class RoutingTable(BaseModel):
    endpoints: dict[str, EndpointConfig] = Field(default_factory=dict)
    stages: dict[str, StageConfig] = Field(default_factory=dict)
    source_path: Optional[Path] = None


# endregion CLASS_RoutingTable


# region FUNC_substitute_env_placeholders [DOMAIN(7): Routing; CONCEPT(7): Template; TECH(7): regex]
## @purpose Replace ${VAR} tokens in YAML string values using settings and os.environ.
## @io str + env map -> str
## @complexity 4
def substitute_env_placeholders(value: str, env_map: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        resolved = env_map.get(key, "")
        if not resolved:
            logger.debug(
                f"[IMP:3][substitute_env_placeholders][MISS] No value for placeholder {key} [TRACE]"
            )
        return resolved

    return _ENV_PLACEHOLDER_PATTERN.sub(replacer, value)


# endregion FUNC_substitute_env_placeholders


# region FUNC_substitute_in_object [DOMAIN(7): Routing; CONCEPT(7): Recursion; TECH(7): yaml]
## @purpose Recursively apply env substitution to all string leaves in parsed YAML structure.
## @complexity 5
def substitute_in_object(node: Any, env_map: dict[str, str]) -> Any:
    if isinstance(node, str):
        return substitute_env_placeholders(node, env_map)
    if isinstance(node, dict):
        return {key: substitute_in_object(val, env_map) for key, val in node.items()}
    if isinstance(node, list):
        return [substitute_in_object(item, env_map) for item in node]
    return node


# endregion FUNC_substitute_in_object


# region FUNC_load_routing_table [DOMAIN(9): Routing; CONCEPT(9): YAMLLoad; TECH(9): PyYAML]
## @purpose Load and validate gateway-models.yaml into a RoutingTable ready for stage resolution.
## @uses GatewaySettings, substitute_in_object
## @io Path + GatewaySettings -> RoutingTable
## @complexity 6
def load_routing_table(
    config_path: Path,
    settings: GatewaySettings,
) -> RoutingTable:
    if not config_path.is_file():
        logger.critical(
            f"[IMP:10][load_routing_table][MISSING] Config file not found: {config_path} [FATAL]"
        )
        raise FileNotFoundError(f"Routing config not found: {config_path}")

    raw_text = config_path.read_text(encoding="utf-8")
    env_map = settings.env_substitution_map()
    parsed = yaml.safe_load(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Routing config must be a YAML mapping, got {type(parsed).__name__}")

    substituted = substitute_in_object(parsed, env_map)
    endpoints_raw = substituted.get("endpoints", {})
    stages_raw = substituted.get("stages", {})

    endpoints: dict[str, EndpointConfig] = {}
    for name, data in endpoints_raw.items():
        if not isinstance(data, dict):
            raise ValueError(f"Endpoint {name} must be a mapping")
        endpoints[name] = EndpointConfig(name=name, **data)

    stages: dict[str, StageConfig] = {}
    for name, data in stages_raw.items():
        if not isinstance(data, dict):
            raise ValueError(f"Stage {name} must be a mapping")
        stages[name] = StageConfig(name=name, **data)

    table = RoutingTable(
        endpoints=endpoints,
        stages=stages,
        source_path=config_path,
    )
    logger.info(
        f"[IMP:7][load_routing_table][LOAD] "
        f"path={config_path} endpoints={len(endpoints)} stages={len(stages)} [CONFIG]"
    )
    logger.info(
        f"[IMP:9][load_routing_table][READY] Routing table loaded for stages: {sorted(stages.keys())} [OK]"
    )
    return table


# endregion FUNC_load_routing_table


# region FUNC_resolve_stage_route [DOMAIN(9): Routing; CONCEPT(9): Resolver; TECH(8): pydantic]
## @purpose Resolve a pipeline stage name into outbound URL, model, auth, and parser for the HTTP client layer.
## @uses RoutingTable, GatewaySettings
## @io str + RoutingTable + GatewaySettings -> StageRoute
## @complexity 5
def resolve_stage_route(
    stage: str,
    table: RoutingTable,
    settings: GatewaySettings,
) -> StageRoute:
    if stage not in table.stages:
        logger.critical(
            f"[IMP:10][resolve_stage_route][UNKNOWN] Stage not configured: {stage} [FATAL]"
        )
        raise KeyError(f"Unknown pipeline stage: {stage}")

    stage_cfg = table.stages[stage]
    if stage_cfg.endpoint not in table.endpoints:
        raise KeyError(
            f"Stage {stage} references unknown endpoint: {stage_cfg.endpoint}"
        )

    endpoint_cfg = table.endpoints[stage_cfg.endpoint]
    path = stage_cfg.path if stage_cfg.path.startswith("/") else f"/{stage_cfg.path}"
    request_url = f"{endpoint_cfg.base_url}{path}"
    api_key = settings.resolve_api_key(endpoint_cfg.api_key_env)
    model = stage_cfg.model or endpoint_cfg.default_model

    route = StageRoute(
        stage=stage,
        mode=stage_cfg.mode,
        model=model,
        base_url=endpoint_cfg.base_url,
        request_path=path,
        request_url=request_url,
        api_key=api_key,
        response_parser=stage_cfg.response_parser,
        system_prompt=stage_cfg.system_prompt,
        endpoint_name=stage_cfg.endpoint,
    )
    logger.info(
        f"[IMP:8][resolve_stage_route][RESOLVE] stage={stage} endpoint={endpoint_cfg.name} "
        f"mode={route.mode} model={route.model} url={route.request_url} [ROUTE]"
    )
    return route


# endregion FUNC_resolve_stage_route
