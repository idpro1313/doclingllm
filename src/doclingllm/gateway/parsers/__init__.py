# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): ParserRegistry; TECH(8): dict]
## @purpose Registry mapping response_parser names from gateway-models.yaml to parser callables.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: parser registry, deepseek_ocr_json, layout_boxes_json, response_parser
# STRUCTURE: ▶ parser_name → ◇ lookup → ⎋ Callable[[str], dict]

from typing import Callable

from doclingllm.gateway.parsers.base import parse_plain_text
from doclingllm.gateway.parsers.classification import parse_classification_json
from doclingllm.gateway.parsers.layout import parse_layout_boxes_json
from doclingllm.gateway.parsers.ocr import parse_deepseek_ocr_json
from doclingllm.gateway.parsers.table import parse_table_structure_json

ParserFn = Callable[[str], dict]

PARSER_REGISTRY: dict[str, ParserFn] = {
    "deepseek_ocr_json": parse_deepseek_ocr_json,
    "layout_boxes_json": parse_layout_boxes_json,
    "table_structure_json": parse_table_structure_json,
    "classification_json": parse_classification_json,
    "plain_text": parse_plain_text,
}


# region FUNC_get_parser [DOMAIN(7): Parsing; CONCEPT(7): Registry; TECH(7): dict]
## @purpose Resolve parser by name with plain_text fallback.
## @complexity 2
def get_parser(parser_name: str | None) -> ParserFn:
    if not parser_name:
        return parse_plain_text
    return PARSER_REGISTRY.get(parser_name, parse_plain_text)


# endregion FUNC_get_parser
