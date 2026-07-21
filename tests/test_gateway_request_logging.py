# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): RequestLogging; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging

from doclingllm.gateway.request_logging import (
    begin_request_trace,
    configure_gateway_logging,
    current_request_id,
    log_docling_kserve_request,
    log_model_inbound_response,
    log_model_outbound_request,
    summarize_kserve_infer_request,
    summarize_openai_chat_payload,
    summarize_openai_response,
)


def test_summarize_kserve_infer_request_redacts_tensor_data():
    body = {
        "inputs": [
            {
                "name": "images",
                "datatype": "FP32",
                "shape": [1, 3, 2, 2],
                "data": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2],
            }
        ]
    }
    summary = summarize_kserve_infer_request("layout", body)
    assert summary["model_name"] == "layout"
    assert summary["inputs"][0]["data"]["length"] == 12
    assert "sample" in summary["inputs"][0]["data"]


def test_summarize_kserve_shows_short_text_bytes():
    body = {
        "inputs": [
            {
                "name": "lang_type",
                "datatype": "BYTES",
                "shape": [1, 1],
                "data": ["en"],
            }
        ]
    }
    summary = summarize_kserve_infer_request("ocr", body)
    assert summary["inputs"][0]["data"]["values"] == ["en"]


def test_summarize_openai_chat_payload_redacts_image():
    payload = {
        "model": "qwen3.6-35b-a3b",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,QUJDRA=="},
                    },
                ],
            }
        ],
    }
    summary = summarize_openai_chat_payload(payload)
    image_part = summary["messages"][0]["content"][1]
    assert image_part["type"] == "image_url"
    assert "chars>" in image_part["url"]
    assert "QUJDRA" not in image_part["url"]


def test_summarize_openai_response_includes_assistant_preview():
    response = {
        "id": "cmpl-1",
        "model": "qwen3.6-35b-a3b",
        "choices": [{"message": {"role": "assistant", "content": '{"boxes":[]}'}}],
    }
    summary = summarize_openai_response(response)
    assert summary["choices"][0]["content"] == '{"boxes":[]}'


def test_request_logging_emits_trace_lines(caplog):
    configure_gateway_logging("INFO")
    caplog.set_level(logging.INFO)
    active_logger = logging.getLogger("doclingllm.gateway.test_trace")

    rid = begin_request_trace("test")
    assert current_request_id() == rid

    log_docling_kserve_request(
        active_logger,
        "layout",
        {
            "inputs": [
                {
                    "name": "images",
                    "datatype": "FP32",
                    "shape": [1, 3, 1, 1],
                    "data": [0.0],
                }
            ]
        },
        framing={"binary_framing": True, "raw_body_bytes": 99},
    )
    log_model_outbound_request(
        active_logger,
        stage="layout",
        request_url="https://example.com/v1/chat/completions",
        payload={
            "model": "qwen3.6-35b-a3b",
            "messages": [{"role": "user", "content": "detect layout"}],
        },
    )
    log_model_inbound_response(
        active_logger,
        stage="layout",
        request_url="https://example.com/v1/chat/completions",
        response_data={
            "choices": [{"message": {"role": "assistant", "content": '{"boxes":[]}'}}]
        },
    )

    messages = [record.message for record in caplog.records]
    joined = "\n".join(messages)
    assert "[DOCLING_IN]" in joined
    assert "[MODEL_OUT]" in joined
    assert "[MODEL_IN]" in joined
    assert f"rid={rid}" in joined
    assert "BEGIN DOCLING_IN" in joined
