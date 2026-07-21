# Thin overlay on upstream docling-serve-cpu:
# - quieter access logs
# - Gradio VLM injects vlm_pipeline_preset=default (avoids legacy local granite)
FROM quay.io/docling-project/docling-serve-cpu:latest

COPY logging_config.py /opt/app-root/src/doclingllm_logging_config.py
COPY apply_gradio_vlm_preset_patch.py /opt/app-root/src/apply_gradio_vlm_preset_patch.py
RUN python -c "import shutil, docling_serve.logging_config as m; shutil.copy('/opt/app-root/src/doclingllm_logging_config.py', m.__file__)" \
    && python /opt/app-root/src/apply_gradio_vlm_preset_patch.py
