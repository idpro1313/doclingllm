# Решение проблемы «Import could not be resolved» (Python / IDE)

$START_DOC_NAME

**PURPOSE:** Устранить расхождение между интерпретатором IDE (venv) и окружением, куда агент ставит пакеты.
**SCOPE:** Windows + VS Code/Cursor; диагностика и установка в правильный venv.
**KEYWORDS:** venv, ModuleNotFoundError, pip, VS Code interpreter, Python

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Описать симптом и причину => G_DIAGNOSIS
- GOAL Дать шаги для агента => G_AGENT_FIX
- GOAL Дать рекомендацию пользователю => G_USER

$END_DOCUMENT_PLAN

---

$START_SECTION_PROBLEM
## Описание проблемы

$START_ARTIFACT_SYMPTOM
#### Symptom

**TYPE:** USE_CASE
**KEYWORDS:** import error, venv empty

$START_CONTRACT
**PURPOSE:** Быстро распознать mismatch global vs venv.
**DESCRIPTION:** Агент ставит пакеты в global Python; IDE использует `./venv/Scripts/python.exe` с пустым site-packages → `Import could not be resolved` / `ModuleNotFoundError`.
**ACCEPTANCE_CRITERIA:** `.\venv\Scripts\python.exe -m pip list` содержит нужные пакеты после fix.
$END_CONTRACT

$END_ARTIFACT_SYMPTOM

$END_SECTION_PROBLEM

---

$START_SECTION_DIAGNOSIS
## Диагностика

$START_BODY

1. **Интерпретатор:** правый нижний угол IDE или `where python` — путь в `venv/Scripts/python.exe`?
2. **Пакеты в venv:** `.\venv\Scripts\python.exe -m pip list` — если только pip/setuptools, venv пуст.
3. **Блокировка файлов:** `OSError: [WinError 32]` — процессы Python держат DLL.

$END_BODY

$END_SECTION_DIAGNOSIS

---

$START_SECTION_AGENT
## Решение для агента

$START_BODY

1. Завершить процессы Python перед установкой:

   ```cmd
   taskkill /F /IM python.exe /T
   ```

2. Установка **в venv**:

   ```cmd
   .\venv\Scripts\python.exe -m pip install -e ".[dev]"
   ```

3. Верификация:

   ```cmd
   .\venv\Scripts\python.exe -c "import pytest; print(pytest.__version__)"
   ```

Для doclingllm gateway-тестов достаточно `pip install -e ".[dev]"` в venv проекта.

$END_BODY

$END_SECTION_AGENT

---

$START_SECTION_USER
## Рекомендация пользователю

$START_BODY

`Ctrl+Shift+P` → **Python: Select Interpreter** → выбрать `./venv/Scripts/python.exe` проекта doclingllm.

$END_BODY

$END_SECTION_USER

$END_DOC_NAME
