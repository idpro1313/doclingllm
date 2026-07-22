# Test Guide — doclingllm Model Gateway

$START_DOC_NAME

**PURPOSE:** Инструкции независимой верификации (mode-qa) для Model Gateway и deploy-конфигурации.
**SCOPE:** pytest без поднятия docling-serve; LDD markers; compose validation; optional smoke на Ubuntu.
**KEYWORDS:** mode-qa, pytest, gateway, LDD, Anti-Loop, compose, smoke

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Запуск unit/integration тестов => G_PYTEST
- GOAL Верификация LDD и deploy YAML => G_VALIDATION
- GOAL Smoke checklist с реальными API => G_SMOKE

$END_DOCUMENT_PLAN

---

$START_SECTION_SCOPE
## Scope

$START_ARTIFACT_SCOPE
#### Test boundary

**TYPE:** PRINCIPLE
**KEYWORDS:** gateway only, no docling-serve runtime

$START_CONTRACT
**PURPOSE:** Изолировать QA gateway от тяжёлого docling-serve stack.
**DESCRIPTION:** Основные тесты — mock httpx, parsers, KServe encode/decode. Compose tests — статическая валидация YAML.
**ACCEPTANCE_CRITERIA:** `pytest tests/ -s -v` PASS без Docker docling-serve.
$END_CONTRACT

$END_ARTIFACT_SCOPE

$END_SECTION_SCOPE

---

$START_SECTION_PREREQ
## Prerequisites

$START_BODY

```powershell
pip install -e ".[dev]"
```

$END_BODY

$END_SECTION_PREREQ

---

$START_SECTION_PYTEST
## Run all gateway tests

$START_BODY

```powershell
python -m pytest tests/ -s -v
```

### Expected LDD markers (IMP:9–10)

| Test file | Log marker |
|-----------|------------|
| `test_gateway_config.py` | `[IMP:9][load_routing_table][READY]` |
| `test_gateway_client.py` | `[IMP:9][ExternalApiClient.chat_completions][OK]` |
| `test_gateway_kserve.py` | `[IMP:9][handle_kserve_infer][OK]` |
| `test_gateway_openai_proxy.py` | `[IMP:9][handle_openai_proxy][OK]` |
| `test_gateway_app.py` | `[IMP:9][create_app][STARTUP]`; ConnectError → 502 |
| `test_gateway_kserve.py` | OCR boxes shape `(N,4,2)` без batch axis |
| `test_gradio_vlm_preset_patch.py` | Dockerfile VLM patch markers |
| `test_gateway_admin_*.py` | Runtime volume seed, routing merge, connection test, save gate, reload |

$END_BODY

$END_SECTION_PYTEST

---

$START_SECTION_ADMIN
## Gateway Admin UI (v0.3)

$START_BODY

Headless tests: `tests/test_gateway_admin_*.py`  
Manual: http://localhost:8080/admin — Test connection → Save → `docker compose restart docling-serve`

$END_BODY

$END_SECTION_ADMIN

---

$START_SECTION_ANTILOOP
## Anti-Loop

$START_BODY

При падении тестов счётчик — `.test_counter.json`. При `failed_attempts > 0` анализировать LDD TRAJECTORY в stdout (mode-debug).

$END_BODY

$END_SECTION_ANTILOOP

---

$START_SECTION_COMPOSE
## Deploy config validation

$START_BODY

`tests/test_compose_config.py` проверяет:

- `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=false`
- presets → `http://model-gateway:8080`
- stages в `gateway-models.yaml`
- overlay Dockerfile: Gradio + app VLM preset patches (≥0.2.23)

$END_BODY

$END_SECTION_COMPOSE

---

$START_SECTION_SMOKE
## Manual smoke (Ubuntu, real API keys)

$START_BODY

```bash
cp deploy/.env.defaults deploy/.env
# edit VISION_API_KEY
./scripts/start.sh
curl http://localhost:5001/health
curl -X POST http://localhost:5001/v1/convert/file -F "files=@sample.pdf"
```

После overlay rebuild в build log: `VLM preset patches verified in image`.

$END_BODY

$END_SECTION_SMOKE

---

$START_SECTION_CHECKLIST
## QA checklist

$START_BODY

- [ ] `pytest tests/ -s -v` — PASS
- [ ] `deploy/.env` не в git
- [ ] `docling-serve/**` без изменений в git diff
- [ ] `scripts/healthcheck.sh` exit 0 на сервере
- [ ] Vlm pipeline не ищет local `granite-docling-258M` (middleware/Gradio inject)
- [ ] `tests/test_gateway_admin_*.py` PASS
- [ ] Admin Save пишет только в volume `doclingllm-config`, не в git tree

$END_BODY

$END_SECTION_CHECKLIST

$END_DOC_NAME
