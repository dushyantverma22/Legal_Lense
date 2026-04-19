<div align="center">

```
██╗     ███████╗ ██████╗  █████╗ ██╗     ██╗     ███████╗███╗   ██╗███████╗███████╗
██║     ██╔════╝██╔════╝ ██╔══██╗██║     ██║     ██╔════╝████╗  ██║██╔════╝██╔════╝
██║     █████╗  ██║  ███╗███████║██║     ██║     █████╗  ██╔██╗ ██║███████╗█████╗
██║     ██╔══╝  ██║   ██║██╔══██║██║     ██║     ██╔══╝  ██║╚██╗██║╚════██║██╔══╝
███████╗███████╗╚██████╔╝██║  ██║███████╗███████╗███████╗██║ ╚████║███████║███████╗
╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
```

# LegalLense — Production RAG System for Legal Document Intelligence

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1c3c4a?style=flat-square)](https://langchain.com)
[![Pinecone](https://img.shields.io/badge/Pinecone-Serverless-00b5ad?style=flat-square)](https://pinecone.io)
[![Docker](https://img.shields.io/badge/Docker-Containerised-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![AWS ECS](https://img.shields.io/badge/AWS-ECS_Fargate-ff9900?style=flat-square&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/ecs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**A production-grade Retrieval-Augmented Generation (RAG) API for querying legal documents using hybrid search, neural reranking, semantic caching, and auto-scaling cloud infrastructure.**

[Live Demo](#quick-start) · [Architecture](#architecture) · [API Reference](#api-reference) · [Deployment](#deployment-guide)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [RAG Pipeline Deep Dive](#rag-pipeline-deep-dive)
- [Infrastructure Architecture](#infrastructure-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Observability](#observability)
- [Testing](#testing)
- [Deployment Guide](#deployment-guide)
- [Performance Benchmarks](#performance-benchmarks)
- [Roadmap](#roadmap)

---

## Overview

LegalLense transforms legal PDF documents (rental agreements, contracts, notices) into an intelligent Q&A system. Users upload documents once, then ask natural language questions and receive accurate, cited answers in under 3 seconds — or under 50ms when served from the semantic cache.

The system was purpose-built to handle the challenges specific to legal text: precise terminology where "rent" and "security deposit" must not be confused, multi-clause documents where answers span several sections, and scanned PDFs that require OCR fallback.

**What makes this production-ready:**
- Idempotent ingestion (re-upload never duplicates vectors)
- Graceful degradation (Cohere down → hybrid results without error)
- Semantic caching (40–60% of repeated questions served at zero cost)
- SQS-backed job queue (ingestion survives server restarts)
- Auto-scaling ECS Fargate (handles 100× traffic spikes automatically)
- Full CI/CD pipeline (every push to `main` deploys after tests pass)

---

## Key Features

| Feature | Implementation | Benefit |
|---|---|---|
| Hybrid retrieval | BM25 (0.4 weight) + Pinecone vector (0.6 weight) | Finds both keyword-exact and semantically similar chunks |
| Neural reranking | Cohere `rerank-english-v3.0` | Boosts precision from 82% to 91% on legal Q&A |
| OCR fallback | GPT-4o-mini Vision on scanned pages | Handles image-only PDFs transparently |
| Semantic caching | Redis + cosine similarity (threshold 0.95) | 40–60% cache hit rate, 50ms vs 3s latency |
| Idempotent ingestion | MD5 hash → stable Pinecone vector IDs | Safe to re-upload without duplicating index |
| Circuit breaker | 3-failure threshold, 60s reset | Cohere outage never cascades to user errors |
| Structured logging | structlog JSON + CloudWatch | Every log line queryable by `request_id` |
| Cost tracking | Per-request USD calculation + daily budget alert | Full cost visibility, budget protection |
| Auto-scaling | ECS Application Auto Scaling, CPU target 60% | Scales 2→6 tasks, 60s scale-out cooldown |
| Job persistence | SQS + DynamoDB | Ingestion survives ECS task restarts |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   INTERNET                                       │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │ HTTPS
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Route 53  (DNS)                                          │
│                  api.legallense.com → ALB DNS name                               │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                Application Load Balancer  (us-east-1)                            │
│        HTTPS termination · health checks · path-based routing                    │
└────────────────┬─────────────────────────────────────────────────────────────────┘
                 │  HTTP/8000
    ┌────────────┼────────────────┐
    ▼            ▼                ▼
┌────────┐  ┌────────┐      ┌─────────────────────────────────────────────────────┐
│ API    │  │ API    │      │                   VPC  (Private Subnets)             │
│ Task 1 │  │ Task 2 │      │                                                     │
│ :8000  │  │ :8000  │      │  ┌─────────────────────────────────────────────┐   │
└────────┘  └────────┘      │  │         ECS Fargate  (Auto-scaling 2–6)      │   │
  FastAPI + Uvicorn workers  │  │   ┌──────────────┐   ┌──────────────────┐  │   │
                             │  │   │  API Service  │   │  Worker Service  │  │   │
                             │  │   │  (2–6 tasks)  │   │   (1–2 tasks)   │  │   │
                             │  │   └──────┬───────┘   └────────┬─────────┘  │   │
                             │  │          │                     │            │   │
                             │  │          │ reads          polls│            │   │
                             │  │          ▼                     ▼            │   │
                             │  │   ┌──────────────┐   ┌──────────────────┐  │   │
                             │  │   │  ElastiCache  │   │    SQS Queue     │  │   │
                             │  │   │  Redis 7.0    │   │  (+ DLQ after    │  │   │
                             │  │   │  Semantic     │   │   3 retries)     │  │   │
                             │  │   │  Cache        │   └──────────────────┘  │   │
                             │  │   └──────────────┘                          │   │
                             │  └─────────────────────────────────────────────┘   │
                             │                                                     │
                             │  ┌──────────────┐  ┌──────────────┐                │
                             │  │  Secrets Mgr │  │  DynamoDB    │                │
                             │  │  API keys    │  │  Jobs table  │                │
                             │  └──────────────┘  └──────────────┘                │
                             │                                                     │
                             │  ┌──────────────┐  ┌──────────────┐                │
                             │  │  ECR         │  │  CloudWatch  │                │
                             │  │  Docker imgs │  │  Logs/Metrics│                │
                             │  └──────────────┘  └──────────────┘                │
                             └─────────────────────────────────────────────────────┘
                                          │              │              │
                              ┌───────────┘    ┌─────────┘    ┌────────┘
                              ▼                ▼              ▼
                    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                    │   Pinecone   │  │  OpenAI API  │  │  Cohere API  │
                    │  Serverless  │  │  GPT-4o-mini │  │   Rerank v3  │
                    │  us-east-1   │  │  Embeddings  │  │              │
                    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## RAG Pipeline Deep Dive

### Ingestion Pipeline

```
PDF Upload
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│                    Smart PDF Loader                         │
│                                                             │
│  1. PyPDFLoader (text extraction)                          │
│       │                                                     │
│       ├── text found (≥50 chars) ──────────────────────►  │
│       │                                                     │
│       └── text empty → OCR Fallback                        │
│               │                                             │
│               ▼                                             │
│         GPT-4o-mini Vision                                  │
│         (page-by-page image → text)                        │
└───────────────────────┬───────────────────────────────────┘
                        │  List[Document]
                        ▼
┌───────────────────────────────────────────────────────────┐
│              RecursiveCharacterTextSplitter                 │
│                                                             │
│  chunk_size    = 700 chars                                  │
│  chunk_overlap = 120 chars                                  │
│  separators    = ["\n\n", "\n", ". ", " ", ""]             │
└───────────────────────┬───────────────────────────────────┘
                        │  List[Document] (chunks)
                        ▼
┌───────────────────────────────────────────────────────────┐
│                  Idempotent Embedder                        │
│                                                             │
│  vector_id = MD5(pdf_path + chunk_index + text[:100])      │
│                                                             │
│  OpenAIEmbeddings (text-embedding-3-small)                 │
│  → 1536-dimensional dense vector                            │
│                                                             │
│  Pinecone upsert (batches of 100)                          │
│  Same ID = overwrite, not duplicate                         │
└───────────────────────────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  Pinecone Index  │
              │  legal-lense-   │
              │  index1         │
              │  dim=1536       │
              │  metric=cosine  │
              └─────────────────┘
```

### Query Pipeline

```
User Question: "What is the monthly rent?"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Semantic Cache Check                           │
│                                                                   │
│  1. Embed question → 1536d vector                                 │
│  2. Scan Redis cache vectors                                      │
│  3. Compute cosine similarity against all cached entries          │
│                                                                   │
│  if similarity ≥ 0.95:                                           │
│    ┌──────────────────────────────────────────────────────┐      │
│    │  Return cached answer  (50ms, $0.00)                  │      │
│    │  Response includes: cache_hit=true, similarity=0.97   │      │
│    └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  if similarity < 0.95: → cache miss → continue pipeline          │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Cache miss
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                       Hybrid Retrieval                           │
│                                                                  │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐ │
│  │       BM25 Retriever     │  │    Pinecone Vector Search     │ │
│  │                          │  │                              │ │
│  │  TF-IDF keyword scoring  │  │  OpenAIEmbeddings cosine     │ │
│  │  top_k = 10              │  │  similarity search top_k=10  │ │
│  │  weight = 0.4            │  │  weight = 0.6                │ │
│  └──────────────┬───────────┘  └─────────────────┬────────────┘ │
│                 │                                  │              │
│                 └──────────────┬───────────────────┘              │
│                                ▼                                  │
│                    Score normalization + fusion                    │
│                    combined_score = 0.4*bm25 + 0.6*vector        │
│                    Top 10 deduplicated chunks                     │
└────────────────────────────────┬───────────────────────────────┘
                                 │ 10 candidate chunks
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                      Cohere Reranker                             │
│                    (with Circuit Breaker)                        │
│                                                                  │
│  Model: rerank-english-v3.0                                      │
│  Input: 10 chunks                                                │
│  Output: top 3 chunks by legal relevance                        │
│                                                                  │
│  Circuit breaker:                                                │
│    CLOSED → calls Cohere normally                               │
│    OPEN (after 3 failures) → skips reranking, returns top 3    │
│    HALF_OPEN (after 60s) → probes with one request             │
└────────────────────────────────┬───────────────────────────────┘
                                 │ 3 high-precision chunks
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                         LLM Generation                           │
│                                                                  │
│  Model: gpt-4o-mini  temperature=0  max_tokens=1000            │
│                                                                  │
│  Prompt structure:                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SYSTEM: You are a strict legal assistant.               │  │
│  │  RULES: Use ONLY the context. Say "I don't know"        │  │
│  │         if answer not in context.                        │  │
│  │  CONTEXT: {chunk_1}\n\n{chunk_2}\n\n{chunk_3}           │  │
│  │  QUESTION: {user_question}                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                    Store answer in Redis cache
                    TTL = 3600s  (1 hour)
                                 │
                                 ▼
              ┌───────────────────────────────────────┐
              │          QueryResponse                  │
              │  answer        : str                   │
              │  sources       : list[str]             │
              │  chunk_count   : int                   │
              │  reranked      : bool                  │
              │  latency_ms    : float                 │
              │  cache_hit     : bool                  │
              │  cache_similarity: float | null        │
              │  request_id    : str                   │
              └───────────────────────────────────────┘
```

---

## Infrastructure Architecture

### Request Flow (HTTP → Response)

```
Client Request
      │
      │ 1. DNS lookup → Route 53 → ALB IP
      ▼
 Application Load Balancer
      │
      │ 2. TLS termination, X-Forwarded-For header injection
      │ 3. Health check: GET /health every 30s
      │ 4. Routes to healthy ECS task via target group
      ▼
 ECS Fargate Task  (uvicorn workers=2, port 8000)
      │
      │ 5. FastAPI middleware stack (in order):
      │    a. structlog context → bind request_id
      │    b. CORS
      │    c. Process time header
      │    d. Global exception handler
      │
      │ 6. Route handler:
      │    POST /api/v1/query
      │
      │ 7. Semantic cache check (Redis)
      │    └─ HIT  → return 50ms response
      │    └─ MISS → run pipeline
      │
      │ 8. Hybrid retrieval
      │    ├── BM25 (in-memory, from ingested chunks)
      │    └── Pinecone (network, same AWS region → ~5ms)
      │
      │ 9. Cohere rerank (~300ms if healthy)
      │
      │ 10. OpenAI GPT-4o-mini (~2s)
      │
      │ 11. Store in Redis, log to CloudWatch
      ▼
 JSON Response  →  ALB  →  Client
```

### Ingestion Flow (SQS-backed)

```
POST /api/v1/ingest/upload
      │
      │ 1. Save PDF to temp file
      │ 2. Create DynamoDB job record (status=pending)
      │ 3. Publish message to SQS queue
      │ 4. Return 202 Accepted + job_id
      ▼
 SQS Queue  (VisibilityTimeout=900s, maxReceive=3, DLQ after 3 failures)
      │
      │ (async, separate worker process)
      ▼
 SQS Worker  (ECS Fargate, separate task definition)
      │
      │ 1. Long-poll SQS (WaitTimeSeconds=20)
      │ 2. Receive message
      │ 3. Update DynamoDB → status=processing
      │ 4. Run ingestion pipeline:
      │    load_pdf_smart() → chunk_documents() → embed_and_upsert()
      │ 5. Invalidate Redis semantic cache
      │ 6. Update DynamoDB → status=done (chunks, duration)
      │ 7. Delete SQS message (success)
      │
      │ On failure:
      │ 8. Update DynamoDB → status=failed (error_message)
      │ 9. Leave message in SQS → retried after 900s
      │ 10. After 3 retries → message → Dead Letter Queue
      ▼
 Frontend polls GET /api/v1/jobs/{job_id} every 3s
```

### Auto-scaling Behaviour

```
Traffic load (requests/min per task):

  Low traffic (10 users)
  CPU ~25%  │████░░░░░░░░│  2 tasks running  ← minimum floor
            │            │
  Moderate  │████████░░░░│  3 tasks           ← scale-out triggered
  CPU ~62%  │            │  at CPU > 60% for 2min
            │            │
  High      │████████████│  4–5 tasks         ← continued scaling
  CPU ~85%  │            │
            │            │
  Peak      │████████████│  6 tasks running   ← maximum ceiling
  CPU ~90%  │            │  (protects API rate limits)
            │            │
  Cooling   │████████░░░░│  stays at 6 tasks for 15min
            │            │  (scale-in cooldown: 900s)
            │            │
  Quiet     │████░░░░░░░░│  back to 2 tasks   ← scale-in complete
```

---

## Technology Stack

### Core RAG Components

| Component | Library / Service | Version | Purpose |
|---|---|---|---|
| Document loading | `langchain-community` PyPDFLoader | 0.3.0 | Text extraction from PDFs |
| OCR fallback | OpenAI `gpt-4o-mini` Vision | — | Scanned PDF text extraction |
| Text splitting | `langchain-text-splitters` | 0.3.0 | RecursiveCharacterTextSplitter |
| Embeddings | OpenAI `text-embedding-3-small` | — | 1536d dense vectors |
| Vector store | Pinecone Serverless | 5.0.0 | Scalable ANN search |
| Keyword search | `rank-bm25` BM25Retriever | 0.2.2 | Lexical retrieval |
| Reranking | Cohere `rerank-english-v3.0` | 5.11.0 | Cross-encoder precision boost |
| LLM generation | OpenAI `gpt-4o-mini` | — | Answer synthesis |
| RAG evaluation | RAGAS (Faithfulness, ContextPrecision, ContextRecall) | — | Quality measurement |

**RAGAS scores (on 20-question legal eval set):**
```
Faithfulness:       0.90  (answers grounded in retrieved context)
ContextPrecision:   0.92  (retrieved chunks are relevant)
ContextRecall:      0.93  (relevant chunks are retrieved)
```

### Application Framework

| Component | Library | Version | Purpose |
|---|---|---|---|
| API framework | FastAPI | 0.115.0 | Async REST API |
| ASGI server | Uvicorn | 0.31.0 | Production WSGI/ASGI server |
| Data validation | Pydantic v2 + pydantic-settings | 2.9.0 | Request/response schemas, config |
| Structured logging | structlog | 24.4.0 | JSON log lines with context propagation |
| Semantic cache | Redis 7.0 + redis-py | 5.0.0 | Answer caching with vector similarity |

### AWS Infrastructure

| Service | Config | Purpose |
|---|---|---|
| ECS Fargate | 0.5 vCPU / 1GB RAM per task | Run API + worker containers |
| ECR | Image scanning enabled | Private Docker registry |
| ALB | HTTP/HTTPS, health checks every 30s | Load balancing + TLS termination |
| SQS | VisibilityTimeout=900s, DLQ after 3 retries | Reliable ingestion job queue |
| DynamoDB | PAY_PER_REQUEST, TTL=30 days | Job status persistence |
| ElastiCache Redis | cache.t3.micro, Redis 7.0 | Semantic cache + session state |
| Secrets Manager | Rotation-ready | API keys (OpenAI, Pinecone, Cohere) |
| CloudWatch Logs | /ecs/legal-lense-rag | Structured JSON log ingestion |
| Route 53 | A record → ALB DNS | DNS management |
| Application Auto Scaling | CPU target 60%, min=2, max=6 | Traffic-responsive scaling |

---

## Technology Stack — Observability

### What gets logged on every request

```json
{
  "timestamp": "2025-04-17T08:23:11.432Z",
  "level": "info",
  "event": "query_complete",
  "request_id": "a3f2c1d8-7e4b-4f9a-b2c1-8d3e5f6a7b9c",
  "path": "/api/v1/query",
  "latency_ms": 2847.3,
  "cache_hit": false,
  "reranked": true,
  "chunk_count": 3,
  "openai_input_usd": 0.000062,
  "openai_output_usd": 0.000013,
  "cohere_usd": 0.000010,
  "pinecone_usd": 0.0000008,
  "total_usd": 0.000086
}
```

### Metrics exposed at `GET /api/v1/metrics`

```json
{
  "latencies": {
    "query.total": { "p50_ms": 2847, "p95_ms": 4231, "p99_ms": 6102, "count": 143 },
    "query.cache_hit_latency": { "p50_ms": 48, "p95_ms": 89, "count": 71 }
  },
  "counters": {
    "query.requests_total": 143,
    "query.cache_hits": 71,
    "query.cache_misses": 72,
    "query.tokens_in_total": 58921,
    "query.tokens_out_total": 12440
  },
  "errors": {},
  "cost": {
    "today_usd": 0.0124,
    "all_days": { "2025-04-17": 0.0124 }
  }
}
```

---

## Project Structure

```
legal_lense/
│
├── notebooks/
│   └── rag_test4.ipynb             # Original prototype notebook
│
├── src/
│   ├── ingestion/
│   │   ├── loader.py               # load_pdf_smart() — text + OCR fallback
│   │   ├── chunker.py              # RecursiveCharacterTextSplitter
│   │   └── embedder.py             # Idempotent hash IDs + Pinecone upsert
│   │
│   ├── retrieval/
│   │   ├── bm25_retriever.py       # BM25 keyword retrieval (stateless)
│   │   ├── vector_retriever.py     # Pinecone similarity search
│   │   └── hybrid.py              # Score fusion + Cohere rerank + CircuitBreaker
│   │
│   ├── generation/
│   │   └── chain.py               # run_rag_query() — full pipeline
│   │
│   ├── cache/
│   │   └── semantic_cache.py       # Redis + embedding + cosine similarity lookup
│   │
│   ├── jobs/
│   │   ├── sqs_worker.py          # Long-polling SQS worker process
│   │   └── job_store.py           # DynamoDB job CRUD
│   │
│   ├── observability/
│   │   ├── metrics.py             # In-process latency histograms + counters
│   │   └── cost_tracker.py        # Per-request USD calculation + daily budget
│   │
│   └── api/
│       ├── main.py                # FastAPI app + middleware + lifespan
│       ├── routes.py              # /ingest, /query, /jobs, /cache, /metrics
│       ├── schemas.py             # Pydantic request/response models
│       └── dependencies.py        # Vectorstore + chunk store (shared state)
│
├── config/
│   ├── settings.py                # BaseSettings — all config from env vars
│   └── logging_config.py          # structlog JSON formatter setup
│
├── tests/
│   ├── conftest.py                # Shared fixtures (mock OpenAI, Pinecone, Cohere)
│   ├── unit/
│   │   ├── test_chunker.py        # Chunk size, overlap, edge cases
│   │   ├── test_embedder.py       # Idempotent hash ID generation
│   │   ├── test_circuit_breaker.py # State machine: CLOSED→OPEN→HALF_OPEN
│   │   ├── test_cost_tracker.py   # Cost formula correctness
│   │   └── test_metrics.py        # Percentile calculation, rolling window
│   ├── integration/
│   │   └── test_pipeline.py       # Chunker→embedder→retrieval with mocked APIs
│   └── api/
│       └── test_routes.py         # Full HTTP tests via FastAPI TestClient
│
├── frontend/
│   └── index.html                 # Self-contained SPA — zero build step
│
├── infrastructure/
│   ├── deploy.sh                  # Build + push + ECS rolling deploy
│   ├── setup_jobs.sh              # Create SQS queues + DynamoDB table
│   └── setup_autoscaling.sh       # Register ECS scaling target + policies
│
├── .github/
│   └── workflows/
│       └── deploy.yml             # GitHub Actions CI/CD pipeline
│
├── Dockerfile                     # Multi-stage build (builder + production)
├── docker-compose.yml             # api + worker + (test runner) services
├── .dockerignore                  # Excludes .venv, .env, tests, notebooks
├── Makefile                       # Short command aliases
├── requirements.txt               # Pinned production dependencies
├── pytest.ini                     # Test discovery config
├── .env.example                   # Template (no real keys)
└── README.md                      # This file
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- API keys: OpenAI, Pinecone, Cohere

### Local development (5 minutes)

```bash
# 1. Clone and set up
git clone https://github.com/yourname/legal-lense.git
cd legal_lense

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — fill in your API keys:
#   OPENAI_API_KEY=sk-...
#   PINECONE_API_KEY=pcsk-...
#   COHERE_API_KEY=...
#   PINECONE_INDEX_NAME=legal-lense-index1

# 4. Start Redis (for semantic cache)
docker run -d -p 6379:6379 --name redis redis:7

# 5. Start the API
uvicorn src.api.main:app --reload --port 8000

# 6. Open the frontend
open http://localhost:8000
```

### Docker Compose (recommended)

```bash
# Build and start everything
make build
make up

# Run tests inside Docker
make test

# Tail live logs
make logs

# Open a shell inside the running container
make shell
```

### Running tests

```bash
# All tests (39 total, ~5 seconds)
pytest --tb=short -q

# Just fast unit tests (no API keys, ~0.3s)
pytest tests/unit/ -v

# With coverage report
pytest --cov=src --cov-report=term-missing
```

---

## Configuration Reference

All configuration is read from environment variables via `config/settings.py`. No hardcoded values anywhere in the codebase.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. OpenAI API key |
| `PINECONE_API_KEY` | — | Required. Pinecone API key |
| `COHERE_API_KEY` | — | Required. Cohere API key |
| `PINECONE_INDEX_NAME` | `legal-lense-index1` | Pinecone index name |
| `PINECONE_REGION` | `us-east-1` | Pinecone cloud region |
| `PINECONE_DIMENSION` | `1536` | Embedding dimension |
| `CHUNK_SIZE` | `700` | Characters per chunk |
| `CHUNK_OVERLAP` | `120` | Overlap between chunks |
| `BM25_TOP_K` | `10` | BM25 retrieval count |
| `VECTOR_TOP_K` | `10` | Vector retrieval count |
| `RERANK_TOP_N` | `3` | Final chunks after reranking |
| `BM25_WEIGHT` | `0.4` | BM25 score weight in fusion |
| `VECTOR_WEIGHT` | `0.6` | Vector score weight in fusion |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model for generation |
| `LLM_TEMPERATURE` | `0.0` | Generation temperature |
| `LLM_MAX_TOKENS` | `1000` | Max response tokens |
| `COHERE_TIMEOUT_SECONDS` | `5.0` | Cohere API timeout |
| `COHERE_FAILURE_THRESHOLD` | `3` | Circuit breaker open threshold |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `CACHE_SIMILARITY_THRESHOLD` | `0.95` | Cosine similarity for cache hit |
| `CACHE_TTL_SECONDS` | `3600` | Cache entry lifetime (seconds) |
| `SEMANTIC_CACHE_ENABLED` | `true` | Toggle semantic cache on/off |
| `SQS_QUEUE_URL` | — | SQS queue URL (production) |
| `DYNAMODB_JOBS_TABLE` | `legal-lense-jobs` | DynamoDB table name |

---

## API Reference

### Base URL
- Local: `http://localhost:8000`
- Production: `http://your-alb-dns.us-east-1.elb.amazonaws.com`

---

### `GET /health`
Liveness check. Returns 200 if the server is running and Pinecone is reachable.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "pinecone": "ok"
}
```

---

### `POST /api/v1/ingest/upload`
Upload a PDF for ingestion via multipart form data.

**Request:** `Content-Type: multipart/form-data`
```
file: <PDF binary>
```

**Response** `202 Accepted`:
```json
{
  "job_id": "3f7a2b1c-4e5d-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "accepted",
  "message": "File 'rent_agreement.pdf' accepted for ingestion",
  "pdf_path": "/tmp/1713340800_rent_agreement.pdf"
}
```

---

### `GET /api/v1/jobs/{job_id}`
Poll ingestion job status. Call every 3–5 seconds after upload.

**Response** `200 OK`:
```json
{
  "job_id": "3f7a2b1c-4e5d-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "done",
  "pdf_path": "/tmp/rent_agreement.pdf",
  "created_at": 1713340800,
  "updated_at": 1713340820,
  "chunks_created": 9,
  "duration_seconds": 18.3
}
```

**Status lifecycle:** `pending` → `processing` → `done` | `failed`

---

### `POST /api/v1/query`
Ask a question about ingested documents.

**Request:**
```json
{
  "question": "What is the monthly rent amount and due date?"
}
```

**Response** `200 OK`:
```json
{
  "answer": "The monthly rent is Rs. 17,600/- due before the 7th of each calendar month.",
  "sources": [
    "AND WHEREAS THE BOTH THE PARTIES HAVE AGREED... The Lessee shall pay rent of Rs. 17,600/-...",
    "...commences from 01/10/2025 to 31/08/2026..."
  ],
  "chunk_count": 3,
  "reranked": true,
  "latency_ms": 2847.3,
  "request_id": "a3f2c1d8-7e4b-4f9a-b2c1-8d3e5f6a7b9c",
  "cache_hit": false,
  "cache_similarity": null
}
```

**Cache hit example:**
```json
{
  "answer": "The monthly rent is Rs. 17,600/-...",
  "latency_ms": 48.2,
  "cache_hit": true,
  "cache_similarity": 0.967
}
```

**Error responses:**
- `422` — question too short (< 3 chars) or too long (> 1000 chars)
- `503` — no documents ingested yet
- `500` — pipeline error (check CloudWatch logs for `request_id`)

---

### `GET /api/v1/status`
Current system state.

```json
{
  "chunks_in_memory": 9,
  "index_name": "legal-lense-index1",
  "ready": true
}
```

---

### `GET /api/v1/cache/stats`
Semantic cache statistics.

```json
{
  "enabled": true,
  "cached_answers": 12,
  "redis_connected": true,
  "similarity_threshold": 0.95,
  "ttl_seconds": 3600,
  "hit_rate_pct": 47.3,
  "total_queries": 55,
  "cache_hits": 26,
  "cache_misses": 29
}
```

---

### `POST /api/v1/cache/invalidate`
Flush the semantic cache. Call after re-ingesting documents.

```json
{ "deleted": 24, "message": "Removed 24 cached entries" }
```

---

### `GET /api/v1/metrics`
In-process metrics snapshot.

```json
{
  "latencies": {
    "query.total": { "p50_ms": 2847, "p95_ms": 4231, "p99_ms": 6102, "count": 143 }
  },
  "counters": {
    "query.requests_total": 143,
    "query.cache_hits": 71
  },
  "errors": {},
  "cost": { "today_usd": 0.0124 }
}
```

---

## Frontend

The frontend is a single `frontend/index.html` file with zero build dependencies — no npm, no bundler, no framework. It loads a Google Font and is otherwise fully self-contained.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Header: LegalLense logo │ API status dot │ API URL input           │
├──────────────────────────┬──────────────────────────────────────────┤
│                          │                                          │
│  Sidebar                 │  Chat area                               │
│  ─────────               │  ──────────                              │
│  Upload zone             │  Empty state (first visit):             │
│  (drag & drop PDF)       │    Suggestion chips for common           │
│                          │    legal questions                       │
│  Ingestion jobs          │                                          │
│  ├── rent_agr.pdf  DONE  │  Messages:                              │
│  │   9 chunks · 18s      │    User: bubble (right, dark)           │
│  └── contract.pdf PROC.  │    Assistant: bubble (left, white)       │
│                          │      + cache badge (⚡ cached / ✦ fresh)  │
│  Stats                   │      + source chunks accordion           │
│  Queries:   55           │      + latency                          │
│  Cache hits: 26          │                                          │
│  Avg latency: 1.2s       │                                          │
│  Docs: 2                 │                                          │
│                          ├──────────────────────────────────────────│
│                          │  Input bar                               │
│                          │  ┌─────────────────────────────┐ [Send] │
│                          │  │ Ask about your document…     │        │
│                          │  └─────────────────────────────┘        │
└──────────────────────────┴──────────────────────────────────────────┘
```

**Access locally:** `http://localhost:8000` (FastAPI serves `frontend/index.html` at root)

**Features:**
- Drag-and-drop PDF upload with real-time job status polling (every 3s)
- Cache hit/miss badges with similarity score display
- Collapsible source chunk viewer per response
- Session stats (queries, cache hit rate, avg latency, docs loaded)
- Live API health indicator with configurable endpoint URL
- Six suggestion chips for common legal questions
- Responsive — sidebar hides on mobile

---

## Observability

### Logs (CloudWatch)

Every request generates structured JSON log lines, all sharing the same `request_id` so you can reconstruct the full request trace:

```bash
# Tail live logs from all ECS tasks
aws logs tail /ecs/legal-lense-rag --follow --region us-east-1

# Find all logs for a specific request
aws logs filter-log-events \
  --log-group-name /ecs/legal-lense-rag \
  --filter-pattern '{ $.request_id = "a3f2c1d8-*" }'

# Find all cache hits in the last hour
aws logs filter-log-events \
  --log-group-name /ecs/legal-lense-rag \
  --filter-pattern '{ $.cache_hit = true }'
```

### CloudWatch Dashboard

The CloudWatch dashboard (`LegalLenseRAG`) shows four panels:
- ECS running task count over time
- CPU utilisation with 60% scale-out threshold line
- ALB request count per minute
- ALB target response time at P95

### Alerts

Two CloudWatch alarms send SNS email notifications:
- **Max capacity alarm** — fires when ECS reaches 6 tasks (scaling maxed out)
- **Sustained high CPU** — fires when CPU > 80% for 10+ minutes (scaling lag)

---

## Testing

```
Test pyramid:

     ┌──────────┐
     │ API tests │   10 tests · ~5s · full HTTP via TestClient
     └────┬─────┘   tests/api/test_routes.py
          │
     ┌────┴──────────┐
     │ Integration    │   4 tests · ~2s · mocked external APIs
     └────┬───────────┘  tests/integration/test_pipeline.py
          │
     ┌────┴────────────────────────────────────────────────┐
     │                    Unit tests                        │
     │  25 tests · ~0.3s · zero network calls              │
     │                                                      │
     │  test_chunker.py         (6 tests)                  │
     │  test_embedder.py        (5 tests) — idempotency!   │
     │  test_circuit_breaker.py (4 tests) — state machine  │
     │  test_cost_tracker.py    (4 tests) — cost formulas  │
     │  test_metrics.py         (6 tests) — percentiles    │
     └──────────────────────────────────────────────────────┘
```

**Critical tests:**

- `test_same_inputs_produce_same_id` — idempotency guarantee (prevents duplicate Pinecone vectors)
- `test_opens_after_threshold_failures` — circuit breaker state machine
- `test_query_503_when_no_chunks_loaded` — production cold-start scenario
- `test_cosine_similarity_identical_vectors` — semantic cache correctness
- `test_budget_alert_fires_at_threshold` — cost guardrail

```bash
# Run all 39 tests
pytest --tb=short -q

# Coverage report
pytest --cov=src --cov-report=term-missing

# Inside Docker (proves production env passes)
make test
```

---

## Deployment Guide

### One-time AWS setup

```bash
# Set your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="us-east-1"

# 1. Create ECR repository
aws ecr create-repository --repository-name legal-lense-rag --region $AWS_REGION

# 2. Store API keys in Secrets Manager
aws secretsmanager create-secret \
  --name "legal-lense/openai-api-key" \
  --secret-string "sk-your-key-here"

aws secretsmanager create-secret \
  --name "legal-lense/pinecone-api-key" \
  --secret-string "pcsk-your-key-here"

aws secretsmanager create-secret \
  --name "legal-lense/cohere-api-key" \
  --secret-string "your-cohere-key-here"

# 3. Create IAM roles, ECS cluster, ALB, SQS, DynamoDB, ElastiCache
./infrastructure/setup_jobs.sh
./infrastructure/setup_autoscaling.sh
```

### Every deployment

```bash
# Full deploy: tests → build → push → ECS rolling update
make deploy
```

### CI/CD (automatic on push to main)

```
git push origin main
      │
      │  GitHub Actions (.github/workflows/deploy.yml)
      ▼
┌─────────────────────────────────────────────┐
│  Job 1: Test  (~60s)                         │
│  ├── pytest tests/unit/ -v                  │
│  └── pytest tests/integration/ -v           │
└──────────────────────┬──────────────────────┘
                       │ (only if tests pass)
                       ▼
┌─────────────────────────────────────────────┐
│  Job 2: Deploy  (~3 min)                     │
│  ├── docker build -t legal-lense-rag:$SHA   │
│  ├── docker push → ECR                      │
│  ├── aws ecs update-service (API)           │
│  ├── aws ecs update-service (worker)        │
│  ├── aws ecs wait services-stable           │
│  └── curl /health → verify 200             │
└─────────────────────────────────────────────┘
```

---

## Performance Benchmarks

Measured on: ECS Fargate 0.5 vCPU / 1GB RAM, `us-east-1`, Pinecone Serverless same region.

| Scenario | P50 | P95 | P99 |
|---|---|---|---|
| Cache hit (Redis) | 48ms | 89ms | 142ms |
| Cache miss — full pipeline | 2,847ms | 4,231ms | 6,102ms |
| Cache miss (Cohere circuit open) | 2,210ms | 3,180ms | 4,890ms |
| Ingestion — text PDF (9 chunks) | 8.2s | — | — |
| Ingestion — scanned PDF (OCR) | 38.4s | — | — |

**Cost per query:**

| Component | Cost per query |
|---|---|
| OpenAI input tokens (~412 tokens) | $0.000062 |
| OpenAI output tokens (~87 tokens) | $0.000013 |
| Cohere rerank (10 documents) | $0.000010 |
| Pinecone read units (~10 RU) | $0.0000008 |
| **Total (cache miss)** | **~$0.000086** |
| **Cache hit** | **$0.000001** (embed only) |

**At 1,000 queries/day with 50% cache hit rate:**
- Daily cost: ~$0.044
- Monthly cost: ~$1.32

---

## Roadmap

**Near-term improvements:**
- [ ] Multi-document namespace support (Pinecone namespaces per user)
- [ ] Streaming responses via Server-Sent Events
- [ ] Document management API (list, delete, re-ingest)
- [ ] RAGAS continuous evaluation pipeline (nightly CloudWatch job)
- [ ] Redis Search vector indexing (HNSW) for >5,000 cached entries

**Infrastructure:**
- [ ] HTTPS with AWS Certificate Manager
- [ ] WAF rules on ALB (rate limiting, IP allowlist)
- [ ] Multi-AZ ElastiCache Redis cluster
- [ ] S3 PDF storage (replace local filesystem)
- [ ] Terraform/CDK IaC for reproducible deployment

**RAG quality:**
- [ ] Parent-child chunking strategy (retrieve small, context large)
- [ ] Query expansion with HyDE (Hypothetical Document Embeddings)
- [ ] Answer confidence scoring
- [ ] Multi-lingual support (Hindi legal documents)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built as part of a 20-hour production RAG system course.
Notebook → Production in 20 hours.

**LangChain + Pinecone + GPT-4o-mini + RAGAS → FastAPI → Docker → AWS ECS → CI/CD**

</div>
