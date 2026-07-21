# Gateway API Contract

Контракт между **docling-serve**, **Model Gateway** и внешними API (Cloud.ru + LAN minimax).

## Backends

| Backend | URL (env) | Model | Auth |
|---------|-----------|-------|------|
| vision | `VISION_API_BASE_URL` | `deepseek-ai/DeepSeek-OCR-2` | `VISION_API_KEY` Bearer |
| text | `TEXT_API_BASE_URL` | `minimax-m2.7` | нет |

Опционально для egress: `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` (httpx `trust_env=True`). При TLS `UNEXPECTED_EOF` к Cloud.ru — сначала сеть/прокси, не контракт KServe.

## Gateway endpoints (internal)

| Method | Path | Consumer |
|--------|------|----------|
| GET | `/health` | docker healthcheck |
| GET | `/v2/models/{name}` | docling api_kserve_v2 metadata probe |
| GET | `/v2/models/{name}/ready` | docling api_kserve_v2 readiness probe |
| POST | `/v2/models/ocr/infer` | docling OCR (`kserve_v2_ocr`) |
| POST | `/v2/models/layout/infer` | docling layout OD (`api_kserve_v2`) |
| POST | `/v2/models/table/infer` | docling table (если remote) |
| POST | `/v2/models/picture_classifier/infer` | picture classification |
| POST | `/v1/chat/completions` | VLM, picture_description, code_formula |

Ошибки upstream (TLS/connect): HTTP **502** с `UpstreamApiError` detail.

## KServe: OCR

**Request inputs:** `lang_type` (BYTES), `image` (UINT8, shape `[1,H,W,C]` или BYTES PNG).  
docling часто шлёт `application/octet-stream` + `Inference-Header-Content-Length` (binary framing).

**Response outputs** (docling `_create_text_cells` — без leading batch axis):

| name | datatype | shape | meaning |
|------|----------|-------|---------|
| boxes | FP32 | `(N, 4, 2)` | quad `[[x0,y0],[x1,y1],[x2,y2],[x3,y3]]` per region |
| txts | BYTES | `(N,)` | text per region |
| scores | FP32 | `(N,)` | confidence |

Parser JSON от vision-модели (`deepseek_ocr_json`):

```json
{"text_regions": [{"text": "...", "bbox": [x1, y1, x2, y2], "score": 0.9}]}
```

## KServe: Layout (object detection)

**Request inputs:** `images` (FP32 pixel values), `orig_target_sizes` (INT64).

**Response outputs** (batch padded):

| name | datatype | shape |
|------|----------|-------|
| labels | INT64 | `(B, N)` |
| boxes | FP32 | `(B, N, 4)` — xyxy |
| scores | FP32 | `(B, N)` |

Parser JSON (`layout_boxes_json`):

```json
{"boxes": [{"label": "title", "bbox": [x1, y1, x2, y2], "score": 0.9}]}
```

## KServe: Picture classifier

**Request:** `pixel_values` / `images` (FP32) или BYTES image.  
**Response:** `logits` FP32 shape `(B, num_classes)`.

Parser JSON (`classification_json`):

```json
{"label": "figure", "score": 0.95}
```

## OpenAI proxy

Gateway принимает `POST /v1/chat/completions` и маршрутизирует:

- `model=minimax-m2.7` → text backend (LAN)
- multimodal messages (`image_url`) → vision backend
- иначе → VLM preset (Cloud.ru)

Authorization добавляется только для vision backend.

### docling-serve VLM / picture_description / code_formula presets

`url` и `params` должны быть в **`engine_options`**, не в `model_spec.api_overrides` (иначе default Ollama `localhost:11434`).

```yaml
engine_options:
  engine_type: api
  url: "http://model-gateway:8080/v1/chat/completions"
  params:
    model: deepseek-ai/DeepSeek-OCR-2
```

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
