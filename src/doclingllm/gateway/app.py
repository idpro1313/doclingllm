# region MODULE_CONTRACT [DOMAIN(9): GatewayApp; CONCEPT(9): FastAPI, Transport; TECH(9): FastAPI, uvicorn]
## @modulecontract
## @purpose ASGI application exposing health, KServe v2 infer, and OpenAI proxy endpoints for docling-serve integration.
## @changes
## LAST_CHANGE: [v0.2.0 Slice S4-S5 – FastAPI app with lifespan and route registration.]
## @modulemap
## FUNC 10[Application factory] => create_app
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: FastAPI, app, health, KServe, OpenAI, uvicorn, gateway server
# STRUCTURE: ▶ create_app → ◇ lifespan load config/routing → ⊕ register routes → ⎋ FastAPI

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from doclingllm.gateway.client import ExternalApiClient
from doclingllm.gateway.config import GatewaySettings, load_gateway_settings
from doclingllm.gateway.kserve import (
    KSERVE_MODEL_TO_STAGE,
    build_kserve_model_metadata,
    handle_kserve_infer,
)
from doclingllm.gateway.openai_proxy import handle_openai_proxy
from doclingllm.gateway.routing import RoutingTable, load_routing_table

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
) -> FastAPI:
    resolved_settings = settings or load_gateway_settings()
    resolved_table = routing_table or load_routing_table(
        resolved_settings.gateway_models_config_path,
        resolved_settings,
    )
    resolved_client = client or ExternalApiClient(resolved_settings)
    owns_client = client is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = GatewayState(resolved_settings, resolved_table, resolved_client)
        app.state.gateway = state
        logger.info(
            f"[IMP:9][create_app][STARTUP] Gateway ready on "
            f"{resolved_settings.gateway_host}:{resolved_settings.gateway_port} [OK]"
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
    async def kserve_infer(model_name: str, request: Request) -> JSONResponse:
        state: GatewayState = app.state.gateway
        if model_name not in KSERVE_MODEL_TO_STAGE:
            raise HTTPException(status_code=404, detail=f"Unknown model: {model_name}")
        try:
            body = await request.json()
            result = handle_kserve_infer(
                model_name,
                body,
                state.client,
                state.routing_table,
                state.settings,
            )
            return JSONResponse(content=result)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/chat/completions")
    async def openai_chat_completions(request: Request) -> JSONResponse:
        state: GatewayState = app.state.gateway
        body = await request.json()
        try:
            result = handle_openai_proxy(
                body,
                state.client,
                state.routing_table,
                state.settings,
            )
            return JSONResponse(content=result)
        except Exception as exc:
            logger.critical(
                f"[IMP:10][openai_chat_completions][ERROR] {exc} [FATAL]"
            )
            raise HTTPException(status_code=502, detail=str(exc)) from exc

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
