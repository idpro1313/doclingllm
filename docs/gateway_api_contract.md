# Gateway API Contract

$START_DOC_NAME

**PURPOSE:** Контракт между **docling-serve**, **Model Gateway** и внешними OpenAI-compatible API (vision Develonica + LAN minimax).
**SCOPE:** HTTP endpoints, KServe tensor layouts, parsers, proxy rules, деплой и observability.
**KEYWORDS:** KServe v2, OpenAI proxy, OCR, layout, gateway, Develonica, minimax, tensors, parsers

$START_DOCUMENT_PLAN
### Document Plan

**SECTION_GOALS:**
- GOAL Зафиксировать backends и env => G_BACKENDS
- GOAL Описать gateway endpoints => G_ENDPOINTS
- GOAL Специфицировать KServe I/O по стадиям => G_KSERVE
- GOAL Описать OpenAI proxy и docling presets => G_OPENAI

**SECTION_USE_CASES:**
- USE_CASE docling-serve → POST /v2/models/ocr/infer => UC_OCR
- USE_CASE docling VLM preset → POST /v1/chat/completions => UC_VLM

$END_DOCUMENT_PLAN

---

$START_SECTION_BACKENDS
## Backends

$START_ARTIFACT_BACKENDS
#### External API backends

**TYPE:** DATA_FORMAT
**KEYWORDS:** vision, text, env

$START_CONTRACT
**PURPOSE:** Единая таблица маршрутизации gateway → внешние API.
**DESCRIPTION:** Значения подставляются из `deploy/.env` и `deploy/config/gateway-models.yaml`.
**RATIONALE:** Секреты только в env; YAML декларативен для stage routing.
**ACCEPTANCE_CRITERIA:** Gateway стартует с loaded routing table; vision auth только для vision backend.
$END_CONTRACT

$START_BODY

| Backend | URL (env) | Model (env) | Auth |
|---------|-----------|-------------|------|
| vision | `VISION_API_BASE_URL` (default `https://ai-billing.develonica.group/v1`) | `VISION_MODEL` (default `qwen3.6-35b-a3b`) | `VISION_API_KEY` Bearer |
| text | `TEXT_API_BASE_URL` | `TEXT_MODEL` (`minimax-m2.7`) | опционально `TEXT_API_KEY` |

Egress proxy (httpx `trust_env=True`): `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`.

Timeout: `GATEWAY_REQUEST_TIMEOUT` (default **300** s) — не ниже KServe OCR timeout в docling-serve.yaml.

$END_BODY

$END_ARTIFACT_BACKENDS
$END_SECTION_BACKENDS

---

$START_SECTION_TRACE
## Gateway TRACE logs

$START_BODY

В логах `model-gateway` (≥0.2.15) ищите по `rid=` или маркерам:

| Маркер | Направление |
|--------|-------------|
| `DOCLING_IN` | docling → gateway (KServe inputs / OpenAI body + framing) |
| `MODEL_OUT` | gateway → vision/text API (prompt, model; image = size placeholder) |
| `MODEL_IN` | model → gateway (текст ответа ассистента, до ~8k) |
| `GATEWAY_OUT` | gateway → docling (KServe tensors summary / OpenAI response) |

`GATEWAY_LOG_LEVEL=INFO` (default). Base64 изображений не дампится.

$END_BODY

$END_SECTION_TRACE

---

$START_SECTION_ENDPOINTS
## Gateway endpoints (internal)

$START_ARTIFACT_GATEWAY_ROUTES
#### HTTP routes

**TYPE:** DATA_FORMAT
**KEYWORDS:** FastAPI, infer, health

$START_BODY

| Method | Path | Consumer |
|--------|------|----------|
| GET | `/health` | docker healthcheck |
| GET | `/v2/models/{name}` | docling api_kserve_v2 metadata probe |
| GET | `/v2/models/{name}/ready` | docling api_kserve_v2 readiness probe |
| POST | `/v2/models/ocr/infer` | docling OCR (`kserve_v2_ocr`) |
| POST | `/v2/models/layout/infer` | docling layout OD (`api_kserve_v2`) |
| POST | `/v2/models/table/infer` | docling table (remote preset) |
| POST | `/v2/models/picture_classifier/infer` | picture classification |
| POST | `/v1/chat/completions` | VLM, picture_description, code_formula |

