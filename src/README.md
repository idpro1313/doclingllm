# src/

$START_DOC_NAME

**PURPOSE:** Навигация по исходному коду приложения doclingllm (Model Gateway).
**SCOPE:** Структура `src/doclingllm/`, соглашения Grace 2, связь с plans/ и tests/.
**KEYWORDS:** doclingllm, gateway, kserve, parsers, Grace 2, semantic markup

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Описать layout пакета gateway => G_LAYOUT
- GOAL Зафиксировать правила разметки кода => G_MARKUP

$END_DOCUMENT_PLAN

---

$START_SECTION_LAYOUT
## Структура

$START_BODY

```text
src/doclingllm/
└── gateway/
    ├── app.py           # L1 FastAPI routes, lifespan
    ├── kserve.py        # L2 KServe decode/encode
    ├── openai_proxy.py  # L2 OpenAI pass-through
    ├── routing.py       # L3 stage → endpoint
    ├── client.py        # L4 httpx outbound
    ├── config.py        # L4 env + YAML
    └── parsers/         # L3 LLM text → tensors
```

Слои: см. [`plans/Architecture.md`](../plans/Architecture.md) §2.

Новые модули — только в фазе **Code** (`mode-code`) по утверждённому [`plans/DevelopmentPlan.md`](../plans/DevelopmentPlan.md).

$END_BODY

$END_SECTION_LAYOUT

---

$START_SECTION_MARKUP
## Grace 2 разметка

$START_ARTIFACT_MARKUP
#### Semantic exoskeleton

**TYPE:** PRINCIPLE
**KEYWORDS:** region, GREP_SUMMARY, STRUCTURE, Doxygen

$START_CONTRACT
**PURPOSE:** Zero-context survival для последующих агентов.
**DESCRIPTION:** Каждый модуль: `# region MODULE_CONTRACT`, `## @purpose`, `# GREP_SUMMARY:`, `# STRUCTURE:`; функции — `# region FUNC_*`, LDD `[IMP:n][func][BLOCK]`.
**RATIONALE:** grace-2-framework.mdc — навигация grep/Doxygen без чтения всего файла.
**ACCEPTANCE_CRITERIA:** Новый код без legacy `START_MODULE_CONTRACT` / `# PURPOSE:` без миграции.
$END_CONTRACT

$END_ARTIFACT_MARKUP

$END_SECTION_MARKUP

$END_DOC_NAME
