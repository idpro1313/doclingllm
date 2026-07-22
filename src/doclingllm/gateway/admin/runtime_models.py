# region MODULE_CONTRACT [DOMAIN(8): Admin; CONCEPT(9): RuntimeConfig; TECH(8): pydantic]
## @purpose Pydantic schema for gateway-runtime.yaml persisted on Docker volume.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: GatewayRuntimeConfig, backends, stages, proxy, meta, volume yaml
# STRUCTURE: ▶ YAML → ◇ validate GatewayRuntimeConfig → ⎋ merge with template

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from doclingllm.gateway.routing import KNOWN_MODES, KNOWN_STAGE_NAMES

DEFAULT_STAGE_ENDPOINTS: dict[str, str] = {
    "ocr": "vision",
    "layout": "vision",
    "table": "vision",
    "picture_classification": "vision",
    "picture_description": "vision",
    "vlm": "vision",
    "code_formula": "text",
}

DEFAULT_STAGE_MODES: dict[str, str] = {
    "ocr": "openai_vision",
    "layout": "openai_vision",
    "table": "openai_vision",
    "picture_classification": "openai_vision",
    "picture_description": "openai_vision",
    "vlm": "openai_proxy",
    "code_formula": "openai_text",
}

KNOWN_RUNTIME_ENDPOINTS = frozenset({"vision", "text", "kserve_native"})


class BackendConfig(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")


class StageOverride(BaseModel):
    endpoint: str
    model: str
    mode: str = ""
    relay_model: str = ""

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        if value not in KNOWN_RUNTIME_ENDPOINTS:
            raise ValueError(
                f"Stage endpoint must be one of {sorted(KNOWN_RUNTIME_ENDPOINTS)}, got {value!r}"
            )
        return value

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value and value not in KNOWN_MODES:
            raise ValueError(f"Unknown routing mode: {value}. Expected one of {sorted(KNOWN_MODES)}")
        return value

    def resolved_mode(self, stage_name: str) -> str:
        if self.mode:
            return self.mode
        return DEFAULT_STAGE_MODES.get(stage_name, "openai_vision")


class GatewaySection(BaseModel):
    request_timeout: float = 300.0
    log_level: str = "INFO"


class ProxySection(BaseModel):
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1,model-gateway,docling-serve"


class MetaSection(BaseModel):
    last_test_at: Optional[str] = None
    last_test_ok: bool = False


class GatewayRuntimeConfig(BaseModel):
    version: str = "1"
    backends: dict[str, BackendConfig] = Field(
        default_factory=lambda: {
            "vision": BackendConfig(),
            "text": BackendConfig(),
            "kserve_native": BackendConfig(),
        }
    )
    gateway: GatewaySection = Field(default_factory=GatewaySection)
    proxy: ProxySection = Field(default_factory=ProxySection)
    stages: dict[str, StageOverride] = Field(default_factory=dict)
    meta: MetaSection = Field(default_factory=MetaSection)

    def with_default_stages(self, vision_model: str, text_model: str) -> "GatewayRuntimeConfig":
        stages = dict(self.stages)
        for stage_name in KNOWN_STAGE_NAMES:
            if stage_name not in stages:
                endpoint = DEFAULT_STAGE_ENDPOINTS[stage_name]
                mode = DEFAULT_STAGE_MODES.get(stage_name, "openai_vision")
                if mode == "kserve_relay":
                    model = stage_name
                    endpoint = "kserve_native"
                else:
                    model = text_model if endpoint == "text" else vision_model
                stages[stage_name] = StageOverride(
                    endpoint=endpoint,
                    model=model,
                    mode=mode,
                    relay_model="",
                )
            else:
                existing = stages[stage_name]
                mode = existing.resolved_mode(stage_name)
                stages[stage_name] = existing.model_copy(
                    update={"mode": mode},
                )
        return self.model_copy(update={"stages": stages})

    def mark_test_result(self, ok: bool) -> "GatewayRuntimeConfig":
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        meta = self.meta.model_copy(update={"last_test_at": now, "last_test_ok": ok})
        return self.model_copy(update={"meta": meta})


def mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"{value[:3]}…{value[-4:]}"
