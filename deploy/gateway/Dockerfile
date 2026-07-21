FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e .

COPY deploy/config/gateway-models.yaml /config/gateway-models.yaml

ENV GATEWAY_MODELS_CONFIG_PATH=/config/gateway-models.yaml
ENV GATEWAY_HOST=0.0.0.0
ENV GATEWAY_PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["doclingllm-gateway"]
