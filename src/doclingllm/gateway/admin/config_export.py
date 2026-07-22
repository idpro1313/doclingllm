# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): ConfigExport; TECH(9): PyYAML]
## @purpose Export runtime, generated, template, and effective merged configs for Admin UI and operators.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: config export, volume yaml, template, effective routing, admin copy
# STRUCTURE: ▶ paths → ◇ load runtime → ⊕ read/generate yaml → ⎋ ConfigExportBundle

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from doclingllm.gateway.admin.config_store import (
    ensure_runtime_config_seeded,
    load_runtime_config,
)
from doclingllm.gateway.admin.docling_generator import render_docling_serve_yaml
from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.routing_merge import build_merged_routing_dict
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigExportBundle:
    paths_summary: str
    runtime_yaml: str
    docling_serve_yaml: str
    models_template_yaml: str
    effective_routing_yaml: str


def _read_or_placeholder(path: Path, missing_label: str) -> str:
    if not path.is_file():
        return f"# {missing_label}: file not found at {path}\n"
    return path.read_text(encoding="utf-8")


def build_paths_summary(paths: ConfigPaths) -> str:
    lines = [
        "Текущие пути конфигурации (runtime):",
        f"- volume dir: {paths.config_dir}",
        f"- gateway-runtime.yaml: {paths.runtime_config}",
        f"- docling-serve.yaml: {paths.docling_serve_output}",
        f"- gateway-models.template.yaml (read-only): {paths.models_template}",
        "",
        "Docker (копирование на хост):",
        f"  docker cp doclingllm-gateway:{paths.runtime_config} ./gateway-runtime.yaml",
        f"  docker cp doclingllm-gateway:{paths.docling_serve_output} ./docling-serve.yaml",
        f"  docker cp doclingllm-gateway:{paths.models_template} ./gateway-models.template.yaml",
    ]
    return "\n".join(lines)


def load_config_export_bundle(
    paths: Optional[ConfigPaths] = None,
    settings: Optional[GatewaySettings] = None,
) -> ConfigExportBundle:
    resolved_paths = paths or resolve_config_paths()
    resolved_settings = settings or load_gateway_settings()
    ensure_runtime_config_seeded(resolved_paths, resolved_settings)
    runtime = load_runtime_config(resolved_paths, resolved_settings)

    runtime_yaml = _read_or_placeholder(
        resolved_paths.runtime_config,
        "gateway-runtime.yaml",
    )
    if resolved_paths.docling_serve_output.is_file():
        docling_serve_yaml = resolved_paths.docling_serve_output.read_text(encoding="utf-8")
    else:
        docling_serve_yaml = render_docling_serve_yaml(runtime, paths=resolved_paths)

    models_template_yaml = _read_or_placeholder(
        resolved_paths.models_template,
        "gateway-models.template.yaml",
    )
    merged = build_merged_routing_dict(runtime, resolved_paths)
    effective_routing_yaml = yaml.safe_dump(
        merged,
        sort_keys=False,
        allow_unicode=True,
    )
    header = (
        "# Effective routing = gateway-models.template.yaml + gateway-runtime.yaml "
        "(secrets resolved from runtime)\n"
    )
    effective_routing_yaml = header + effective_routing_yaml

    logger.info(
        f"[IMP:7][load_config_export_bundle][READY] "
        f"runtime={resolved_paths.runtime_config} docling={resolved_paths.docling_serve_output} [OK]"
    )
    return ConfigExportBundle(
        paths_summary=build_paths_summary(resolved_paths),
        runtime_yaml=runtime_yaml,
        docling_serve_yaml=docling_serve_yaml,
        models_template_yaml=models_template_yaml,
        effective_routing_yaml=effective_routing_yaml,
    )
