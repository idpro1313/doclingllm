# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): GradioUI; TECH(9): gradio]
## @purpose Build Gradio Blocks admin UI mounted at /admin on gateway FastAPI app.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: gradio admin UI, /admin, gateway settings form, kserve_relay, stage mode
# STRUCTURE: ▶ Blocks tabs → ◇ handlers → ⊕ test state → Save gated

import logging
from typing import Any, Optional

import gradio as gr
from pydantic import ValidationError

from doclingllm.gateway.admin.gradio_handlers import (
    STAGE_ENDPOINT_CHOICES,
    STAGE_MODE_CHOICES,
    form_to_runtime,
    handle_refresh_config_export,
    handle_save_config,
    handle_test_connection,
    load_admin_runtime,
    parse_stage_inputs_from_form_tail,
    runtime_to_form,
    sync_stage_models_from_backends,
)
from doclingllm.gateway.routing import KNOWN_STAGE_NAMES

logger = logging.getLogger(__name__)

DEV_WARNING = (
    "**Dev-only admin UI (no auth).** Settings persist on Docker volume `doclingllm-config`, "
    "not in the project folder. Run **Test connection** before **Save**."
)


def build_admin_blocks(app: Any) -> gr.Blocks:
    runtime = load_admin_runtime()
    form = runtime_to_form(runtime)
    stage_names = sorted(KNOWN_STAGE_NAMES)

    with gr.Blocks(title="doclingllm Gateway Admin") as blocks:
        gr.Markdown(DEV_WARNING)
        test_ok_state = gr.State(value=form["last_test_ok"])
        runtime_state = gr.State(value=runtime)

        with gr.Tab("Vision"):
            vision_base_url = gr.Textbox(label="Base URL", value=form["vision_base_url"])
            vision_api_key = gr.Textbox(
                label="API Key",
                value=form["vision_api_key"],
                type="password",
            )
            vision_model = gr.Textbox(label="Model", value=form["vision_model"])

        with gr.Tab("Text"):
            text_base_url = gr.Textbox(label="Base URL", value=form["text_base_url"])
            text_api_key = gr.Textbox(
                label="API Key",
                value=form["text_api_key"],
                type="password",
            )
            text_model = gr.Textbox(label="Model", value=form["text_model"])

        with gr.Tab("KServe Native"):
            kserve_native_base_url = gr.Textbox(
                label="Base URL",
                value=form["kserve_native_base_url"],
                placeholder="http://triton:8000",
            )
            kserve_native_api_key = gr.Textbox(
                label="API Key (optional)",
                value=form["kserve_native_api_key"],
                type="password",
            )
            gr.Markdown(
                "Backend для **kserve_relay**: byte-for-byte passthrough "
                "`/v2/models/{relay_model}/infer`. Заполните URL перед включением relay на стадиях."
            )

        with gr.Tab("Stages"):
            stage_mode_inputs = []
            stage_endpoint_inputs = []
            stage_model_inputs = []
            stage_relay_model_inputs = []
            for stage in stage_names:
                with gr.Row():
                    stage_mode_inputs.append(
                        gr.Dropdown(
                            choices=STAGE_MODE_CHOICES,
                            value=form["stage_modes"].get(stage, "openai_vision"),
                            label=f"{stage} mode",
                        )
                    )
                    stage_endpoint_inputs.append(
                        gr.Dropdown(
                            choices=STAGE_ENDPOINT_CHOICES,
                            value=form["stage_endpoints"].get(stage, "vision"),
                            label=f"{stage} endpoint",
                        )
                    )
                    stage_model_inputs.append(
                        gr.Textbox(
                            label=f"{stage} model",
                            value=form["stage_models"].get(stage, form["vision_model"]),
                        )
                    )
                    stage_relay_model_inputs.append(
                        gr.Textbox(
                            label=f"{stage} relay_model",
                            value=form["stage_relay_models"].get(stage, ""),
                            placeholder="upstream KServe name",
                        )
                    )
            sync_models_btn = gr.Button(
                "Применить модели из вкладок Vision / Text",
                variant="secondary",
            )
            gr.Markdown(
                "**mode** — как gateway обрабатывает стадию. "
                "**kserve_relay** — passthrough на KServe Native (нужны endpoint=kserve_native, "
                "relay_model и base URL на вкладке KServe Native). "
                "**model** для relay — gateway alias (ocr/layout/…); **relay_model** — имя модели на Triton."
            )

        with gr.Tab("Proxy / Timeout"):
            request_timeout = gr.Number(
                label="Gateway request timeout (s)",
                value=form["request_timeout"],
            )
            http_proxy = gr.Textbox(label="HTTP_PROXY", value=form["http_proxy"])
            https_proxy = gr.Textbox(label="HTTPS_PROXY", value=form["https_proxy"])
            no_proxy = gr.Textbox(label="NO_PROXY", value=form["no_proxy"])

        with gr.Tab("Test & Save"):
            test_report = gr.Markdown("Run **Test connection** before Save.")
            docling_preview = gr.Code(label="Generated docling-serve.yaml preview", language="yaml")
            status_message = gr.Markdown("")
            test_btn = gr.Button("Test connection", variant="secondary")
            save_btn = gr.Button("Save", variant="primary")

        export = handle_refresh_config_export()
        with gr.Tab("Configs"):
            gr.Markdown(
                "Текущие конфиги с volume и bind-mount template. "
                "Выделите текст в поле (Ctrl+A) и скопируйте (Ctrl+C)."
            )
            config_paths_info = gr.Code(
                label="Пути и docker cp",
                value=export[0],
                language="markdown",
                lines=10,
            )
            refresh_configs_btn = gr.Button("Обновить", variant="secondary")
            runtime_yaml_view = gr.Code(
                label="gateway-runtime.yaml (volume)",
                value=export[1],
                language="yaml",
                lines=20,
            )
            docling_yaml_view = gr.Code(
                label="docling-serve.yaml (volume)",
                value=export[2],
                language="yaml",
                lines=20,
            )
            template_yaml_view = gr.Code(
                label="gateway-models.template.yaml (read-only mount)",
                value=export[3],
                language="yaml",
                lines=20,
            )
            effective_yaml_view = gr.Code(
                label="Effective routing (template + runtime merge)",
                value=export[4],
                language="yaml",
                lines=20,
            )

        common_inputs = [
            vision_base_url,
            vision_api_key,
            vision_model,
            text_base_url,
            text_api_key,
            text_model,
            kserve_native_base_url,
            kserve_native_api_key,
            request_timeout,
            http_proxy,
            https_proxy,
            no_proxy,
            *stage_mode_inputs,
            *stage_endpoint_inputs,
            *stage_model_inputs,
            *stage_relay_model_inputs,
            runtime_state,
        ]

        def _collect_runtime(*values: Any):
            *rest, previous = values
            (
                v_url,
                v_key,
                v_model,
                t_url,
                t_key,
                t_model,
                kn_url,
                kn_key,
                timeout,
                h_proxy,
                hs_proxy,
                n_proxy,
            ) = rest[:12]
            stage_tail = rest[12 : 12 + 4 * len(stage_names)]
            stage_modes, stage_endpoints, stage_models, stage_relay_models = (
                parse_stage_inputs_from_form_tail(stage_names, stage_tail)
            )
            return form_to_runtime(
                v_url,
                v_key,
                v_model,
                t_url,
                t_key,
                t_model,
                kn_url,
                kn_key,
                timeout,
                h_proxy,
                hs_proxy,
                n_proxy,
                stage_modes,
                stage_endpoints,
                stage_models,
                stage_relay_models,
                previous=previous,
            )

        def _format_config_error(exc: Exception) -> str:
            return f"**Ошибка конфигурации:**\n\n```\n{exc}\n```"

        def on_sync_models(v_model: str, t_model: str, *stage_values: str):
            count = len(stage_names)
            stage_modes = dict(zip(stage_names, stage_values[:count], strict=True))
            stage_endpoints = dict(
                zip(stage_names, stage_values[count : 2 * count], strict=True)
            )
            current_models = dict(
                zip(stage_names, stage_values[2 * count : 3 * count], strict=True)
            )
            return sync_stage_models_from_backends(
                stage_names,
                v_model.strip(),
                t_model.strip(),
                stage_endpoints,
                stage_modes,
                current_models,
            )

        def on_test(*values: Any):
            try:
                runtime_cfg = _collect_runtime(*values)
            except (ValidationError, ValueError) as exc:
                logger.error(
                    f"[IMP:10][on_test][CONFIG_ERROR] {exc} [FATAL]"
                )
                return _format_config_error(exc), False, values[-1]
            report, updated = handle_test_connection(runtime_cfg)
            return report.to_markdown(), updated.meta.last_test_ok, updated

        def on_save(test_ok: bool, *values: Any):
            if not test_ok:
                return (
                    "Save blocked: run Test connection successfully first.",
                    "",
                    test_ok,
                    values[-1],
                )
            try:
                runtime_cfg = _collect_runtime(*values)
            except (ValidationError, ValueError) as exc:
                logger.error(
                    f"[IMP:10][on_save][CONFIG_ERROR] {exc} [FATAL]"
                )
                return _format_config_error(exc), "", False, values[-1]
            result = handle_save_config(
                runtime_cfg,
                last_test_ok=test_ok,
                app=app,
            )
            preview = result.docling_preview if result.ok else ""
            msg = result.message
            return msg, preview, test_ok, runtime_cfg

        sync_models_btn.click(
            on_sync_models,
            inputs=[
                vision_model,
                text_model,
                *stage_mode_inputs,
                *stage_endpoint_inputs,
                *stage_model_inputs,
            ],
            outputs=stage_model_inputs,
        )

        test_btn.click(
            on_test,
            inputs=common_inputs,
            outputs=[test_report, test_ok_state, runtime_state],
        )
        save_btn.click(
            on_save,
            inputs=[test_ok_state, *common_inputs],
            outputs=[status_message, docling_preview, test_ok_state, runtime_state],
        )

        refresh_configs_btn.click(
            handle_refresh_config_export,
            outputs=[
                config_paths_info,
                runtime_yaml_view,
                docling_yaml_view,
                template_yaml_view,
                effective_yaml_view,
            ],
        )

    logger.info("[IMP:7][build_admin_blocks][READY] Gradio admin blocks constructed [OK]")
    return blocks


def mount_admin_ui(app: Any) -> Any:
    from fastapi.responses import RedirectResponse

    # BUG_FIX_CONTEXT: Gradio index.html links /manifest.json at site root; when mounted at
    # /admin the file lives at /admin/manifest.json — redirect removes browser 404 noise.
    @app.get("/manifest.json", include_in_schema=False)
    async def admin_manifest_redirect() -> RedirectResponse:
        return RedirectResponse(url="/admin/manifest.json", status_code=307)

    blocks = build_admin_blocks(app)
    mounted = gr.mount_gradio_app(
        app,
        blocks,
        path="/admin",
        root_path="/admin",
        pwa=False,
    )
    logger.info("[IMP:9][mount_admin_ui][MOUNT] Gradio admin at /admin [OK]")
    return mounted
