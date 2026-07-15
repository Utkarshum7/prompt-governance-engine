# Enterprise AI Prompt Governance Platform

### Smart Prompt Parser & Canonicalisation Engine

A production-oriented system that incrementally ingests prompts, embeds them, clusters semantically equivalent variants, extracts **canonical templates with typed variable slots**, versions those templates immutably, tracks their evolution, and continuously evaluates cluster quality — with **explainability and auditability treated as first-class requirements**, not afterthoughts.

This is not a demonstration notebook. It is a service-shaped codebase: interface-driven, configuration-driven, observable, and deployable. Business logic is deliberately isolated from any single AI vendor.

---

## Table of Contents

- [Project Overview](#project-overview)
  - [Problem Statement](#problem-statement)
  - [Why Prompt Governance Matters](#why-prompt-governance-matters)
  - [Goals](#goals)
- [Architecture](#architecture)
  - [System Architecture Diagram](#system-architecture-diagram)
  - [Request Processing Pipeline](#request-processing-pipeline)
  - [Deployment Architecture](#deployment-architecture)
  - [Component Responsibilities](#component-responsibilities)
- [Tech Stack](#tech-stack)
- [AI Pipeline](#ai-pipeline)
  - [Decision Engine](#decision-engine)
  - [Model Router](#model-router)
  - [Provider Abstraction](#provider-abstraction)
  - [Embedding Generation](#embedding-generation)
  - [Similarity Search](#similarity-search)
  - [Incremental Clustering](#incremental-clustering)
  - [Canonicalisation](#canonicalisation)
  - [Variable Slot Extraction](#variable-slot-extraction)
  - [Template Versioning](#template-versioning)
  - [Evolution Tracking](#evolution-tracking)
  - [Evaluation Engine](#evaluation-engine)
- [Database Schema Overview](#database-schema-overview)
- [API Documentation](#api-documentation)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Project Structure](#project-structure)
- [Engineering Decisions](#engineering-decisions)
  - [Production Engineering Principles](#production-engineering-principles)
- [Confidence Thresholds](#confidence-thresholds)
- [Drift Detection Strategy](#drift-detection-strategy)
- [Evaluation Metrics](#evaluation-metrics)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Project Overview

Large organisations accumulate prompts faster than they can govern them. The same underlying intent — *"summarise this document,"* *"generate a function that does X,"* *"translate this to French"* — is expressed thousands of times with trivially different surface forms. Without governance, this results in duplicated evaluation effort, inconsistent output quality, uncontrolled cost, and zero traceability from a production prompt back to a reviewed, versioned template.

This platform treats a prompt corpus as **managed state** rather than an append-only log. It:

1. **Ingests** prompts incrementally from API calls or bulk dataset workers.
2. **Embeds** each prompt with a deterministic embedding model (`text-embedding-004`, 768 dimensions).
3. **Clusters** semantically equivalent prompts using vector similarity search over Qdrant.
4. **Canonicalises** each cluster into a reusable template with typed variable slots via an LLM.
5. **Versions** every template immutably — new understanding produces a new version, never an in-place mutation.
6. **Tracks evolution** as an explicit, queryable event history.
7. **Evaluates** cluster quality on a schedule and exposes the metrics.

Every decision the system makes — which cluster a prompt joined, why, with what confidence, and which nearest neighbours drove that choice — is recorded and retrievable.

### Problem Statement

Ad-hoc prompt management fails at scale in specific, measurable ways:

- **Semantic duplication is invisible.** String matching cannot tell that two differently-worded prompts request the same thing, so deduplication and consolidation are impossible.
- **No canonical source of truth.** There is no single reviewed template that variants can be traced back to, so improvements cannot be propagated and regressions cannot be attributed.
- **No traceability or audit trail.** When a production prompt behaves badly, there is no lineage back to a governed artefact, no versioned history, and no record of *why* it was grouped or classified the way it was.
- **Uncontrolled model cost.** Routing every prompt to the most capable (and most expensive) model wastes budget on trivial workloads; routing everything to the cheapest degrades quality on hard ones.
- **Vendor lock-in.** Business logic that calls a provider SDK directly cannot survive a provider migration, a price change, or an outage.

This platform addresses each of these directly.

### Why Prompt Governance Matters

Prompts are becoming production assets with the same lifecycle demands as code: review, versioning, testing, deprecation, and audit. An ungoverned prompt corpus is technical debt that compounds — every new variant increases evaluation surface, cost variance, and the blast radius of a bad prompt.

Governance converts that liability into a managed system: a bounded set of canonical templates, each versioned and evaluated, with every raw prompt traceable to exactly one governed artefact and every automated decision explained. That is the difference between *"we have a lot of prompts"* and *"we operate a prompt platform."*

### Goals

| Goal | How it is realised |
|------|--------------------|
| **Explainability** | Every cluster assignment stores a human-readable `reasoning` string, a similarity score, and a confidence score. |
| **Incremental processing** | Prompts are processed one at a time against existing state; there is no global re-clustering step. |
| **Determinism** | LLM calls use low temperature (`0.1`); embeddings are deterministic; canonicalisation returns structured JSON. |
| **Auditability** | Templates are immutable and versioned; evolution is an explicit event log. |
| **Provider independence** | All model access flows through the `ILLMProvider` interface and a factory, never a direct SDK call from business logic. |
| **Cost/quality control** | A Decision Engine + Model Router pair sends cheap prompts to a fast model and hard prompts to a capable one. |
| **Observability** | Structured JSON logging, Prometheus-style metrics, and startup dependency validation ("fail fast"). |
| **Production correctness under multiple workers** | A Redis-backed leadership lock ensures periodic background jobs run exactly once, regardless of how many uvicorn worker processes are running. |

---

## Architecture

### System Architecture Diagram

```
                         ┌──────────────────────────────────────────┐
                         │                 CLIENT                     │
                         │   REST API consumers  ·  Jinja2 Web UI     │
                         └───────────────────────┬────────────────────┘
                                                 │
                         ┌───────────────────────▼────────────────────┐
                         │            FastAPI (ASGI, async)            │
                         │                                             │
                         │   Request Logging Middleware  (structlog)   │
                         │   Rate Limit Middleware       (Redis)       │
                         └───────────────────────┬─────────────────────┘
                                                 │
                         ┌───────────────────────▼─────────────────────┐
                         │             AI ORCHESTRATOR                  │
                         │   coordinates the per-prompt pipeline        │
                         └───┬───────────────┬───────────────┬─────────┘
                             │               │               │
                  ┌──────────▼───────┐  ┌────▼─────────┐  ┌──▼────────────────┐
                  │ Decision Engine  │  │ Model Router │  │ Moderation Service│
                  │ complexity/task  │  │ model select │  │ safety gate       │
                  └──────────────────┘  └────┬─────────┘  └───────────────────┘
                                             │
                                   ┌─────────▼──────────┐
                                   │   ILLMProvider     │   ← interface (ABC)
                                   │   (abstraction)    │
                                   └─────────┬──────────┘
                                             │
                                   ┌─────────▼──────────┐
                                   │    LLM Factory     │   ← constructs provider
                                   └─────────┬──────────┘
                                             │
                                   ┌─────────▼──────────┐
                                   │  Gemini Provider   │   ← concrete impl
                                   └─────────┬──────────┘
                                             │
        ┌────────────────────────────────────┼────────────────────────────────────┐
        │                                    │                                     │
┌───────▼────────┐                 ┌─────────▼──────────┐                ┌─────────▼─────────┐
│ Embedding Svc  │                 │  Canonicalisation  │                │  Evaluation Engine │
│ text-embed-004 │                 │  + Slot Extraction │                │  quality metrics   │
└───────┬────────┘                 │  + Versioning      │                └─────────┬──────────┘
        │                          │  + Evolution       │                          │
┌───────▼────────┐                 └─────────┬──────────┘                          │
│  Redis Cache   │                           │                                     │
│ embedding/rate │                           │                                     │
│ + leader lock  │                           │                                     │
└───────┬────────┘                           │                                     │
        │                                     │                                     │
┌───────▼────────┐   ┌──────────────────┐    │                                     │
│  Qdrant Cloud  │   │  Similarity /    │    │                                     │
│  vector search │◄──┤  Incremental     │    │                                     │
│  768-dim       │   │  Clustering      │    │                                     │
└────────────────┘   └────────┬─────────┘    │                                     │
                              │              │                                     │
                     ┌────────▼──────────────▼─────────────────────────────────────▼──┐
                     │             PostgreSQL (Neon) — durable system state             │
                     │  prompts · clusters · assignments · templates · slots ·          │
                     │  evolution_events · prompt_families · family_cluster_mappings    │
                     └──────────────────────────────────────────────────────────────────┘

                     ┌──────────────────────────────────────────────────────────────────┐
                     │  Background Scheduler (async, single-leader across workers)       │
                     │   drift_detection (6h) · evaluation_metrics (12h) ·               │
                     │   cache_cleanup (24h) · dataset_refresh (1h)                      │
                     │   → leadership arbitrated via a Redis lock (see below)            │
                     └──────────────────────────────────────────────────────────────────┘
```

### Request Processing Pipeline

```
   Prompt (API POST /api/v1/prompts  |  bulk dataset worker)
      │
      ▼
 ┌─────────────────┐
 │ 1. Moderation   │  reject unsafe content early (fail-closed on the ingest path)
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 2. Embedding    │  generate 768-dim vector via Gemini text-embedding-004
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 3. Redis cache  │  reuse embedding if this exact content was seen before
 │    lookup       │
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 4. Qdrant       │  k-NN search over existing prompt vectors
 │    similarity   │  (exact-content shortcut checked first)
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 5. Incremental  │  best cluster ≥ similarity_threshold → JOIN
 │    clustering   │  otherwise                          → CREATE new cluster
 │                 │  → persist similarity, confidence, reasoning
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 6. Canonical    │  LLM extracts a template with {{slots}} for the cluster
 │    extraction   │  (on new-cluster creation or on demand)
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 7. Slot         │  regex + LLM merge → typed variable slots
 │    detection    │
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 8. Versioning   │  write a NEW immutable template version (never overwrite)
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 9. Evolution    │  emit an evolution_event (CREATED / UPDATED …)
 │    tracking     │
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 10. Evaluation  │  cluster quality metrics (scheduled + on demand)
 └───────┬─────────┘
         ▼
 ┌─────────────────┐
 │ 11. Persist     │  commit to PostgreSQL; upsert vector to Qdrant
 └─────────────────┘
```

The pipeline is **incremental and idempotent-friendly**: an exact-content match short-circuits to the existing cluster with similarity `1.0`, avoiding redundant model calls.

### Deployment Architecture

The application runs as a single Render web service (native Python environment, no Docker on the active path) backed entirely by managed cloud services. There is no infrastructure to provision or operate beyond the service itself:

```
                              Internet / Client
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │       Render Web Service          │
                    │   env: python (native runtime)    │
                    │   plan: free · region: oregon      │
                    │                                     │
                    │  build:  render-build.sh            │
                    │  start:  start.sh                   │
                    │    1. alembic upgrade head            │
                    │    2. uvicorn src.main:app             │
                    │         --host 0.0.0.0 --port $PORT     │
                    │         --workers 2                      │
                    │                                            │
                    │  Each worker is a separate OS process.    │
                    │  Only ONE acquires the scheduler          │
                    │  leadership lock (via Redis) and runs     │
                    │  the periodic background jobs.            │
                    └───────┬───────────┬────────────┬─────────┘
                            │           │            │
              ┌─────────────┘           │            └─────────────┐
              ▼                         ▼                          ▼
   ┌─────────────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
   │   Neon PostgreSQL     │   │   Upstash Redis       │   │   Qdrant Cloud         │
   │   (managed, serverless)│  │  (managed, TLS)        │   │  (managed vector DB)   │
   │   via DATABASE_URL      │  │   via REDIS_URL         │   │   via QDRANT_URL       │
   └─────────────────────┘   └──────────────────────┘   └───────────────────────┘

                            ┌──────────────────────────┐
                            │   Google Gemini API        │
                            │   (external managed API)    │
                            │   via GEMINI_API_KEY         │
                            └──────────────────────────┘
```

All four external dependencies are managed SaaS — there is no self-hosted database, cache, or vector store to operate. Startup performs **fail-fast dependency validation**: if Postgres, Redis, or Qdrant is unreachable, the process refuses to start rather than serving a half-broken service.

An AWS/ECS-compatible path also exists (`Backend/docker/ecs-task-definition.json`, plus ECR/S3/Secrets Manager/CloudWatch configuration), but **Render is the active, primary deployment target**; the AWS artefacts are documented for completeness, not exercised in the current deployment.

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **AI Orchestrator** | `services/orchestrator.py` | Coordinates the per-prompt pipeline; owns the transaction boundary for ingestion. |
| **Decision Engine** | `services/decision_engine.py` | Classifies each prompt (tokens, complexity, task type, code detection) before inference. |
| **Model Router** | `services/model_router.py` | Consumes the decision to select a Gemini model and build a fallback routing config. |
| **ILLMProvider** | `interfaces/llm.py` | Abstract contract for chat, embeddings, and moderation. Business logic depends only on this. |
| **Gemini Provider / Client** | `clients/gemini.py`, `clients/llm_client.py` | Concrete provider implementation constructed behind the interface. |
| **Embedding Service** | `services/embedding.py` | Generates and caches embeddings. |
| **Similarity Service** | `services/similarity.py` | Vector k-NN search against Qdrant. |
| **Clustering Service** | `services/clustering.py` | Incremental cluster assignment with reasoning and confidence. |
| **Canonicalisation Service** | `services/canonicalization.py` | LLM template extraction + slot detection + persistence. |
| **Template Versioning** | `services/template_versioning.py` | Immutable version creation and lookup. |
| **Evolution Service** | `services/evolution.py` | Records and queries template evolution events. |
| **Family Tracking / Lineage** | `services/family_tracking.py`, `services/lineage.py` | Groups clusters into prompt families and tracks lineage/versioning. |
| **Drift Detection** | `services/drift_detection.py` | Detects semantic drift across clusters and templates. |
| **Evaluation Engine** | `services/evaluation.py` | Per-cluster and system-wide quality metrics. |
| **Scheduler** | `services/scheduler.py` | Async periodic jobs (drift, evaluation, cache cleanup, dataset refresh), gated by a Redis-backed leadership lock so exactly one worker process runs them. |
| **Dataset Worker** | `workers/dataset_ingestion.py` | Bulk ingestion from datasets. |
| **Middleware** | `api/middleware/` | Structured request logging and Redis-backed rate limiting. |
| **ICache** | `interfaces/cache.py` | Abstract cache contract (`get`/`set`/`delete`/`exists`/`ping`/`acquire_lock`/`renew_lock`), implemented by `RedisClient`. The lock primitives back the scheduler leadership mechanism. |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Web framework** | FastAPI (async, ASGI) |
| **Language / runtime** | Python 3.12 |
| **Server-rendered UI** | Jinja2 + Bootstrap (HTML templates) |
| **ORM** | SQLAlchemy (async) |
| **Migrations** | Alembic (async engine, `postgresql+asyncpg`) |
| **Relational DB** | Neon PostgreSQL |
| **Vector DB** | Qdrant Cloud |
| **Cache / rate limiting / leader election** | Upstash Redis |
| **Embeddings** | Google `text-embedding-004` (768-dim) |
| **LLMs** | Google Gemini — `gemini-2.5-flash`, `gemini-2.5-pro` |
| **Provider seam** | `ILLMProvider` interface + LLM factory |
| **Config / secrets** | YAML + env vars + optional AWS Secrets Manager (disabled by default), validated by Pydantic |
| **Observability** | `structlog` (JSON), Prometheus-client scaffolding, CloudWatch-compatible logging |
| **Containerisation** | Docker / Docker Compose (used for local backing services and the AWS-compatible path; not the active Render deployment path) |
| **Deployment** | Render (native Python via `render.yaml` / `Procfile`); AWS ECS task definition also provided as an alternate path |
| **CI/CD** | Not yet configured. No GitHub Actions workflow currently exists in this repository — see [Future Improvements](#future-improvements). |

> **Configuration note:** the codebase carries both Render and AWS (ECR/S3/Secrets Manager/CloudWatch/ECS) configuration. Render is the active managed-deployment path; the AWS artefacts make an ECS/Fargate deployment possible without code changes, but are not currently exercised.

---

## AI Pipeline

### Decision Engine

Before any inference happens, every incoming prompt is analysed by the **AI Decision Engine** (`services/decision_engine.py`). This is intentionally a **cheap, deterministic, heuristic** stage — no model call — so that routing decisions add negligible latency and cost.

It produces a `DecisionOutput` object with:

- **`token_count`** — estimated (`len(prompt) // 4`).
- **`is_code`** — regex + keyword-density detection of code (fenced blocks, language keywords, SQL, C preprocessor, arrow functions).
- **`complexity`** — `low` / `medium` / `high`, derived from token count, code presence, and task type.
- **`task_type`** — one of `coding`, `translation`, `summarization`, `moderation`, `canonicalization`, `reasoning`, `general`.
- **`latency_preference`** / **`cost_preference`** — hints for the router.
- **`confidence_estimate`** — an initial confidence prior.

Keeping this stage heuristic and side-effect-free is a deliberate tradeoff: it is fast and reproducible, at the cost of the nuance a model classifier would provide. The design leaves room to swap in a model-backed classifier behind the same `DecisionOutput` contract without touching the router.

### Model Router

The **Model Router** (`services/model_router.py`) consumes a `DecisionOutput` and selects the target model, then builds a **fallback routing config** (primary + secondary target) so a failure on the first model degrades gracefully to the second.

**Routing strategy (as implemented):**

| Condition | Primary target |
|-----------|----------------|
| Low complexity | `gemini-2.5-flash` (fast, cheap) |
| Medium complexity | `gemini-2.5-pro` |
| High complexity | `gemini-2.5-pro` |
| Code / `coding` task | `gemini-2.5-pro` |
| Prior confidence below threshold (retry) | `gemini-2.5-pro` (reasoning upgrade) |

**Why routing improves cost, latency, and quality simultaneously:** the majority of real-world prompts are simple and are served by the fast model at a fraction of the cost and latency of the capable model; the minority that are genuinely hard — or where a first attempt returned low confidence — are escalated to the capable model. The **confidence-gated retry** is what makes this safe — a low-confidence extraction is automatically re-attempted on the stronger model rather than being silently accepted.

### Provider Abstraction

> **Business logic never calls Gemini directly.**

All model access flows through a single seam:

```
        business logic (services)
                 │
                 ▼
          ILLMProvider          interfaces/llm.py   (abstract: chat / embeddings / moderation)
                 │
                 ▼
           LLM Factory          clients/llm_client.py
                 │
                 ▼
          Gemini Provider       clients/gemini.py   (concrete implementation)
```

The project previously routed model traffic through an AI gateway; the production codebase has since **migrated fully to Gemini**. Critically, the migration did **not** touch business logic, because business logic was never coupled to the gateway — it depended on `ILLMProvider`. That is the entire point of the abstraction: the concrete provider changed, the interface did not, and no service had to be rewritten.

Adding **OpenAI**, **Claude**, **DeepSeek**, or **Llama** in future is a matter of writing a new class that satisfies `ILLMProvider` and registering it in the factory. No service, router, or orchestrator changes.

### Embedding Generation

- **Model:** Gemini `text-embedding-004`.
- **Dimension:** 768 — configured as `models.embedding.dimensions` and read by the Qdrant client when creating its collection, so the vector size cannot silently drift from the active embedding model.
- **Determinism:** the same content produces the same vector, which is what makes exact-content short-circuiting and caching sound.
- **Caching:** embeddings are cached in Redis; a cache hit avoids a model round-trip entirely.
- **Batching:** the embedding config exposes a batch size for bulk ingestion paths.
- **Storage:** vectors are upserted into Qdrant with a payload carrying `prompt_id`, `cluster_id`, and content, so a single k-NN query returns both the neighbours and the clusters they belong to.

### Similarity Search

The **Similarity Service** (`services/similarity.py`) wraps Qdrant k-NN search behind a stable interface consumed by the clustering service. It queries the `prompt_embeddings` collection (768-dim, cosine distance) and returns scored candidates with their stored payload (`prompt_id`, `cluster_id`, `content`), which the clustering service then groups by cluster to find the best match.

### Incremental Clustering

Clustering (`services/clustering.py`) is **online and incremental** — there is no batch re-clustering pass. Each prompt is assigned as it arrives:

1. **Exact-content shortcut.** If an identical prompt already exists, the new prompt joins that prompt's cluster with similarity `1.0`. This avoids a redundant vector search and an LLM call.
2. **Vector search.** Otherwise, Qdrant returns up to 50 candidate neighbours (using a deliberately low search threshold to surface all plausible matches), grouped by their `cluster_id`.
3. **Best-cluster selection.** For each candidate cluster the **maximum** neighbour similarity is used (not the average) — this ensures a prompt that is near-identical to *one* member of a diverse cluster still matches, rather than being penalised by dissimilar members.
4. **Threshold gate.** The best cluster is accepted only if its score ≥ `similarity_threshold` (default `0.85`). Otherwise a **new cluster** is created.
5. **Explainability.** Every assignment persists `similarity_score`, a derived `confidence_score`, and a human-readable `reasoning` string.

**Tradeoff:** incremental assignment is cheap and traceable but is *order-sensitive* — the cluster structure depends on ingestion order. This is an accepted tradeoff for online processing; the scheduled drift-detection and evaluation jobs exist precisely to catch the cluster-quality degradation that order sensitivity can cause over time.

### Canonicalisation

Once a cluster exists, the **Canonicalisation Service** (`services/canonicalization.py`) extracts a single **canonical template** that represents every prompt in the cluster, replacing the parts that vary between members with **typed variable slots**.

- The LLM is prompted (low temperature) to return **structured JSON** — the canonical template string, its slots, a confidence score, and an explanation.
- If the returned confidence is **below the configured threshold**, the extraction is **automatically retried with a reasoning-model upgrade** (see [Confidence Thresholds](#confidence-thresholds)). Low-confidence output is never silently accepted.
- The extracted template is validated: regex-detected slots are reconciled against the LLM-declared slots so nothing is missed.

The result is a reusable, parameterised template rather than a frozen example — the difference between *"generate a Python function to parse dates"* and `Generate a {{language}} function to {{task}}`.

### Variable Slot Extraction

Slot detection is a **hybrid** of deterministic parsing and model output:

- **Regex layer.** `{{variable}}` placeholders in the template are extracted deterministically.
- **LLM layer.** The model proposes slots with a **type** (e.g. `programming_language`, `string`), example values, and a per-slot confidence.
- **Reconciliation.** Any slot the regex finds that the model omitted is added back with a conservative default type (`string`) and a lower confidence, so the persisted slot set is a superset that never loses a placeholder.

Typed slots are what make templates *governable*: a slot with type `programming_language` carries a contract that a downstream consumer can validate against.

### Template Versioning

**Templates are immutable. Improvements create a new version; they never overwrite the old one.**

Each `canonical_templates` row carries an explicit `version`. When a cluster's canonical understanding changes — a better template, new slots, a corrected type — a **new row** is written rather than mutating the existing one. See [Engineering Decisions](#engineering-decisions) for why.

### Evolution Tracking

Template history is not implicit in versioned rows — it is an **explicit, queryable event log** (`evolution_events`). Each event records:

- `event_type` (`CREATED`, `UPDATED`, …)
- `previous_version` → `new_version`
- `change_reason`
- `detected_by` (which model or process detected the change)
- `created_at`

This turns *"how did this template get here?"* from an archaeology exercise into a single query.

### Evaluation Engine

The **Evaluation Engine** (`services/evaluation.py`) computes cluster-quality signals both **per cluster** and **system-wide**, and is invoked both on demand (via the evaluation API) and on a schedule (every 12 hours). Metrics are surfaced through the API so quality is observable, not assumed. See [Evaluation Metrics](#evaluation-metrics) for the metric set.

---

## Database Schema Overview

PostgreSQL (Neon) is the durable system of record. Core tables:

| Table | Purpose | Key columns |
|-------|---------|-------------|
| **`prompts`** | Raw prompt corpus | `id`, `content`, `embedding_id`, `moderation_status`, timestamps |
| **`clusters`** | Semantic clusters | `id`, `name`, `centroid_embedding_id`, `similarity_threshold`, `confidence_score` |
| **`cluster_assignments`** | Prompt → cluster membership with explanation | `prompt_id`, `cluster_id`, `similarity_score`, `confidence_score`, `reasoning` |
| **`canonical_templates`** | Immutable, versioned templates | `cluster_id`, `template_content`, `version`, `slots` (JSONB), `confidence_score` |
| **`template_slots`** | Typed variable slots | `template_id`, `slot_name`, `slot_type`, `example_values` (JSONB), `confidence_score` |
| **`evolution_events`** | Template change log | `template_id`, `event_type`, `previous_version`, `new_version`, `change_reason`, `detected_by` |
| **`prompt_families`** | Hierarchical grouping of clusters | `id`, `parent_family_id` (self-ref), `name`, `description` |
| **`family_cluster_mappings`** | Family ↔ cluster join | `family_id`, `cluster_id` |

Notes:

- Primary keys are UUIDs (generated application-side).
- Cascade deletes maintain referential integrity (e.g. deleting a cluster removes its assignments and templates).
- `slots` / `example_values` use `JSONB` for flexible, indexable structured data.
- Vector data lives in **Qdrant**, not PostgreSQL — PostgreSQL holds relational state, Qdrant holds the ANN index. Redis holds ephemeral state (rate limits, embedding cache, cached similarity scores, scheduler leadership lock).

Schema is managed with **Alembic** (`migrations/alembic/versions/001_initial_schema.py`).

---

## API Documentation

REST endpoints are versioned under `/api/v1`. Interactive docs are served at `/docs` (Swagger) and `/redoc`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/prompts` | Ingest a single prompt through the full pipeline (moderation → embed → cluster → template). |
| `GET`  | `/api/v1/clusters` | List clusters. |
| `GET`  | `/api/v1/clusters/{cluster_id}` | Cluster detail. |
| `GET`  | `/api/v1/clusters/{cluster_id}/prompts` | Prompts belonging to a cluster. |
| `GET`  | `/api/v1/templates` | List canonical templates. |
| `GET`  | `/api/v1/templates/{template_id}` | Template detail. |
| `GET`  | `/api/v1/templates/{template_id}/versions` | All immutable versions of a template. |
| `GET`  | `/api/v1/templates/{template_id}/evolution` | Evolution history for a template. |
| `POST` | `/api/v1/templates/extract/{cluster_id}` | Extract (or re-extract) a canonical template for a cluster. |
| `GET`  | `/api/v1/evolution/events` | Query evolution events. |
| `GET`  | `/api/v1/evolution/families` | List prompt families. |
| `GET`  | `/api/v1/evolution/drift` | Drift-detection results. |
| `GET`  | `/api/v1/evaluation/system` | System-wide quality metrics. |
| `GET`  | `/api/v1/evaluation/cluster/{cluster_id}` | Per-cluster quality metrics. |
| `GET`  | `/health` | Liveness probe (no external dependency checks). |
| `GET`  | `/health/ready` | Readiness probe — checks PostgreSQL, Redis, Qdrant, and Gemini connectivity. |
| `GET`  | `/metrics` | Prometheus-format metrics endpoint. |

A server-rendered **Jinja2 web UI** (dashboard, cluster/template/evolution views, ingestion forms) is mounted alongside the JSON API.

### Example: ingest a prompt

**Request**

```http
POST /api/v1/prompts
Content-Type: application/json

{
  "content": "Write a Python function that reverses a linked list"
}
```

**Response** `201 Created`

```json
{
  "prompt_id": "6f1c2e7a-2b0e-4a1e-9d3a-8c5f0b7d1e42",
  "cluster_id": "b3d9c1f0-77aa-4c2b-9e10-2f0a4c6d8b91",
  "similarity_score": 0.92,
  "confidence_score": 1.0,
  "reasoning": "Assigned to cluster b3d9c1f0... with similarity score 0.920 (threshold: 0.85)",
  "status": "accepted",
  "is_new_cluster": false
}
```

A prompt rejected by moderation returns `400` with the flagged categories; a downstream failure returns `500` and the ingestion transaction is rolled back.

### Example: readiness check

**Request:** `GET /health/ready`

**Response** `200 OK` (all dependencies reachable):

```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected",
  "qdrant": "connected",
  "gemini": "connected"
}
```

If any dependency is unreachable, the same shape is returned with `status: "not_ready"` and the failing service's field describing the error, at HTTP `503`.

### Example: canonical template

The internal slot convention uses `{{double-brace}}` placeholders:

```json
{
  "cluster_id": "b3d9c1f0-77aa-4c2b-9e10-2f0a4c6d8b91",
  "template": "Generate a {{language}} function to {{task}}",
  "slots": [
    { "name": "language", "type": "programming_language", "example_values": ["Python", "Go"], "confidence": 0.94 },
    { "name": "task",     "type": "string",               "example_values": ["reverse a linked list"], "confidence": 0.88 }
  ],
  "version": "3.0.0",
  "confidence": 0.91,
  "explanation": "Cluster members share the intent 'generate a function', varying only by language and task."
}
```

---

## Environment Variables

No real credentials are shown below — every value is a placeholder. See `.env.example` (root) and `Backend/.env.example` for the canonical templates.

| Variable | Required | Description | Example |
|---|---|---|---|
| `ENV` | Recommended | Application environment. `production`/`development` are normalized to `prod`/`dev`; `staging` is also accepted. Defaults to `dev` if unset. | `prod` |
| `LOG_LEVEL` | No | Log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`). Defaults to `INFO`. | `INFO` |
| `PORT` | No (Render sets it) | Port uvicorn binds to. Defaults to `10000` in `start.sh`. | `10000` |
| `WORKERS` | No | Number of uvicorn worker processes. Only one worker runs the background scheduler regardless of this value. | `2` |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key, used for chat/embeddings/moderation via the `ILLMProvider` seam. | `your_gemini_api_key_here` |
| `DATABASE_URL` | **Yes** | Neon PostgreSQL connection string. `postgres://` is auto-normalized to `postgresql://`; SSL is forced for non-localhost hosts. | `postgresql://user:password@host/db?sslmode=require` |
| `REDIS_URL` | **Yes** | Upstash Redis connection string (cache, rate limiting, scheduler leadership lock). `rediss://` implies TLS. | `rediss://default:password@host:6379` |
| `QDRANT_URL` | **Yes** | Qdrant Cloud cluster URL. Collection is created lazily on first use, at 768 dimensions. | `https://your-cluster.qdrant.tech:6333` |
| `QDRANT_API_KEY` | **Yes** | Qdrant Cloud API key. | `your_qdrant_cloud_api_key_here` |
| `AWS_SECRETS_ENABLED` | No | Enables AWS Secrets Manager as a secrets source. Defaults to `false`; leave disabled for Render. | `false` |
| `AWS_REGION` | Only if AWS Secrets enabled | AWS region for Secrets Manager / S3 / CloudWatch (AWS-compatible path only). | `us-east-2` |
| `S3_BUCKET_NAME` | Only if AWS path used | S3 bucket for artefacts (AWS-compatible path only). | `your-s3-bucket-name` |

**Local-only fallback variables** (used only when the corresponding `*_URL` is unset — e.g. local Docker Compose): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL_MODE`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`, `QDRANT_HOST`, `QDRANT_PORT`.

---

## Local Development

**Prerequisites:** Python 3.12, Docker + Docker Compose, `make` (optional).

```bash
cd Backend

# 1. One-command bootstrap: venv + deps + docker services + migrations
make quickstart

# 2. Provide configuration
cp config/config.example.yaml config/config.yaml
#   → set your Gemini API key and datastore connection details in config.yaml
#   (or export the environment variables listed above)

# 3. Run the API
make dev
#   equivalently:
#   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Database migrations (Alembic):**

```bash
cd Backend
alembic -c migrations/alembic.ini upgrade head        # apply migrations
alembic -c migrations/alembic.ini revision --autogenerate -m "message"   # new migration
```

**Docker Compose (backing services only):**

```bash
cd Backend
docker compose -f docker/docker-compose.yml up -d      # PostgreSQL, Redis, Qdrant
```

Once running, visit:

- `http://localhost:8000/` — service root / web UI dashboard
- `http://localhost:8000/docs` — interactive API docs

---

## Production Deployment

**Platform:** Render, native Python environment (`env: python` in `render.yaml`) — no Docker on the active deployment path.

**Build:** `render-build.sh` installs dependencies from `requirements.txt` and seeds `config/config.yaml` from `config.example.yaml` if it doesn't exist.

**Start:** `start.sh` (invoked via `Procfile`'s `web: ./start.sh`) runs, in order:

1. `alembic upgrade head` — database migrations run automatically on every deploy, before the server starts. The script uses `set -o errexit`, so a failed migration aborts the deploy before `uvicorn` starts (Render keeps the previous healthy instance serving traffic in that case).
2. `uvicorn src.main:app --host 0.0.0.0 --port $PORT --workers $WORKERS`

**Health endpoints:**
- `GET /health` — liveness only, no dependency checks. Used for Render's health check.
- `GET /health/ready` — readiness probe that actively checks PostgreSQL, Redis, Qdrant, and Gemini connectivity; returns `503` if any is unreachable.
- Startup itself performs the same fail-fast validation before the app accepts traffic at all.

**Scheduler behavior in production:** `render.yaml` currently runs `WORKERS=2`. Since `uvicorn --workers N` forks **separate OS processes**, an in-memory flag cannot coordinate which one runs the periodic jobs (drift detection, evaluation metrics, cache cleanup, dataset refresh). Instead, each worker attempts to acquire a Redis-backed lock (`scheduler:leader_lock`, atomic `SET NX EX`) on startup; only the winner registers and runs the jobs, and it renews the lock every 30 seconds to hold leadership for as long as it's alive. If the leader process dies, the lock expires (90-second TTL) and is available for another worker to acquire. This guarantees background jobs run exactly once regardless of worker count.

**Logging:** structured JSON logs via `structlog`, configured in `src/main.py` (timestamp, log level, logger name, request context). A `redact_sensitive_data` helper exists in `utils/logging.py` for stripping sensitive keys from log payloads, though it is defined as a reusable utility rather than wired into the live logging pipeline today.

**Worker sizing:** `WORKERS=2` on the `free` Render plan is a deliberate choice — each worker's SQLAlchemy pool can open up to `pool_size + max_overflow` (20 + 10 = 30) Postgres connections, so 2 workers bound total connections to Neon at 60 rather than the 120 that `WORKERS=4` would allow. Raise this if upgrading to a paid Render plan with more available RAM.

**Post-deploy smoke test:**

1. `GET /health` → `200`
2. `GET /health/ready` → `200`, all of `database`/`redis`/`qdrant`/`gemini` report `"connected"`
3. Check startup logs for exactly one `"This worker acquired scheduler leadership"` line
4. `POST /api/v1/prompts` with a sample prompt → `201`, returns a `cluster_id`
5. `POST /api/v1/prompts` again with the **same** content → `201`, same `cluster_id`, `is_new_cluster: false`, `similarity_score: 1.0`
6. `POST /api/v1/templates/extract/{cluster_id}` → `200`, returns a template with slots
7. `GET /api/v1/evaluation/system` → `200`, metrics present
8. `GET /docs` loads Swagger UI

---

## Project Structure

```
prompt-governance-engine/
├── Backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── v1/                 # Versioned REST endpoints: prompts, clusters, templates,
│   │   │   │                       #   evolution, evaluation, health
│   │   │   │   └── web/            # Server-rendered dashboard routes (Jinja2)
│   │   │   ├── middleware/         # Request logging, Redis-backed rate limiting
│   │   │   └── dependencies.py     # DB session / engine factory
│   │   ├── clients/                # I/O adapters: Gemini, Qdrant, Redis, LLM factory
│   │   ├── config/                 # Pydantic settings models + YAML/env loader
│   │   ├── interfaces/             # Abstract contracts: ILLMProvider, ICache, IVectorDBProvider,
│   │   │                           #   IEmbeddingProvider — the seams business logic depends on
│   │   ├── models/                 # SQLAlchemy ORM models + Pydantic request/response schemas
│   │   ├── services/               # Business logic: orchestrator, decision engine, model router,
│   │   │                           #   embedding, clustering, canonicalization, template versioning,
│   │   │                           #   evolution, lineage, drift detection, evaluation, scheduler
│   │   ├── templates/              # Jinja2 HTML templates for the web dashboard
│   │   ├── utils/                  # Logging, metrics, batch processing, CloudWatch helpers
│   │   ├── workers/                # Bulk dataset ingestion worker
│   │   └── main.py                 # FastAPI application entry point
│   ├── migrations/                 # Alembic environment (env.py) and versioned migrations
│   ├── config/                     # config.yaml (gitignored, real values) / config.example.yaml (template)
│   ├── docker/                     # Dockerfile, docker-compose.yml, ECS task definition (AWS-compatible path)
│   ├── scripts/                    # setup.sh / start.sh / deploy.sh — local developer convenience scripts
│   ├── tests/                      # Test scaffolding (fixtures/, unit/, integration/ directories exist;
│   │                               #   no test cases are implemented yet)
│   ├── Makefile                    # make quickstart / dev / migrate / test, etc.
│   └── requirements.txt
├── render.yaml                     # Render Infrastructure-as-Code service definition (build/start commands, env vars)
├── render-build.sh                 # Render build command (installs deps, seeds config.yaml)
├── start.sh                        # Render start command: runs migrations, then starts uvicorn
├── Procfile                        # Process type declaration (web: ./start.sh)
├── .env.example                    # Root-level environment variable template
└── README.md
```

---

## Engineering Decisions

A summary of the trade-offs behind the system's core design choices. Deeper rationale for each lives in the linked section.

**Provider abstraction (`ILLMProvider`).** All LLM/embedding/moderation calls flow through an interface, never a direct SDK import in business logic. The cost is an extra layer of indirection; the payoff was proven in this codebase's own history — the provider was migrated from an AI gateway to Gemini with **zero changes to business logic**, because nothing above the interface knew which vendor was underneath. See [Provider Abstraction](#provider-abstraction).

**Incremental clustering over batch re-clustering.** Assigning each prompt to a cluster as it arrives (rather than periodically re-clustering the whole corpus) keeps ingestion cheap and streaming-friendly, at the cost of being order-sensitive — cluster quality can drift as new prompts accrete. The trade-off is deliberately accepted and compensated for with scheduled drift detection rather than solved by a more expensive batch algorithm. See [Incremental Clustering](#incremental-clustering) and [Drift Detection Strategy](#drift-detection-strategy).

**Immutable template versioning.** Canonical templates are never updated in place; a change always produces a new version row plus an evolution event. This costs extra storage (every version is retained) in exchange for full auditability, safe rollback, and a reproducible history of what a template looked like at any point in time. See [Template Versioning](#template-versioning).

**Structured (JSON) logging.** Every log line is a structured event (`structlog`) rather than a free-text message, which makes logs machine-parseable for future log aggregation and correlates cleanly with request context. The trade-off is verbosity in raw log output compared to plain text — acceptable given logs are consumed by tooling, not read raw in production.

**Redis for caching, rate limiting, and leader election.** Redis was already a dependency for embedding/similarity caching and rate limiting, so when the scheduler needed cross-process coordination (see [Production Deployment](#production-deployment)), reusing Redis for an atomic `SET NX EX` leadership lock avoided introducing a new piece of infrastructure (e.g. a dedicated coordination service) for a single, well-understood need.

**Qdrant for vector search.** Cosine similarity search over prompt embeddings is delegated entirely to a managed vector database rather than implemented in-application (e.g. brute-force comparison in PostgreSQL). This keeps k-NN search fast and horizontally scalable independent of the relational database, at the cost of an additional managed service and an additional point of failure that the readiness check and fail-fast startup validation explicitly account for.

### Production Engineering Principles

Patterns applied throughout the codebase to keep it maintainable, testable, and operable as it grows:

- **Dependency Injection.** Services receive their collaborators (DB session, clients) via constructor injection, enabling substitution and testing.
- **Factory Pattern.** The LLM provider is constructed behind a factory, so the concrete vendor is a configuration/wiring concern, not a code-coupling one.
- **Repository-adjacent data access.** SQLAlchemy async models isolate persistence from business logic, though there is no dedicated repository layer — services query the ORM directly.
- **Strategy Pattern.** The Model Router selects among model strategies based on runtime signals from the Decision Engine.
- **Configuration-driven design.** Behaviour (thresholds, models, pool sizes, batch sizes) is driven by YAML + environment variables + optional AWS Secrets Manager, validated by Pydantic — no magic constants buried in logic.
- **Async processing.** FastAPI + async SQLAlchemy + async clients throughout, for high I/O concurrency.
- **Observability.** Structured JSON logging (`structlog`), a Prometheus metrics endpoint, and per-request logging middleware.
- **Health checks.** Liveness (`/health`) and readiness (`/health/ready`), plus **fail-fast startup validation** that verifies PostgreSQL, Redis, and Qdrant connectivity before serving traffic.
- **Retry policies.** Configurable retry attempts for external calls; router fallback targets for model failures.
- **Idempotency-friendliness.** Exact-content short-circuiting makes re-ingesting the same prompt cheap and non-duplicative.
- **Fault isolation.** External-dependency failures are caught, logged with context, and surfaced as typed errors; the ingest transaction rolls back cleanly on failure.
- **Distributed coordination.** The scheduler leadership lock is the one place the system explicitly coordinates state across multiple worker processes, using Redis as the shared arbiter.

---

## Confidence Thresholds

Two thresholds (both default `0.85`, configurable) gate the system's automated decisions:

- **`similarity_threshold`** governs **clustering**. A prompt **joins** the best cluster only if its similarity clears this bar; otherwise a **new cluster** is created.
- **`confidence_threshold`** governs **canonicalisation**. If a template extraction returns confidence below this bar, the system **retries with a reasoning-model upgrade** rather than accepting the weak result.

| Regime | Condition | Action |
|--------|-----------|--------|
| **Merge / Join** | similarity ≥ `similarity_threshold` | Assign the prompt to the matching cluster. |
| **New cluster** | best similarity < `similarity_threshold` | Create a new cluster (do not force a weak merge). |
| **Escalate / Review** | extraction confidence < `confidence_threshold` | Retry on the stronger model; low-confidence artefacts are surfaced rather than silently trusted. |

The guiding principle: **the system refuses to make a low-confidence decision quietly.** It either escalates to more capability or records the uncertainty explicitly.

---

## Drift Detection Strategy

Prompt corpora are non-stationary — the distribution of what people ask shifts over time. Drift detection (`services/drift_detection.py`, scheduled every 6 hours) addresses this:

- **Semantic drift.** A cluster's members gradually diverge from its original centroid as new, loosely-related prompts accrete. Detecting this flags clusters that have become too broad to canonicalise cleanly.
- **Template evolution.** When drift changes what a cluster represents, the canonical template must evolve — producing a new immutable version and an evolution event rather than a silent mismatch between template and members.
- **Cluster splits (roadmap).** A drifted cluster that has fractured into distinct sub-intents is a candidate to be split into multiple tighter clusters.
- **Future merge strategies (roadmap).** Symmetrically, clusters that have converged are candidates for a governed, audited merge.

Drift results are exposed at `GET /api/v1/evolution/drift`.

---

## Evaluation Metrics

The Evaluation Engine computes the following per cluster (`GET /api/v1/evaluation/cluster/{id}`) and as system-wide aggregates (`GET /api/v1/evaluation/system`):

| Metric | What it tells you | Basis |
|--------|-------------------|-------|
| **Cluster Purity** | Average similarity score of a cluster's assignments — do members genuinely share one intent? | Computed from stored assignment data |
| **Merge Accuracy / False Merge Rate** | Fraction of assignments below a sanity similarity threshold (`0.8`) — flags weak merges. | Computed from stored assignment data |
| **Embedding Quality** | A purity-derived quality signal for the cluster's embedding cohesion. | Derived from cluster purity |
| **Canonical Template Quality** | Validity check on the extracted template content (non-trivial length). | Heuristic |
| **Slot Extraction Quality** | Average confidence across a template's extracted slots. | Computed from stored slot confidence values |
| **Average Confidence** | The active template's stored confidence score. | Computed |
| **Estimated Model Cost (USD)** | Token-based cost estimate for the cluster's assignment reasoning text. | Heuristic estimate |
| **Average Latency (ms)** | A per-assignment latency figure. | **Simulated** — not a measured wall-clock latency (see code comment in `services/evaluation.py`) |

Being explicit about which metrics are computed from real stored data versus heuristic/simulated placeholders is intentional — this is an area flagged for hardening rather than a claim of full production telemetry today.

---

## Future Improvements

Intentionally deferred — not implemented, and not claimed as implemented:

- **CI/CD pipeline** — no GitHub Actions workflow exists yet; adding lint/test/build automation is a natural next step.
- **Streaming ingestion** — event-driven intake (queue/stream) in place of request-scoped processing.
- **Multi-provider routing** — activate OpenAI / Claude / DeepSeek / Llama behind the existing `ILLMProvider` seam with cross-provider fallback.
- **Batch embeddings** — amortise embedding cost across large bulk loads.
- **Distributed workers** — horizontally scaled ingestion workers with a shared queue.
- **Human-review workflow** — a first-class review queue for low-confidence extractions and proposed merges/splits.
- **OpenTelemetry** — distributed tracing across the pipeline, complementing the existing structured logs and Prometheus metrics.
- **Automated test suite** — `Backend/tests/` currently contains only scaffolding directories; unit and integration tests are not yet implemented.
- **Wired-in log redaction** — apply the existing `redact_sensitive_data` helper to the live logging pipeline.
- **Kubernetes / multi-region deployment** — not warranted at current scale; documented here as a deliberately deferred option, not a near-term plan.

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE) for details.
