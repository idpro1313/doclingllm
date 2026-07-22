# Development Plan: doclingllm — docling-serve через внешний API

$START_DEV_PLAN

**PURPOSE:** Реализовать обёртку вокруг неизменяемого `docling-serve`, которая на Ubuntu в Docker направляет все стадии ML-пайплайна во внешний custom OpenAI-compatible API через промежуточный Model Gateway (KServe v2 + OpenAI proxy).

**Версия плана:** 0.2.0  
**Статус:** Architecture designed — см. `plans/Architecture.md`; готов к делегированию mode-code  
**Архитектура:** `plans/Architecture.md` (C4, слои L1–L4, feature slices S1–S8)
**Выбор концепции:** Гипотеза B (см. §0) — Gateway-адаптер + конфигурация docling-serve без правок исходников

---

## 0. Критерии успеха и выбор архитектуры

### Критерии (из THINK_AND_CLARIFY)

| # | Критерий | Вес |
|---|----------|-----|
| K1 | `docling-serve/**` не изменяется | 10 |
| K2 | В runtime не загружаются локальные веса моделей | 9 |
| K3 | Все стадии пайплайна используют внешний API | 9 |
| K4 | Запуск на Ubuntu одним скриптом | 8 |
| K5 | CPU-only, без GPU | 7 |
| K6 | Обновляемость upstream docling-serve | 7 |

### Гипотезы (superposition)

| ID | Концепция | Оценка |
|----|-----------|--------|
| A | Только env vars docling-serve → прямой OpenAI-compatible URL | ❌ OCR/layout/table не поддерживают OpenAI API (K3) |
| B | **Model Gateway (наш код) + docling-serve presets → KServe v2 / OpenAI** | ✅ K1–K6; требует адаптер контракта custom API |
| C | Патч docling-serve / форк | ❌ нарушает C1/K1 |

**Collapse:** принимаем **гипотезу B**.

### Уточнения оператора (зафиксированы)

- Все модели через API (включая OCR/layout/table)
- Сервер: CPU-only, Ubuntu, Docker, скрипт запуска
- **Два OpenAI-compatible backend'а** (см. §1.1)

#### 1.1. Маршрутизация моделей (collapse v0.1.1)

| Backend | URL | Модель | Auth | Стадии docling |
|---------|-----|--------|------|----------------|
| **vision** (Develonica) | `https://ai-billing.develonica.group/v1` | `qwen3.6-35b-a3b` (`VISION_MODEL`) | Bearer (`VISION_API_KEY`) | OCR, layout, table, picture_*, VLM pipeline |
| **text** (LAN) | `http://192.168.101.15:8111/v1` | `minimax-m2.7` | нет | code/formula enrichment (текст) |

**Ключевая идея:** vision — OpenAI-compatible multimodal (Qwen3.6); KServe-стадии в gateway → `POST /chat/completions` + parse → tensors. Text → `minimax-m2.7` на LAN.

**Сеть Docker:** `model-gateway` → LAN minimax и HTTPS к `ai-billing.develonica.group`.

**Секреты:** `VISION_API_KEY` **только** в `deploy/.env`. Шаблон: `deploy/.env.example` / `.env.defaults`.

**Артефакты конфигурации (draft):**
- `deploy/.env.example`
- `deploy/config/gateway-models.yaml`

---

### 1. Draft Code Graph

