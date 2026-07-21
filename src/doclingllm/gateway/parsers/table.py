# region MODULE_CONTRACT [DOMAIN(8): Parsing; CONCEPT(8): TableStructure; TECH(8): json]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import json
from typing import Any

from doclingllm.gateway.parsers.base import extract_json_from_text


# region FUNC_parse_table_structure_json [DOMAIN(8): Table; CONCEPT(8): TableParser; TECH(8): json]
## @purpose Normalize table structure LLM output to {rows, cols, cells} structure.
## @complexity 4
def parse_table_structure_json(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_from_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"rows": 0, "cols": 0, "cells": []}

    if isinstance(parsed, dict):
        cells = parsed.get("cells", [])
        rows = parsed.get("rows", len(cells))
        cols = parsed.get("cols", 0)
        return {"rows": rows, "cols": cols, "cells": cells}
    return {"rows": 0, "cols": 0, "cells": []}


# endregion FUNC_parse_table_structure_json
