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
[![Live on AWS](https://img.shields.io/badge/Live-AWS_ALB-brightgreen?style=flat-square)](http://legal-lense-alb-45989434.us-east-1.elb.amazonaws.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**A production-grade Retrieval-Augmented Generation (RAG) API for querying legal documents using hybrid search, neural reranking, and auto-scaling cloud infrastructure — live on AWS.**

[Live Demo](#quick-start) · [Architecture](#system-architecture) · [API Reference](#api-reference) · [Deployment](#deployment-guide)

</div>

---

## Live Screenshots

### Frontend — Empty State with Suggestion Chips
![LegalLense empty state showing upload zone, ingestion job processing, session stats, and suggestion chips](screenshots/empty-state.png)

> *The UI on first load — drag-and-drop PDF upload on the left, smart suggestion chips in the centre, live session stats at the bottom of the sidebar.*

---

### Frontend — Query Result with Source Chunks
![LegalLense showing query result: monthly rent is dollar 685, with 3 source chunks expanded, 1819ms latency, FRESH badge](screenshots/query-result.png)

> *Real query: "Tell me the monthly rent of Tenant?" → "$685" in 1819ms from the live ALB endpoint. The 3 source chunks that grounded the answer are expanded below.*

---

### Live on AWS ALB
![LegalLense running at legal-lense-alb-45989434.us-east-1.elb.amazonaws.com](screenshots/live-aws.png)

> *The application live at the AWS Application Load Balancer URL. 16 document chunks loaded, 1 query completed, API ONLINE indicator confirmed.*

---

### GitHub Repository
![Legal_Lense public GitHub repository with 9 commits, 2 contributors](screenshots/github-repo.png)

> *The full project is open source with CI/CD wired up — pushing to `main` runs tests and deploys automatically.*

---

## Table of Contents

- [Overview](#overview)
- [What Is Implemented](#what-is-implemented)
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

LegalLense transforms legal PDF documents — rental agreements, contracts, notices — into an intelligent Q&A system. Users upload documents once, then ask natural language questions and receive accurate, cited answers in under 2 seconds, grounded in actual clauses from the document.

The system was built over 20 hours, taking a working Jupyter notebook (LangChain + Pinecone + GPT-4o-mini + RAGAS evaluation) all the way to a containerised, auto-scaling production service running on AWS ECS Fargate behind an Application Load Balancer.

**The core problem solved:** Legal documents contain precise, clause-specific information where a wrong answer is worse than no answer. The hybrid BM25 + vector retrieval approach, combined with Cohere neural reranking, achieves Faithfulness 0.90 on RAGAS evaluation — the system only answers from what is in the document.

---

## What Is Implemented

The following production features are fully working and deployed:

| Layer | Status | Detail |
|---|---|---|
| PDF ingestion (text + OCR fallback) | ✅ Live | PyPDFLoader + GPT-4o-mini Vision for scanned PDFs |
| Hybrid retrieval (BM25 + Vector) | ✅ Live | 0.4 BM25 weight + 0.6 Pinecone cosine similarity |
| Cohere neural reranking | ✅ Live | `rerank-english-v3.0`, top 3 from 10 candidates |
| Circuit breaker | ✅ Live | 3-failure threshold, graceful degradation |
| GPT-4o-mini answer generation | ✅ Live | temp=0, strict context-only prompt |
| FastAPI REST API | ✅ Live | `/ingest`, `/query`, `/status`, `/metrics`, `/health` |
| Structured JSON logging | ✅ Live | structlog + CloudWatch, every log has `request_id` |
| Per-request cost tracking | ✅ Live | USD breakdown per query, daily budget alert |
| In-process metrics | ✅ Live | P50/P95/P99 latency, counters at `/api/v1/metrics` |
| Docker containerisation | ✅ Live | Multi-stage build, `.dockerignore`, non-root user |
| AWS ECR | ✅ Live | Image push on every deploy |
| AWS ECS Fargate | ✅ Live | 2 tasks, 0.5 vCPU / 1GB RAM each |
| AWS ALB | ✅ Live | Health checks, load balancing |
| Auto-scaling | ✅ Live | CPU target 60%, min=2 tasks, max=6 tasks |
| AWS Secrets Manager | ✅ Live | API keys injected at task start |
| GitHub Actions CI/CD | ✅ Live | Push to `main` → tests → build → ECS deploy |
| 39-test test suite | ✅ Live | Unit + integration + API tests, all passing |
| Frontend (HTML/CSS/JS) | ✅ Live | Self-contained SPA, zero build step |
| Idempotent ingestion | ✅ Live | MD5 hash IDs, safe to re-upload without duplicates |
| RAGAS evaluation | ✅ Measured | Faithfulness 0.90, ContextPrecision 0.92 |
| Semantic cache (Redis) | 🔜 Roadmap | Planned: 50ms cache hits, 40–60% hit rate |
| SQS job queue | 🔜 Roadmap | Planned: durable ingestion, survives restarts |
| DynamoDB job tracking | 🔜 Roadmap | Planned: persistent job status, `GET /jobs/{id}` |

---

## Key Features

| Feature | Implementation | Benefit |
|---|---|---|
| Hybrid retrieval | BM25 (0.4 weight) + Pinecone vector (0.6 weight) | Finds both keyword-exact and semantically similar chunks |
| Neural reranking | Cohere `rerank-english-v3.0` | Boosts precision from BM25-only baseline |
| OCR fallback | GPT-4o-mini Vision on scanned pages | Handles image-only PDFs transparently |
| Idempotent ingestion | MD5 hash → stable Pinecone vector IDs | Safe to re-upload without duplicating the index |
| Circuit breaker | 3-failure threshold, 60s reset | Cohere outage never cascades to user errors |
| Structured logging | structlog JSON + CloudWatch | Every log line queryable by `request_id` |
| Cost tracking | Per-request USD calculation + daily budget alert | Full cost visibility per query |
| Auto-scaling | ECS Application Auto Scaling, CPU target 60% | Scales 2→6 tasks under load, 60s cooldown |
| CI/CD | GitHub Actions — tests gate every deploy | Zero-touch deployment on push to `main` |
| Frontend | Self-contained `index.html`, zero dependencies | Drag-and-drop upload, chat UI, source chunks |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   INTERNET                                       │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │ HTTP (HTTPS planned)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│         Application Load Balancer  (us-east-1)                                   │
│   legal-lense-alb-45989434.us-east-1.elb.amazonaws.com                          │
│         Health checks every 30s · Path routing · Load balancing                  │
└────────────────┬────────────────────────────────────────────────────────────────┘
                 │  HTTP/8000
         ┌───────┴────────┐
         ▼                ▼
   ┌──────────┐    ┌──────────┐
   │ API Task │    │ API Task │     ECS Fargate  (Auto-scaling: 2–6 tasks)
   │    1     │    │    2     │     0.5 vCPU · 1GB RAM per task
   │  :8000   │    │  :8000   │     legal-lense-rag:latest image from ECR
   └──────────┘    └──────────┘
         │                │
         └───────┬────────┘
                 │
         ┌───────▼─────────────────────────────────────────┐
         │              VPC  (Private Subnets)               │
         │                                                   │
         │  ┌─────────────┐  ┌──────────────┐               │
         │  │  ECR        │  │  Secrets Mgr │               │
         │  │  Docker img │  │  API keys    │               │
         │  └─────────────┘  └──────────────┘               │
         │                                                   │
         │  ┌─────────────┐  ┌──────────────┐               │
         │  │  CloudWatch │  │  Auto Scaling│               │
         │  │  Logs+Alarm │  │  CPU target  │               │
         │  └─────────────┘  └──────────────┘               │
         └───────────────────────────────────────────────────┘
                 │                    │                │
                 ▼                    ▼                ▼
       ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
       │   Pinecone   │    │  OpenAI API  │   │  Cohere API  │
       │  Serverless  │    │  GPT-4o-mini │   │  Rerank v3   │
       │  us-east-1   │    │  Embeddings  │   │              │
       └──────────────┘    └──────────────┘   └──────────────┘
```

---

## RAG Pipeline Deep Dive

### Ingestion Pipeline

```
PDF Upload (via POST /api/v1/ingest/upload)
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│                    Smart PDF Loader                         │
│                                                             │
│  1. PyPDFLoader — text extraction                          │
│       │                                                     │
│       ├── text found (≥50 chars) ──────────────────────►  │
│       │                             continue normally       │
│       └── text empty → OCR Fallback                        │
│               │                                             │
│               ▼                                             │
│         GPT-4o-mini Vision                                  │
│         page-by-page: image → extracted text               │
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
                        │  List[Document] — chunks
                        ▼
┌───────────────────────────────────────────────────────────┐
│                  Idempotent Embedder                        │
│                                                             │
│  vector_id = MD5(pdf_path + chunk_index + text[:100])      │
│                                                             │
│  OpenAIEmbeddings (text-embedding-3-small)                 │
│  → 1536-dimensional dense vector per chunk                  │
│                                                             │
│  Pinecone upsert in batches of 100                         │
│  Same ID = overwrite, NOT duplicate                         │
└──────────────────────────┬────────────────────────────────┘
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
User Question: "Tell me the monthly rent of Tenant?"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Hybrid Retrieval                           │
│                                                                  │
│  ┌──────────────────────────┐  ┌───────────────────────────┐   │
│  │      BM25 Retriever       │  │   Pinecone Vector Search   │   │
│  │                           │  │                            │   │
│  │  TF-IDF keyword scoring   │  │  Cosine similarity search  │   │
│  │  top_k = 10               │  │  top_k = 10               │   │
│  │  weight = 0.4             │  │  weight = 0.6             │   │
│  └───────────┬───────────────┘  └────────────────┬──────────┘   │
│              │                                    │              │
│              └─────────────────┬──────────────────┘              │
│                                ▼                                 │
│                   Score normalisation + weighted fusion           │
│                   combined = 0.4 × bm25 + 0.6 × vector          │
│                   → Top 10 deduplicated chunks                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │  10 candidate chunks
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Cohere Reranker  (Circuit Breaker)              │
│                                                                  │
│  Model:  rerank-english-v3.0                                     │
│  Input:  10 chunks                                               │
│  Output: top 3 chunks by cross-encoder relevance score          │
│                                                                  │
│  Circuit breaker:                                                │
│    CLOSED (normal)   → calls Cohere                             │
│    OPEN  (3 failures) → returns top 3 from hybrid, no error     │
│    HALF_OPEN (60s)   → probes with one request                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │  3 high-precision chunks
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        LLM Generation                            │
│                                                                  │
│  Model:  gpt-4o-mini   temperature=0   max_tokens=1000          │
│                                                                  │
│  System prompt:                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  You are a strict legal assistant.                       │  │
│  │  RULES:                                                  │  │
│  │  - Use ONLY the context below                           │  │
│  │  - Do NOT add external knowledge                        │  │
│  │  - If answer not found, say "I don't know"             │  │
│  │                                                          │  │
│  │  Context: {chunk_1}\n\n{chunk_2}\n\n{chunk_3}           │  │
│  │  Question: {user_question}                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────────────────┐
              │              QueryResponse                  │
              │                                             │
              │  answer          : "The monthly rent is    │
              │                    $685."                  │
              │  sources         : [chunk_1, chunk_2, ...]│
              │  chunk_count     : 3                       │
              │  reranked        : true                    │
              │  latency_ms      : 1819                    │
              │  cache_hit       : false                   │
              │  request_id      : "a3f2c1d8-..."          │
              └───────────────────────────────────────────┘
```

---

## Infrastructure Architecture

### Request Flow

```
Client Browser
      │
      │  DNS lookup → ALB hostname
      ▼
  legal-lense-alb-45989434.us-east-1.elb.amazonaws.com
      │
      │  ALB:
      │   • Health check GET /health every 30s
      │   • Routes to any healthy ECS task
      │   • Removes unhealthy tasks from rotation
      ▼
  ECS Fargate Task  (uvicorn, 2 workers, port 8000)
      │
      │  FastAPI middleware stack (runs on every request):
      │    1. structlog context  → binds request_id to all logs
      │    2. CORS middleware
      │    3. Process time header → X-Process-Time-Ms
      │    4. Global exception handler → always returns JSON
      │
      │  Route: POST /api/v1/query
      │
      │  Pipeline (sequential):
      │    1. Hybrid retrieval (BM25 in-memory + Pinecone network)
      │    2. Cohere rerank (300ms avg, with circuit breaker)
      │    3. GPT-4o-mini generation (~1.5s avg)
      │    4. Cost calculation + structlog emit
      ▼
  JSON response → ALB → Client
```

### Auto-scaling Behaviour

```
  ECS task count vs CPU:

  Traffic:   Low           Rising          Peak         Cooling       Quiet
  Users:     ~10           ~50             ~100         ~50           ~10
             │             │               │             │             │
  CPU:       25%           62%  ←trigger   85%          58%           22%
             │             │               │             │             │
  Tasks:    ┌──┐          ┌──┬──┬──┐      ┌──┬──┬──┬──┬──┬──┐      ┌──┬──┐
            │ 2│          │ 4│  │  │      │ 6│  │  │  │  │  │      │ 2│  │
            └──┘          └──┴──┴──┘      └──┴──┴──┴──┴──┴──┘      └──┴──┘
                              ▲ Scale-out triggered                  ▲ Scale-in after
                              at CPU>60% for 2min                    15min cooldown
                              +2 tasks in 60s
```

### CI/CD Pipeline

```
  Developer pushes to main branch
            │
            ▼
  ┌─────────────────────────────────────────────────────┐
  │          GitHub Actions  (.github/workflows/)        │
  │                                                       │
  │  Job 1: Test  (~60 seconds)                          │
  │  ├── python -m pytest tests/unit/ -v                │
  │  └── python -m pytest tests/integration/ -v         │
  │         │                                             │
  │         │  (only if all 39 tests pass)               │
  │         ▼                                             │
  │  Job 2: Deploy  (~3 minutes)                         │
  │  ├── docker build -t legal-lense-rag:$SHA .         │
  │  ├── docker push → ECR                              │
  │  ├── aws ecs update-service (force-new-deployment)  │
  │  ├── aws ecs wait services-stable                   │
  │  └── curl $ALB_DNS/health → assert 200             │
  └─────────────────────────────────────────────────────┘
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
| Vector store | Pinecone Serverless | 5.0.0 | Scalable approximate nearest neighbour |
| Keyword search | `rank-bm25` BM25Retriever | 0.2.2 | Lexical retrieval |
| Reranking | Cohere `rerank-english-v3.0` | 5.11.0 | Cross-encoder precision boost |
| LLM generation | OpenAI `gpt-4o-mini` | — | Answer synthesis |
| RAG evaluation | RAGAS | — | Faithfulness, ContextPrecision, ContextRecall |

**RAGAS scores on 20-question legal eval set:**

```
Faithfulness:       0.90   (answers grounded in retrieved context)
ContextPrecision:   0.92   (retrieved chunks are relevant)
ContextRecall:      0.93   (relevant chunks are retrieved)
```

### Application Framework

| Component | Library | Version | Purpose |
|---|---|---|---|
| API framework | FastAPI | 0.115.0 | Async REST API with Pydantic validation |
| ASGI server | Uvicorn | 0.31.0 | Production process manager |
| Data validation | Pydantic v2 + pydantic-settings | 2.9.0 | Request/response schemas, env config |
| Structured logging | structlog | 24.4.0 | JSON log lines with `request_id` propagation |

### AWS Infrastructure

| Service | Config | Purpose |
|---|---|---|
| ECS Fargate | 0.5 vCPU / 1GB RAM per task | Run API containers — no server to manage |
| ECR | Image scanning enabled | Private Docker registry |
| ALB | Health checks every 30s | Load balancing, future HTTPS termination |
| Secrets Manager | Rotation-ready | OpenAI, Pinecone, Cohere API keys |
| CloudWatch Logs | `/ecs/legal-lense-rag` | Structured JSON log ingestion |
| Application Auto Scaling | CPU target 60%, min=2, max=6 | Traffic-responsive task count |

---

## Project Structure

```
legal_lense/
│
├── notebooks/
│   └── rag_test4.ipynb             # Original prototype — starting point
│
├── src/
│   ├── ingestion/
│   │   ├── loader.py               # load_pdf_smart() — text + OCR fallback
│   │   ├── chunker.py              # RecursiveCharacterTextSplitter wrapper
│   │   └── embedder.py             # Idempotent MD5 hash IDs + Pinecone upsert
│   │
│   ├── retrieval/
│   │   └── hybrid.py               # BM25 + vector fusion + Cohere rerank + CircuitBreaker
│   │
│   ├── generation/
│   │   └── chain.py                # run_rag_query() — full pipeline function
│   │
│   ├── observability/
│   │   ├── metrics.py              # In-process latency histograms + counters
│   │   └── cost_tracker.py         # Per-request USD calculation + daily budget
│   │
│   └── api/
│       ├── main.py                 # FastAPI app + middleware + lifespan
│       ├── routes.py               # /ingest, /query, /status, /cache, /metrics
│       ├── schemas.py              # Pydantic request/response models
│       └── dependencies.py         # Shared vectorstore + chunk store
│
├── config/
│   ├── settings.py                 # BaseSettings — all config from env vars
│   └── logging_config.py           # structlog JSON formatter
│
├── tests/
│   ├── conftest.py                 # Shared fixtures (mocked OpenAI, Pinecone, Cohere)
│   ├── unit/                       # 25 tests — zero network, ~0.3s
│   │   ├── test_chunker.py
│   │   ├── test_embedder.py        # Critical: idempotency guarantee
│   │   ├── test_circuit_breaker.py # State machine correctness
│   │   ├── test_cost_tracker.py
│   │   └── test_metrics.py
│   ├── integration/                # 4 tests — mocked APIs, ~2s
│   │   └── test_pipeline.py
│   └── api/                        # 10 tests — full HTTP via TestClient
│       └── test_routes.py
│
├── frontend/
│   └── index.html                  # Self-contained SPA — no build step, no npm
│
├── infrastructure/
│   ├── deploy.sh                   # Build + push + ECS rolling deploy
│   └── setup_autoscaling.sh        # Register ECS scaling target + policies
│
├── .github/
│   └── workflows/
│       └── deploy.yml              # GitHub Actions CI/CD
│
├── Dockerfile                      # Multi-stage build (builder + production stages)
├── docker-compose.yml              # api service + test runner
├── .dockerignore
├── Makefile                        # Short aliases: make build, make up, make test, make deploy
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- API keys: OpenAI, Pinecone, Cohere

### Local development

```bash
# 1. Clone
git clone https://github.com/dushyantver/Legal_Lense.git
cd Legal_Lense

# 2. Set up Python environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
# Fill in .env:
#   OPENAI_API_KEY=sk-...
#   PINECONE_API_KEY=pcsk-...
#   COHERE_API_KEY=...
#   PINECONE_INDEX_NAME=legal-lense-index1

# 4. Start the API
uvicorn src.api.main:app --reload --port 8000

# 5. Open the frontend
open http://localhost:8000
```

### Docker Compose

```bash
make build    # Build image
make up       # Start API in background
make test     # Run all 39 tests inside Docker
make logs     # Tail live structured logs
make deploy   # Full deploy: tests → build → push → ECS update
```

---

## Configuration Reference

All values read from environment variables. Zero hardcoded configuration in the codebase.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `PINECONE_API_KEY` | — | Required |
| `COHERE_API_KEY` | — | Required |
| `PINECONE_INDEX_NAME` | `legal-lense-index1` | Pinecone index |
| `PINECONE_REGION` | `us-east-1` | AWS region for Pinecone |
| `CHUNK_SIZE` | `700` | Characters per chunk |
| `CHUNK_OVERLAP` | `120` | Overlap between consecutive chunks |
| `BM25_TOP_K` | `10` | BM25 retrieval count |
| `VECTOR_TOP_K` | `10` | Vector retrieval count |
| `RERANK_TOP_N` | `3` | Final chunks after reranking |
| `BM25_WEIGHT` | `0.4` | BM25 fusion weight |
| `VECTOR_WEIGHT` | `0.6` | Vector fusion weight |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model |
| `LLM_TEMPERATURE` | `0.0` | Deterministic output |
| `LLM_MAX_TOKENS` | `1000` | Max answer length |
| `COHERE_TIMEOUT_SECONDS` | `5.0` | Cohere API timeout |
| `COHERE_FAILURE_THRESHOLD` | `3` | Circuit breaker threshold |

---

## API Reference

**Base URL:**
- Local: `http://localhost:8000`
- Production: `http://legal-lense-alb-45989434.us-east-1.elb.amazonaws.com`

---

### `GET /health`

Liveness check pinged by the ALB every 30s.

```json
{ "status": "ok", "version": "0.1.0", "pinecone": "ok" }
```

---

### `POST /api/v1/ingest/upload`

Upload a PDF. Returns 202 immediately; ingestion runs as a FastAPI `BackgroundTask`.

**Request:** `multipart/form-data` with `file` field.

**Response `202`:**
```json
{
  "job_id": "3f7a2b1c-4e5d-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "accepted",
  "message": "File 'sample_rent.pdf' accepted for ingestion",
  "pdf_path": "/tmp/sample_rent.pdf"
}
```

---

### `POST /api/v1/query`

Ask a natural language question about ingested documents.

**Request:**
```json
{ "question": "Tell me the monthly rent of Tenant?" }
```

**Response `200`:**
```json
{
  "answer": "The monthly rent of Tenant is $685.",
  "sources": [
    "ending June 30, 2013. Upon expiration, this Agreement shall become...",
    "the month, Tenant agrees to pay a $25 late fee...",
    "out to the Landlord. 4. RENT PAYMENT PROCEDURE: Tenants agree..."
  ],
  "chunk_count": 3,
  "reranked": true,
  "latency_ms": 1819,
  "request_id": "a3f2c1d8-7e4b-4f9a-b2c1-8d3e5f6a7b9c",
  "cache_hit": false,
  "cache_similarity": null
}
```

**Error responses:**
- `422` — question too short (< 3 chars) or too long (> 1000 chars)
- `503` — no documents ingested yet
- `500` — pipeline error (check CloudWatch for `request_id`)

---

### `GET /api/v1/status`

Current system state.

```json
{ "chunks_in_memory": 16, "index_name": "legal-lense-index1", "ready": true }
```

---

### `GET /api/v1/metrics`

In-process metrics snapshot.

```json
{
  "latencies": {
    "query.total": { "p50_ms": 1819, "p95_ms": 3200, "p99_ms": 5100, "count": 1 }
  },
  "counters": {
    "query.requests_total": 1,
    "query.tokens_in_total": 412,
    "query.tokens_out_total": 24
  },
  "errors": {},
  "cost": { "today_usd": 0.000086 }
}
```

---

## Frontend

A single `frontend/index.html` — zero npm, zero build step, zero framework dependencies beyond a Google Font.

```
┌──────────────────────────────────────────────────────────────────┐
│  Header:  LegalLense logo │ ● API ONLINE │ API URL input field   │
├──────────────────────┬───────────────────────────────────────────┤
│  UPLOAD DOCUMENTS    │                                           │
│  ┌────────────────┐  │   Empty state (first visit):             │
│  │ Drop PDF or    │  │                                           │
│  │ click to upload│  │   ┌─────────────────────┐               │
│  └────────────────┘  │   │   Document icon     │               │
│                       │   └─────────────────────┘               │
│  INGESTION JOBS       │                                           │
│  sample_rent.pdf      │   Ask anything about your documents      │
│  Processing... PROC.  │                                           │
│                       │   [Monthly rent?] [Who are the parties?] │
│  SESSION STATS        │   [Security deposit?] [Lock-in period?]  │
│  Queries:      1      │                                           │
│  Cache hits:   0      │  ─────────────────────────────────────  │
│  Avg latency: 1819ms  │                                           │
│  Docs loaded:  16     │   User message ──────────────────► You  │
│                       │                                           │
│                       │   LL  The monthly rent of Tenant is $685 │
│                       │        1819ms  ✦ FRESH  3 chunks used    │
│                       │        ▼ 3 source chunks                 │
│                       │          [chunk text excerpt...]         │
│                       ├───────────────────────────────────────────│
│                       │  ┌───────────────────────────────┐ [▶] │
│                       │  │ Ask a question about your doc… │     │
│                       │  └───────────────────────────────┘     │
└──────────────────────┴───────────────────────────────────────────┘
```

**Features:**
- Drag-and-drop PDF upload with real-time job status
- Chat interface with message bubbles (user right, assistant left)
- Cache hit/miss badge (`✦ FRESH` or `⚡ cached`) with latency display
- Collapsible source chunk accordion per answer
- Live session stats (queries, cache hits, avg latency, docs loaded)
- API health dot with configurable endpoint URL
- Suggestion chips for common legal questions
- Responsive — sidebar hides below 768px

---

## Observability

### Structured log lines (CloudWatch)

Every request generates JSON lines all sharing the same `request_id`:

```json
{"timestamp":"2025-04-19T19:00:00Z","level":"info","event":"query_started","request_id":"a3f2c1d8","question_len":32,"chunks_available":16}
{"timestamp":"2025-04-19T19:00:01Z","level":"info","event":"query_complete","request_id":"a3f2c1d8","latency_ms":1819,"reranked":true,"chunk_count":3,"total_usd":0.000086}
```

```bash
# Tail live logs from ECS
aws logs tail /ecs/legal-lense-rag --follow

# Find all logs for one request
aws logs filter-log-events \
  --log-group-name /ecs/legal-lense-rag \
  --filter-pattern '{ $.request_id = "a3f2c1d8*" }'
```

### Test suite

```
39 tests total:

  Unit (25 tests, ~0.3s, no network)
  ├── test_chunker.py         — chunk size, overlap, edge cases
  ├── test_embedder.py        — IDEMPOTENCY: same PDF = same vector ID
  ├── test_circuit_breaker.py — CLOSED → OPEN → HALF_OPEN state machine
  ├── test_cost_tracker.py    — cost formula arithmetic
  └── test_metrics.py         — percentile calculation, rolling window

  Integration (4 tests, ~2s, mocked external APIs)
  └── test_pipeline.py        — chunker→embedder→retrieval chain

  API (10 tests, ~5s, full HTTP via TestClient)
  └── test_routes.py          — /health, /ingest, /query, /status, /metrics
```

---

## Deployment Guide

### One-time AWS setup

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="us-east-1"

# 1. Create ECR repository
aws ecr create-repository --repository-name legal-lense-rag

# 2. Store API keys
aws secretsmanager create-secret --name "legal-lense/openai-api-key"  --secret-string "sk-..."
aws secretsmanager create-secret --name "legal-lense/pinecone-api-key" --secret-string "pcsk-..."
aws secretsmanager create-secret --name "legal-lense/cohere-api-key"   --secret-string "..."

# 3. Set up auto-scaling
./infrastructure/setup_autoscaling.sh
```

### Every deployment

```bash
make deploy
# Runs: pytest → docker build → ECR push → ecs update-service → health verify
```

### CI/CD (automatic)

Push to `main` → GitHub Actions runs tests → builds image → deploys to ECS.
No manual steps needed after the initial setup.

---

## Performance Benchmarks

Measured on live ECS Fargate 0.5 vCPU / 1GB RAM, `us-east-1`.

| Scenario | P50 | Measured |
|---|---|---|
| Full pipeline query (live) | — | 1,819ms |
| Ingestion — text PDF (16 chunks) | — | ~18s |
| Ingestion — scanned PDF (OCR) | — | ~35–60s |

**Cost per query (full pipeline, no cache):**

| Component | Cost |
|---|---|
| OpenAI input tokens (~412 tokens) | $0.000062 |
| OpenAI output tokens (~24 tokens) | $0.000014 |
| Cohere rerank (10 documents) | $0.000010 |
| Pinecone read units | $0.0000008 |
| **Total per query** | **~$0.000086** |

At 1,000 queries/day: **~$0.086/day → $2.58/month**

---

## Roadmap

**Near-term (planned next):**
- [ ] Semantic cache (Redis + cosine similarity) — 50ms cache hits, 40–60% hit rate
- [ ] SQS job queue — durable ingestion, survives ECS task restarts
- [ ] DynamoDB job tracking — `GET /jobs/{id}` status polling endpoint
- [ ] HTTPS via AWS Certificate Manager

**Future improvements:**
- [ ] Multi-document namespace support (per-user Pinecone namespaces)
- [ ] Streaming responses via Server-Sent Events
- [ ] S3 PDF storage (replace local temp files)
- [ ] Multi-lingual support (Hindi legal documents)
- [ ] RAGAS continuous evaluation pipeline (nightly automated run)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built in 20 hours — Notebook → Production RAG**

`Jupyter Notebook` → `FastAPI` → `Docker` → `AWS ECS Fargate` → `CI/CD`

LangChain · Pinecone · GPT-4o-mini · Cohere · RAGAS · structlog · GitHub Actions

*Live at* `legal-lense-alb-45989434.us-east-1.elb.amazonaws.com`

</div>