```xml
<DraftCodeGraph>
  <doclingllm_project TYPE="PROJECT_ROOT">
    <annotation>Обёртка docling-serve: deploy, gateway, scripts, tests. Vendor docling-serve read-only.</annotation>
  </doclingllm_project>

  <deploy_docker_compose_yml FILE="deploy/docker-compose.yml" TYPE="DEPLOYMENT_MANIFEST">
    <annotation>Orchestration: docling-serve-cpu + model-gateway + shared network.</annotation>
    <CrossLinks>
      <Link TARGET="scripts_start_sh" TYPE="STARTED_BY" />
      <Link TARGET="deploy_config_docling_serve_yaml" TYPE="MOUNTS" />
    </CrossLinks>
  </deploy_docker_compose_yml>

  <deploy_config_docling_serve_yaml FILE="deploy/config/docling-serve.yaml" TYPE="CONFIG_FILE">
    <annotation>Admin presets: kserve_v2 для OCR/layout/table; api engine для VLM/picture/code.</annotation>
    <CrossLinks>
      <Link TARGET="docling_serve_settings_py" TYPE="LOADED_BY" />
    </CrossLinks>
  </deploy_config_docling_serve_yaml>

  <deploy_env_example FILE="deploy/.env.example" TYPE="CONFIG_TEMPLATE">
    <annotation>EXTERNAL_API_BASE_URL, API keys, gateway ports, docling-serve flags.</annotation>
  </deploy_env_example>

  <scripts_start_sh FILE="scripts/start.sh" TYPE="DEPLOY_SCRIPT">
    <annotation>Ubuntu: проверка docker, загрузка .env, docker compose up -d, healthcheck.</annotation>
    <CrossLinks>
      <Link TARGET="deploy_docker_compose_yml" TYPE="INVOKES" />
    </CrossLinks>
  </scripts_start_sh>

  <scripts_stop_sh FILE="scripts/stop.sh" TYPE="DEPLOY_SCRIPT">
    <annotation>Graceful shutdown docker compose stack.</annotation>
  </scripts_stop_sh>

  <src_doclingllm_gateway_app_py FILE="src/doclingllm/gateway/app.py" TYPE="API_GATEWAY_MODULE">
    <annotation>FastAPI/uvicorn: KServe v2 infer endpoints + OpenAI proxy.</annotation>
    <src_doclingllm_gateway_app_py_create_app_FUNC NAME="create_app" TYPE="IS_FUNCTION_OF_MODULE">
      <annotation>Factory ASGI app with route registration.</annotation>
    </src_doclingllm_gateway_app_py_create_app_FUNC>
  </src_doclingllm_gateway_app_py>

  <src_doclingllm_gateway_kserve_py FILE="src/doclingllm/gateway/kserve.py" TYPE="ADAPTER_MODULE">
    <annotation>KServe v2 HTTP handlers: OCR, layout OD, table, picture classifier.</annotation>
    <src_doclingllm_gateway_kserve_py_infer_handler_FUNC NAME="infer_handler" TYPE="IS_FUNCTION_OF_MODULE">
      <annotation>Parse KServe request tensors → call ExternalApiClient → KServe response.</annotation>
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_client_py" TYPE="CALLS_MODULE" />
      </CrossLinks>
    </src_doclingllm_gateway_kserve_py_infer_handler_FUNC>
  </src_doclingllm_gateway_kserve_py>

  <src_doclingllm_gateway_openai_proxy_py FILE="src/doclingllm/gateway/openai_proxy.py" TYPE="PROXY_MODULE">
    <annotation>Pass-through /v1/chat/completions → EXTERNAL_API_BASE_URL.</annotation>
    <CrossLinks>
      <Link TARGET="src_doclingllm_gateway_client_py" TYPE="USES_API" />
    </CrossLinks>
  </src_doclingllm_gateway_openai_proxy_py>

  <src_doclingllm_gateway_client_py FILE="src/doclingllm/gateway/client.py" TYPE="HTTP_CLIENT_MODULE">
    <annotation>httpx client: mapping stage→endpoint/model; retries, timeouts, auth headers.</annotation>
    <src_doclingllm_gateway_client_py_ExternalApiClient_CLASS NAME="ExternalApiClient" TYPE="IS_CLASS_OF_MODULE">
      <annotation>Unified outbound calls to operator custom API.</annotation>
      <src_doclingllm_gateway_client_py_ExternalApiClient_infer_stage_METHOD NAME="infer_stage" TYPE="IS_METHOD_OF_CLASS">
        <annotation>stage in {ocr, layout, table, picture_class, vlm, code_formula}.</annotation>
      </src_doclingllm_gateway_client_py_ExternalApiClient_infer_stage_METHOD>
    </src_doclingllm_gateway_client_py_ExternalApiClient_CLASS>
  </src_doclingllm_gateway_client_py>

  <src_doclingllm_gateway_config_py FILE="src/doclingllm/gateway/config.py" TYPE="CONFIG_MODULE">
    <annotation>Pydantic settings: EXTERNAL_API_*, model name map, gateway bind host/port.</annotation>
  </src_doclingllm_gateway_config_py>

  <deploy_gateway_Dockerfile FILE="deploy/gateway/Dockerfile" TYPE="CONTAINER_BUILD">
    <annotation>Python 3.12 slim; pip install src/doclingllm; CMD uvicorn gateway.app.</annotation>
    <CrossLinks>
      <Link TARGET="src_doclingllm_gateway_app_py" TYPE="BUILDS_IMAGE_FOR" />
    </CrossLinks>
  </deploy_gateway_Dockerfile>

  <docling_serve_vendor TYPE="VENDOR_READONLY">
    <annotation>docling-serve/ — upstream, без изменений. Образ quay.io/docling-project/docling-serve-cpu.</annotation>
    <docling_serve_settings_py FILE="docling-serve/docling_serve/settings.py" TYPE="VENDOR_CONFIG_REFERENCE">
      <annotation>DOCLING_SERVE_* env vars, custom_*_presets, enable_remote_services.</annotation>
    </docling_serve_settings_py>
  </docling_serve_vendor>

  <tests_test_gateway_kserve_py FILE="tests/test_gateway_kserve.py" TYPE="TEST_MODULE">
    <annotation>pytest + caplog: KServe infer mock external API.</annotation>
    <CrossLinks>
      <Link TARGET="src_doclingllm_gateway_kserve_py" TYPE="TESTS" />
    </CrossLinks>
  </tests_test_gateway_kserve_py>

  <tests_test_compose_config_py FILE="tests/test_compose_config.py" TYPE="TEST_MODULE">
    <annotation>Валидация compose/env: enable_remote_services, load_models_at_boot=false.</annotation>
  </tests_test_compose_config_py>
</DraftCodeGraph>
```

