# region MODULE_CONTRACT [DOMAIN(8): Configuration; CONCEPT(9): Settings, EnvSecrets; TECH(9): pydantic-settings]
## @modulecontract
## @purpose Provide typed, validated gateway configuration from environment variables with safe defaults for local development and Docker deployment.
## @scope Gateway bind host/port, external API URLs, model names, routing YAML path, HTTP timeouts.
## @input Process environment variables and optional .env file.
## @output GatewaySettings instance and load_gateway_settings factory.
## @links [USES_API(8): pydantic_settings.BaseSettings]
## @links_to_spec plans/Architecture.md L4 Integration
## @invariants
## - load_gateway_settings ALWAYS returns GatewaySettings.
## - vision_api_base_url and text_api_base_url MUST be non-empty after load.
## - gateway_models_config_path MUST exist when load_routing_table is called (routing module).
## @rationale
## Q: Why pydantic-settings instead of raw os.environ?
## A: Typed validation catches misconfiguration at startup before docling-serve receives bad routes.
## @changes
## LAST_CHANGE: [v0.3.1 – GATEWAY_UPSTREAM_RETRIES for transport retry on timeout.]
## @modulemap
## FUNC 10[Load validated settings from env] => load_gateway_settings
## CLASS 9[Gateway configuration model] => GatewaySettings
## @usecases
## - [load_gateway_settings]: Gateway (Startup) → ReadEnv → ValidatedSettingsReady
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: gateway settings, env, VISION_API, TEXT_API, pydantic, configuration, secrets, timeout
# STRUCTURE: ▶ os.environ ┌GatewaySettings┐ → ◇ validate → ⎋ GatewaySettings

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_MODELS_YAML = Path("deploy/config/gateway-models.yaml")


# region CLASS_GatewaySettings [DOMAIN(8): Configuration; CONCEPT(9): Settings; TECH(9): pydantic]
## @purpose Hold all gateway runtime parameters in one validated object for injection into routing and HTTP client layers.
class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vision_api_base_url: str = Field(
        default="https://ai-billing.develonica.group/v1",
        alias="VISION_API_BASE_URL",
    )
    vision_api_key: str = Field(default="", alias="VISION_API_KEY")
    vision_model: str = Field(
        default="qwen3.6-35b-a3b",
        alias="VISION_MODEL",
    )

    text_api_base_url: str = Field(
        default="http://192.168.101.15:8111/v1",
        alias="TEXT_API_BASE_URL",
    )
    text_api_key: str = Field(default="", alias="TEXT_API_KEY")
    text_model: str = Field(default="minimax-m2.7", alias="TEXT_MODEL")

    gateway_host: str = Field(default="0.0.0.0", alias="GATEWAY_HOST")
    gateway_port: int = Field(default=8080, alias="GATEWAY_PORT")
    gateway_request_timeout: float = Field(default=300.0, alias="GATEWAY_REQUEST_TIMEOUT")
    gateway_upstream_retries: int = Field(default=1, alias="GATEWAY_UPSTREAM_RETRIES")
    gateway_log_level: str = Field(default="INFO", alias="GATEWAY_LOG_LEVEL")

    gateway_models_config_path: Path = Field(
        default=_DEFAULT_MODELS_YAML,
        alias="GATEWAY_MODELS_CONFIG_PATH",
    )

    @field_validator("vision_api_base_url", "text_api_base_url")
    @classmethod
    def strip_trailing_slash_from_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("gateway_models_config_path", mode="before")
    @classmethod
    def coerce_path(cls, value: object) -> Path:
        if isinstance(value, Path):
            return value
        return Path(str(value))

    def env_substitution_map(self) -> dict[str, str]:
        """Return placeholder map for gateway-models.yaml ${VAR} expansion."""
        return {
            "VISION_API_BASE_URL": self.vision_api_base_url,
            "VISION_API_KEY": self.vision_api_key,
            "VISION_MODEL": self.vision_model,
            "TEXT_API_BASE_URL": self.text_api_base_url,
            "TEXT_API_KEY": self.text_api_key,
            "TEXT_MODEL": self.text_model,
        }

    def resolve_api_key(self, api_key_env_name: Optional[str]) -> str:
        """Resolve API key from settings field referenced by api_key_env in YAML."""
        if not api_key_env_name:
            return ""
        env_value = os.environ.get(api_key_env_name, "")
        if env_value:
            return env_value
        field_map = {
            "VISION_API_KEY": self.vision_api_key,
            "TEXT_API_KEY": self.text_api_key,
        }
        return field_map.get(api_key_env_name, "")


# endregion CLASS_GatewaySettings


# region FUNC_load_gateway_settings [DOMAIN(8): Configuration; CONCEPT(8): Factory; TECH(8): pydantic-settings]
## @purpose Enable gateway startup and tests to obtain a cached, validated settings snapshot from the current environment.
## @uses GatewaySettings
## @io Optional env overrides -> GatewaySettings
## @complexity 3
@lru_cache(maxsize=1)
def load_gateway_settings() -> GatewaySettings:
    settings = GatewaySettings()
    logger.info(
        f"[IMP:7][load_gateway_settings][LOAD] "
        f"vision_base={settings.vision_api_base_url} text_base={settings.text_api_base_url} "
        f"models_yaml={settings.gateway_models_config_path} [CONFIG]"
    )
    logger.info(
        f"[IMP:9][load_gateway_settings][READY] Gateway settings validated for remote inference routing [OK]"
    )
    return settings


# endregion FUNC_load_gateway_settings
