# Документация проекта

> Карта для агентов — **`plans/`** (Grace 2): `DevelopmentPlan.md`, `AppGraph.xml`. Журнал — **`docs/HISTORY.md`**.

## Обзор

(Опишите назначение проекта для людей: 2–3 предложения.)

## Стек

(Языки, фреймворки, запуск и деплой.)

## Структура репозитория

| Путь | Назначение |
|------|------------|
| `src/` | Исходный код |
| `plans/` | План и граф для агента (Grace 2) |
| `tests/` | Тесты, `test_guide.md` для mode-qa |
| `docs/` | Эта документация, `HISTORY.md`, гайды |
| `work/` | Вспомогательные артефакты агента (отчёты, черновики); **не в git** |
| `.cursor/`, `.kilocode/` | Grace 2: rules, skills (**локально**, в `.gitignore`) |

## Версия

Файл **`VERSION`** в корне (SemVer).

## Гайды в `docs/`

- [`subagent_setup_guide.md`](subagent_setup_guide.md)
- [`environment_fix_guide.md`](environment_fix_guide.md)

## Правила агента

- **Grace 2:** `.cursor/rules/grace-2-framework.mdc`, skills `mode-architect` → `mode-code` → `mode-debug` → `mode-qa`
- **Ops:** `.cursor/rules/agent-rules.mdc`; пользовательские правила — **`.cursor/rules/<имя_проекта>.mdc`** (§8, один файл)
