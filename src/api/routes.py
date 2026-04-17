# src/api/routes.py — UPDATED query endpoint (replace the existing one)
import time
import asyncio
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.requests import Request
import tempfile, os

from src.api.schemas import IngestRequest, IngestResponse, QueryRequest, QueryResponse
from src.api.dependencies import get_vectorstore, get_chunks, add_chunks
from src.ingestion.loader import load_pdf_smart
from src.ingestion.chunker import chunk_documents
from src.ingestion.embedder import embed_and_upsert
from src.generation.chain import run_rag_query
from src.observability import metrics, calculate_query_cost, calculate_ingestion_cost, budget_tracker
from config.settings import get_settings
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document

settings = get_settings()
router = APIRouter()
log = structlog.get_logger()


def _run_ingestion_pipeline(pdf_path: str, cleanup_after: bool = False) -> None:
    """Ingestion pipeline — now with structured logging and cost tracking."""
    ingest_start = time.perf_counter()
    log.info("ingestion_started", pdf_path=pdf_path)

    try:
        docs = load_pdf_smart(pdf_path)
        log.info("pdf_loaded", pages=len(docs), pdf_path=pdf_path)

        chunks = chunk_documents(docs)
        log.info("chunking_complete", chunks=len(chunks), pdf_path=pdf_path)

        add_chunks(chunks)

        upsert_start = time.perf_counter()
        count = embed_and_upsert(chunks, pdf_path)
        upsert_ms = (time.perf_counter() - upsert_start) * 1000

        # Track ingestion cost
        # Detect if OCR was used: if docs have no page metadata, OCR ran
        ocr_pages = sum(1 for d in docs if not d.metadata.get("page"))
        cost = calculate_ingestion_cost(
            total_chunks=count,
            ocr_pages=ocr_pages,
        )
        budget_tracker.record(cost)
        metrics.increment("ingestion.documents_processed")
        metrics.increment("ingestion.chunks_total", count)

        total_ms = (time.perf_counter() - ingest_start) * 1000
        metrics.record_latency("ingestion.total", total_ms)

        log.info(
            "ingestion_complete",
            vectors_upserted=count,
            ocr_pages=ocr_pages,
            upsert_ms=round(upsert_ms, 1),
            total_ms=round(total_ms, 1),
            cost_usd=round(cost.total_usd, 6),
        )

    except Exception as e:
        metrics.record_error("ingestion", type(e).__name__)
        log.error("ingestion_failed", error=str(e), pdf_path=pdf_path, exc_info=True)
    finally:
        if cleanup_after and os.path.exists(pdf_path):
            os.remove(pdf_path)


@router.post("/ingest/path", response_model=IngestResponse, status_code=202)
async def ingest_from_path(
    request: Request,
    body: IngestRequest,
    background_tasks: BackgroundTasks,
):
    if not os.path.exists(body.pdf_path):
        raise HTTPException(status_code=404, detail=f"File not found: {body.pdf_path}")

    log.info("ingest_request_accepted", pdf_path=body.pdf_path)
    background_tasks.add_task(_run_ingestion_pipeline, body.pdf_path, cleanup_after=False)

    return IngestResponse(
        status="accepted",
        message="Ingestion started in background",
        pdf_path=body.pdf_path,
    )


@router.post("/ingest/upload", response_model=IngestResponse, status_code=202)
async def ingest_uploaded_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    log.info("file_upload_accepted", filename=file.filename, size_bytes=len(content))
    background_tasks.add_task(_run_ingestion_pipeline, tmp_path, cleanup_after=True)

    return IngestResponse(
        status="accepted",
        message=f"File '{file.filename}' accepted for ingestion",
        pdf_path=tmp_path,
    )


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: Request,
    body: QueryRequest,
    vectorstore: PineconeVectorStore = Depends(get_vectorstore),
    chunks: list[Document] = Depends(get_chunks),
):
    request_id = getattr(request.state, "request_id", "unknown")
    start = time.perf_counter()

    log.info("query_started", question_len=len(body.question), chunks_available=len(chunks))

    if not chunks:
        metrics.record_error("query", "no_chunks")
        raise HTTPException(status_code=503, detail="No documents ingested yet.")

    metrics.increment("query.requests_total")

    try:
        result = await asyncio.to_thread(
            run_rag_query,
            body.question,
            chunks,
            vectorstore,
        )
    except Exception as e:
        metrics.record_error("query", type(e).__name__)
        log.error("query_pipeline_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Pipeline error") from e

    latency_ms = (time.perf_counter() - start) * 1000
    metrics.record_latency("query.total", latency_ms)

    # ── Cost calculation ─────────────────────────────────────────────────────
    # result["usage"] comes from the LLM response — we need to pass it through.
    # For now we estimate from typical token counts; Hour 5 wires actual usage.
    est_input_tokens  = len(body.question.split()) * 2 + (result["chunk_count"] * 150)
    est_output_tokens = len(result["answer"].split()) * 2

    cost = calculate_query_cost(
        input_tokens=est_input_tokens,
        output_tokens=est_output_tokens,
        docs_reranked=10 if result["reranked"] else 0,
        pinecone_read_units=10,
    )
    budget_tracker.record(cost)
    metrics.increment("query.tokens_in_total",  est_input_tokens)
    metrics.increment("query.tokens_out_total", est_output_tokens)

    log.info(
        "query_complete",
        latency_ms=round(latency_ms, 1),
        reranked=result["reranked"],
        chunk_count=result["chunk_count"],
        answer_len=len(result["answer"]),
        **cost.to_dict(),
    )

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        chunk_count=result["chunk_count"],
        reranked=result["reranked"],
        latency_ms=round(latency_ms, 1),
        request_id=request_id,
    )


@router.get("/status")
async def pipeline_status(chunks: list[Document] = Depends(get_chunks)):
    return {
        "chunks_in_memory": len(chunks),
        "index_name": settings.pinecone_index_name,
        "ready": len(chunks) > 0,
    }


@router.get("/metrics")
async def get_metrics():
    """
    Expose all in-process metrics as JSON.
    
    CONCEPT: pull-based metrics.
    CloudWatch Agent, Prometheus, or even a simple cron job can
    call this endpoint and scrape the current metric state.
    This is the monitoring dashboard data source.
    """
    snapshot = metrics.get_snapshot()
    snapshot["cost"] = {
        "today_usd": round(budget_tracker.get_today_spend(), 4),
        "all_days": {k: round(v, 4) for k, v in budget_tracker.get_all_spend().items()},
    }
    return snapshot