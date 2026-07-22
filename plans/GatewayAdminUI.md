# Development Plan: Gateway Admin UI (Gradio)

$START_DEV_PLAN

**PURPOSE:** Gradio UI на Model Gateway (`/admin`) для настройки vision/text backends, stage models, proxy/timeout; проверка связи перед Save; persistence в **Docker named volume** (не в папке проекта); генерация `docling-serve.yaml` на volume с **ручным restart** docling-serve.

**Версия плана:** 0.3.0 (Gateway Admin UI)  
**Статус:** Collapse подтверждён оператором — **гипотеза A**; docling apply — **вариант 2** (preview + warning)  
**Связь:** [`DevelopmentPlan.md`](DevelopmentPlan.md) v0.2.x (S1–S8 выполнены); [`Architecture.md`](Architecture.md) L1–L4

---

## 0. Критерии успеха (collapse оператора)

| # | Критерий | Вес |
|---|----------|-----|
| K1 | Смена URL/model/key без правки файлов репозитория | 10 |
| K2 | **Test connection обязателен** перед Save | 10 |
| K3 | Настройки в **named Docker volume**, не в `deploy/config/` проекта | 9 |
| K4 | Gateway hot-reload через `POST /admin/reload` | 8 |
| K5 | pytest headless на UI handlers (Grace Pattern 4) | 8 |
| K6 | `docling-serve/**` не изменяется | 10 |

**Collapse:** **Гипотеза A** — Gradio `/admin` внутри `create_app()`, backend `ConfigAdminService` + `ConnectionTester` в `src/doclingllm/gateway/admin/`.

**Исключено:** отдельный контейнер admin (B); auth v1 (осознанный dev-риск при `:8080` publish).

---

## 1. Draft Code Graph

```xml
<DraftCodeGraph>
  <deploy_docker_compose_yml FILE="deploy/docker-compose.yml" TYPE="DEPLOYMENT_MANIFEST">
    <annotation>Named volume doclingllm-config; publish 8080; gateway rw volume; docling-serve ro same volume.</annotation>
    <CrossLinks>
      <Link TARGET="volume_doclingllm_config" TYPE="DECLARES" />
      <Link TARGET="scripts_start_sh" TYPE="SEEDS_VOLUME" />
    </CrossLinks>
  </deploy_docker_compose_yml>

  <volume_doclingllm_config TYPE="DOCKER_NAMED_VOLUME">
    <annotation>Persistent runtime: gateway-runtime.yaml, docling-serve.yaml (generated). Not in git.</annotation>
  </volume_doclingllm_config>

  <deploy_config_gateway_runtime_defaults_yaml FILE="deploy/config/gateway-runtime.defaults.yaml" TYPE="CONFIG_TEMPLATE">
    <annotation>Shipped defaults for first-time volume seed; no secrets in git.</annotation>
    <CrossLinks>
      <Link TARGET="src_doclingllm_gateway_admin_config_store_py" TYPE="SEED_SOURCE" />
    </CrossLinks>
  </deploy_config_gateway_runtime_defaults_yaml>

  <deploy_config_gateway_models_template_yaml FILE="deploy/config/gateway-models.template.yaml" TYPE="CONFIG_TEMPLATE">
    <annotation>Stage prompts, parsers, paths — read-only in container; merged with runtime on load.</annotation>
  </deploy_config_gateway_models_template_yaml>

  <deploy_config_docling_serve_template_yaml FILE="deploy/config/docling-serve.template.yaml" TYPE="CONFIG_TEMPLATE">
    <annotation>Jinja/YAML template for docling preset URLs → model-gateway:8080.</annotation>
    <CrossLinks>
      <Link TARGET="src_doclingllm_gateway_admin_docling_generator_py" TYPE="RENDERED_BY" />
    </CrossLinks>
  </deploy_config_docling_serve_template_yaml>

  <src_doclingllm_gateway_admin_config_store_py FILE="src/doclingllm/gateway/admin/config_store.py" TYPE="L3_ADAPTATION">
    <annotation>Read/write gateway-runtime.yaml on volume; env fallback; validate pydantic schema.</annotation>
    <save_runtime_config_FUNC NAME="save_runtime_config" TYPE="IS_FUNCTION_OF_MODULE">
      <annotation>Atomic write; triggers docling yaml generation.</annotation>
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_admin_docling_generator_py" TYPE="CALLS_MODULE" />
      </CrossLinks>
    </save_runtime_config_FUNC>
    <load_merged_routing_FUNC NAME="load_merged_routing" TYPE="IS_FUNCTION_OF_MODULE">
      <annotation>Merge runtime + gateway-models.template.yaml → effective routing.</annotation>
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_routing_py" TYPE="USES_API" />
      </CrossLinks>
    </load_merged_routing_FUNC>
  </src_doclingllm_gateway_admin_config_store_py>

  <src_doclingllm_gateway_admin_connection_tester_py FILE="src/doclingllm/gateway/admin/connection_tester.py" TYPE="L3_ADAPTATION">
    <annotation>Probe models list, minimal chat, vision ping, per-stage infer simulation.</annotation>
    <test_all_backends_FUNC NAME="test_all_backends" TYPE="IS_FUNCTION_OF_MODULE">
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_client_py" TYPE="USES_API" />
      </CrossLinks>
    </test_all_backends_FUNC>
  </src_doclingllm_gateway_admin_connection_tester_py>

  <src_doclingllm_gateway_admin_docling_generator_py FILE="src/doclingllm/gateway/admin/docling_generator.py" TYPE="L3_ADAPTATION">
    <annotation>Render docling-serve.yaml to volume path; preview diff for UI.</annotation>
  </src_doclingllm_gateway_admin_docling_generator_py>

  <src_doclingllm_gateway_admin_gradio_ui_py FILE="src/doclingllm/gateway/admin/gradio_ui.py" TYPE="L1_UI">
    <annotation>Gradio tabs: Vision, Text, Stages, Proxy/Timeout, Test and Save. Headless handlers.</annotation>
    <on_save_handler_FUNC NAME="on_save_handler" TYPE="IS_FUNCTION_OF_MODULE">
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_admin_connection_tester_py" TYPE="CALLS_MODULE" />
        <Link TARGET="src_doclingllm_gateway_admin_config_store_py" TYPE="CALLS_MODULE" />
      </CrossLinks>
    </on_save_handler_FUNC>
  </src_doclingllm_gateway_admin_gradio_ui_py>

  <src_doclingllm_gateway_app_py FILE="src/doclingllm/gateway/app.py" TYPE="L1_TRANSPORT">
    <annotation>Mount Gradio at /admin; POST /admin/reload; refresh GatewayState.</annotation>
    <admin_reload_route_FUNC NAME="admin_reload" TYPE="IS_FUNCTION_OF_MODULE">
      <CrossLinks>
        <Link TARGET="src_doclingllm_gateway_admin_config_store_py" TYPE="CALLS_MODULE" />
      </CrossLinks>
    </admin_reload_route_FUNC>
  </src_doclingllm_gateway_app_py>

  <scripts_start_sh FILE="scripts/start.sh" TYPE="DEPLOY_SCRIPT">
    <annotation>Ensure named volume exists; seed gateway-runtime.yaml if missing; compose up.</annotation>
  </scripts_start_sh>
</DraftCodeGraph>
```