Upstream connect/TLS errors: HTTP **502** с `UpstreamApiError` detail.

$END_BODY

$END_ARTIFACT_GATEWAY_ROUTES
$END_SECTION_ENDPOINTS

---

$START_SECTION_KSERVE
## KServe stage contracts

$START_ARTIFACT_OCR
#### OCR

**TYPE:** DATA_FORMAT
**KEYWORDS:** boxes, txts, deepseek_ocr_json

$START_BODY

**Request inputs:** `lang_type` (BYTES), `image` (UINT8 shape `[1,H,W,C]` или BYTES PNG).  
docling часто шлёт `application/octet-stream` + `Inference-Header-Content-Length` (binary framing).

**Response outputs** (docling `_create_text_cells` — **без** leading batch axis):

| name | datatype | shape | meaning |
|------|----------|-------|---------|
| boxes | FP32 | `(N, 4, 2)` | quad `[[x0,y0],[x1,y1],[x2,y2],[x3,y3]]` per region |
| txts | BYTES | `(N,)` | text per region |
| scores | FP32 | `(N,)` | confidence |

Parser JSON (`deepseek_ocr_json`):

```json
{"text_regions": [{"text": "...", "bbox": [x1, y1, x2, y2], "score": 0.9}]}
```

При prose-ответе без JSON — fallback с синтетическими bbox (см. gateway parsers).

$END_BODY

$END_ARTIFACT_OCR

$START_ARTIFACT_LAYOUT
#### Layout (object detection)

$START_BODY

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

Gateway clamp/drop invalid boxes перед ответом docling (≥0.2.16).

$END_BODY

$END_ARTIFACT_LAYOUT

$START_ARTIFACT_PICCLASS
#### Picture classifier

$START_BODY

**Request:** `pixel_values` / `images` (FP32) или BYTES image.  
**Response:** `logits` FP32 shape `(B, num_classes)`.

Parser JSON (`classification_json`):

```json
{"label": "figure", "score": 0.95}
```

$END_BODY

$END_ARTIFACT_PICCLASS

$END_SECTION_KSERVE

---

$START_SECTION_OPENAI
## OpenAI proxy

$START_ARTIFACT_PROXY
#### Routing rules

**TYPE:** DECISION
**KEYWORDS:** chat completions, vlm, proxy

$START_CONTRACT
**PURPOSE:** Единая точка `/v1/chat/completions` для docling api engine presets.
**DESCRIPTION:** Gateway маршрутизирует по model/stage из YAML и телу запроса.
**ACCEPTANCE_CRITERIA:** Presets в docling-serve.yaml указывают `http://model-gateway:8080/v1/chat/completions`.
$END_CONTRACT

$START_BODY

| Условие | Backend |
|---------|---------|
| `model` = text model (`minimax-m2.7`) | text LAN |
| multimodal messages (`image_url`) | vision |
| иначе | vision (VLM preset) |

Authorization добавляется только для vision backend. Proxy подставляет `route.model` из `gateway-models.yaml`.

### docling-serve VLM / picture_description / code_formula presets

`url` и `params` — в **`engine_options`**, не в `model_spec.api_overrides`:

```yaml
engine_options:
  engine_type: api
  url: "http://model-gateway:8080/v1/chat/completions"
  params:
    model: qwen3.6-35b-a3b
```

**VLM preset inject (overlay ≥0.2.22):** при `pipeline=vlm` без `vlm_pipeline_preset` overlay inject `default` (Gradio patch + API middleware) — иначе legacy local `ibm-granite/granite-docling-258M`.

$END_BODY

$END_ARTIFACT_PROXY
$END_SECTION_OPENAI

---

$START_SECTION_DEPLOY
## Deployment

$START_BODY

```bash
./scripts/start.sh      # deploy/.env из .env.defaults; prompt VISION_API_KEY
./scripts/redeploy.sh   # git pull → rebuild overlay docling-serve
./scripts/healthcheck.sh
```

**UI (Gradio):** http://localhost:5001/ui — `DOCLING_SERVE_ENABLE_UI=true`.

Секреты только в `deploy/.env` (gitignored).

$START_LINKS
**REQUIRES:** deploy/config/gateway-models.yaml, deploy/config/docling-serve.yaml
**IMPACTS:** plans/Architecture.md §3
$END_LINKS

$END_BODY

$END_SECTION_DEPLOY

$END_DOC_NAME
