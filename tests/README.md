# tests/

$START_DOC_NAME

**PURPOSE:** Навигация по тестам doclingllm и связь с фазой QA (mode-qa).
**SCOPE:** Расположение pytest, naming, test_guide, Anti-Loop.
**KEYWORDS:** pytest, test_guide, mode-qa, gateway, LDD, Anti-Loop

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Описать layout тестов => G_LAYOUT
- GOAL Указать QA entry point => G_QA

$END_DOCUMENT_PLAN

---

$START_SECTION_LAYOUT
## Расположение

$START_BODY

Все тесты — **в корневой папке `tests/`** (не внутри `src/`).

| Паттерн | Пример |
|---------|--------|
| `tests/test_<module>.py` | `test_gateway_kserve.py` |
| fixtures | `tests/fixtures/` (если есть) |
| conftest | `tests/conftest.py` — Anti-Loop counter |

Запуск:

```powershell
pip install -e ".[dev]"
python -m pytest tests/ -s -v
```

$END_BODY

$END_SECTION_LAYOUT

---

$START_SECTION_QA
## mode-qa

$START_ARTIFACT_TEST_GUIDE
#### Independent verification

**TYPE:** USE_CASE
**KEYWORDS:** test_guide, checklist

$START_CONTRACT
**PURPOSE:** Независимая верификация после mode-code.
**DESCRIPTION:** QA-агент загружает skill **`mode-qa`** и следует [`test_guide.md`](test_guide.md).
**ACCEPTANCE_CRITERIA:** `pytest tests/ -s -v` — PASS; checklist в test_guide выполнен.
$END_CONTRACT

$START_BODY

- [`test_guide.md`](test_guide.md) — scope, LDD markers IMP:9–10, deploy validation, smoke checklist
- Subagent verification: prompt должен содержать «Load mode-qa skill»

$END_BODY

$END_ARTIFACT_TEST_GUIDE

$END_SECTION_QA

$END_DOC_NAME
