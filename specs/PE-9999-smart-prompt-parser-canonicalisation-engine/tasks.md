# Task Breakdown: Smart Prompt Parser & Canonicalisation Engine

**Spec ID**: SPEC-2025-001  
**JIRA ID**: PE-9999  
**Status**: Approved  
**Created**: 2025-01-27  
**Approved**: 2025-01-27

---

## Task Organization

Tasks are organized by implementation phase and feature area. Tasks marked with `[P]` can be parallelized.

**Key Changes**:
- **Dataset Ingestion**: All dataset files will be read from the `Dataset/` folder (Phase 2.6)
- **Lightweight Frontend**: Simple FastAPI template-based frontend (no React/complex UI) - Jinja2 templates only (Phase 6.7)
- **Testing**: Test tasks are skipped for now - focus on core implementation first
- **Optimization**: Performance testing and optimization tasks deferred to later phases

---

## Phase 1: Foundation & Infrastructure

### 1.1 Project Setup & Structure

**Task 1.1.1**: Initialize Python project structure
- **File**: `Backend/pyproject.toml`, `Backend/requirements.txt`, `Backend/requirements-dev.txt`
- **Dependencies**: None
- **Description**: Create project structure with proper Python packaging, dependencies, and development tools
- **Acceptance Criteria**:
  - `pyproject.toml` with project metadata
  - `requirements.txt` with production dependencies
  - `requirements-dev.txt` with development dependencies
  - Proper `.gitignore` file

**Task 1.1.2**: Create project directory structure
- **File**: `Backend/src/` (all subdirectories), `Backend/tests/`, `Backend/config/`, `Backend/migrations/`, `Backend/docker/`, `Backend/scripts/`
- **Dependencies**: Task 1.1.1
- **Description**: Create all directory structure as per plan.md
- **Acceptance Criteria**:
  - All directories from plan.md file structure exist
  - `__init__.py` files in all Python packages
  - Empty placeholder files where needed

### 1.2 Configuration Management

**Task 1.2.1**: Create configuration file template
- **File**: `Backend/config/config.example.yaml`
- **Dependencies**: Task 1.1.2
- **Description**: Create `config.example.yaml` with all configuration keys and placeholder values
- **Acceptance Criteria**:
  - All configuration sections from spec.md included
  - Placeholder values for all secrets
  - Comments explaining each configuration option

**Task 1.2.2**: Implement configuration loader
- **File**: `Backend/src/config/settings.py`, `Backend/src/config/models.py`
- **Dependencies**: Task 1.2.1
- **Description**: Create Pydantic models and loader for configuration file
- **Acceptance Criteria**:
  - Loads from `config.yaml` or environment variables
  - Validates all required configurations
  - Supports AWS Secrets Manager integration
  - Fails fast on missing critical configs

### 1.3 Database Schema Design

**Task 1.3.1**: Design PostgreSQL database schema
- **File**: `Backend/migrations/alembic/versions/001_initial_schema.py`
- **Dependencies**: Task 1.1.2
- **Description**: Create Alembic migration for initial database schema
- **Acceptance Criteria**:
  - All 8 tables created (prompts, clusters, cluster_assignments, canonical_templates, template_slots, evolution_events, prompt_families, family_cluster_mappings)
  - All indexes created
  - Foreign key constraints defined
  - JSONB columns for flexible schema

**Task 1.3.2**: Create SQLAlchemy models
- **File**: `Backend/src/models/database.py`
- **Dependencies**: Task 1.3.1
- **Description**: Create SQLAlchemy async models for all database tables
- **Acceptance Criteria**:
  - All tables mapped to SQLAlchemy models
  - Relationships defined correctly
  - Async-compatible models
  - Type hints for all fields

