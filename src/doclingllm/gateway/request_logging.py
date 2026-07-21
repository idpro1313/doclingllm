# region MODULE_CONTRACT [DOMAIN(8): Logging; CONCEPT(9): RequestTrace, Sanitize; TECH(9): logging, contextvars]
## @modulecontract
## @purpose Emit correlated DOCLING_IN / MODEL_OUT / MODEL_IN / GATEWAY_OUT traces so operators see the full gateway hop without secrets or raw images.
## @invariants
## - Authorization and raw API keys are NEVER logged.
## - Large base64/image payloads are size placeholders; short text BYTES are shown.
## @changes
## LAST_CHANGE: [v0.2.15 – request_id correlation, configure logging, richer TEXT previews, TRACE banners.]
## @modulemap
## FUNC 9[Configure root gateway logging] => configure_gateway_logging
## FUNC 8[Begin correlated request trace] => begin_request_trace
## FUNC 8[Summarize KServe infer body] => summarize_kserve_infer_request
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: request logging, DOCLING_IN, MODEL_OUT, MODEL_IN, GATEWAY_OUT, request_id, TRACE, sanitize
# STRUCTURE: ▶ begin_trace(rid) → ⊕ DOCLING_IN → ⊕ MODEL_OUT → ⊕ MODEL_IN → ⊕ GATEWAY_OUT → ⎋ clear

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Optional

MAX_TEXT_PREVIEW = 8000
MAX_NUMERIC_SAMPLE = 12
MAX_BYTES_PREVIEW_CHARS = 120
MAX_SHORT_TEXT_BYTES = 512

_request_id_var: ContextVar[str] = ContextVar("gateway_request_id", default="-")
_logging_configured = False

logger = logging.getLogger(__name__)


# region FUNC_configure_gateway_logging [DOMAIN(9): Logging; CONCEPT(9): Bootstrap; TECH(9): logging]
## @purpose Attach a stdout handler to doclingllm loggers so TRACE lines appear in docker logs (uvicorn alone is not enough).
## @complexity 4
def configure_gateway_logging(level_name: str = "INFO") -> None:
    global _logging_configured
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # BUG_FIX_CONTEXT: uvicorn alone prints access lines only; attach StreamHandler to
    # package logger so DOCLING_IN/MODEL_*/GATEWAY_OUT appear in docker logs.
    # Keep propagate=True so pytest caplog still sees records via root.
    package_logger = logging.getLogger("doclingllm")
    package_logger.setLevel(level)
    has_stream = any(
        isinstance(existing, logging.StreamHandler) and getattr(existing, "stream", None) is sys.stdout
        for existing in package_logger.handlers
    )
    if not has_stream:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        package_logger.addHandler(handler)

    _logging_configured = True
    logging.getLogger("doclingllm.gateway").info(
        f"[IMP:9][configure_gateway_logging][READY] level={logging.getLevelName(level)} [OK]"
    )


# endregion FUNC_configure_gateway_logging


# region FUNC_begin_request_trace [DOMAIN(8): Logging; CONCEPT(8): Correlation; TECH(8): contextvars]
## @purpose Allocate a short request_id for one inbound gateway call and bind it into context.
## @complexity 2
def begin_request_trace(prefix: str = "req") -> str:
    request_id = f"{prefix}-{uuid.uuid4().hex[:10]}"
    _request_id_var.set(request_id)
    return request_id


# endregion FUNC_begin_request_trace


# region FUNC_current_request_id [DOMAIN(6): Logging; CONCEPT(6): Correlation; TECH(6): contextvars]
## @purpose Read active correlated request id for log lines.
## @complexity 1
def current_request_id() -> str:
    return _request_id_var.get()


# endregion FUNC_current_request_id


# region FUNC_truncate_text [DOMAIN(5): Logging; CONCEPT(5): Truncate; TECH(5): str]
## @purpose Limit long text fragments in log lines.
## @complexity 2
def truncate_text(text: str, limit: int = MAX_TEXT_PREVIEW) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<{len(text) - limit} more chars>"


# endregion FUNC_truncate_text


# region FUNC__looks_like_printable_text [DOMAIN(5): Logging; CONCEPT(5): Heuristic; TECH(5): str]
## @purpose Decide whether a short BYTES value is safe to log as text.
## @complexity 2
def _looks_like_printable_text(value: str) -> bool:
    if not value or len(value) > MAX_SHORT_TEXT_BYTES:
        return False
    if value.startswith("data:") or value.startswith("iVBOR") or value.startswith("/9j/"):
        return False
    printable = sum(1 for char in value if char.isprintable() or char in "\n\r\t")
    return printable / max(len(value), 1) >= 0.9


# endregion FUNC__looks_like_printable_text


