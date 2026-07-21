# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): OCR; TECH(8): json]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text, parse_plain_text


# region FUNC_parse_deepseek_ocr_json [DOMAIN(8): OCR; CONCEPT(8): OCRParser; TECH(8): json]
## @purpose Normalize OCR LLM output to {text_regions: [...]} structure.
## @complexity 4
def parse_deepseek_ocr_json(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        plain = parse_plain_text(text)
        return {"text_regions": [{"text": plain["text"], "bbox": [0, 0, 0, 0]}]}

    if isinstance(parsed, list):
        return {"text_regions": parsed}
    if "text_regions" in parsed:
        return parsed
    if "lines" in parsed:
        return {"text_regions": parsed["lines"]}
    if "text" in parsed:
        return {"text_regions": [{"text": parsed["text"], "bbox": parsed.get("bbox", [0, 0, 0, 0])}]}
    return {"text_regions": [parsed]}


# endregion FUNC_parse_deepseek_ocr_json