**Task 1.3.4**: Set up Alembic configuration
- **File**: `Backend/migrations/alembic.ini`, `Backend/migrations/alembic/env.py`
- **Dependencies**: Task 1.3.1
- **Description**: Configure Alembic for database migrations
- **Acceptance Criteria**:
  - Alembic configured for async PostgreSQL
  - Migration scripts can run up and down
  - Connection string from config

### 1.4 Docker & Local Development Setup

**Task 1.4.1**: Create Docker Compose configuration
- **File**: `Backend/docker/docker-compose.yml`
- **Dependencies**: Task 1.2.1
- **Description**: Create Docker Compose with PostgreSQL, Redis, Qdrant
- **Acceptance Criteria**:
  - PostgreSQL container configured
  - Redis container configured
  - Qdrant container configured
  - Networks and volumes configured
  - Environment variables from config

**Task 1.4.2**: Create development Dockerfile
- **File**: `Backend/docker/Dockerfile.dev`
- **Dependencies**: Task 1.1.1
- **Description**: Create Dockerfile for local development
- **Acceptance Criteria**:
  - Python 3.11+ base image
  - Development dependencies installed
  - Hot reload support
  - Proper working directory

### 1.5 Basic FastAPI Application

**Task 1.5.1**: Create FastAPI application entry point
- **File**: `Backend/src/main.py`
- **Dependencies**: Task 1.2.2
- **Description**: Create basic FastAPI app with configuration loading
- **Acceptance Criteria**:
  - FastAPI app initialized
  - Configuration loaded on startup
  - Proper error handling
  - Logging configured

**Task 1.5.2**: Create health check endpoints
- **File**: `Backend/src/api/v1/health.py`
- **Dependencies**: Task 1.5.1
- **Description**: Create `/health` and `/ready` endpoints
- **Acceptance Criteria**:
  - `/health` endpoint returns 200
  - `/ready` endpoint checks database connectivity
  - Proper response schemas

## Phase 2: Model Integration & Core Services

### 2.1 Portkey AI Client Wrapper

**Task 2.1.1**: Create Portkey AI client wrapper
- **File**: `Backend/src/clients/portkey.py`
- **Dependencies**: Task 1.2.2
- **Description**: Create wrapper for Portkey AI SDK with retry logic and error handling
- **Acceptance Criteria**:
  - Uses `from portkey_ai import Portkey` and `from portkey_ai import AsyncPortkey`
  - Portkey client initialized: `Portkey(api_key="...", provider="@...")` or `Portkey(api_key="...", config="cf-***")`
  - Async client: `AsyncPortkey(api_key="...", provider="@...")`
  - API key from config or environment variable `PORTKEY_API_KEY`
  - Virtual Key or Config object for provider selection
  - Support for `with_options(trace_id="...", metadata={...})` for request-level overrides
  - Retry logic with exponential backoff
  - Error handling for API failures
  - Timeout guards
  - Logging for all API calls
  - Support for custom httpx.Client if needed

### 2.2 Moderation Service

**Task 2.2.1**: Implement moderation service
- **File**: `Backend/src/services/moderation.py`
- **Dependencies**: Task 2.1.1
- **Description**: Create service for content moderation using text-moderation-latest
- **Acceptance Criteria**:
  - Uses `portkey.moderations.create()` API
  - Model: `@openai/text-moderation-latest`
  - Returns moderation status
  - Logs rejected content
  - Handles API errors gracefully
  - Uses AsyncPortkey for async operations

### 2.3 Embedding Service

**Task 2.3.1**: Implement embedding generation service
- **File**: `Backend/src/services/embedding.py`
- **Dependencies**: Task 2.1.1
- **Description**: Create service for generating embeddings using text-embedding-3-small
- **Acceptance Criteria**:
  - Uses `portkey.embeddings.create()` API
  - Model: `@openai/text-embedding-3-small` (primary)
  - Falls back to `@openai/text-embedding-3-large` for long prompts (>8k tokens)
  - Batch processing support (50-200 items)
  - Returns embeddings with metadata
  - Uses AsyncPortkey for async operations
  - Supports `encoding_format="float"` parameter

