# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): DoclingGenerator; TECH(8): PyYAML]
## @purpose Generate docling-serve.yaml on config volume from runtime settings.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: docling generator, docling-serve.yaml, presets, model-gateway
# STRUCTURE: ▶ runtime → ⊕ preset dict → ⚡ yaml dump → ⎋ volume path

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from doclingllm.gateway.admin.paths import ConfigPaths, resolve_config_paths
from doclingllm.gateway.admin.runtime_models import GatewayRuntimeConfig

logger = logging.getLogger(__name__)

GATEWAY_BASE = "http://model-gateway:8080"
DOCLING_RESTART_HINT = (
    "Перезапустите docling-serve вручную: "
    "docker compose -f deploy/docker-compose.yml restart docling-serve"
)


def build_docling_serve_document(
    runtime: GatewayRuntimeConfig,
    gateway_base: str = GATEWAY_BASE,
) -> dict[str, Any]:
    text_model = runtime.backends["text"].model
    openai_url = f"{gateway_base}/v1/chat/completions"
    remote_vlm = {
        "engine_options": {
            "engine_type": "api",
            "url": openai_url,
            "params": {"model": "remote-vision"},
            "timeout": float(runtime.gateway.request_timeout),
            "concurrency": 1,
        },
        "model_spec": {
            "name": "Remote-Vision-VLM",
            "default_repo_id": "remote-vision",
            "prompt": "Convert this page to docling.",
            "response_format": "markdown",
        },
    }
    remote_pic_desc = {
        "engine_options": {
            "engine_type": "api",
            "url": openai_url,
            "params": {"model": "remote-vision"},
            "timeout": float(runtime.gateway.request_timeout),
            "concurrency": 1,
        },
        "model_spec": {
            "name": "Remote-Vision-PictureDesc",
            "default_repo_id": "remote-vision",
            "prompt": "Describe this picture from a document. Be concise and accurate.",
            "response_format": "plain",
        },
        "prompt": "Describe this picture from a document. Be concise and accurate.",
    }
    return {
        "enable_remote_services": True,
        "load_models_at_boot": False,
        "log_format": "json",
        "default_ocr_kind": "kserve_v2_ocr",
        "default_ocr_preset": "remote_ocr",
        "custom_ocr_presets": {
            "auto": {
                "kind": "kserve_v2_ocr",
                "url": gateway_base,
                "transport": "http",
                "model_name": "ocr",
                "timeout": float(runtime.gateway.request_timeout),
            },
            "remote_ocr": {
                "kind": "kserve_v2_ocr",
                "url": gateway_base,
                "transport": "http",
                "model_name": "ocr",
                "timeout": float(runtime.gateway.request_timeout),
            },
        },
        "default_layout_kind": "layout_object_detection",
        "default_layout_preset": "remote_layout",
        "custom_layout_presets": {
            "default": {
                "kind": "layout_object_detection",
                "engine_options": {
                    "engine_type": "api_kserve_v2",
                    "url": gateway_base,
                    "transport": "http",
                    "model_name": "layout",
                    "timeout": 180.0,
                },
            },
            "remote_layout": {
                "kind": "layout_object_detection",
                "engine_options": {
                    "engine_type": "api_kserve_v2",
                    "url": gateway_base,
                    "transport": "http",
                    "model_name": "layout",
                    "timeout": 180.0,
                },
            },
        },
        "default_table_structure_preset": "tableformer_v1_accurate",
        "default_picture_classification_preset": "remote_pic_class",
        "custom_picture_classification_presets": {
            "default": {
                "engine_options": {
                    "engine_type": "api_kserve_v2",
                    "url": gateway_base,
                    "transport": "http",
                    "model_name": "picture_classifier",
                    "timeout": 180.0,
                },
                "model_spec": {
                    "name": "document_figure_classifier_v2_5",
                    "repo_id": "docling-project/DocumentFigureClassifier-v2.5",
                },
            },
            "remote_pic_class": {
                "engine_options": {
                    "engine_type": "api_kserve_v2",
                    "url": gateway_base,
                    "transport": "http",
                    "model_name": "picture_classifier",
                    "timeout": 180.0,
                },
                "model_spec": {
                    "name": "document_figure_classifier_v2_5",
                    "repo_id": "docling-project/DocumentFigureClassifier-v2.5",
                },
            },
        },
        "default_vlm_preset": "remote_vlm",
        "allowed_vlm_engines": ["api"],
        "custom_vlm_presets": {
            "remote_vlm": remote_vlm,
            "default": remote_vlm,
            "granite_docling": remote_vlm,
        },
        "default_picture_description_preset": "remote_pic_desc",
        "custom_picture_description_presets": {
            "default": remote_pic_desc,
            "remote_pic_desc": remote_pic_desc,
            "smolvlm": remote_pic_desc,
        },
        "default_code_formula_preset": "remote_code_formula",
        "custom_code_formula_presets": {
            "remote_code_formula": {
                "engine_options": {
                    "engine_type": "api",
                    "url": openai_url,
                    "params": {"model": text_model},
                    "timeout": 120.0,
                    "concurrency": 1,
                },
                "model_spec": {
                    "name": "Minimax-CodeFormula",
                    "default_repo_id": text_model,
                    "prompt": "Transcribe the code or mathematical formula accurately.",
                    "response_format": "plain",
                },
            }
        },
        "allowed_vlm_presets": ["remote_vlm", "default", "granite_docling"],
        "allowed_picture_description_presets": [
            "remote_pic_desc",
            "default",
            "smolvlm",
        ],
        "allowed_code_formula_presets": ["remote_code_formula"],
    }


def render_docling_serve_yaml(
    runtime: GatewayRuntimeConfig,
    paths: Optional[ConfigPaths] = None,
    gateway_base: str = GATEWAY_BASE,
) -> str:
    document = build_docling_serve_document(runtime, gateway_base=gateway_base)
    header = (
        "# Generated by doclingllm gateway admin — do not edit manually.\n"
        f"# {DOCLING_RESTART_HINT}\n"
    )
    return header + yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def write_docling_serve_yaml(
    runtime: GatewayRuntimeConfig,
    paths: Optional[ConfigPaths] = None,
    gateway_base: str = GATEWAY_BASE,
) -> Path:
    resolved_paths = paths or resolve_config_paths()
    resolved_paths.config_dir.mkdir(parents=True, exist_ok=True)
    text = render_docling_serve_yaml(runtime, paths=resolved_paths, gateway_base=gateway_base)
    resolved_paths.docling_serve_output.write_text(text, encoding="utf-8")
    logger.info(
        f"[IMP:9][write_docling_serve_yaml][WRITE] path={resolved_paths.docling_serve_output} [OK]"
    )
    return resolved_paths.docling_serve_output
