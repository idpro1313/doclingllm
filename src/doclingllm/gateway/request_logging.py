# region MODULE_CONTRACT [DOMAIN(8): Logging; CONCEPT(8): RequestTrace, Sanitize; TECH(8): json]
## @modulecontract
## @purpose Summarize docling inbound and external model outbound/inbound payloads for gateway audit logs without leaking secrets or full tensors.
## @invariants
## - Authorization and raw API keys are NEVER logged.
## - Base64 image payloads are replaced with size placeholders.
## @changes
## LAST_CHANGE: [v0.2.9 – structured DOCLING_IN / MODEL_OUT / MODEL_IN trace logging.]
## @modulemap
## FUNC 8[Summarize KServe infer body] => summarize_kserve_infer_request
## FUNC 8[Summarize OpenAI chat payload] => summarize_openai_chat_payload
## FUNC 8[Summarize OpenAI response] => summarize_openai_response
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: request logging, docling inbound, model outbound, sanitize, base64, trace
# STRUCTURE: ▶ raw payload → ◇ redact/truncate → ⊕ JSON summary → ⎋ logger.info

import json
import logging
from typing import Any

MAX_TEXT_PREVIEW = 4000
MAX_NUMERIC_SAMPLE = 8
MAX_BYTES_PREVIEW_CHARS = 64

logger = logging.getLogger(__name__)


# region FUNC_truncate_text [DOMAIN(5): Logging; CONCEPT(5): Truncate; TECH(5): str]
## @purpose Limit long text fragments in log lines.
## @complexity 2
def truncate_text(text: str, limit: int = MAX_TEXT_PREVIEW) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<{len(text) - limit} more chars>"


# endregion FUNC_truncate_text


# region FUNC__preview_numeric_list [DOMAIN(6): Logging; CONCEPT(6): TensorPreview; TECH(6): list]
## @purpose Summarize large numeric tensor data lists without dumping full arrays.
## @complexity 3
def _preview_numeric_list(data: list[Any]) -> dict[str, Any]:
    length = len(data)
    sample = data[:MAX_NUMERIC_SAMPLE]
    preview: dict[str, Any] = {"length": length, "sample": sample}
    if length > MAX_NUMERIC_SAMPLE:
        preview["sample_note"] = f"first {MAX_NUMERIC_SAMPLE} of {length}"
    return preview


# endregion FUNC__preview_numeric_list


# region FUNC__preview_bytes_value [DOMAIN(6): Logging; CONCEPT(6): BytesPreview; TECH(6): str]
## @purpose Describe BYTES tensor values as size-only placeholders.
## @complexity 3
def _preview_bytes_value(value: Any) -> str:
    if isinstance(value, str):
        if value.startswith("data:"):
            return f"<data-url {len(value)} chars>"
        return f"<base64 {len(value)} chars>"
    if isinstance(value, (bytes, bytearray)):
        return f"<bytes {len(value)}>"
    if value is None:
        return "<null>"
    return f"<{type(value).__name__}>"


# endregion FUNC__preview_bytes_value


# region FUNC__preview_kserve_tensor_data [DOMAIN(7): KServe; CONCEPT(7): TensorPreview; TECH(7): json]
## @purpose Build a compact preview for one KServe input tensor data field.
## @complexity 4
def _preview_kserve_tensor_data(data: Any, datatype: str) -> Any:
    dtype = str(datatype).upper()
    if data is None:
        return None
    if dtype == "BYTES":
        if isinstance(data, list):
            if not data:
                return {"length": 0}
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


# region FUNC_summarize_kserve_infer_request [DOMAIN(8): KServe; CONCEPT(8): RequestSummary; TECH(8): json]
## @purpose Summarize docling KServe v2 infer request for gateway logs.
## @complexity 5
def summarize_kserve_infer_request(model_name: str, body: dict[str, Any]) -> dict[str, Any]:
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

    return {
        "protocol": "kserve_v2_infer",
        "model_name": model_name,
        "inputs": inputs_summary,
        "outputs_requested": outputs_summary,
        "parameters": body.get("parameters"),
    }


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
        preview: Any
        datatype = str(tensor.get("datatype", "")).upper()
        if datatype == "BYTES" and isinstance(data, list) and data:
            preview = _preview_bytes_value(data[0])
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
) -> None:
    summary = summarize_kserve_infer_request(model_name, body)
    active_logger.info(
        f"[IMP:7][gateway][DOCLING_IN] KServe infer "
        f"{json.dumps(summary, ensure_ascii=False)} [REQUEST]"
    )


# endregion FUNC_log_docling_kserve_request


# region FUNC_log_docling_openai_request [DOMAIN(8): Logging; CONCEPT(8): DOCLING_IN; TECH(8): logging]
## @purpose Log inbound OpenAI proxy request from docling-serve.
## @complexity 3
def log_docling_openai_request(active_logger: logging.Logger, body: dict[str, Any]) -> None:
    summary = summarize_openai_proxy_body(body)
    active_logger.info(
        f"[IMP:7][gateway][DOCLING_IN] OpenAI proxy "
        f"{json.dumps(summary, ensure_ascii=False)} [REQUEST]"
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
    active_logger.info(
        f"[IMP:7][gateway][MODEL_OUT] kind={call_kind} stage={stage} url={request_url} "
        f"{json.dumps(summary, ensure_ascii=False)} [REQUEST]"
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
    active_logger.info(
        f"[IMP:8][gateway][MODEL_IN] kind={call_kind} stage={stage} url={request_url} "
        f"{json.dumps(summary, ensure_ascii=False)} [RESPONSE]"
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
    active_logger.info(
        f"[IMP:8][gateway][GATEWAY_OUT] KServe infer model={model_name} "
        f"{json.dumps(summary, ensure_ascii=False)} [RESPONSE]"
    )


# endregion FUNC_log_gateway_kserve_response
