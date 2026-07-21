# Thin overlay: quiet Gradio status-poll log spam without forking docling-serve sources.
# Note: quay UBI images often deny rm under /tmp — leave the COPY source in place.
FROM quay.io/docling-project/docling-serve-cpu:latest

COPY logging_config.py /opt/app-root/src/doclingllm_logging_config.py
RUN python -c "import shutil, docling_serve.logging_config as m; shutil.copy('/opt/app-root/src/doclingllm_logging_config.py', m.__file__)"
