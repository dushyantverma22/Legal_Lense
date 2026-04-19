# src/api/main.py
import time
import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import structlog
from structlog.contextvars import clear_contextvars, bind_contextvars
from config.logging_config import setup_logging

from src.api.routes import router
from src.api.dependencies import init_vectorstore
from src.api.schemas import ErrorResponse
from config.settings import get_settings

settings = get_settings()

log = structlog.get_logger()

# ─── Lifespan (startup + shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────
    setup_logging()
    log.info("startup_beginning", index=settings.pinecone_index_name)

    init_vectorstore()

    log.info("startup_complete", status="ready")

    yield  # 🚀 App runs here

    # ── Graceful Shutdown ─────────────────────
    log.info("shutdown_initiated", reason="SIGTERM received")

    # If you had resources, clean them here:
    # await db.close()
    # await redis.close()
    # close pinecone if needed (not required currently)

    # Small delay for log flushing (optional)
    await asyncio.sleep(0.1)

    log.info("shutdown_complete", status="clean_exit")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LegalLense RAG API",
    description="Production RAG API for legal document question-answering",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Middleware ────────────────────────────────────────────────────────────────

# CORS — allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this to your frontend URL in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def structlog_request_context(request: Request, call_next) -> Response:
    """Bind request_id to structlog context — auto-appears in all log calls."""
    clear_contextvars()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    bind_contextvars(request_id=request_id, path=request.url.path, method=request.method)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def add_process_time(request: Request, call_next) -> Response:
    """
    CONCEPT: Latency tracking at the HTTP layer.
    Measures total time including all middleware, not just pipeline time.
    This is what the user actually experiences.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    CONCEPT: Never let a raw Python exception reach the caller.
    Without this, FastAPI returns an HTML 500 page on unhandled errors.
    This catches everything and returns clean JSON.
    
    The request_id in the error lets callers tell you exactly
    which request failed when they contact support.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    print(f"[error] Unhandled exception on request {request_id}: {exc}")

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.openai_api_key else None,  # hide details in prod
            request_id=request_id,
        ).model_dump(),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """
    Simple liveness check — AWS ALB, k8s, and load balancers ping this.
    Must respond in <100ms and require no external calls.
    """
    return {"status": "ok", "version": "0.1.0"}