---

### 2. Step-by-step Data Flow

#### 2.1. Bootstrap (Ubuntu, оператор)

1. **Step 1:** Оператор клонирует репозиторий на Ubuntu, копирует `deploy/.env.example` → `deploy/.env`, заполняет `VISION_API_KEY`, проверяет `VISION_API_BASE_URL`, `TEXT_API_BASE_URL`, модели.
2. **Step 2:** Оператор запускает `scripts/start.sh` — скрипт проверяет наличие Docker и Docker Compose v2, загружает `.env`, выполняет `docker compose -f deploy/docker-compose.yml up -d --build`.
3. **Step 3:** Compose поднимает два сервиса: `model-gateway` (порт 8080 внутренний) и `docling-serve` (порт 5001 наружу). `docling-serve` монтирует `deploy/config/docling-serve.yaml` и получает env из compose.

#### 2.2. Конфигурация docling-serve (без правок кода)

4. **Step 4:** `DOCLING_SERVE_CONFIG_FILE=/config/docling-serve.yaml` задаёт admin presets:
   - `default_ocr_preset: api_ocr` → kind `kserve_v2_ocr`, url `model-gateway:8080`, model_name `ocr`
   - `default_layout_preset: api_layout` → KServe v2 object detection на gateway
   - `default_table_structure_preset: api_table` → KServe v2 на gateway
   - `default_vlm_preset: api_vlm` → engine `api`, url `http://model-gateway:8080/v1/chat/completions`
   - аналогично picture_description, code_formula, picture_classification
5. **Step 5:** Критичные флаги env:
   - `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true`
   - `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=false` — не прогревать локальные веса
   - `DOCLING_DEVICE=cpu`
   - `DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS=false` (достаточно kserve + api presets)
6. **Step 6:** docling-serve при старте читает YAML → `DoclingConverterManager` (docling-jobkit) создаёт конвертеры с remote options; локальный `DOCLING_SERVE_ARTIFACTS_PATH` не используется для инференса.

