# work/

$START_DOC_NAME

**PURPOSE:** Каталог вспомогательных артефактов агента — отчёты, черновики, временные выгрузки для анализа.
**SCOPE:** Правила размещения файлов, gitignore, отличие от канонических каталогов.
**KEYWORDS:** work, agent artifacts, gitignore, reports, drafts

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Запретить мусор в plans/docs/src => G_ISOLATION
- GOAL Указать что не коммитится => G_GIT

$END_DOCUMENT_PLAN

---

$START_SECTION_RULES
## Правила

$START_ARTIFACT_WORK_DIR
#### work/ contract

**TYPE:** PRINCIPLE
**KEYWORDS:** auxiliary, not in git

$START_CONTRACT
**PURPOSE:** Изолировать одноразовые артефакты от продукта репозитория.
**DESCRIPTION:** Сюда: аудиты, сравнения, CSV/JSON для расследований, скриншоты логов. Не сюда: код, планы, human docs.
**RATIONALE:** agent-rules.mdc §7 — канон в `plans/`, `docs/`, `src/`.
**ACCEPTANCE_CRITERIA:** Содержимое `work/` (кроме этого README) в `.gitignore`.
$END_CONTRACT

$START_BODY

| Класть в `work/` | Не класть в `work/` |
|------------------|---------------------|
| отчёты расследований | `DevelopmentPlan.md` |
| временные CSV/JSON | исходники gateway |
| черновики анализа | `docs/HISTORY.md` |

Исключение: оператор явно просит путь в другом каталоге или артефакт должен войти в git.

$END_BODY

$END_ARTIFACT_WORK_DIR

$END_SECTION_RULES

$END_DOC_NAME
