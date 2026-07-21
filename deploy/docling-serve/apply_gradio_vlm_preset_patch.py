# region MODULE_CONTRACT [DOMAIN(8): Deploy; CONCEPT(9): GradioPatch; TECH(8): pathlib]
## @purpose Inject vlm_pipeline_preset into Gradio convert payloads so VlmPipeline uses remote admin preset.
## @rationale
## Q: Why patch Gradio instead of YAML granite_docling overwrite?
## A: Gradio omits vlm_pipeline_preset; jobkit then takes legacy GRANITEDOCLING_TRANSFORMERS and never reads custom_vlm_presets.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: Gradio patch, vlm_pipeline_preset, granite_docling, remote VLM
# STRUCTURE: ▶ find gradio_ui.py → ◇ already patched? → ⊕ inject after parameters= → ⎋ write

from pathlib import Path

import docling_serve.gradio_ui as gradio_ui

MARKER = "DOCLINGLLM_VLM_PRESET_INJECT"
INJECT_BLOCK = """
    # DOCLINGLLM_VLM_PRESET_INJECT
    # Gradio omits vlm_pipeline_preset → jobkit legacy local granite. Force admin remote preset.
    if str(pipeline) == "vlm":
        parameters["options"]["vlm_pipeline_preset"] = "default"
"""


def main() -> None:
    path = Path(gradio_ui.__file__)
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"[doclingllm] Gradio VLM preset patch already present: {path}")
        return

    url_anchor = (
        '        "target": target,\n'
        "    }\n"
        "    if (\n"
        '        not parameters["sources"]'
    )
    url_replacement = (
        '        "target": target,\n'
        "    }\n"
        f"{INJECT_BLOCK}"
        "    if (\n"
        '        not parameters["sources"]'
    )
    if url_anchor not in text:
        raise SystemExit(f"[doclingllm] process_url anchor not found in {path}")

    file_anchor = (
        '        "target": target,\n'
        "    }\n"
        "\n"
        "    headers = {}\n"
        "    if docling_serve_settings.api_key:\n"
        '        headers["X-Api-Key"] = str(auth)\n'
        "\n"
        "    try:\n"
        "        ssl_ctx = get_ssl_context()\n"
        "        response = httpx.post(\n"
        '            f"{get_api_endpoint()}/v1/convert/source/async",'
    )
    # process_file also posts to convert/source/async - need unique context.
    # Use return_as_file which appears only in process_file options block end vicinity.
    file_anchor = (
        '            "return_as_file": return_as_file,\n'
        '            "do_code_enrichment": do_code_enrichment,\n'
        '            "do_formula_enrichment": do_formula_enrichment,\n'
        '            "do_picture_classification": do_picture_classification,\n'
        '            "do_picture_description": do_picture_description,\n'
        "        },\n"
        '        "target": target,\n'
        "    }\n"
        "\n"
        "    headers = {}"
    )
    file_replacement = (
        '            "return_as_file": return_as_file,\n'
        '            "do_code_enrichment": do_code_enrichment,\n'
        '            "do_formula_enrichment": do_formula_enrichment,\n'
        '            "do_picture_classification": do_picture_classification,\n'
        '            "do_picture_description": do_picture_description,\n'
        "        },\n"
        '        "target": target,\n'
        "    }\n"
        f"{INJECT_BLOCK}"
        "\n"
        "    headers = {}"
    )
    if file_anchor not in text:
        raise SystemExit(f"[doclingllm] process_file anchor not found in {path}")

    text = text.replace(url_anchor, url_replacement, 1)
    text = text.replace(file_anchor, file_replacement, 1)
    if text.count(MARKER) != 2:
        raise SystemExit(
            f"[doclingllm] Expected 2 inject markers, found {text.count(MARKER)}"
        )
    path.write_text(text, encoding="utf-8")
    print(f"[doclingllm] Patched Gradio VLM preset inject into {path}")


if __name__ == "__main__":
    main()