#### 2.3. Запрос конвертации документа

7. **Step 7:** Клиент отправляет `POST http://host:5001/v1/convert/file` с PDF и options (или defaults из presets).
8. **Step 8:** docling-serve (policy → orchestrator) запускает пайплайн Docling:
   - **Layout stage** → HTTP/gRPC KServe infer → `model-gateway` `/v2/models/layout/infer`
   - **OCR stage** → `model-gateway` `/v2/models/ocr/infer`
   - **Table structure** → `model-gateway` `/v2/models/table/infer`
   - **Picture classification / VLM / picture description / code-formula** → OpenAI-compatible через gateway proxy или KServe (по preset)
9. **Step 9:** Model Gateway в `infer_handler`:
   - декодирует tensor payload (image bytes, metadata lang/scale)
   - по `gateway-models.yaml` выбирает backend `vision` или `text`
   - **vision:** `POST https://ai-billing.develonica.group/v1/chat/completions` с `Authorization: Bearer $VISION_API_KEY`, model из `VISION_MODEL`
   - **text:** `POST http://192.168.101.15:8111/v1/chat/completions`, model `minimax-m2.7`, без auth
   - парсит JSON/text ответ → KServe v2 response tensors для docling
10. **Step 10:** docling-serve собирает Document, возвращает JSON/HTML/Markdown клиенту.

#### 2.4. Контракт адаптера custom API (Phase 1 — минимальный)

11. **Step 11:** Gateway modes в `gateway-models.yaml`:
    - **`openai_vision`** → Develonica vision / `VISION_MODEL` (OCR, layout, table, picture_*)
    - **`openai_proxy`** → pass-through chat/completions для VLM preset docling
    - **`openai_text`** → minimax-m2.7 для code/formula
12. **Step 12:** Response parsers (`deepseek_ocr_json`, `layout_boxes_json`, `table_structure_json`) конвертируют ответ LLM в tensor layout docling. Контракт парсеров — в `docs/gateway_api_contract.md` (Phase P8).

#### 2.5. Shutdown и observability

13. **Step 13:** `scripts/stop.sh` выполняет `docker compose down`. Логи: `docker compose logs -f docling-serve model-gateway`.
14. **Step 14:** Health: gateway `GET /health`, docling-serve `GET /health` (или `/v1/health` per upstream).

---

### 3. Структура репозитория (целевая)

```text
doclingllm/
├── docling-serve/              # READ-ONLY vendor
├── deploy/
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── config/
│   │   ├── docling-serve.yaml
│   │   └── gateway-models.yaml
│   └── gateway/
│       └── Dockerfile
├── src/
│   └── doclingllm/
│       └── gateway/
│           ├── app.py              # L1 Transport
│           ├── kserve.py           # L2 Protocol
│           ├── openai_proxy.py     # L2 Protocol
│           ├── routing.py          # L3 Adaptation
│           ├── parsers/            # L3 Adaptation
│           ├── client.py           # L4 Integration
│           └── config.py           # L4 Integration
├── scripts/
│   ├── start.sh
│   ├── stop.sh
│   └── healthcheck.sh
├── tests/
│   ├── test_gateway_config.py
│   ├── test_gateway_client.py
│   ├── test_gateway_parsers.py
│   ├── test_gateway_kserve.py
│   ├── test_gateway_openai_proxy.py
│   └── test_compose_config.py
├── docs/
│   └── gateway_api_contract.md
└── plans/
    ├── DevelopmentPlan.md
    ├── Architecture.md           # ← архитектурный документ
    ├── business_requirements.md
    └── AppGraph.xml
```

---

### 4. Docker Compose (логика)

| Сервис | Образ | Порты | Зависимости |
|--------|-------|-------|-------------|
| `model-gateway` | build `deploy/gateway/Dockerfile` | internal 8080 | — |
| `docling-serve` | build `deploy/docling-serve` → `doclingllm-docling-serve:local` (FROM upstream cpu + quiet logging overlay) | `5001:5001` | `model-gateway` healthy |

