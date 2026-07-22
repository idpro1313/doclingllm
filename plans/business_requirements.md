# Бизнес-требования: doclingllm

$START_DOC_NAME

**PURPOSE:** Зафиксировать целевое поведение сервиса doclingllm — запуск docling-serve в Docker на Ubuntu с выносом всех ML-моделей во внешний API без изменения исходников docling-serve.
**SCOPE:** Развёртывание, конфигурация, адаптер моделей, эксплуатация.
**KEYWORDS:** docling-serve, remote inference, OpenAI-compatible, KServe v2, Docker, Ubuntu, CPU

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Обеспечить конвертацию документов через docling-serve API => G1
- GOAL Исключить локальный инференс моделей в runtime => G2
- GOAL Сохранить docling-serve/read-only => G3
- GOAL Развёртывание одной командой на Ubuntu => G4

**SECTION_USE_CASES:**
- USE_CASE Оператор запускает сервис скриптом на Ubuntu => UC1
- USE_CASE Клиент вызывает POST /v1/convert/file => UC2
- USE_CASE Все стадии пайплайна обращаются к внешнему API через шлюз => UC3

$END_DOCUMENT_PLAN

$START_SECTION_CONSTRAINTS
### Ограничения и допущения

$START_ARTIFACT_CONSTRAINTS
#### Ограничения

**TYPE:** PRINCIPLE
**KEYWORDS:** immutability, docling-serve, vendor

$START_CONTRACT
**PURPOSE:** Зафиксировать жёсткие границы проекта.
**DESCRIPTION:** Каталог `docling-serve/` — read-only vendor-копия. Запрещены патчи, форки и runtime-override исходников. Допустимы только: официальный образ, монтирование конфигов, env vars, docker-compose, отдельные сервисы-обёртки в `src/` и `deploy/`.
**RATIONALE:** Требование заказчика; снижение стоимости сопровождения при обновлении upstream.
**ACCEPTANCE_CRITERIA:** В git diff отсутствуют изменения внутри `docling-serve/**`.
$END_CONTRACT

$START_BODY
| ID | Ограничение |
|----|-------------|
| C1 | `docling-serve/**` не изменяется |
| C2 | Целевая ОС — Ubuntu Server, запуск через bash-скрипт |
| C3 | Сервер CPU-only (образ `docling-serve-cpu` или эквивалент) |
| C4 | Два OpenAI-compatible backend'а: vision Develonica (`VISION_*`) + LAN minimax (text) |
| C5 | Все стадии пайплайна (OCR, layout, table, VLM, picture, code/formula) — через удалённый инференс |
| C6 | Vision: `VISION_MODEL` (default `qwen3.6-35b-a3b`), Bearer `VISION_API_KEY` в `deploy/.env` |
| C7 | LAN text: `minimax-m2.7` @ `http://192.168.101.15:8111/v1`, без токена |
$END_BODY

$END_ARTIFACT_CONSTRAINTS

$START_ARTIFACT_TECH_REALITY
#### Техническая реальность docling

**TYPE:** DECISION
**KEYWORDS:** KServe v2, OpenAI API, adapter

$START_CONTRACT
**PURPOSE:** Согласовать требование «все модели через API» с возможностями docling без правок serve.
**DESCRIPTION:** docling-serve нативно поддерживает OpenAI-compatible API только для VLM/picture description/code-formula. OCR/layout/table в docling поддерживают удалённый инференс через KServe v2 (Triton-compatible), не через `/v1/chat/completions`. Поэтому проект doclingllm включает **Model Gateway** — отдельный сервис, реализующий KServe v2 для docling и транслирующий вызовы в custom API заказчика по контракту адаптера.
**RATIONALE:** Единственный путь выполнить C5 без модификации docling-serve.
**ACCEPTANCE_CRITERIA:** Gateway покрывает все стадии; docling-serve настроен только env/YAML.
$END_CONTRACT

$END_ARTIFACT_TECH_REALITY

$END_SECTION_CONSTRAINTS

$START_SECTION_NFR
### Нефункциональные требования

$START_ARTIFACT_NFR
#### NFR

**TYPE:** NFR
**KEYWORDS:** docker, secrets, observability

$START_CONTRACT
**PURPOSE:** Эксплуатационные требования.
**DESCRIPTION:** Секреты только в `.env` (не в git). Healthcheck контейнеров. JSON-логи docling-serve в production. Скрипт `scripts/start.sh` идempotent (повторный запуск безопасен).
**ACCEPTANCE_CRITERIA:** `scripts/start.sh` + `curl /health` успешны на чистом Ubuntu с Docker.
$END_CONTRACT

$END_ARTIFACT_NFR

$END_SECTION_NFR

$END_DOC_NAME
