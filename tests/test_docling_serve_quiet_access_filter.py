# region MODULE_CONTRACT [DOMAIN(6): Testing; CONCEPT(7): LogFilter; TECH(7): pytest]
def _module_contract():
    pass
# endregion MODULE_CONTRACT

import logging
import re
from pathlib import Path


def test_quiet_access_filter_contract_in_overlay():
    """Overlay logging_config must define QuietAccessFilter dropping poll/health."""
    path = (
        Path(__file__).resolve().parents[1]
        / "deploy"
        / "docling-serve"
        / "logging_config.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "class QuietAccessFilter" in text
    assert "/v1/status/poll/" in text
    assert "/ui/assets/" in text
    assert "/ui/gradio_api/" in text
    assert "QuietTenantPollFilter" in text
    assert '"httpx"' in text
    assert '"httpcore"' in text


def test_quiet_access_filter_behavior():
    # Mirror filter logic (starlette may be absent in local test env).
    quiet_substrings = ("/v1/status/poll/", "/health")

    class QuietAccessFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            message = record.getMessage()
            return not any(fragment in message for fragment in quiet_substrings)

    filt = QuietAccessFilter()
    poll = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '127.0.0.1:1 - "GET /v1/status/poll/abc?wait=5 HTTP/1.1" 200',
        (),
        None,
    )
    convert = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '10.0.0.1:1 - "POST /v1/convert/source/async HTTP/1.1" 200',
        (),
        None,
    )
    assert filt.filter(poll) is False
    assert filt.filter(convert) is True
    assert re.search(r"/v1/status/poll/", poll.getMessage())