# region FUNC__preview_numeric_list [DOMAIN(6): Logging; CONCEPT(6): TensorPreview; TECH(6): list]
## @purpose Summarize large numeric tensor data lists without dumping full arrays.
## @complexity 3
def _preview_numeric_list(data: list[Any]) -> dict[str, Any]:
    length = len(data)
    sample = data[:MAX_NUMERIC_SAMPLE]
    preview: dict[str, Any] = {"length": length, "sample": sample}
    if length > MAX_NUMERIC_SAMPLE:
        preview["tail_sample"] = data[-min(4, length) :]
        preview["sample_note"] = f"first {MAX_NUMERIC_SAMPLE} + last up to 4 of {length}"
    return preview


# endregion FUNC__preview_numeric_list


# region FUNC__preview_bytes_value [DOMAIN(6): Logging; CONCEPT(6): BytesPreview; TECH(6): str]
## @purpose Describe BYTES tensor values: short text shown, large/base64 size-only.
## @complexity 4
def _preview_bytes_value(value: Any) -> Any:
    if isinstance(value, str):
        if _looks_like_printable_text(value):
            return truncate_text(value, MAX_SHORT_TEXT_BYTES)
        if value.startswith("data:"):
            return f"<data-url {len(value)} chars>"
        return f"<base64-or-binary {len(value)} chars>"
    if isinstance(value, (bytes, bytearray)):
        try:
            decoded = value.decode("utf-8")
            if _looks_like_printable_text(decoded):
                return truncate_text(decoded, MAX_SHORT_TEXT_BYTES)
        except UnicodeDecodeError:
            pass
        return f"<bytes {len(value)}>"
    if value is None:
        return "<null>"
    return f"<{type(value).__name__}>"


# endregion FUNC__preview_bytes_value


# region FUNC__preview_kserve_tensor_data [DOMAIN(7): KServe; CONCEPT(7): TensorPreview; TECH(7): json]
## @purpose Build a compact preview for one KServe input/output tensor data field.
## @complexity 4
def _preview_kserve_tensor_data(data: Any, datatype: str) -> Any:
    dtype = str(datatype).upper()
    if data is None:
        return None
    if dtype == "BYTES":
        if isinstance(data, list):
            if not data:
                return {"length": 0}
            if len(data) <= 8 and all(
                isinstance(item, str) and _looks_like_printable_text(item) for item in data
            ):
                return {"length": len(data), "values": data}
            return {
                "length": len(data),
                "first": _preview_bytes_value(data[0]),
            }
        return _preview_bytes_value(data)
    if isinstance(data, list):
        if not data:
            return {"length": 0}
        if all(isinstance(item, (int, float)) for item in data[:MAX_NUMERIC_SAMPLE]):
            return _preview_numeric_list(data)
        if len(data) == 1:
            return _preview_bytes_value(data[0])
        return {"length": len(data), "first": str(data[0])[:MAX_BYTES_PREVIEW_CHARS]}
    return str(data)[:MAX_BYTES_PREVIEW_CHARS]


# endregion FUNC__preview_kserve_tensor_data


# region FUNC__emit_trace [DOMAIN(8): Logging; CONCEPT(8): TraceBanner; TECH(8): logging]
## @purpose Emit a multi-line TRACE banner with request_id for docker log grepping.
## @complexity 3
def _emit_trace(
    active_logger: logging.Logger,
    *,
    direction: str,
    title: str,
    payload: dict[str, Any],
    importance: int = 8,
) -> None:
    request_id = current_request_id()
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    active_logger.info(
        f"[IMP:{importance}][gateway][{direction}] rid={request_id} {title}\n"
        f"----- BEGIN {direction} rid={request_id} -----\n"
        f"{body}\n"
        f"----- END {direction} rid={request_id} ----- [TRACE]"
    )


# endregion FUNC__emit_trace


