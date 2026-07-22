# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): LLMResponse, JSONExtract; TECH(8): json, regex]
## @purpose Shared utilities to extract JSON and plain text from LLM assistant responses for KServe tensor encoding.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: parser, json extract, plain text, LLM response, json repair, trailing quote
# STRUCTURE: ▶ str content → ◇ fence/brace slice → ⊕ repair trailing garbage → json.loads → ⎋ dict

import json
import re
from typing import Any

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


# region FUNC__strip_trailing_json_garbage [DOMAIN(8): Parsing; CONCEPT(8): JSONRepair; TECH(8): str]
## @purpose Remove common LLM suffix noise (stray quotes, backslashes) after a JSON object/array.
## @complexity 4
def _strip_trailing_json_garbage(candidate: str) -> str:
    text = candidate.strip().rstrip("`").strip()
    changed = True
    while changed and text:
        changed = False
        if text.endswith('\\"'):
            text = text[:-2].rstrip()
            changed = True
            continue
        if text.endswith('"') and (text[:-1].rstrip().endswith("}") or text[:-1].rstrip().endswith("]")):
            text = text[:-1].rstrip()
            changed = True
            continue
        if text.endswith("\\"):
            text = text[:-1].rstrip()
            changed = True
    return text


# endregion FUNC__strip_trailing_json_garbage


# region FUNC__balanced_json_slice [DOMAIN(8): Parsing; CONCEPT(8): JSONExtract; TECH(8): bracket scan]
## @purpose Return substring from first opening brace/bracket to its matching close when greedy regex fails.
## @complexity 6
def _balanced_json_slice(text: str) -> str | None:
    start = -1
    open_char = ""
    close_char = ""
    for index, char in enumerate(text):
        if char == "{":
            start = index
            open_char = "{"
            close_char = "}"
            break
        if char == "[":
            start = index
            open_char = "["
            close_char = "]"
            break
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


# endregion FUNC__balanced_json_slice


# region FUNC__loads_json_with_repair [DOMAIN(8): Parsing; CONCEPT(8): JSONRepair; TECH(8): json]
## @purpose Parse JSON from LLM output using progressive repair when strict json.loads fails.
## @complexity 6
def _loads_json_with_repair(candidate: str) -> Any:
    attempts: list[str] = []
    stripped = candidate.strip()
    if stripped:
        attempts.append(stripped)
    repaired = _strip_trailing_json_garbage(stripped)
    if repaired and repaired not in attempts:
        attempts.append(repaired)
    balanced = _balanced_json_slice(stripped)
    if balanced:
        if balanced not in attempts:
            attempts.append(balanced)
        balanced_repaired = _strip_trailing_json_garbage(balanced)
        if balanced_repaired and balanced_repaired not in attempts:
            attempts.append(balanced_repaired)

    last_error: json.JSONDecodeError | None = None
    for attempt in attempts:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("Empty JSON candidate", candidate, 0)


# endregion FUNC__loads_json_with_repair


# region FUNC_extract_json_from_text [DOMAIN(8): Parsing; CONCEPT(8): JSONExtract; TECH(8): regex]
## @purpose Extract first JSON object or array from LLM text including fenced code blocks with repair fallback.
## @complexity 5
def extract_json_from_text(text: str) -> Any:
    if not text.strip():
        return {}

    fenced = _JSON_BLOCK_PATTERN.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        return _loads_json_with_repair(candidate)

    obj_match = _JSON_OBJECT_PATTERN.search(text)
    if obj_match:
        return _loads_json_with_repair(obj_match.group(0))

    return _loads_json_with_repair(text.strip())


# endregion FUNC_extract_json_from_text


# region FUNC_parse_plain_text [DOMAIN(7): Parsing; CONCEPT(7): PlainText; TECH(7): str]
## @purpose Wrap raw assistant text for downstream KServe BYTES encoding.
## @complexity 2
def parse_plain_text(text: str) -> dict[str, Any]:
    return {"text": text.strip()}


# endregion FUNC_parse_plain_text