**Task 2.3.2**: Implement Redis caching for embeddings
- **File**: `Backend/src/clients/redis.py`, `Backend/src/services/embedding.py` (update)
- **Dependencies**: Task 2.3.1, Task 1.4.1
- **Description**: Add Redis caching layer for embeddings
- **Acceptance Criteria**:
  - Cache embeddings by prompt hash
  - TTL of 7 days
  - Cache hit/miss logging
  - Proper error handling

### 2.4 Model Router

**Task 2.4.1**: Implement model routing logic
- **File**: `Backend/src/services/model_router.py`
- **Dependencies**: Task 2.1.1
- **Description**: Create router to select appropriate model (Claude for code-heavy prompts)
- **Acceptance Criteria**:
  - Detects code-heavy prompts
  - Routes to Claude Sonnet for code prompts
  - Routes to GPT-4o for regular prompts
  - Configurable routing rules

### 2.5 Batch Processing Coordinator

**Task 2.5.1**: Implement batch processing utilities
- **File**: `Backend/src/utils/batch_processor.py`
- **Dependencies**: None
- **Description**: Create utilities for chunking and processing batches
- **Acceptance Criteria**:
  - Chunks items into batches (50-200 configurable)
  - Async batch processing
  - Progress tracking
  - Error handling per batch

### 2.6 Dataset Ingestion Service

**Task 2.6.1**: Implement dataset reader from Dataset folder
- **File**: `Backend/src/services/dataset_reader.py`
- **Dependencies**: Task 1.1.2
- **Description**: Create service to read prompts from `Dataset/` folder
- **Acceptance Criteria**:
  - Reads files from `Dataset/` folder
  - Supports common formats (JSON, CSV, TXT, JSONL)
  - Generator-based reading (memory efficient)
  - Handles file encoding errors
  - Logs files processed

**Task 2.6.2**: Implement dataset ingestion pipeline
- **File**: `Backend/src/workers/dataset_ingestion.py`
- **Dependencies**: Task 2.6.1, Task 2.2.1, Task 2.3.2, Task 3.3.2
- **Description**: Create worker to ingest all prompts from Dataset folder
- **Acceptance Criteria**:
  - Processes all files in Dataset folder
  - Runs full pipeline (moderation → embedding → clustering → canonicalization)
  - Progress tracking and checkpointing
  - Handles errors gracefully (continues on file errors)
  - Reports ingestion summary

## Phase 3: Clustering & Similarity

### 3.1 Qdrant Client Setup

**Task 3.1.1**: Create Qdrant client wrapper
- **File**: `Backend/src/clients/qdrant.py`
- **Dependencies**: Task 1.2.2
- **Description**: Create wrapper for Qdrant client with connection management
- **Acceptance Criteria**:
  - Qdrant client initialized from config
  - Collection management
  - Connection pooling
  - Error handling

**Task 3.1.2**: Set up Qdrant collection
- **File**: `Backend/src/clients/qdrant.py` (update)
- **Dependencies**: Task 3.1.1
- **Description**: Create collection for prompt embeddings
- **Acceptance Criteria**:
  - Collection created with correct vector size (1536)
  - HNSW index configured
  - Collection name: `prompt_embeddings`

### 3.2 Vector Similarity Search

**Task 3.2.1**: Implement vector similarity search service
- **File**: `Backend/src/services/similarity.py`
- **Dependencies**: Task 3.1.2
- **Description**: Create service for finding similar prompts using vector search
- **Acceptance Criteria**:
  - Approximate nearest neighbor search
  - Configurable similarity threshold
  - Returns top-k similar prompts
  - Performance optimized

### 3.3 Clustering Service