Volumes: `./deploy/config` → `/config:ro` в docling-serve.  
Overlay: `deploy/docling-serve/logging_config.py` — WARNING для httpx; filter access `/v1/status/poll` и `/health`.  
Networks: `doclingllm-net` (bridge).  
Secrets: через `.env`, не bake в образ.

---

### 5. Конфиг docling-serve (ключевые поля YAML)

```yaml
# deploy/config/docling-serve.yaml (draft)
enable_remote_services: true
load_models_at_boot: false
log_format: json

default_ocr_kind: kserve_v2_ocr
default_ocr_preset: remote_ocr
custom_ocr_presets:
  remote_ocr:
    kind: kserve_v2_ocr
    url: "http://model-gateway:8080"
    transport: http
    model_name: ocr

default_layout_kind: kserve_v2_layout  # kind per docling version
default_layout_preset: remote_layout
custom_layout_presets:
  remote_layout:
    url: "http://model-gateway:8080"
    model_name: layout

default_vlm_preset: remote_vlm
custom_vlm_presets:
  remote_vlm:
    engine_options:
      engine_type: api
    model_spec:
      api_overrides:
        api:
          url: "http://model-gateway:8080/v1/chat/completions"
          params:
            model: "${MODEL_VLM}"

# table, picture_description, code_formula, picture_classification — аналогично
```

> **Примечание для Code-агента:** точные `kind` и поля preset сверить с версией `docling` в `docling-serve/pyproject.toml` (≥2.113) и документацией pipeline_options; при расхождении — скорректировать YAML без правок vendor.

---

### 6. План реализации (ToDo для mode-code)

> **Детализация:** feature slices S1–S8, слои L1–L4, sequence diagrams — в [`plans/Architecture.md`](Architecture.md) §8.

| Phase | Slice | Задача | Артефакты |
|-------|-------|--------|-----------|
| P1 | S1 | Config + routing load | `config.py`, `routing.py` |
| P2 | S2 | HTTP client L4 | `client.py`, `test_gateway_client.py` |
| P3 | S3 | Response parsers L3 | `parsers/*.py`, `test_gateway_parsers.py` |
| P4 | S4 | KServe adapter L2 + app L1 | `kserve.py`, `app.py`, `test_gateway_kserve.py` |
| P5 | S5 | OpenAI proxy | `openai_proxy.py`, `test_gateway_openai_proxy.py` |
| P6 | S6 | Deploy + scripts | `docker-compose.yml`, `Dockerfile`, `docling-serve.yaml`, `scripts/*` |
| P7 | S7–S8 | Docs, test_guide, VERSION | `gateway_api_contract.md`, `tests/test_guide.md` |

**Зависимости Python (gateway):**

```text
fastapi>=0.115.0      # ASGI gateway, KServe + proxy routes
uvicorn>=0.32.0       # Production server in container
httpx>=0.28.0         # Async HTTP to external custom API
pydantic-settings>=2  # Typed config from env
numpy>=2.0.0          # Tensor encode/decode for KServe payloads
pyyaml>=6.0           # gateway-models.yaml loading
```

---

### 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Custom API не совместим с KServe tensor format | Высокая | Gateway adapter + документированный contract; итерация mapping per stage |
| Версия docling изменит имена `kind` для kserve | Средняя | Pin образ docling-serve; smoke-test при обновлении |
| Vision model не отдаёт структурированный JSON layout/table | Высокая | Prompt engineering + response parsers; итерация на реальных PDF |
| Gateway в Docker не видит 192.168.101.15 | Средняя | `network_mode: host` или маршрутизация LAN; проверка в start.sh |
| Latency vision API + LAN на больших PDF | Средняя | `GATEWAY_REQUEST_TIMEOUT`, async endpoints docling-serve |
| Утечка VISION_API_KEY | Средняя | только deploy/.env; ротация при попадании в чат/логи |

---

### 8. Acceptance Criteria

