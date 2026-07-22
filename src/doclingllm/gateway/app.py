# region MODULE_CONTRACT [DOMAIN(9): GatewayApp; CONCEPT(9): FastAPI, Transport; TECH(9): FastAPI, uvicorn]
## @modulecontract
## @purpose ASGI application exposing health, KServe v2 infer, and OpenAI proxy endpoints for docling-serve integration.
## @changes
## LAST_CHANGE: [v0.2.15 – configure TRACE logging; correlate DOCLING/MODEL/GATEWAY hops by request_id.]
## @modulemap
## FUNC 10[Application factory] => create_app
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: FastAPI, app, health, KServe, OpenAI, uvicorn, gateway server, UpstreamApiError, TRACE, request_id
# STRUCTURE: ▶ create_app → ◇ configure logging → ⊕ routes with begin_request_trace → ⎋ FastAPI

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from doclingllm.gateway.admin.reload import build_gateway_state, reload_gateway_state
from doclingllm.gateway.client import ExternalApiClient, UpstreamApiError
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings
from doclingllm.gateway.kserve import (
    KSERVE_MODEL_TO_STAGE,
    build_kserve_model_metadata,
    handle_kserve_infer,
)
from doclingllm.gateway.kserve_binary import parse_kserve_infer_request
from doclingllm.gateway.openai_proxy import handle_openai_proxy
from doclingllm.gateway.request_logging import (
    begin_request_trace,
    configure_gateway_logging,
    log_docling_kserve_request,
    log_docling_openai_request,
    log_gateway_kserve_response,
    log_gateway_openai_response,
)
from doclingllm.gateway.routing import RoutingTable

logger = logging.getLogger(__name__)


# region CLASS_GatewayState [DOMAIN(7): GatewayApp; CONCEPT(7): AppState; TECH(7): dataclass-like]
## @purpose Hold shared gateway runtime objects attached to FastAPI app.state.
class GatewayState:
    def __init__(
        self,
        settings: GatewaySettings,
        routing_table: RoutingTable,
        client: ExternalApiClient,
    ):
        self.settings = settings
        self.routing_table = routing_table
        self.client = client


# endregion CLASS_GatewayState


# region FUNC_create_app [DOMAIN(9): GatewayApp; CONCEPT(9): Factory; TECH(9): FastAPI]
## @purpose Build configured FastAPI application with optional dependency injection for tests.
## @complexity 6
def create_app(
    settings: Optional[GatewaySettings] = None,
    routing_table: Optional[RoutingTable] = None,
    client: Optional[ExternalApiClient] = None,
    *,
    enable_admin_ui: bool = True,
) -> FastAPI:
    resolved_settings = settings or load_gateway_settings()
    configure_gateway_logging(resolved_settings.gateway_log_level)
    if routing_table is not None and client is not None:
        resolved_table = routing_table
        resolved_client = client
        initial_state = GatewayState(resolved_settings, resolved_table, resolved_client)
    else:
        initial_state = build_gateway_state(resolved_settings, client=client)
        resolved_table = initial_state.routing_table
        resolved_client = initial_state.client
    owns_client = client is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.gateway = initial_state
        logger.info(
            f"[IMP:9][create_app][STARTUP] Gateway ready on "
            f"{resolved_settings.gateway_host}:{resolved_settings.gateway_port} "
            f"log_level={resolved_settings.gateway_log_level} [OK]"
        )
        yield
        if owns_client:
            resolved_client.close()
        logger.info("[IMP:7][create_app][SHUTDOWN] Gateway stopped [OK]")

    app = FastAPI(title="doclingllm Model Gateway", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "doclingllm-gateway"}

    @app.get("/v2/health/ready")
    async def kserve_server_ready() -> dict[str, bool]:
        return {"ready": True}

    @app.get("/v2/models/{model_name}")
    async def kserve_model_metadata(model_name: str) -> JSONResponse:
        try:
            metadata = build_kserve_model_metadata(model_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(content=metadata)

    @app.get("/v2/models/{model_name}/ready")
    async def kserve_model_ready(model_name: str) -> JSONResponse:
        if model_name not in KSERVE_MODEL_TO_STAGE:
            raise HTTPException(status_code=404, detail=f"Unknown model: {model_name}")
        return JSONResponse(content={"ready": True})

    @app.post("/v2/models/{model_name}/infer")
    async def kserve_infer(model_name: str, request: Request) -> Response:
        state: GatewayState = app.state.gateway
        if model_name not in KSERVE_MODEL_TO_STAGE:
            raise HTTPException(status_code=404, detail=f"Unknown model: {model_name}")
        try:
            request_id = begin_request_trace(prefix=f"kserve-{model_name}")
            raw_body = await request.body()
            content_type = request.headers.get("content-type", "")
            header_len = request.headers.get("Inference-Header-Content-Length")
            framing = {
                "content_type": content_type,
                "content_length": request.headers.get("content-length"),
                "inference_header_content_length": header_len,
                "raw_body_bytes": len(raw_body),
                "binary_framing": bool(header_len)
                or "octet-stream" in content_type.lower(),
                "request_id": request_id,
            }
            body = parse_kserve_infer_request(raw_body, request.headers)
            log_docling_kserve_request(logger, model_name, body, framing=framing)
            result = handle_kserve_infer(
                model_name,
                body,
                state.client,
                state.routing_table,
                state.settings,
            )
            log_gateway_kserve_response(logger, model_name, result)
            return JSONResponse(content=result)
        except (ValueError, TypeError) as exc:
            # BUG_FIX_CONTEXT: bad request tensors and malformed VLM bbox must map to 400, not ASGI 500.
            logger.error(
                f"[IMP:10][kserve_infer][BAD_REQUEST] model={model_name} error={exc} [FATAL]"
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except UpstreamApiError as exc:
            logger.critical(
                f"[IMP:10][kserve_infer][UPSTREAM] model={model_name} error={exc} [FATAL]"
            )
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/v1/chat/completions")
    async def openai_chat_completions(request: Request) -> JSONResponse:
        state: GatewayState = app.state.gateway
        begin_request_trace(prefix="openai")
        body = await request.json()
        log_docling_openai_request(logger, body)
        try:
            result = handle_openai_proxy(
                body,
                state.client,
                state.routing_table,
                state.settings,
            )
            log_gateway_openai_response(logger, result)
            return JSONResponse(content=result)
        except UpstreamApiError as exc:
            logger.critical(
                f"[IMP:10][openai_chat_completions][UPSTREAM] {exc} [FATAL]"
            )
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            logger.critical(
                f"[IMP:10][openai_chat_completions][ERROR] {exc} [FATAL]"
            )
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/admin/reload")
    async def admin_reload() -> dict[str, str]:
        reload_gateway_state(app)
        return {"status": "ok", "message": "Gateway configuration reloaded from volume"}

    if enable_admin_ui:
        from doclingllm.gateway.admin.gradio_ui import mount_admin_ui

        mount_admin_ui(app)

    return app


# endregion FUNC_create_app


# region FUNC_run_gateway [DOMAIN(7): GatewayApp; CONCEPT(7): Entrypoint; TECH(7): uvicorn]
## @purpose CLI entrypoint for gateway container and local runs.
## @complexity 3
def run_gateway() -> None:
    import uvicorn

    settings = load_gateway_settings()
    app = create_app(settings=settings)
    uvicorn.run(
        app,
        host=settings.gateway_host,
        port=settings.gateway_port,
        log_level="info",
    )


# endregion FUNC_run_gateway

if __name__ == "__main__":
    run_gateway()
