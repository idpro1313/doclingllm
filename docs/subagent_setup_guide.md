# Настройка поисковых субагентов (OpenRouter & Kilo Gateway)

$START_DOC_NAME

**PURPOSE:** Настроить «дешёвые» поисковые субагенты (grok_searcher) для сбора контекста без расхода основной модели.
**SCOPE:** Kilo CLI, регистрация моделей, профили агентов, вызов через `task()`.
**KEYWORDS:** grok_searcher, Kilo CLI, OpenRouter, subagent, task, semantic search

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Объяснить наследование моделей в task() => G_INHERITANCE
- GOAL Описать регистрацию моделей и профилей => G_SETUP
- GOAL Дать пример оркестрации => G_USAGE

$END_DOCUMENT_PLAN

---

$START_SECTION_PROBLEM
## 1. Проблема наследования моделей

$START_ARTIFACT_INHERITANCE
#### Model inheritance

**TYPE:** DECISION
**KEYWORDS:** task tool, subagent

$START_CONTRACT
**PURPOSE:** Явно маршрутизировать субагента на дешёвую LLM.
**DESCRIPTION:** По умолчанию `task` в Kilo CLI наследует модель родителя. UI-команды вроде `/ask` внутри параметров инструмента модель не переключают.
**RATIONALE:** Нужен профиль агента + регистрация модели в реестре.
**ACCEPTANCE_CRITERIA:** `subagent_type` указывает на файл в `agents/` с явным `model:` в frontmatter.
$END_CONTRACT

$END_ARTIFACT_INHERITANCE

$END_SECTION_PROBLEM

---

$START_SECTION_REGISTRY
## 2. Регистрация моделей

$START_BODY

Модель должна быть в глобальном `~/.config/kilo/kilo.jsonc`:

```jsonc
"provider": {
  "kilo": {
    "models": {
      "x-ai/grok-code-fast-1:optimized:free": {
        "name": "Grok Code Fast 1",
        "limit": { "context": 128000, "output": 4096 }
      }
    }
  },
  "openrouter": {
    "models": {
      "nvidia/nemotron-3-nano-30b-a3b:free": {
        "name": "Nemotron 3 Nano",
        "limit": { "context": 128000, "output": 4096 }
      }
    }
  }
}
```

После изменения `kilo.jsonc` — полная перезагрузка CLI.

$END_BODY

$END_SECTION_REGISTRY

---

$START_SECTION_PROFILE
## 3. Профиль субагента

$START_BODY

Профили в репозитории:

| Среда | Путь |
|-------|------|
| Cursor | [`.cursor/agents/grok_searcher.md`](../.cursor/agents/grok_searcher.md) |
| Kilo Code | [`.kilocode/agents/grok_searcher.md`](../.kilocode/agents/grok_searcher.md) |
| Kilo CLI | `.kilo/agents/` — создать при необходимости |

Пример frontmatter:

```yaml
---
description: Поисковый субагент на базе Grok
mode: subagent
model: "kilo/x-ai/grok-code-fast-1:optimized:free"
temperature: 0.1
steps: 5
permission:
  edit: deny
  write: deny
  bash:
    "*": deny
    "grep *": allow
    "ls *": allow
  read: allow
  glob: allow
---
Ты — поисковый субагент. Находи файлы, читай GREP_SUMMARY/STRUCTURE и # region.
Отвечай кратко. Не изменяй файлы.
```

$END_BODY

$END_SECTION_PROFILE

---

$START_SECTION_USAGE
## 4. Оркестрация

$START_BODY

```python
task(
    subagent_type="grok-searcher",
    prompt="Найди GREP_SUMMARY в src/doclingllm/gateway/",
    description="Архитектурный поиск через Grok",
)
```

**Нюансы:**

- Префиксы модели: `kilo/`, `openrouter/`
- ID модели с `:` — в кавычках в YAML
- `permission: edit: deny` — субагент не пишет в репозиторий
- Субагент наследует project rules (Grace 2, `IMP` logging)

$END_BODY

$END_SECTION_USAGE

$END_DOC_NAME
