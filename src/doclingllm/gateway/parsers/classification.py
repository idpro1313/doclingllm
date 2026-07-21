# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): Classification; TECH(8): json]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text, parse_plain_text


# region FUNC_parse_classification_json [DOMAIN(8): PictureClassification; CONCEPT(8): Classifier; TECH(8): json]
## @purpose Normalize picture classification LLM output to {label, score} structure.
## @complexity 4
def parse_classification_json(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        plain = parse_plain_text(text)
        return {"label": plain["text"], "score": 1.0}

    if isinstance(parsed, dict):
        label = parsed.get("label", parsed.get("class", "unknown"))
        score = float(parsed.get("score", parsed.get("confidence", 1.0)))
        return {"label": label, "score": score}
    return {"label": str(parsed), "score": 1.0}


# endregion FUNC_parse_classification_json