- [ ] **AC1:** В репозитории нет изменений в `docling-serve/**` (git diff clean для vendor).
- [ ] **AC2:** `scripts/start.sh` на Ubuntu с Docker поднимает stack; `scripts/healthcheck.sh` возвращает 0.
- [ ] **AC3:** `DOCLING_SERVE_LOAD_MODELS_AT_BOOT=false` и presets указывают только на `model-gateway` (проверка в `tests/test_compose_config.py`).
- [ ] **AC4:** Gateway маршрутизирует vision → Develonica и text → minimax LAN (unit tests с mock httpx).
- [ ] **AC5:** Model Gateway отвечает на KServe v2 infer для OCR и layout (unit tests с mock tensors).
- [ ] **AC6:** E2E smoke (manual или pytest с mock external API): POST `/v1/convert/file` на docling-serve возвращает 200 и non-empty `md_content`.
- [ ] **AC7:** Секреты только в `.env`; `.env` в `.gitignore`.
- [ ] **AC8:** Документ `docs/gateway_api_contract.md` описывает ожидаемый формат custom API для каждой стадии.

---

### 9. Статус перед mode-code

1. **Architecture.md** — утверждён Architect (слои, API, deploy, slices S1–S8).
2. **O1:** формат OCR-ответа vision model — начать с heuristic parser (Architecture §10).
3. **O2:** LAN из Docker — default bridge, fallback host network (Architecture §5).
4. **Действие:** делегировать **Slice S1** Code-агенту или последовательно S1→S8.

---

### 10. Compliance audit vs docling-serve / docling (2026-07-22, v0.2.10)

**Полный отчёт:** `work/architect_docling_serve_compliance_audit.md` (не в git).

| Статус | Область |
|--------|---------|
| OK | KServe HTTP presets OCR/layout; binary infer request; layout OD I/O; OCR inputs; remote_services; table local fallback |
| CRITICAL | VLM/pic_desc/code_formula: `url` в `api_overrides` вместо `engine_options` → default Ollama localhost |
| CRITICAL | `docs/gateway_api_contract.md` устарел (legacy BYTES) |
| HIGH | OCR boxes shape `(1,N,4,2)` vs engine `(N,4,2)` |
| HIGH | picture_classifier `repo_id` не совпадает с upstream v2.5 |

**Критерии следующего slice:** C1 immutability; C2 YAML schema; C3 tensor shapes; C5 docs sync.

**Collapse (оператор 2026-07-22):** полный фикс B+C + иммунизация SSL/502 (без binary response encoding — JSON fallback OK).

**Реализовано в 0.2.12:** YAML `engine_options.url`; OCR `(N,4,2)`; layout per-batch OD; `DocumentFigureClassifier-v2.5`; `UpstreamApiError`→502; proxy env; docs sync.

---

### 11. Gateway Admin UI (Gradio) — v0.3.0

**Collapse (оператор 2026-07-22):**

| Решение | Выбор |
|---------|--------|
| Архитектура | **Гипотеза A** — Gradio `/admin` в `model-gateway`, модуль `gateway/admin/` |
| Persistence | **Named Docker volume** `doclingllm-config` → `/data/doclingllm/config` (не папка проекта) |
| Runtime file | `gateway-runtime.yaml` на volume (ключи внутри) |
| Templates в git | `gateway-models.template.yaml`, `docling-serve.template.yaml`, `gateway-runtime.defaults.yaml` |
| docling apply | **Вариант 2** — preview + warning; **ручной** `docker compose restart docling-serve` |
| Gateway apply | `POST /admin/reload` hot-reload |
| Test gate | Save только после успешного test (models, chat, vision, per-stage) |
| Auth v1 | Нет; `:8080` publish для local dev |
| Stage UI v1 | endpoint + model; prompts в template |

**Полный план:** [`plans/GatewayAdminUI.md`](GatewayAdminUI.md) — Draft Code Graph, data flow, slices **G1–G7**, acceptance AC-G1…G9.

**Статус:** ожидает утверждения оператора → mode-code G1.

$END_DEV_PLAN
