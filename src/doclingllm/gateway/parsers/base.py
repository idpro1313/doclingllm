# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): LLMResponse, JSONExtract; TECH(8): json, regex]
## @purpose Shared utilities to extract JSON and plain text from LLM assistant responses for KServe tensor encoding.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: parser, json extract, plain text, LLM response
# STRUCTURE: ▶ str content → ◇ regex/json.loads → ⎋ dict

import json
import re
from typing import Any

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


# region FUNC_extract_json_from_text [DOMAIN(8): Parsing; CONCEPT(8): JSONExtract; TECH(8): regex]
## @purpose Extract first JSON object or array from LLM text including fenced code blocks.
## @complexity 5
def extract_json_from_text(text: str) -> Any:
    if not text.strip():
        return {}

    fenced = _JSON_BLOCK_PATTERN.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        return json.loads(candidate)

    obj_match = _JSON_OBJECT_PATTERN.search(text)
    if obj_match:
        return json.loads(obj_match.group(0))

    return json.loads(text.strip())


# endregion FUNC_extract_json_from_text


# region FUNC_parse_plain_text [DOMAIN(7): Parsing; CONCEPT(7): PlainText; TECH(7): str]
## @purpose Wrap raw assistant text for downstream KServe BYTES encoding.
## @complexity 2
def parse_plain_text(text: str) -> dict[str, Any]:
    return {"text": text.strip()}


# endregion FUNC_parse_plain_text