**Task 3.3.1**: Implement clustering algorithm
- **File**: `Backend/src/services/clustering.py`
- **Dependencies**: Task 3.2.1
- **Description**: Create clustering service with confidence scoring
- **Acceptance Criteria**:
  - Semantic similarity-based clustering
  - Configurable similarity threshold (default 0.85)
  - Confidence scoring for assignments
  - Incremental clustering (no full reprocessing)

**Task 3.3.2**: Implement cluster assignment logic
- **File**: `Backend/src/services/clustering.py` (update)
- **Dependencies**: Task 3.3.1
- **Description**: Assign prompts to clusters with reasoning
- **Acceptance Criteria**:
  - Assigns to existing cluster if similarity > threshold
  - Creates new cluster if no match
  - Generates reasoning for assignment
  - Stores assignment in database

### 3.4 Similarity Score Caching

**Task 3.4.1**: Implement Redis caching for similarity scores
- **File**: `Backend/src/services/clustering.py` (update)
- **Dependencies**: Task 3.3.2, Task 2.3.2
- **Description**: Cache similarity scores in Redis
- **Acceptance Criteria**:
  - Cache key: `similarity:{prompt_id}:{cluster_id}`
  - TTL of 1 day
  - Cache hit/miss logging

## Phase 4: Canonicalization Engine

### 4.1 Template Extraction Service

**Task 4.1.1**: Implement template extraction using GPT-4o
- **File**: `Backend/src/services/canonicalization.py`
- **Dependencies**: Task 2.1.1, Task 3.3.2
- **Description**: Create service for extracting canonical templates from prompt clusters
- **Acceptance Criteria**:
  - Uses `portkey.chat.completions.create()` API
  - Model: `@openai/gpt-4o-2024-08-06` or `@openai/gpt-4o`
  - Diff-based template extraction
  - Returns canonical template with variable slots
  - JSON schema validation for output (using `response_format` parameter)
  - Uses AsyncPortkey for async operations
  - Supports structured output with JSON schema

**Task 4.1.2**: Implement variable slot detection
- **File**: `Backend/src/services/canonicalization.py` (update)
- **Dependencies**: Task 4.1.1
- **Description**: Extract variable slots with type inference
- **Acceptance Criteria**:
  - Identifies variable slots ({{variable}})
  - Infers slot types
  - Extracts example values
  - Calculates confidence scores

### 4.2 Code-Heavy Prompt Handler

**Task 4.2.1**: Implement Claude Sonnet integration for code prompts
- **File**: `Backend/src/services/canonicalization.py` (update)
- **Dependencies**: Task 4.1.1, Task 2.4.1
- **Description**: Use Claude Sonnet for code-heavy prompt template extraction
- **Acceptance Criteria**:
  - Detects code-heavy prompts
  - Uses `portkey.chat.completions.create()` API
  - Model: `@anthropic/claude-3-5-sonnet-latest` or `@anthropic/claude-3-5-sonnet-20241022`
  - Extracts variables from code context
  - Returns canonical template
  - Uses AsyncPortkey for async operations

### 4.3 Template Versioning

**Task 4.3.1**: Implement template versioning system
- **File**: `Backend/src/services/template_versioning.py`
- **Dependencies**: Task 4.1.2, Task 1.3.2
- **Description**: Create service for versioning canonical templates
- **Acceptance Criteria**:
  - Versions templates (semantic versioning)
  - Stores version history
  - Tracks changes between versions
  - Prevents overwriting templates

## Phase 5: Evolution Tracking & Reasoning

### 5.1 Evolution Tracking Service

**Task 5.1.1**: Implement evolution event tracking
- **File**: `Backend/src/services/evolution.py`
- **Dependencies**: Task 4.3.1, Task 1.3.2
- **Description**: Track template evolution events (CREATED, UPDATED, SLOT_ADDED, etc.)
- **Acceptance Criteria**:
  - Records evolution events
  - Stores change reasons
  - Tracks detected_by (model name)
  - Links to template versions

### 5.2 Drift Detection Service

