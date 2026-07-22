# doclingllm

$START_DOC_NAME

**PURPOSE:** Точка входа в репозиторий — обёртка вокруг read-only `docling-serve` с Model Gateway для выноса всех ML-стадий во внешние OpenAI-compatible API без правок vendor-кода.
**SCOPE:** Быстрый старт, навигация по документации, Grace 2 workflow, деплой на Ubuntu/Docker.
**KEYWORDS:** docling-serve, Model Gateway, KServe v2, Docker, Grace 2, remote inference, Develonica, minimax

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Дать оператору команды запуска и обновления => G_QUICKSTART
- GOAL Указать карту документации для людей и агентов => G_NAV
- GOAL Зафиксировать Grace 2 workflow => G_WORKFLOW

**SECTION_USE_CASES:**
- USE_CASE Operator → git clone → start.sh → convert PDF => UC_DEPLOY
- USE_CASE Agent → plans/ → mode-architect/code => UC_DEV

$END_DOCUMENT_PLAN

---

$START_SECTION_OVERVIEW
## Обзор

$START_ARTIFACT_PROJECT
#### doclingllm

**TYPE:** GOAL
**KEYWORDS:** docling, gateway, adapter

$START_CONTRACT
**PURPOSE:** Конвертация документов через официальный API docling-serve с удалённым инференсом.
**DESCRIPTION:** Два контейнера: `docling-serve-cpu` (оркестрация пайплайна Docling) и `model-gateway` (адаптер KServe v2 ↔ OpenAI). Каталог `docling-serve/` — vendor read-only; кастомизация через `deploy/` overlay и `src/doclingllm/`.
**RATIONALE:** Сохранить совместимость с upstream и обновляемость vendor без форка.
**ACCEPTANCE_CRITERIA:** `docling-serve/**` без изменений в git; все remote-стадии идут через gateway.
$END_CONTRACT

$START_BODY

| Компонент | Порт | Роль |
|-----------|------|------|
| docling-serve | `:5001` | HTTP API, Gradio UI `/ui`, очередь задач |
| model-gateway | `:8080` (internal) | KServe + OpenAI proxy → vision/text API |

**Версия:** см. [`VERSION`](VERSION) (текущая SemVer для коммитов).

$END_BODY

$START_LINKS
**REQUIRES:** plans/business_requirements.md, plans/Architecture.md
**IMPLEMENTS:** docs/gateway_api_contract.md
$END_LINKS

$END_ARTIFACT_PROJECT
$END_SECTION_OVERVIEW

---

$START_SECTION_QUICKSTART
## Быстрый старт (Ubuntu + Docker)

$START_ARTIFACT_DEPLOY
#### Деплой

**TYPE:** USE_CASE
**KEYWORDS:** docker compose, start.sh, redeploy

$START_BODY

```bash
git clone https://github.com/idpro1313/doclingllm.git
cd doclingllm
./scripts/start.sh          # первый запуск: deploy/.env + prompt VISION_API_KEY
./scripts/healthcheck.sh
```

Обновление на сервере:

```bash
./scripts/redeploy-fast.sh    # быстро: pull + rebuild gateway (Docker cache)
./scripts/redeploy.sh         # полный: pull → stop → rebuild всего стека
```

**`redeploy-fast.sh`** (по умолчанию только `model-gateway`, без `--no-cache`):

| Опция | Действие |
|-------|----------|
| *(без флагов)* | `git pull` → build gateway → up |
| `--all` | оба сервиса |
| `--docling` | только docling-serve overlay |
| `--no-build` | pull + restart без rebuild (config/.env) |
| `--no-pull` | без git pull |

```bash
./scripts/redeploy-fast.sh --no-build   # после Save в Admin UI
./scripts/redeploy-fast.sh --all        # после смены base image docling-serve
```

После старта:

| URL | Назначение |
|-----|------------|
| http://localhost:5001/docs | OpenAPI docling-serve |
| http://localhost:5001/ui | Gradio demo |
| http://localhost:8080/admin | Gateway Admin UI (Gradio) |
| http://localhost:5001/v1/convert/* | API конвертации |

Секреты — только в `deploy/.env` (gitignored). Шаблон: `deploy/.env.defaults`.

**Производительность remote VLM:** sync UI/API ждёт до `DOCLING_SERVE_MAX_SYNC_WAIT` секунд (по умолчанию **600**). Gateway ограничивает structured-стадии (`ocr`, `layout`, …) через `max_tokens` в `gateway-models.template.yaml`, чтобы reasoning-модели не тратили минуты на короткий JSON. Для OCR/layout предпочтительна быстрая vision-модель без reasoning (например `qwen3.6-35b-a3b`), не `kimi-k2-6`.

$END_BODY

$END_ARTIFACT_DEPLOY
$END_SECTION_QUICKSTART

---

$START_SECTION_REPO
## Структура репозитория

$START_BODY

| Путь | Назначение | Аудитория |
|------|------------|-----------|
| [`src/doclingllm/`](src/) | Model Gateway (Python) | Code-агент |
| [`deploy/`](deploy/) | Docker, YAML, overlay docling-serve | Operator / Code |
| [`scripts/`](scripts/) | start, stop, redeploy, healthcheck | Operator |
| [`plans/`](plans/) | DevelopmentPlan, Architecture, AppGraph | **Agent (Grace 2)** |
| [`docs/`](docs/) | Документация для людей, контракты, гайды | Human + Agent |
| [`tests/`](tests/) | pytest, `test_guide.md` | mode-qa |
| [`work/`](work/) | Вспомогательные артефакты агента (не в git) | Agent |
| `docling-serve/` | Vendor read-only | Reference only |

$END_BODY

$END_SECTION_REPO

---

$START_SECTION_DOCS
## Документация

$START_BODY

| Документ | Назначение |
|----------|------------|
| [`docs/README.md`](docs/README.md) | Обзор для людей, стек, индекс гайдов |
| [`docs/gateway_api_contract.md`](docs/gateway_api_contract.md) | Контракт gateway ↔ docling ↔ API |
| [`plans/DevelopmentPlan.md`](plans/DevelopmentPlan.md) | План разработки (devplan-protocol) |
| [`plans/Architecture.md`](plans/Architecture.md) | C4, слои, sequence, slices |
| [`plans/business_requirements.md`](plans/business_requirements.md) | Бизнес-ограничения |
| [`tests/test_guide.md`](tests/test_guide.md) | QA (mode-qa) |
| [`docs/HISTORY.md`](docs/HISTORY.md) | Журнал итераций |

Upstream docling-serve: [`docling-serve/README.md`](docling-serve/README.md) (не редактируется).

$END_BODY

$END_SECTION_DOCS

---

$START_SECTION_GRACE
## Grace 2 workflow

$START_BODY

```text
Новая задача → mode-architect (plans/) → утверждённый план → mode-code (src/, deploy/)
  → при сбоях mode-debug → mode-qa (tests/test_guide.md)
```

- **Rules:** `.cursor/rules/grace-2-framework.mdc`, `.cursor/rules/agent-rules.mdc`, `.cursor/rules/doclingllm.mdc`
- **Skills:** `mode-architect`, `mode-code`, `mode-debug`, `mode-qa`, `devplan-protocol`, `graph-protocol`, `document-protocol`
- **Разметка кода:** `# region` + Doxygen `## @*` + `# GREP_SUMMARY:` + `# STRUCTURE:`

Подробнее: [`docs/README.md`](docs/README.md).

$END_BODY

$END_SECTION_GRACE

$END_DOC_NAME
