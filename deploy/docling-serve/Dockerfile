# Thin overlay on upstream docling-serve-cpu:
# - quieter access logs
# - API+Gradio inject vlm_pipeline_preset=default (avoids legacy local granite)
FROM quay.io/docling-project/docling-serve-cpu:v1.27.0

COPY logging_config.py /opt/app-root/src/doclingllm_logging_config.py
COPY vlm_preset_middleware.py /opt/app-root/src/doclingllm_vlm_preset_middleware.py
COPY apply_gradio_vlm_preset_patch.py /opt/app-root/src/apply_gradio_vlm_preset_patch.py
COPY apply_app_vlm_middleware_patch.py /opt/app-root/src/apply_app_vlm_middleware_patch.py

RUN python - <<'PY'
import shutil
from pathlib import Path
import docling_serve.logging_config as logging_config

pkg_dir = Path(logging_config.__file__).parent
shutil.copy("/opt/app-root/src/doclingllm_logging_config.py", logging_config.__file__)
shutil.copy(
    "/opt/app-root/src/doclingllm_vlm_preset_middleware.py",
    pkg_dir / "vlm_preset_middleware.py",
)
print(f"[doclingllm] overlayed logging_config + vlm_preset_middleware into {pkg_dir}")
PY
RUN python /opt/app-root/src/apply_gradio_vlm_preset_patch.py \
    && python /opt/app-root/src/apply_app_vlm_middleware_patch.py \
    && python - <<'PY'
from pathlib import Path
import docling_serve.app as app
import docling_serve.gradio_ui as gui

app_text = Path(app.__file__).read_text(encoding="utf-8")
gui_text = Path(gui.__file__).read_text(encoding="utf-8")
assert "DOCLINGLLM_VLM_PRESET_MIDDLEWARE" in app_text, "app middleware marker missing"
assert "DOCLINGLLM_VLM_PRESET_INJECT" in gui_text, "gradio inject marker missing"
print("[doclingllm] VLM preset patches verified in image")
PY
