# Test Guide — doclingllm Model Gateway

## Scope

Unit/integration tests для Model Gateway (без поднятия docling-serve).

## Prerequisites

```powershell
pip install -e ".[dev]"
```

## Run all gateway tests

```powershell
python -m pytest tests/ -s -v
```

## Expected LDD markers (IMP:9-10)

| Test file | Log marker |
|-----------|------------|
| `test_gateway_config.py` | `[IMP:9][load_routing_table][READY]` |
| `test_gateway_client.py` | `[IMP:9][ExternalApiClient.chat_completions][OK]` |
| `test_gateway_kserve.py` | `[IMP:9][handle_kserve_infer][OK]` |
| `test_gateway_openai_proxy.py` | `[IMP:9][handle_openai_proxy][OK]` |
| `test_gateway_app.py` | `[IMP:9][create_app][STARTUP]` (lifespan) |

## Anti-Loop

При падении тестов счётчик пишется в `.test_counter.json`. При `failed_attempts > 0` смотреть LDD TRAJECTORY в stdout.

## Deploy config validation

`tests/test_compose_config.py` проверяет:

- `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=false`
- presets указывают на `http://model-gateway:8080`
- все stages в `gateway-models.yaml`

## Manual smoke (Ubuntu, with real API keys)

```bash
cp deploy/.env.example deploy/.env
# edit VISION_API_KEY
./scripts/start.sh
curl http://localhost:5001/health
curl -X POST http://localhost:5001/v1/convert/file -F "files=@sample.pdf"
```

## QA checklist

- [ ] `pytest tests/ -s -v` — 100% PASS
- [ ] `deploy/.env` не в git
- [ ] `docling-serve/**` без изменений
- [ ] healthcheck.sh exit 0 на сервере