---

## 2. Step-by-step Data Flow

### 2.1. First boot (empty volume)

1. **Step 1:** `scripts/start.sh` создаёт volume `doclingllm-config` (compose `external: false`).
2. **Step 2:** Gateway entrypoint/init проверяет `/data/doclingllm/config/gateway-runtime.yaml`.
3. **Step 3:** Если файла нет — seed из `gateway-runtime.defaults.yaml` + **env fallback** (`deploy/.env`: `VISION_*`, `TEXT_*`, proxy, timeout).
4. **Step 4:** Генерация `docling-serve.yaml` на volume из `docling-serve.template.yaml`.
5. **Step 5:** docling-serve стартует с `DOCLING_SERVE_CONFIG_FILE=/data/doclingllm/config/docling-serve.yaml`.

### 2.2. Admin UI — Load

1. **Step 1:** Gradio `/admin` вызывает `load_runtime_config()` → читает volume YAML.
2. **Step 2:** UI заполняет поля: vision URL/key/model, text URL/key/model, per-stage endpoint+model, timeout, proxy.
3. **Step 3:** Keys отображаются **masked** (`sk-…xxxx`); полное значение только в памяти до Save.

### 2.3. Test connection (обязательно перед Save)

1. **Step 1:** User нажимает **Test** → `ConnectionTester.test_all()`.
2. **Step 2:** Vision backend: `GET {base}/models` (или fallback HEAD/health).
3. **Step 3:** Vision: `POST {base}/chat/completions` minimal text `"ping"`.
4. **Step 4:** Vision: multimodal ping (1×1 PNG base64 или skip if model text-only — log warning).
5. **Step 5:** Text backend: те же probes.
6. **Step 6:** Per-stage: для каждой stage из runtime вызвать `resolve_stage_route` + minimal request по mode (openai_vision / openai_text / openai_proxy).
7. **Step 7:** UI показывает таблицу pass/fail/latency; **Save disabled** пока любой обязательный probe failed.

