# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): OCR; TECH(8): json]
## @changes
## LAST_CHANGE: [v0.2.19 – plain OCR fallback keeps text without zero-area bbox that encode drops.]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text, parse_plain_text


# region FUNC__plain_ocr_to_regions [DOMAIN(7): OCR; CONCEPT(7): PlainFallback; TECH(7): str]
## @purpose Split free-form OCR prose into line regions; bbox filled later from page size.
## @complexity 3
def _plain_ocr_to_regions(text: str) -> list[dict[str, Any]]:
    # BUG_FIX_CONTEXT: bbox [0,0,0,0] was rejected by coerce_xyxy → empty KServe OCR tensors
    # while the model had already transcribed the page as markdown/prose.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        plain = parse_plain_text(text)
        if not plain["text"]:
            return []
        return [{"text": plain["text"], "score": 0.5}]
    return [{"text": line, "score": 0.5} for line in lines]


# endregion FUNC__plain_ocr_to_regions


# region FUNC_parse_deepseek_ocr_json [DOMAIN(8): OCR; CONCEPT(8): OCRParser; TECH(8): json]
## @purpose Normalize OCR LLM output to {text_regions: [...]} structure.
## @complexity 4
def parse_deepseek_ocr_json(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"text_regions": _plain_ocr_to_regions(text)}

    if isinstance(parsed, list):
        return {"text_regions": parsed}
    if isinstance(parsed, dict):
        if "text_regions" in parsed:
            return parsed
        if "lines" in parsed:
            return {"text_regions": parsed["lines"]}
        if "text" in parsed:
            region: dict[str, Any] = {"text": parsed["text"]}
            if "bbox" in parsed:
                region["bbox"] = parsed["bbox"]
            if "score" in parsed:
                region["score"] = parsed["score"]
            return {"text_regions": [region]}
        return {"text_regions": [parsed]}
    return {"text_regions": _plain_ocr_to_regions(text)}


# endregion FUNC_parse_deepseek_ocr_json
