# region MODULE_CONTRACT [DOMAIN(8): Admin; CONCEPT(8): ConfigPaths; TECH(8): pathlib]
## @purpose Resolve admin config file paths from environment for Docker volume and tests.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: ConfigPaths, DOCLINGLLM_CONFIG_DIR, volume, gateway-runtime, templates
# STRUCTURE: ▶ env ┌ConfigPaths┐ → ⎋ runtime_yaml + docling_yaml + template paths

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfigPaths:
    config_dir: Path
    runtime_config: Path
    docling_serve_output: Path
    models_template: Path
    runtime_defaults: Path


def resolve_config_paths() -> ConfigPaths:
    repo_root = Path(__file__).resolve().parents[4]
    config_dir = Path(
        os.environ.get("DOCLINGLLM_CONFIG_DIR", "/data/doclingllm/config")
    )
    runtime_config = Path(
        os.environ.get(
            "GATEWAY_RUNTIME_CONFIG",
            str(config_dir / "gateway-runtime.yaml"),
        )
    )
    docling_serve_output = config_dir / "docling-serve.yaml"
    models_template = Path(
        os.environ.get(
            "GATEWAY_MODELS_TEMPLATE",
            str(repo_root / "deploy" / "config" / "gateway-models.template.yaml"),
        )
    )
    runtime_defaults = Path(
        os.environ.get(
            "GATEWAY_RUNTIME_DEFAULTS",
            str(repo_root / "deploy" / "config" / "gateway-runtime.defaults.yaml"),
        )
    )
    return ConfigPaths(
        config_dir=config_dir,
        runtime_config=runtime_config,
        docling_serve_output=docling_serve_output,
        models_template=models_template,
        runtime_defaults=runtime_defaults,
    )
