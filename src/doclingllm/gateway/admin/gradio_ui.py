# region MODULE_CONTRACT [DOMAIN(9): Admin; CONCEPT(9): GradioUI; TECH(9): gradio]
## @purpose Build Gradio Blocks admin UI mounted at /admin on gateway FastAPI app.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: gradio admin UI, /admin, gateway settings form
# STRUCTURE: ▶ Blocks tabs → ◇ handlers → ⊕ test state → Save gated

import logging
from typing import Any, Optional

import gradio as gr

from doclingllm.gateway.admin.gradio_handlers import (
    form_to_runtime,
    handle_save_config,
    handle_test_connection,
    load_admin_runtime,
    runtime_to_form,
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

        with gr.Tab("Stages"):
            stage_endpoint_inputs = []
            stage_model_inputs = []
            for stage in stage_names:
                with gr.Row():
                    stage_endpoint_inputs.append(
                        gr.Dropdown(
                            choices=["vision", "text"],
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

        common_inputs = [
            vision_base_url,
            vision_api_key,
            vision_model,
            text_base_url,
            text_api_key,
            text_model,
            request_timeout,
            http_proxy,
            https_proxy,
            no_proxy,
            *stage_endpoint_inputs,
            *stage_model_inputs,
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
                timeout,
                h_proxy,
                hs_proxy,
                n_proxy,
            ) = rest[:10]
            stage_model_values = rest[10 : 10 + len(stage_names)]
            stage_endpoint_values = rest[10 + len(stage_names) : 10 + 2 * len(stage_names)]
            stage_models = dict(zip(stage_names, stage_model_values, strict=True))
            stage_endpoints = dict(zip(stage_names, stage_endpoint_values, strict=True))
            return form_to_runtime(
                v_url,
                v_key,
                v_model,
                t_url,
                t_key,
                t_model,
                timeout,
                h_proxy,
                hs_proxy,
                n_proxy,
                stage_models,
                stage_endpoints,
                previous=previous,
            )

        def on_test(*values: Any):
            runtime_cfg = _collect_runtime(*values)
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
            runtime_cfg = _collect_runtime(*values)
            result = handle_save_config(
                runtime_cfg,
                last_test_ok=test_ok,
                app=app,
            )
            preview = result.docling_preview if result.ok else ""
            msg = result.message
            return msg, preview, test_ok, runtime_cfg

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

    logger.info("[IMP:7][build_admin_blocks][READY] Gradio admin blocks constructed [OK]")
    return blocks


def mount_admin_ui(app: Any) -> Any:
    blocks = build_admin_blocks(app)
    mounted = gr.mount_gradio_app(app, blocks, path="/admin")
    logger.info("[IMP:9][mount_admin_ui][MOUNT] Gradio admin at /admin [OK]")
    return mounted
