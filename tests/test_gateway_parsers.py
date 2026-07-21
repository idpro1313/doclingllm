# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(8): Parsers; TECH(8): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json

from doclingllm.gateway.parsers import get_parser
from doclingllm.gateway.parsers.base import extract_json_from_text
from doclingllm.gateway.parsers.layout import parse_layout_boxes_json
from doclingllm.gateway.parsers.ocr import parse_deepseek_ocr_json
from doclingllm.gateway.parsers.table import parse_table_structure_json


def test_extract_json_from_fenced_block():
    text = 'Here:\n```json\n{"text_regions": [{"text": "A"}]}\n```'
    parsed = extract_json_from_text(text)
    assert parsed["text_regions"][0]["text"] == "A"


def test_parse_deepseek_ocr_json_plain_fallback():
    result = parse_deepseek_ocr_json("Plain OCR line\nSecond line")
    assert len(result["text_regions"]) == 2
    assert result["text_regions"][0]["text"] == "Plain OCR line"
    assert "bbox" not in result["text_regions"][0]


def test_parse_layout_boxes_json_list():
    payload = json.dumps([{"label": "title", "bbox": [0, 0, 10, 10]}])
    result = parse_layout_boxes_json(payload)
    assert len(result["boxes"]) == 1


def test_parse_table_structure_json():
    payload = json.dumps({"rows": 2, "cols": 2, "cells": [{"r": 0, "c": 0, "text": "A"}]})
    result = parse_table_structure_json(payload)
    assert result["rows"] == 2
    assert len(result["cells"]) == 1


def test_parser_registry_get_parser():
    parser = get_parser("deepseek_ocr_json")
    result = parser('{"text_regions": [{"text": "x", "bbox": [0,0,0,0]}]}')
    assert "text_regions" in result
