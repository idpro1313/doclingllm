# Thin overlay: quiet Gradio status-poll log spam without forking docling-serve sources.
FROM quay.io/docling-project/docling-serve-cpu:latest

COPY logging_config.py /tmp/doclingllm_logging_config.py
RUN python -c "import shutil, docling_serve.logging_config as m; shutil.copy('/tmp/doclingllm_logging_config.py', m.__file__)" \
    && rm -f /tmp/doclingllm_logging_config.py