### 2.4. Save + gateway reload

1. **Step 1:** User **Save** (only if tests passed) → `save_runtime_config()` atomic write to volume.
2. **Step 2:** `docling_generator.render()` → `/data/doclingllm/config/docling-serve.yaml`.
3. **Step 3:** UI показывает **preview diff** docling yaml + banner: *«Перезапустите docling-serve: `docker compose restart docling-serve`»*.
4. **Step 4:** Internal `POST /admin/reload` → перечитать runtime + merge template → обновить `GatewayState.routing_table`, `ExternalApiClient` settings, proxy env.
5. **Step 5:** Infer endpoints (`/v2/models/*/infer`, `/v1/chat/completions`) используют новые backends **без** restart gateway container.

### 2.5. docling-serve apply (manual, v1)

1. **Step 1:** Оператор выполняет `docker compose restart docling-serve` (или `./scripts/redeploy.sh` partial).
2. **Step 2:** docling-serve перечитывает yaml с volume.
3. **Step 3:** UI может показать статус «docling config mtime vs running pod» (optional v1.1).

---

## 3. Runtime config schema (`gateway-runtime.yaml` on volume)

```yaml
# /data/doclingllm/config/gateway-runtime.yaml — NOT IN GIT
version: "1"
backends:
  vision:
    base_url: "https://ai-billing.develonica.group/v1"
    api_key: "..."          # stored on volume only
    model: "qwen3.6-35b-a3b"
  text:
    base_url: "http://192.168.101.15:8111/v1"
    api_key: ""
    model: "minimax-m2.7"
gateway:
  request_timeout: 300
  log_level: INFO
proxy:
  http_proxy: ""
  https_proxy: ""
  no_proxy: "localhost,127.0.0.1,model-gateway,docling-serve"
stages:
  ocr:       { endpoint: vision, model: "qwen3.6-35b-a3b" }
  layout:    { endpoint: vision, model: "qwen3.6-35b-a3b" }
  table:     { endpoint: vision, model: "qwen3.6-35b-a3b" }
  picture_classification: { endpoint: vision, model: "..." }
  picture_description:    { endpoint: vision, model: "..." }
  vlm:       { endpoint: vision, model: "..." }
  code_formula: { endpoint: text, model: "minimax-m2.7" }
meta:
  last_test_at: "2026-07-22T08:00:00Z"
  last_test_ok: true
```

**Merge rule:** `gateway-models.template.yaml` (repo, ro) supplies `mode`, `path`, `response_parser`, `system_prompt` per stage; runtime overrides `endpoint` + `model` only (v1 scope).

**Env fallback:** при seed/merge пустые поля runtime ← `GatewaySettings` / `deploy/.env`.

---

## 4. Docker / volume layout

| Mount | Container | Mode | Content |
|-------|-----------|------|---------|
| `doclingllm-config` → `/data/doclingllm/config` | model-gateway | **rw** | `gateway-runtime.yaml`, `docling-serve.yaml` |
| same volume | docling-serve | **ro** | `docling-serve.yaml` |
| `./config/*.template.yaml` | model-gateway | ro | templates only |
| `deploy/.env` | both | env_file | proxy, legacy fallback, compose vars |

```yaml
# deploy/docker-compose.yml (delta)
volumes:
  doclingllm-config:
    name: doclingllm-config

services:
  model-gateway:
    ports:
      - "8080:8080"
    volumes:
      - doclingllm-config:/data/doclingllm/config
      - ./config/gateway-models.template.yaml:/config/templates/gateway-models.template.yaml:ro
      - ./config/docling-serve.template.yaml:/config/templates/docling-serve.template.yaml:ro
    environment:
      DOCLINGLLM_CONFIG_DIR: /data/doclingllm/config
      GATEWAY_RUNTIME_CONFIG: /data/doclingllm/config/gateway-runtime.yaml
      GATEWAY_MODELS_TEMPLATE: /config/templates/gateway-models.template.yaml
      DOCLING_SERVE_TEMPLATE: /config/templates/docling-serve.template.yaml

  docling-serve:
    volumes:
      - doclingllm-config:/data/doclingllm/config:ro
    environment:
      DOCLING_SERVE_CONFIG_FILE: /data/doclingllm/config/docling-serve.yaml
```

**Удалить** bind-mount `./config/gateway-models.yaml` и `./config/docling-serve.yaml` из project folder для runtime (файлы в repo → **templates/defaults only**).

