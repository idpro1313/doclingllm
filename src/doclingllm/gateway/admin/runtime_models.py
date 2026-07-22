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

from doclingllm.gateway.routing import KNOWN_STAGE_NAMES

DEFAULT_STAGE_ENDPOINTS: dict[str, str] = {
    "ocr": "vision",
    "layout": "vision",
    "table": "vision",
    "picture_classification": "vision",
    "picture_description": "vision",
    "vlm": "vision",
    "code_formula": "text",
}


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

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        if value not in {"vision", "text"}:
            raise ValueError(f"Stage endpoint must be vision or text, got {value!r}")
        return value


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
                model = text_model if endpoint == "text" else vision_model
                stages[stage_name] = StageOverride(endpoint=endpoint, model=model)
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
