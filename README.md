# Шаблон проекта Grace 2.0

Стартовый каркас для AI-разработки по **KiloCode Prompt Framework 2.0.0** (ветка Grace 2.0).  
Источник фреймворка: папка [`Grace 2.0`](../Grace%202.0) в этом workspace.  
Пакет **grace-dev-compilation (GRACE 1.0)** в этом шаблоне **не используется**.

## Что внутри

| Путь | Назначение |
|------|------------|
| [`.kilocode/`](.kilocode/) | Kilo Code: `rules/rules.md`, 8 skills в `skill/`, `agents/`, `mcp.json` |
| [`.cursor/`](.cursor/) | Cursor: те же 8 skills в `skills/`, правила в `rules/grace-2-framework.mdc`, `agents/` |
| `kilo.json`, `kilo.jsonc` | Права Kilo CLI и `instructions`; **локально**, в `.gitignore` |
| `Doxyfile` | Doxygen (`INPUT`, XML в `doxygen_output/`); **локально**, в `.gitignore` |
| `Prompts.xml` | Мета-карта фреймворка (skills ↔ rules); **локально**, в `.gitignore` |
| [`docs/`](docs/) | `README.md`, `HISTORY.md`, гайды |
| [`plans/`](plans/) | Карта агента: `DevelopmentPlan.md`, `AppGraph.xml` |
| [`VERSION`](VERSION) | SemVer для коммитов |
| `.cursor/rules/agent-rules.mdc` | Навигация и ops для агента (§2 — без корневого `AGENTS.md`) |
| `.cursor/rules/agent-rules.mdc` | Ops: журнал, git, среда (дополняет Grace 2) |
| [`plans/`](plans/) | Сюда Architect создаёт `DevelopmentPlan.md`, `business_requirements.md` |
| [`tests/`](tests/) | Централизованные тесты; для QA нужен `tests/test_guide.md` |
| [`src/`](src/) | Исходный код приложения |

## Быстрый старт

1. Скопируйте всю папку `_template 2.0` в каталог нового проекта (или переименуйте в корень репозитория).
2. Откройте проект в **Cursor** или **Kilo Code**.
3. Начните **новую сессию** агента, чтобы подхватились rules/skills.
4. Дайте задачу на разработку — агент должен войти в фазу **Architect**: `skill(mode-architect)` / skill `mode-architect`.
5. После утверждения плана — `mode-code` → при сбоях `mode-debug` → `mode-qa` (когда есть `tests/test_guide.md`).

## Workflow (Grace 2.0)

```text
Новая задача → mode-architect → (утверждённый план) → mode-code
  → при ошибках mode-debug → mode-qa
```

Обязательно вызывать skill соответствующей фазы; иначе **CRITICAL_RULE_VIOLATION** (см. `.kilocode/rules/rules.md`).

## Kilo Code vs Cursor

| | Kilo Code | Cursor |
|--|-----------|--------|
| Rules | `.kilocode/rules/rules.md`, `agent-rules.md` | `.cursor/rules/grace-2-framework.mdc`, `agent-rules.mdc` |
| Skills | `.kilocode/skill/<name>/SKILL.md` | `.cursor/skills/<name>/SKILL.md` |
| Субагент | `.kilocode/agents/grok_searcher.md` | `.cursor/agents/grok_searcher.md` |
| Конфиг | `kilo.json` + опц. `kilo.jsonc` | встроенная загрузка `.cursor/` |

Имена skills одинаковые: `mode-architect`, `mode-code`, `mode-debug`, `mode-qa`, `graph-protocol`, `devplan-protocol`, `document-protocol`, `data-transform`.

## Субагент grok_searcher

Гайд: [`docs/subagent_setup_guide.md`](docs/subagent_setup_guide.md).  
Профиль лежит в `.kilocode/agents/` и `.cursor/agents/`.  
Документ также упоминает `.kilo/agents/` — создайте эту папку при использовании **Kilo CLI**, если `task()` не видит профиль в `.kilocode/agents/`.

## Отличие от GRACE 1.0

- Нет `$grace-init`, нет `docs/*.xml`, нет `START_*` как канона кода.
- План: markdown в `plans/`, граф: `AppGraph.xml` / draft в плане.
- Разметка кода: `# region` + Doxygen + `GREP_SUMMARY` / `STRUCTURE`.

Сравнение с GRACE 1.0: см. план `grace_2.0_vs_dev-compilation` в workspace Cursor (если есть).