**Task 5.2.1**: Implement drift detection using o1-mini
- **File**: `Backend/src/services/drift_detection.py`
- **Dependencies**: Task 2.1.1, Task 5.1.1
- **Description**: Create service for detecting semantic drift using o1-mini
- **Acceptance Criteria**:
  - Uses `portkey.chat.completions.create()` API
  - Model: `@openai/o1-mini`
  - Detects semantic shifts in clusters
  - Returns drift analysis with reasoning
  - Triggers evolution events
  - Uses AsyncPortkey for async operations

### 5.3 Family Relationship Mapping

**Task 5.3.1**: Implement prompt family tracking
- **File**: `Backend/src/services/family_tracking.py`
- **Dependencies**: Task 3.3.2, Task 1.3.2
- **Description**: Create service for tracking prompt family relationships
- **Acceptance Criteria**:
  - Creates prompt families
  - Maps clusters to families
  - Tracks parent-child relationships
  - Supports family hierarchies

**Task 5.3.2**: Implement family split/merge logic
- **File**: `Backend/src/services/family_tracking.py` (update)
- **Dependencies**: Task 5.3.1, Task 5.2.1
- **Description**: Handle family split and merge decisions using o1-mini
- **Acceptance Criteria**:
  - Uses `portkey.chat.completions.create()` API
  - Model: `@openai/o1-mini`
  - Creates new families on split
  - Merges families when appropriate
  - Records decision reasoning
  - Uses AsyncPortkey for async operations

### 5.4 Edge Case Reasoning Service

**Task 5.4.1**: Implement edge case classification using o1-mini
- **File**: `Backend/src/services/reasoning.py`
- **Dependencies**: Task 2.1.1, Task 3.3.2
- **Description**: Create service for handling ambiguous clustering decisions
- **Acceptance Criteria**:
  - Uses `portkey.chat.completions.create()` API
  - Model: `@openai/o1-mini`
  - Handles borderline similarity scores
  - Provides reasoning for decisions
  - Returns classification with confidence
  - Uses AsyncPortkey for async operations

## Phase 6: API & Integration

### 6.1 Prompt Ingestion API

**Task 6.1.1**: Create prompt ingestion endpoint
- **File**: `Backend/src/api/v1/prompts.py`
- **Dependencies**: Task 2.2.1, Task 2.3.2, Task 3.3.2, Task 4.1.2
- **Description**: Create POST `/api/v1/prompts` endpoint for ingesting prompts
- **Acceptance Criteria**:
  - Accepts prompt content
  - Validates input schema
  - Triggers full pipeline (moderation → embedding → clustering → canonicalization)
  - Returns prompt ID and cluster assignment

### 6.2 Cluster Query API

**Task 6.2.1**: Create cluster query endpoints
- **File**: `Backend/src/api/v1/clusters.py`
- **Dependencies**: Task 3.3.2
- **Description**: Create GET endpoints for querying clusters
- **Acceptance Criteria**:
  - GET `/api/v1/clusters` - List all clusters
  - GET `/api/v1/clusters/{cluster_id}` - Get cluster details
  - GET `/api/v1/clusters/{cluster_id}/prompts` - Get prompts in cluster
  - Proper pagination and filtering

### 6.3 Template API

**Task 6.3.1**: Create template endpoints
- **File**: `Backend/src/api/v1/templates.py`
- **Dependencies**: Task 4.3.1
- **Description**: Create GET endpoints for querying templates
- **Acceptance Criteria**:
  - GET `/api/v1/templates` - List all templates
  - GET `/api/v1/templates/{template_id}` - Get template details
  - GET `/api/v1/templates/{template_id}/versions` - Get template versions
  - GET `/api/v1/templates/{template_id}/evolution` - Get evolution history

### 6.4 Evolution Tracking API

