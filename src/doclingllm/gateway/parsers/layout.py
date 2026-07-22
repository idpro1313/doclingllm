# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): Layout; TECH(8): json]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
import logging
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text

logger = logging.getLogger(__name__)


# region FUNC_parse_layout_boxes_json [DOMAIN(8): Layout; CONCEPT(8): LayoutParser; TECH(8): json]
## @purpose Normalize layout detection LLM output to {boxes: [{label, bbox}]} structure.
## @complexity 4
def parse_layout_boxes_json(text: str) -> dict[str, Any]:
    content_len = len(text.strip())
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        if content_len > 0:
            logger.warning(
                f"[IMP:9][parse_layout_boxes_json][PARSE_EMPTY] "
                f"content_len={content_len} reason=decode_error error={exc} [VALUE]"
            )
        return {"boxes": []}

    if isinstance(parsed, list):
        boxes = parsed
    elif isinstance(parsed, dict):
        if "boxes" in parsed:
            boxes = parsed["boxes"]
        elif "regions" in parsed:
            boxes = parsed["regions"]
        else:
            boxes = [parsed]
    else:
        boxes = []

    if content_len > 0 and not boxes:
        logger.warning(
            f"[IMP:9][parse_layout_boxes_json][PARSE_EMPTY] "
            f"content_len={content_len} reason=no_boxes parsed_type={type(parsed).__name__} [VALUE]"
        )

    return {"boxes": boxes}


# endregion FUNC_parse_layout_boxes_json