# region FUNC_summarize_kserve_infer_request [DOMAIN(8): KServe; CONCEPT(8): RequestSummary; TECH(8): json]
## @purpose Summarize docling KServe v2 infer request for gateway logs.
## @complexity 5
def summarize_kserve_infer_request(
    model_name: str,
    body: dict[str, Any],
    *,
    framing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    inputs_summary: list[dict[str, Any]] = []
    for tensor in body.get("inputs", []):
        inputs_summary.append(
            {
                "name": tensor.get("name"),
                "datatype": tensor.get("datatype"),
                "shape": tensor.get("shape"),
                "data": _preview_kserve_tensor_data(
                    tensor.get("data"),
                    str(tensor.get("datatype", "")),
                ),
            }
        )

    outputs_summary: list[dict[str, Any]] = []
    for tensor in body.get("outputs", []) or []:
        outputs_summary.append(
            {
                "name": tensor.get("name"),
                "parameters": tensor.get("parameters"),
            }
        )

    summary: dict[str, Any] = {
        "direction": "docling -> gateway",
        "protocol": "kserve_v2_infer",
        "model_name": model_name,
        "inputs": inputs_summary,
        "outputs_requested": outputs_summary,
        "parameters": body.get("parameters"),
    }
    if framing:
        summary["framing"] = framing
    return summary


# endregion FUNC_summarize_kserve_infer_request


# region FUNC__summarize_openai_message_content [DOMAIN(7): OpenAI; CONCEPT(7): MessageSummary; TECH(7): json]
## @purpose Summarize one OpenAI message content block list or string.
## @complexity 5
def _summarize_openai_message_content(content: Any) -> Any:
    if isinstance(content, str):
        return truncate_text(content)
    if not isinstance(content, list):
        return truncate_text(str(content))

    parts_summary: list[Any] = []
    for part in content:
        if not isinstance(part, dict):
            parts_summary.append(truncate_text(str(part)))
            continue
        part_type = part.get("type", "unknown")
        if part_type == "text":
            parts_summary.append(
                {"type": "text", "text": truncate_text(str(part.get("text", "")))}
            )
            continue
        if part_type == "image_url":
            image_url = part.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
            parts_summary.append({"type": "image_url", "url": _preview_bytes_value(url)})
            continue
        parts_summary.append(
            {
                "type": part_type,
                "preview": truncate_text(json.dumps(part, ensure_ascii=False)),
            }
        )
    return parts_summary


# endregion FUNC__summarize_openai_message_content


# region FUNC_summarize_openai_chat_payload [DOMAIN(8): OpenAI; CONCEPT(8): RequestSummary; TECH(8): json]
## @purpose Summarize outbound OpenAI chat/completions payload before HTTP POST.
## @complexity 4
def summarize_openai_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    messages_summary: list[dict[str, Any]] = []
    for message in payload.get("messages", []):
        if not isinstance(message, dict):
            continue
        messages_summary.append(
            {
                "role": message.get("role"),
                "content": _summarize_openai_message_content(message.get("content")),
            }
        )

    extra_keys = {
        key: payload[key]
        for key in payload
        if key not in {"model", "messages"}
    }
    return {
        "direction": "gateway -> model",
        "model": payload.get("model"),
        "messages": messages_summary,
        "extra_params": extra_keys,
    }


# endregion FUNC_summarize_openai_chat_payload


# region FUNC_summarize_openai_proxy_body [DOMAIN(8): OpenAI; CONCEPT(8): ProxySummary; TECH(8): json]
## @purpose Summarize full OpenAI proxy request body from docling.
## @complexity 4
def summarize_openai_proxy_body(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "direction": "docling -> gateway",
        "protocol": "openai_chat_completions",
        "model": body.get("model"),
        "stream": body.get("stream"),
        "payload": summarize_openai_chat_payload(body),
    }


# endregion FUNC_summarize_openai_proxy_body


# region FUNC_summarize_openai_response [DOMAIN(8): OpenAI; CONCEPT(8): ResponseSummary; TECH(8): json]
## @purpose Summarize external model chat/completions JSON response.
## @complexity 5
def summarize_openai_response(response_data: dict[str, Any]) -> dict[str, Any]:
    choices_summary: list[dict[str, Any]] = []
    for choice in response_data.get("choices", [])[:3]:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            content_preview = _summarize_openai_message_content(content)
        else:
            content_preview = truncate_text(str(content))
        choices_summary.append(
            {
                "index": choice.get("index"),
                "finish_reason": choice.get("finish_reason"),
                "role": message.get("role"),
                "content": content_preview,
            }
        )

    return {
        "direction": "model -> gateway",
        "id": response_data.get("id"),
        "model": response_data.get("model"),
        "choices": choices_summary,
        "usage": response_data.get("usage"),
        "error": response_data.get("error"),
    }


# endregion FUNC_summarize_openai_response


# region FUNC_summarize_kserve_infer_response [DOMAIN(7): KServe; CONCEPT(7): ResponseSummary; TECH(7): json]
## @purpose Summarize encoded KServe infer response returned to docling.
## @complexity 4
def summarize_kserve_infer_response(response_data: dict[str, Any]) -> dict[str, Any]:
    outputs_summary: list[dict[str, Any]] = []
    for tensor in response_data.get("outputs", []):
        data = tensor.get("data")
        datatype = str(tensor.get("datatype", "")).upper()
        if datatype == "BYTES":
            preview = _preview_kserve_tensor_data(data, datatype)
        elif isinstance(data, list):
            preview = _preview_numeric_list(data)
        else:
            preview = data
        outputs_summary.append(
            {
                "name": tensor.get("name"),
                "datatype": tensor.get("datatype"),
                "shape": tensor.get("shape"),
                "data": preview,
            }
        )
    return {
        "direction": "gateway -> docling",
        "model_name": response_data.get("model_name"),
        "model_version": response_data.get("model_version"),
        "outputs": outputs_summary,
    }


# endregion FUNC_summarize_kserve_infer_response


# region FUNC_log_docling_kserve_request [DOMAIN(8): Logging; CONCEPT(8): DOCLING_IN; TECH(8): logging]
## @purpose Log inbound KServe infer request from docling-serve.
## @complexity 3
def log_docling_kserve_request(
    active_logger: logging.Logger,
    model_name: str,
    body: dict[str, Any],
    *,
    framing: Optional[dict[str, Any]] = None,
) -> None:
    summary = summarize_kserve_infer_request(model_name, body, framing=framing)
    _emit_trace(
        active_logger,
        direction="DOCLING_IN",
        title=f"KServe infer model={model_name}",
        payload=summary,
        importance=7,
    )


# endregion FUNC_log_docling_kserve_request


# region FUNC_log_docling_openai_request [DOMAIN(8): Logging; CONCEPT(8): DOCLING_IN; TECH(8): logging]
## @purpose Log inbound OpenAI proxy request from docling-serve.
## @complexity 3
def log_docling_openai_request(active_logger: logging.Logger, body: dict[str, Any]) -> None:
    summary = summarize_openai_proxy_body(body)
    _emit_trace(
        active_logger,
        direction="DOCLING_IN",
        title="OpenAI proxy /v1/chat/completions",
        payload=summary,
        importance=7,
    )


# endregion FUNC_log_docling_openai_request


# region FUNC_log_model_outbound_request [DOMAIN(8): Logging; CONCEPT(8): MODEL_OUT; TECH(8): logging]
## @purpose Log payload sent from gateway to external vision/text model.
## @complexity 3
def log_model_outbound_request(
    active_logger: logging.Logger,
    *,
    stage: str,
    request_url: str,
    payload: dict[str, Any],
    call_kind: str = "chat_completions",
) -> None:
    summary = summarize_openai_chat_payload(payload)
    summary["stage"] = stage
    summary["url"] = request_url
    summary["call_kind"] = call_kind
    _emit_trace(
        active_logger,
        direction="MODEL_OUT",
        title=f"kind={call_kind} stage={stage}",
        payload=summary,
        importance=7,
    )


# endregion FUNC_log_model_outbound_request


# region FUNC_log_model_inbound_response [DOMAIN(8): Logging; CONCEPT(8): MODEL_IN; TECH(8): logging]
## @purpose Log JSON response received from external vision/text model.
## @complexity 3
def log_model_inbound_response(
    active_logger: logging.Logger,
    *,
    stage: str,
    request_url: str,
    response_data: dict[str, Any],
    call_kind: str = "chat_completions",
) -> None:
    summary = summarize_openai_response(response_data)
    summary["stage"] = stage
    summary["url"] = request_url
    summary["call_kind"] = call_kind
    _emit_trace(
        active_logger,
        direction="MODEL_IN",
        title=f"kind={call_kind} stage={stage}",
        payload=summary,
        importance=8,
    )


# endregion FUNC_log_model_inbound_response


# region FUNC_log_gateway_kserve_response [DOMAIN(7): Logging; CONCEPT(7): GATEWAY_OUT; TECH(7): logging]
## @purpose Log KServe infer response returned by gateway to docling.
## @complexity 3
def log_gateway_kserve_response(
    active_logger: logging.Logger,
    model_name: str,
    response_data: dict[str, Any],
) -> None:
    summary = summarize_kserve_infer_response(response_data)
    _emit_trace(
        active_logger,
        direction="GATEWAY_OUT",
        title=f"KServe infer model={model_name}",
        payload=summary,
        importance=8,
    )


# endregion FUNC_log_gateway_kserve_response


# region FUNC_log_gateway_openai_response [DOMAIN(7): Logging; CONCEPT(7): GATEWAY_OUT; TECH(7): logging]
## @purpose Log OpenAI proxy response returned by gateway to docling.
## @complexity 3
def log_gateway_openai_response(
    active_logger: logging.Logger,
    response_data: dict[str, Any],
) -> None:
    summary = summarize_openai_response(response_data)
    summary["direction"] = "gateway -> docling"
    _emit_trace(
        active_logger,
        direction="GATEWAY_OUT",
        title="OpenAI proxy response",
        payload=summary,
        importance=8,
    )


# endregion FUNC_log_gateway_openai_response
