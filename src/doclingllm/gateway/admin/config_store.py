# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): ConfigStore; TECH(9): PyYAML, pydantic]
## @purpose Read/write gateway-runtime.yaml on volume with seed, env fallback, atomic save.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: config_store, gateway-runtime, seed, env fallback, atomic write, volume
# STRUCTURE: ▶ paths → ◇ exists? seed : load → ⊕ env fallback → ⎋ GatewayRuntimeConfig

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import yaml

from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.runtime_models import (
    BackendConfig,
    GatewayRuntimeConfig,
    GatewaySection,
    ProxySection,
    mask_api_key,
)
from doclingllm.gateway.config import GatewaySettings

logger = logging.getLogger(__name__)


def apply_env_fallback(
    config: GatewayRuntimeConfig,
    settings: GatewaySettings,
) -> GatewayRuntimeConfig:
    vision = config.backends.get("vision")
    text = config.backends.get("text")
    kserve_native = config.backends.get("kserve_native")
    vision_data = (vision.model_dump() if vision else {}).copy()
    text_data = (text.model_dump() if text else {}).copy()
    kserve_data = (kserve_native.model_dump() if kserve_native else {}).copy()
    if not vision_data.get("base_url"):
        vision_data["base_url"] = settings.vision_api_base_url
    if not vision_data.get("api_key"):
        vision_data["api_key"] = settings.vision_api_key
    if not vision_data.get("model"):
        vision_data["model"] = settings.vision_model
    if not text_data.get("base_url"):
        text_data["base_url"] = settings.text_api_base_url
    if not text_data.get("api_key"):
        text_data["api_key"] = settings.text_api_key
    if not text_data.get("model"):
        text_data["model"] = settings.text_model
    if kserve_native is None:
        kserve_data = {"base_url": "", "api_key": "", "model": ""}
    gateway = config.gateway.model_dump()
    if not config.gateway.request_timeout:
        gateway["request_timeout"] = settings.gateway_request_timeout
    if not config.gateway.log_level:
        gateway["log_level"] = settings.gateway_log_level
    proxy = config.proxy.model_dump()
    for key, env_name in (
        ("http_proxy", "HTTP_PROXY"),
        ("https_proxy", "HTTPS_PROXY"),
        ("no_proxy", "NO_PROXY"),
    ):
        if not proxy.get(key):
            proxy[key] = os.environ.get(env_name, "")
    gateway_section = config.gateway.model_copy(update=gateway)
    proxy_section = config.proxy.model_copy(update=proxy)
    merged = config.model_copy(
        update={
            "backends": {
                "vision": BackendConfig(**vision_data),
                "text": BackendConfig(**text_data),
                "kserve_native": BackendConfig(**kserve_data),
            },
            "gateway": gateway_section,
            "proxy": proxy_section,
        }
    )
    return merged.with_default_stages(
        vision_model=merged.backends["vision"].model,
        text_model=merged.backends["text"].model,
    )


def load_runtime_config(
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> GatewayRuntimeConfig:
    from doclingllm.gateway.config import load_gateway_settings

    resolved_paths = paths or resolve_config_paths()
    resolved_settings = settings or load_gateway_settings()
    if not resolved_paths.runtime_config.is_file():
        raise FileNotFoundError(
            f"Runtime config not found: {resolved_paths.runtime_config}. "
            "Call ensure_runtime_config_seeded first."
        )
    raw = yaml.safe_load(resolved_paths.runtime_config.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("gateway-runtime.yaml must be a mapping")
    config = GatewayRuntimeConfig.model_validate(raw)
    config = apply_env_fallback(config, resolved_settings)
    logger.info(
        f"[IMP:7][load_runtime_config][LOAD] path={resolved_paths.runtime_config} "
        f"vision_model={config.backends['vision'].model} [CONFIG]"
    )
    return config


def save_runtime_config(
    config: GatewayRuntimeConfig,
    paths: Optional[ConfigPaths] = None,
) -> Path:
    resolved_paths = paths or resolve_config_paths()
    resolved_paths.config_dir.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json")
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    target = resolved_paths.runtime_config
    fd, tmp_name = tempfile.mkstemp(
        dir=str(resolved_paths.config_dir),
        prefix=".gateway-runtime-",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        os.close(fd)
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    logger.info(
        f"[IMP:9][save_runtime_config][SAVE] path={target} "
        f"vision_key={mask_api_key(config.backends['vision'].api_key)} [OK]"
    )
    return target


def ensure_runtime_config_seeded(
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> GatewayRuntimeConfig:
    from doclingllm.gateway.config import load_gateway_settings

    resolved_paths = paths or resolve_config_paths()
    resolved_settings = settings or load_gateway_settings()
    resolved_paths.config_dir.mkdir(parents=True, exist_ok=True)
    if resolved_paths.runtime_config.is_file():
        logger.info(
            f"[IMP:7][ensure_runtime_config_seeded][EXISTING] "
            f"path={resolved_paths.runtime_config} [SKIP]"
        )
        return load_runtime_config(resolved_paths, resolved_settings)
    if not resolved_paths.runtime_defaults.is_file():
        raise FileNotFoundError(
            f"Runtime defaults missing: {resolved_paths.runtime_defaults}"
        )
    raw = yaml.safe_load(
        resolved_paths.runtime_defaults.read_text(encoding="utf-8")
    )
    config = GatewayRuntimeConfig.model_validate(raw)
    config = apply_env_fallback(config, resolved_settings)
    save_runtime_config(config, resolved_paths)
    logger.info(
        f"[IMP:9][ensure_runtime_config_seeded][SEED] Created {resolved_paths.runtime_config} [OK]"
    )
    return config


def runtime_to_settings(
    runtime: GatewayRuntimeConfig,
    base: Optional[GatewaySettings] = None,
) -> GatewaySettings:
    from doclingllm.gateway.config import load_gateway_settings

    seed = base or load_gateway_settings()
    return seed.model_copy(
        update={
            "vision_api_base_url": runtime.backends["vision"].base_url,
            "vision_api_key": runtime.backends["vision"].api_key,
            "vision_model": runtime.backends["vision"].model,
            "text_api_base_url": runtime.backends["text"].base_url,
            "text_api_key": runtime.backends["text"].api_key,
            "text_model": runtime.backends["text"].model,
            "kserve_native_api_base_url": runtime.backends.get(
                "kserve_native", BackendConfig()
            ).base_url,
            "kserve_native_api_key": runtime.backends.get(
                "kserve_native", BackendConfig()
            ).api_key,
            "gateway_request_timeout": runtime.gateway.request_timeout,
            "gateway_log_level": runtime.gateway.log_level,
        }
    )


def apply_proxy_env(runtime: GatewayRuntimeConfig) -> None:
    mapping = {
        "HTTP_PROXY": runtime.proxy.http_proxy,
        "HTTPS_PROXY": runtime.proxy.https_proxy,
        "NO_PROXY": runtime.proxy.no_proxy,
    }
    for key, value in mapping.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