---

## 5. Gradio UI (Hypothesis A)

| Tab | Поля | v1 |
|-----|------|-----|
| Vision | base_url, api_key, model | edit |
| Text | base_url, api_key, model | edit |
| Stages | таблица stage → endpoint dropdown + model | edit |
| Proxy/Timeout | HTTP_PROXY, HTTPS_PROXY, NO_PROXY, GATEWAY_REQUEST_TIMEOUT | edit |
| Test & Save | Run tests, results table, Save, docling preview, reload status | Test gates Save |

**URL:** `http://localhost:8080/admin`  
**Auth v1:** none (dev-only warning in UI header).

**Dependencies (gateway):**

```text
gradio>=5.0,<6.0    # Admin UI mounted in FastAPI; pin after smoke
```

---

## 6. Feature slices (mode-code)

| Slice | Scope | Files | Tests |
|-------|-------|-------|-------|
| **G1** | RuntimeConfig pydantic + ConfigStore (volume R/W, seed, env fallback) | `admin/config_store.py`, `gateway-runtime.defaults.yaml` | `test_gateway_admin_config_store.py` |
| **G2** | Template merge → RoutingTable; refactor `load_routing_table` | `routing.py`, `gateway-models.template.yaml` | `test_gateway_admin_routing_merge.py` |
| **G3** | ConnectionTester (models, chat, vision, per-stage) | `admin/connection_tester.py` | `test_gateway_admin_connection_tester.py` |
| **G4** | docling-serve.yaml generator + template | `admin/docling_generator.py`, `docling-serve.template.yaml` | `test_gateway_admin_docling_generator.py` |
| **G5** | Gradio UI handlers (headless) | `admin/gradio_ui.py` | `test_gateway_admin_gradio_handlers.py` |
| **G6** | app mount `/admin`, `POST /admin/reload`, compose volume + :8080, start.sh seed | `app.py`, `docker-compose.yml`, `start.sh` | `test_compose_config.py` extend |
| **G7** | Docs + test_guide + AppGraph | `docs/`, `plans/` | mode-qa checklist |

**Prompt template (mode-code):**

```text
Load mode-code skill.
Study: plans/GatewayAdminUI.md, plans/Architecture.md
Implement Slice G<N>: ...
Constraints: docling-serve/** read-only; Grace 2 markup; Pattern 4 headless Gradio tests
Deliver: code + tests PASS
```

---

## 7. Acceptance Criteria

- [ ] **AC-G1:** `gateway-runtime.yaml` создаётся на named volume `doclingllm-config`, **не** в git working tree.
- [ ] **AC-G2:** Пустой volume → seed из defaults + env fallback при `start.sh`.
- [ ] **AC-G3:** Gradio `/admin` доступен на `:8080`; поля vision/text/stages/proxy редактируются.
- [ ] **AC-G4:** **Save заблокирован** без успешного `test_all()` (models + chat + vision + per-stage).
- [ ] **AC-G5:** Save → atomic write volume → generate `docling-serve.yaml` on volume → `POST /admin/reload` обновляет routing без restart gateway.
- [ ] **AC-G6:** UI показывает preview docling yaml + текст «restart docling-serve manually»; без auto-restart docling в v1.
- [ ] **AC-G7:** pytest headless: `on_save_handler`, `test_all_backends`, `save_runtime_config` с tmp_path/volume mock — PASS, LDD IMP:9.
- [ ] **AC-G8:** Секреты не попадают в логи gateway (mask keys in `[IMP:*]`).
- [ ] **AC-G9:** `docling-serve/**` без изменений; templates только в `deploy/config/*.template.yaml`.

---

## 8. Риски

| ID | Риск | Митигация |
|----|------|-----------|
| R-G1 | Volume потерян при `docker volume rm` | Document backup `docker run ... tar`; export button v1.1 |
| R-G2 | docling не подхватил yaml без restart | Явный banner + docs; optional health hint v1.1 |
| R-G3 | :8080 без auth — утечка keys | Dev-only warning; keys only on volume; v1.1 GATEWAY_ADMIN_TOKEN |
| R-G4 | Gradio + FastAPI mount conflicts | Pin gradio; mount at `/admin` sub-path; test in G6 |
| R-G5 | Merge template/runtime drift | `test_gateway_admin_routing_merge.py` golden fixtures |

---

## 9. Делегирование

**Порядок:** G1 → G2 → G3 → G4 → G5 → G6 → G7.

**Не начинать mode-code** до явного «утверждаю план» оператора (этот документ).

$END_DEV_PLAN