**Task 6.4.1**: Create evolution tracking endpoints
- **File**: `Backend/src/api/v1/evolution.py`
- **Dependencies**: Task 5.1.1
- **Description**: Create GET endpoints for evolution tracking
- **Acceptance Criteria**:
  - GET `/api/v1/evolution/events` - List evolution events
  - GET `/api/v1/evolution/families` - List prompt families
  - GET `/api/v1/evolution/drift` - Get drift detection results
  - Proper filtering and pagination

### 6.5 Authentication & Rate Limiting

**Task 6.5.1**: Implement API authentication middleware
- **File**: `Backend/src/api/middleware/auth.py`
- **Dependencies**: Task 1.2.2
- **Description**: Create API key authentication middleware
- **Acceptance Criteria**:
  - Validates API key from header
  - Returns 401 for invalid keys
  - Logs authentication attempts
  - Configurable API keys

**Task 6.5.2**: Implement rate limiting middleware
- **File**: `Backend/src/api/middleware/rate_limit.py`
- **Dependencies**: Task 2.3.2
- **Description**: Create rate limiting middleware using Redis
- **Acceptance Criteria**:
  - Rate limit per API key
  - Configurable limits per endpoint
  - Returns 429 for rate limit exceeded
  - Uses Redis for counters

### 6.6 API Documentation

**Task 6.6.1**: Create OpenAPI/Swagger documentation
- **File**: `Backend/src/main.py` (update)
- **Dependencies**: All API endpoints
- **Description**: Configure FastAPI OpenAPI documentation
- **Acceptance Criteria**:
  - Swagger UI accessible at `/docs`
  - ReDoc accessible at `/redoc`
  - All endpoints documented
  - Request/response schemas documented

### 6.7 Lightweight Frontend (FastAPI Templates)

**Task 6.7.1**: Set up FastAPI templates directory
- **File**: `Backend/src/templates/` (directory), `Backend/src/static/` (directory)
- **Dependencies**: Task 1.1.2
- **Description**: Create directories for Jinja2 templates and static files
- **Acceptance Criteria**:
  - `templates/` directory created
  - `static/` directory created (for CSS/JS if needed)
  - Base template created
  - FastAPI configured for Jinja2 templates

**Task 6.7.2**: Create base HTML template
- **File**: `Backend/src/templates/base.html`
- **Dependencies**: Task 6.7.1
- **Description**: Create base HTML template with minimal styling
- **Acceptance Criteria**:
  - Simple, clean HTML structure
  - Basic CSS (inline or minimal external)
  - No complex frameworks (no React, no Vue)
  - Responsive design (basic mobile support)

**Task 6.7.3**: Create prompt ingestion form page
- **File**: `Backend/src/templates/ingest_prompt.html`, `Backend/src/api/v1/web/prompts.py`
- **Dependencies**: Task 6.7.2, Task 6.1.1
- **Description**: Create simple HTML form for ingesting single prompt
- **Acceptance Criteria**:
  - Form with textarea for prompt input
  - Submit button
  - Success/error messages
  - Redirects to results page

**Task 6.7.4**: Create dataset ingestion page
- **File**: `Backend/src/templates/ingest_dataset.html`, `Backend/src/api/v1/web/dataset.py`
- **Dependencies**: Task 6.7.2, Task 2.6.2
- **Description**: Create page to trigger dataset ingestion from Dataset folder
- **Acceptance Criteria**:
  - Button to start ingestion
  - Progress indicator (simple)
  - Shows files being processed
  - Displays ingestion summary

**Task 6.7.5**: Create cluster/template viewing pages
- **File**: `Backend/src/templates/clusters.html`, `Backend/src/templates/templates.html`, `Backend/src/api/v1/web/clusters.py`, `Backend/src/api/v1/web/templates.py`
- **Dependencies**: Task 6.7.2, Task 6.2.1, Task 6.3.1
- **Description**: Create simple pages to view clusters and templates
- **Acceptance Criteria**:
  - List view of clusters/templates
  - Basic pagination
  - Click to view details
  - Simple, clean layout

