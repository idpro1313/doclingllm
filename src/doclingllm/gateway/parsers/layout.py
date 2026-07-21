# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): Layout; TECH(8): json]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text, parse_plain_text


# region FUNC_parse_layout_boxes_json [DOMAIN(8): Layout; CONCEPT(8): LayoutParser; TECH(8): json]
## @purpose Normalize layout detection LLM output to {boxes: [{label, bbox}]} structure.
## @complexity 4
def parse_layout_boxes_json(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"boxes": []}

    if isinstance(parsed, list):
        return {"boxes": parsed}
    if "boxes" in parsed:
        return parsed
    if "regions" in parsed:
        return {"boxes": parsed["regions"]}
    return {"boxes": [parsed]}


# endregion FUNC_parse_layout_boxes_json
