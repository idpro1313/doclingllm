# plans/

$START_DOC_NAME

**PURPOSE:** Навигация по артефактам планирования Grace 2 для Architect-агента и оператора.
**SCOPE:** Обязательные и опциональные файлы в `plans/`, протоколы, порядок работы mode-architect → mode-code.
**KEYWORDS:** DevelopmentPlan, AppGraph, Architecture, business_requirements, devplan-protocol, graph-protocol, document-protocol

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Перечислить обязательные артефакты plans/ => G_ARTIFACTS
- GOAL Указать протоколы и skills => G_PROTOCOLS
- GOAL Зафиксировать gate перед mode-code => G_GATE

$END_DOCUMENT_PLAN

---

$START_SECTION_ARTIFACTS
## Артефакты

$START_BODY

| Файл | Протокол | Статус | Назначение |
|------|----------|--------|------------|
| [`DevelopmentPlan.md`](DevelopmentPlan.md) | devplan-protocol | **обязателен** | Draft Code Graph, data flow, acceptance criteria, slices |
| [`Architecture.md`](Architecture.md) | document-protocol | **обязателен** | C4, слои L1–L4, sequence, deploy, S1–S8 |
| [`AppGraph.xml`](AppGraph.xml) | graph-protocol | **обязателен** | XML knowledge graph кодовой базы |
| [`business_requirements.md`](business_requirements.md) | document-protocol | по необходимости | Ограничения C1–C7, NFR |

$END_BODY

$END_SECTION_ARTIFACTS

---

$START_SECTION_WORKFLOW
## Workflow Architect

$START_ARTIFACT_GATE
#### Gate mode-code

**TYPE:** PRINCIPLE
**KEYWORDS:** mode-architect, approval

$START_CONTRACT
**PURPOSE:** Запретить реализацию без согласованного плана.
**DESCRIPTION:** mode-code стартует только после утверждения `DevelopmentPlan.md` оператором и наличия `Architecture.md` для нетривиальных задач.
**RATIONALE:** Grace 2 PHASE ACTIVATION PROTOCOL — CRITICAL_RULE_VIOLATION при пропуске architect.
**ACCEPTANCE_CRITERIA:** План содержит `$START_DEV_PLAN`, Draft Code Graph (XML), acceptance criteria.
$END_CONTRACT

$START_BODY

1. Загрузить skill **`mode-architect`**.
2. Обновить `DevelopmentPlan.md` (devplan-protocol) и при необходимости `Architecture.md` (document-protocol).
3. Обновить `AppGraph.xml` через **`graph-protocol`** при изменении модулей.
4. Согласовать с оператором → **`mode-code`**.

Human docs: [`docs/README.md`](../docs/README.md).  
Журнал: [`docs/HISTORY.md`](../docs/HISTORY.md).

$END_BODY

$END_ARTIFACT_GATE

$END_SECTION_WORKFLOW

$END_DOC_NAME