**Task 6.7.6**: Create home/dashboard page
- **File**: `Backend/src/templates/index.html`, `Backend/src/api/v1/web/index.py`
- **Dependencies**: Task 6.7.2
- **Description**: Create simple home page with links to main features
- **Acceptance Criteria**:
  - Links to prompt ingestion
  - Links to dataset ingestion
  - Links to clusters/templates views
  - Basic stats display (if available)

## Phase 7: Observability & Production Readiness

### 7.1 Structured Logging

**Task 7.1.1**: Implement structured JSON logging
- **File**: `Backend/src/utils/logging.py`
- **Dependencies**: Task 1.2.2
- **Description**: Set up structured logging with structlog
- **Acceptance Criteria**:
  - JSON structured logs
  - Request IDs and correlation IDs
  - Log levels configurable
  - Sensitive data redaction

**Task 7.1.2**: Add request logging middleware
- **File**: `Backend/src/api/middleware/logging.py`
- **Dependencies**: Task 7.1.1
- **Description**: Create middleware for request/response logging
- **Acceptance Criteria**:
  - Logs all requests
  - Includes request IDs
  - Logs response times
  - Excludes sensitive data

### 7.2 Metrics & Monitoring

**Task 7.2.1**: Implement Prometheus metrics
- **File**: `Backend/src/utils/metrics.py`
- **Dependencies**: Task 1.5.1
- **Description**: Create Prometheus metrics endpoint
- **Acceptance Criteria**:
  - Metrics endpoint at `/metrics`
  - Tracks latency (p50, p95, p99)
  - Tracks throughput
  - Tracks error rates
  - Tracks token usage

**Task 7.2.2**: Add CloudWatch integration
- **File**: `Backend/src/utils/cloudwatch.py`
- **Dependencies**: Task 7.1.1
- **Description**: Integrate CloudWatch logging
- **Acceptance Criteria**:
  - Sends logs to CloudWatch
  - Configurable log group
  - Proper AWS credentials handling
  - Error handling for CloudWatch failures

### 7.3 Production Dockerfile

**Task 7.3.1**: Create production Dockerfile
- **File**: `Backend/docker/Dockerfile`
- **Dependencies**: Task 1.1.1
- **Description**: Create optimized production Dockerfile
- **Acceptance Criteria**:
  - Multi-stage build
  - Minimal image size
  - Non-root user
  - Health check configured
  - Proper working directory

### 7.4 AWS Deployment Configuration

**Task 7.4.1**: Create ECS task definition
- **File**: `Backend/docker/ecs-task-definition.json`
- **Dependencies**: Task 7.3.1
- **Description**: Create AWS ECS task definition
- **Acceptance Criteria**:
  - Container definitions
  - Environment variables
  - Secrets from Secrets Manager
  - Resource limits
  - Health checks

**Task 7.4.2**: Create deployment scripts
- **File**: `Backend/scripts/deploy.sh`
- **Dependencies**: Task 7.4.1
- **Description**: Create deployment script for AWS
- **Acceptance Criteria**:
  - Builds Docker image
  - Pushes to ECR
  - Updates ECS service
  - Handles rollback on failure

---

## Task Dependencies Summary

### Critical Path
1. Project Setup → Configuration → Database Schema → Docker Setup → Basic API
2. Portkey Client → Moderation → Embedding → Clustering → Canonicalization
3. API Endpoints → Authentication → Documentation
4. Logging → Metrics → Production Docker → Deployment

### Parallelizable Tasks
- Service implementations can be parallelized after core dependencies
- API endpoints can be developed in parallel
- Frontend pages can be developed in parallel

---

## Success Criteria

- All core implementation tasks completed
- System functional and deployable
- Basic API endpoints working
- Dataset ingestion functional
- Lightweight frontend operational
- Production deployment successful

**Note**: Testing, optimization, and comprehensive documentation tasks are deferred to later phases. Focus is on core functionality first.

