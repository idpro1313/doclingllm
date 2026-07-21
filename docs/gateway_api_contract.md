# Gateway API Contract

Контракт между **docling-serve**, **Model Gateway** и внешними API (Cloud.ru + LAN minimax).

## Backends

| Backend | URL (env) | Model | Auth |
|---------|-----------|-------|------|
| vision | `VISION_API_BASE_URL` | `deepseek-ai/DeepSeek-OCR-2` | `VISION_API_KEY` Bearer |
| text | `TEXT_API_BASE_URL` | `minimax-m2.7` | нет |

## Gateway endpoints (internal)

| Method | Path | Consumer |
|--------|------|----------|
| GET | `/health` | docker healthcheck |
| GET | `/v2/models/{name}` | docling api_kserve_v2 metadata probe |
| GET | `/v2/models/{name}/ready` | docling api_kserve_v2 readiness probe |
| POST | `/v2/models/ocr/infer` | docling OCR (kserve_v2) |
| POST | `/v2/models/layout/infer` | docling layout |
| POST | `/v2/models/table/infer` | docling table |
| POST | `/v2/models/picture_classifier/infer` | picture classification |
| POST | `/v1/chat/completions` | VLM, picture_description, code_formula |

## KServe request (vision stages)

```json
{
  "inputs": [
    {
      "name": "image",
      "shape": [1],
      "datatype": "BYTES",
      "data": ["<base64 PNG/JPEG>"]
    }
  ]
}
```

## KServe response

Gateway возвращает JSON в BYTES tensor:

```json
{
  "model_name": "ocr",
  "outputs": [
    {
      "name": "output",
      "shape": [1],
      "datatype": "BYTES",
      "data": ["<base64 UTF-8 JSON>"]
    }
  ]
}
```

### Parsed JSON schemas (после decode)

**OCR** (`deepseek_ocr_json`):

```json
{"text_regions": [{"text": "...", "bbox": [x1, y1, x2, y2]}]}
```

**Layout** (`layout_boxes_json`):

```json
{"boxes": [{"label": "title", "bbox": [x1, y1, x2, y2]}]}
```

**Table** (`table_structure_json`):

```json
{"rows": 2, "cols": 3, "cells": [{"r": 0, "c": 0, "text": "A"}]}
```

**Classification** (`classification_json`):

```json
{"label": "figure", "score": 0.95}
```

## OpenAI proxy

Gateway принимает стандартный `POST /v1/chat/completions` и маршрутизирует:

- `model=minimax-m2.7` → text backend (LAN)
- multimodal messages (image_url) → vision backend
- иначе → VLM preset (Cloud.ru)

Authorization добавляется только для vision backend.

## Deployment

```bash
chmod +x scripts/*.sh   # не нужно, если clone с git (mode 100755)
./scripts/start.sh      # создаст deploy/.env из .env.defaults и запросит VISION_API_KEY
./scripts/redeploy.sh   # git pull → stop → start (обновление на сервере)
./scripts/healthcheck.sh
```

При первом запуске скрипт копирует `deploy/.env.defaults` → `deploy/.env` и **интерактивно запрашивает** Cloud.ru `VISION_API_KEY` (ввод скрыт). Токен сохраняется только в `deploy/.env` (gitignored).

**UI (Gradio demo):** http://localhost:5001/ui — включено через `DOCLING_SERVE_ENABLE_UI=true`.

Секреты только в `deploy/.env` (gitignored).
