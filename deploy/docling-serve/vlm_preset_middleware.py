# region MODULE_CONTRACT [DOMAIN(8): Deploy; CONCEPT(9): VlmPresetInject; TECH(8): starlette]
## @purpose Force remote VLM preset on convert API when Gradio/clients omit vlm_pipeline_preset.
## @rationale
## Q: Why middleware instead of YAML granite overwrite alone?
## A: Without vlm_pipeline_preset jobkit uses legacy local GRANITEDOCLING_TRANSFORMERS and never reads custom_vlm_presets.
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: VlmPresetInjectMiddleware, vlm_pipeline_preset, convert async, granite bypass
# STRUCTURE: ▶ POST /v1/convert → ◇ pipeline==vlm & no preset → ⊕ options.vlm_pipeline_preset=default → ⎋ call_next

import json
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_CONVERT_PATH_MARKERS = (
    "/v1/convert/source",
    "/v1/convert/file",
    "/v1/convert/source/async",
    "/v1/convert/file/async",
)


class VlmPresetInjectMiddleware(BaseHTTPMiddleware):
    """Inject vlm_pipeline_preset=default for Vlm pipeline convert JSON bodies."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        content_type = request.headers.get("content-type", "")
        if (
            request.method == "POST"
            and "application/json" in content_type
            and any(marker in path for marker in _CONVERT_PATH_MARKERS)
        ):
            body = await request.body()
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                options = payload.get("options")
                if isinstance(options, dict) and str(options.get("pipeline")) == "vlm":
                    if not options.get("vlm_pipeline_preset"):
                        options["vlm_pipeline_preset"] = "default"
                        payload["options"] = options
                        new_body = json.dumps(payload).encode("utf-8")
                        logger.info(
                            "[IMP:8][VlmPresetInjectMiddleware][INJECT] "
                            "vlm_pipeline_preset=default for Gradio/API Vlm request [FIX]"
                        )

                        async def receive() -> dict:
                            return {
                                "type": "http.request",
                                "body": new_body,
                                "more_body": False,
                            }

                        request = Request(request.scope, receive)
        return await call_next(request)
