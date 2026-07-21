# region MODULE_CONTRACT [DOMAIN(8): Deploy; CONCEPT(8): AppPatch; TECH(8): pathlib]
## @purpose Register VlmPresetInjectMiddleware inside docling_serve.app.create_app.
def _module_contract():
    pass
# endregion MODULE_CONTRACT

from pathlib import Path

import docling_serve.app as app_module

MARKER = "DOCLINGLLM_VLM_PRESET_MIDDLEWARE"
ANCHOR = (
    "    app.add_middleware(\n"
    "        LogContextMiddleware,\n"
    "        header_prefix=docling_serve_settings.log_header_prefix,\n"
    "    )\n"
)
REPLACEMENT = (
    "    app.add_middleware(\n"
    "        LogContextMiddleware,\n"
    "        header_prefix=docling_serve_settings.log_header_prefix,\n"
    "    )\n"
    "\n"
    "    # DOCLINGLLM_VLM_PRESET_MIDDLEWARE\n"
    "    from docling_serve.vlm_preset_middleware import VlmPresetInjectMiddleware\n"
    "    app.add_middleware(VlmPresetInjectMiddleware)\n"
)


def main() -> None:
    path = Path(app_module.__file__)
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"[doclingllm] App VLM middleware patch already present: {path}")
        return
    if ANCHOR not in text:
        raise SystemExit(f"[doclingllm] create_app middleware anchor not found in {path}")
    text = text.replace(ANCHOR, REPLACEMENT, 1)
    if MARKER not in text:
        raise SystemExit("[doclingllm] App VLM middleware patch failed to apply")
    path.write_text(text, encoding="utf-8")
    print(f"[doclingllm] Patched VlmPresetInjectMiddleware into {path}")


if __name__ == "__main__":
    main()
