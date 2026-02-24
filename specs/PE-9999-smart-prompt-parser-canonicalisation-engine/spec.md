---
spec_id: SPEC-2025-001
jira_id: PE-9999
title: Smart Prompt Parser & Canonicalisation Engine
status: approved
owner: TBD
created_date: 2025-01-27
approved_date: 2025-01-27
---

# Smart Prompt Parser & Canonicalisation Engine

## Overview

A production-grade AI system for clustering semantically equivalent prompts, extracting canonical templates with variable slots, and tracking prompt family evolution. Designed for cloud deployment (AWS), scalable to 100k+ prompts, with full observability and safety guardrails.

## System Objectives

1. **Semantic Clustering**: Group prompts by semantic equivalence, not string similarity
2. **Canonical Template Extraction**: Generate normalized templates with variable slots
3. **Evolution Detection**: Track new prompt families and variable schema changes
4. **Incremental Ingestion**: Process new prompts without full dataset reprocessing
5. **Explainable Grouping**: Provide reasoning for all clustering decisions
6. **Confidence Thresholds**: Enforce configurable merge confidence gates

## Architecture

### Three-Layer AI Architecture

#### Layer 1 — Retrieval
- **Vector DB**: Qdrant/Elastic/Pinecone for approximate nearest neighbor search
- **Redis Cache**: Embedding and similarity score caching
- **Index Management**: HNSW/FAISS for efficient similarity search

#### Layer 2 — Intelligence
- **Embedding Generation**: `@openai/text-embedding-3-small` (primary), `@openai/text-embedding-3-large` (fallback for long/complex prompts)
- **Clustering**: Semantic similarity-based grouping with configurable thresholds
- **Canonicalization**: Template extraction via diff-based analysis using `@openai/gpt-4o-2024-08-06`
- **Variable Detection**: Slot identification with type inference
- **Code-Heavy Prompts**: Use `@anthropic/claude-3-5-sonnet-latest` for superior code logic handling
- **Batch Processing**: Chunked processing (50-200 items) with async workers

#### Layer 3 — Knowledge/Graph
- **Prompt Families**: Hierarchical family structures
- **Template Lineage**: Versioned canonical templates
- **Variable Schema Evolution**: Track slot additions/removals/changes
- **Relationship Mapping**: Inter-family relationships and overlaps
- **Drift Detection**: Semantic drift monitoring within clusters

## Model Orchestration

### 1. Embedding Layer (Vector Representation)
**Purpose**: Vectorize prompts to find semantic clusters (e.g., grouping "translate this" and "translation needed")

- **Primary Model**: `@openai/text-embedding-3-small`
  - **Rationale**: Best cost/performance ratio for clustering
  - **Efficiency**: Faster and significantly cheaper than ada-002
  - **Performance**: Outperforms local models like all-MiniLM-L6-v2 in capturing semantic nuance
  - **Dimensionality**: Highly efficient for vector databases like Qdrant
  - **Use Case**: Semantic clustering, similarity search, duplicate detection

- **Fallback Model**: `@openai/text-embedding-3-large`
  - **When to Use**: Only for very long prompts (>8k tokens) or complex technical instructions
  - **Rationale**: Higher precision at increased cost

### 2. Canonicalization Engine (Template Extraction)
**Purpose**: Diff-based logic to extract canonical templates with `{{VARIABLE}}` structure from prompt clusters

- **Primary Model**: `@openai/gpt-4o-2024-08-06` (or `@openai/gpt-4o` if specific version unavailable)
  - **Rationale**: Fast, reliable JSON outputs for database storage
  - **Structured Outputs**: Excellent support for enforcing JSON Schemas
  - **Reliability**: Most reliable at maintaining strict JSON format without breaking
  - **Speed**: Much faster than gpt-4-turbo
  - **Use Case**: Diff-based template extraction, variable slot detection, CanonicalTemplate generation

- **Alternative Model**: `@anthropic/claude-3-5-sonnet-20241022` (or latest)
  - **When to Use**: Code-heavy prompts or prompts with multi-language code blocks
  - **Rationale**: Superior handling of code logic and variable extraction within code contexts
  - **Use Case**: Code generation prompts, variable extraction inside code blocks

### 3. Evolution & Reasoning Layer (Advanced Decision Making)
**Purpose**: Handle ambiguous clustering decisions, drift detection, and family evolution analysis

- **Model**: `@openai/o1-mini`
  - **Rationale**: Reasoning-optimized for edge cases in clustering
  - **Reasoning Capability**: o1 series is designed to "think" before answering
  - **Use Cases**:
    - Ambiguous clustering decisions (when similarity scores are borderline)
    - Drift detection (semantic shift within prompt families)
    - Family split/merge decisions
    - Edge-case classification
  - **Cost/Speed**: Provides reasoning power of full o1 model but faster and cheaper, perfect for batch pipelines processing thousands of items

### 4. Safety & Content Filtering (Pre-Ingestion)
**Purpose**: Ensure no PII or illegal content enters the database before processing

- **Model**: `@openai/text-moderation-latest`
  - **Rationale**: Free (usually) and fast, ensures database remains clean
  - **Use Cases**:
    - PII filtering
    - Harmful content detection
    - Compliance screening
  - **Mandatory**: Pre-ingestion check before any prompt enters the system
  - **Rejected Content**: Must be logged, not stored, and marked in ingestion report

### Model Routing Policy

**Always use routing logic**:
- **Embedding Requests** → `@openai/text-embedding-3-small`
- **Template Extraction** → `@openai/gpt-4o-2024-08-06`
- **Code-Heavy Prompts** → `@anthropic/claude-3-5-sonnet-latest`
- **Ambiguous Reasoning** → `@openai/o1-mini`
- **Content Safety** → `@openai/text-moderation-latest`

**Never use experimental or placeholder models in production.**

### Model Configuration Summary

| Architecture Component | Recommended Model | Rationale |
|------------------------|-------------------|-----------|
| **Vector Embeddings** | `@openai/text-embedding-3-small` | Best cost/performance ratio for clustering |
| **Template Extraction** | `@openai/gpt-4o-2024-08-06` | Fast, reliable JSON outputs for database storage |
| **Complex Reasoning** | `@openai/o1-mini` | For deciding tricky edge cases in clustering |
| **Code Prompts** | `@anthropic/claude-3-5-sonnet-latest` | Superior handling of code-heavy prompts |

## Pipeline Flow

```
Raw Prompt
  ↓
Moderation Check (text-moderation-latest)
  ↓
Embedding Generation (text-embedding-3-small)
  ↓
Vector Retrieval (Qdrant/Elastic)
  ↓
Similarity Threshold Logic
  ↓
Cluster Assignment (with confidence score)
  ↓
Canonical Template Extraction (gpt-4o)
  ↓
Variable Schema Detection
  ↓
Versioning & Evolution Tracking
  ↓
Storage (Postgres + Vector DB)
```

## Data Persistence

### Storage Strategy
- **PostgreSQL (RDS)**: 
  - Prompt metadata
  - Cluster assignments
  - Template versions
  - Variable schemas
  - Evolution history
- **Vector DB (Qdrant/Elastic)**:
  - Embeddings
  - Similarity indices
- **Redis (ElastiCache)**:
  - Embedding cache
  - Similarity score cache
  - Processing checkpoints
- **S3**:
  - Dataset backups
  - Batch processing artifacts
  - Audit logs

### Stateless Containers
- All containers must be stateless
- No data stored in Docker images
- Persistent volumes for local development only
- Production: External databases only

## Configuration Management

### Configuration File Structure
All API keys, AWS configurations, database credentials, and environment-specific variables will be managed through a centralized configuration file for visibility and easy management.

**File Location**: `config/config.yaml` (or `config/config.json`)

**File Structure**:
```yaml
# config/config.yaml
# This file should NOT be committed to repository
# Use config/config.example.yaml as template

# Portkey AI Configuration
portkey:
  api_key: "${PORTKEY_API_KEY}"  # Load from environment or AWS Secrets Manager
  base_url: "https://api.portkey.ai"
  timeout: 30
  retry_attempts: 3

# Model Configurations
models:
  embedding:
    primary: "@openai/text-embedding-3-small"
    fallback: "@openai/text-embedding-3-large"
    batch_size: 100
  
  canonicalization:
    primary: "@openai/gpt-4o-2024-08-06"
    alternative: "@anthropic/claude-3-5-sonnet-latest"
    max_tokens: 2000
    temperature: 0.1
  
  reasoning:
    model: "@openai/o1-mini"
    max_tokens: 1000
  
  moderation:
    model: "@openai/text-moderation-latest"

# AWS Configuration
aws:
  region: "us-east-2"
  ecr:
    repository: "429441944860.dkr.ecr.us-east-2.amazonaws.com/portkeyaibuilderchallenge"
    region: "us-east-2"
  s3:
    bucket: "${S3_BUCKET_NAME}"
    region: "us-east-2"
  secrets_manager:
    enabled: true
    secret_name: "portkey-prompt-parser/secrets"
  
# Database Configuration
database:
  postgresql:
    host: "${DB_HOST}"
    port: 5432
    database: "${DB_NAME}"
    username: "${DB_USER}"
    password: "${DB_PASSWORD}"  # Load from AWS Secrets Manager in production
    ssl_mode: "require"
    pool_size: 20
    max_overflow: 10
  
  redis:
    host: "${REDIS_HOST}"
    port: 6379
    password: "${REDIS_PASSWORD}"  # Load from AWS Secrets Manager in production
    db: 0
    decode_responses: true
  
  vector_db:
    type: "qdrant"  # Options: qdrant, elasticsearch, pinecone
    qdrant:
      host: "${QDRANT_HOST}"
      port: 6333
      api_key: "${QDRANT_API_KEY}"
    elasticsearch:
      host: "${ELASTICSEARCH_HOST}"
      port: 9200
      username: "${ELASTICSEARCH_USER}"
      password: "${ELASTICSEARCH_PASSWORD}"
    pinecone:
      api_key: "${PINECONE_API_KEY}"
      environment: "${PINECONE_ENVIRONMENT}"
      index_name: "${PINECONE_INDEX_NAME}"

# Application Configuration
app:
  environment: "${ENV}"  # dev, staging, prod
  log_level: "${LOG_LEVEL}"  # DEBUG, INFO, WARNING, ERROR
  api:
    host: "0.0.0.0"
    port: 8000
    rate_limit_per_minute: 100
    max_request_size_mb: 10
  
  clustering:
    similarity_threshold: 0.85
    confidence_threshold: 0.85
    batch_size: 100
    max_cluster_size: 1000
  
  processing:
    worker_concurrency: 4
    batch_size: 100
    max_retries: 3
    retry_backoff_seconds: 2

# Observability
observability:
  cloudwatch:
    enabled: true
    log_group: "/aws/ecs/portkey-prompt-parser"
    region: "us-east-2"
  metrics:
    enabled: true
    endpoint: "/metrics"
    port: 9090
```

### Configuration Loading Strategy

1. **Local Development**:
   - Load from `config/config.yaml` (not committed to repo)
   - Use `config/config.example.yaml` as template (committed)
   - Environment variables can override config file values

2. **Production (AWS)**:
   - Primary: Load from AWS Secrets Manager
   - Fallback: Environment variables injected by ECS/EKS
   - Config file can be mounted as secret volume
   - Never hardcode secrets in code or config files

3. **Configuration Validation**:
   - Validate all required configs at startup
   - Fail fast if critical configs are missing
   - Log configuration loading (without sensitive values)

### Configuration File Visibility

- **Template File**: `config/config.example.yaml` (committed to repo)
  - Contains all configuration keys with placeholder values
  - Documents all required and optional configurations
  - Serves as reference for developers

- **Actual Config File**: `config/config.yaml` (in `.gitignore`)
  - Contains real values for local development
  - Never committed to repository
  - Used for local testing and development

- **Production Configs**: Managed via AWS Secrets Manager or environment variables
  - No config files in production containers
  - All secrets loaded at runtime from secure sources

## Security & Safety

### API Layer
- Rate limiting per API key
- Authentication: API Key / JWT
- Request size limits (configurable)
- Input schema validation (JSON Schema)

### Secrets Management
- **Configuration File**: Centralized `config/config.yaml` for all API keys, AWS configs, and variables
  - Provides visibility of all secrets and variables in one place
  - Template file (`config/config.example.yaml`) committed to repo
  - Actual config file (`config/config.yaml`) excluded via `.gitignore`
- **Production**: AWS Secrets Manager or environment variables
  - No secrets in repository or committed config files
  - Config file compatible with AWS Secrets Manager
  - Environment variables can override config file values
- **Security**:
  - All sensitive values loaded from secure sources at runtime
  - Config validation on startup
  - Logging excludes sensitive values

### AI Safety
- Prompt injection awareness
- Output bounds validation
- Timeout guards on all LLM calls
- Content moderation pre-filtering

## Observability

### Logging
- JSON structured logs
- Request IDs and correlation IDs
- Decision reasoning logged
- Model usage tracking

### Metrics
- Queue depth
- Latency (p50, p95, p99)
- Throughput (prompts/second)
- Error rate
- Cost tracking (token usage, API costs)
- Cluster quality metrics

### Health Endpoints
- `/health`: Basic health check
- `/ready`: Readiness probe (DB connectivity, vector DB connectivity)
- `/metrics`: Prometheus-compatible metrics

## Performance Requirements

### Scalability
- Design for 100k+ prompts
- Batch embedding calls (50-200 items)
- Async workers for ingestion
- Chunked batch dispatch
- Avoid O(N²) operations

### Optimization
- Cache model clients
- Limit concurrency (configurable)
- Cap CPU and memory
- Avoid synchronous AI calls in API threads
- Use generator-based ingestion

## Deployment Strategy

### Local Development
- Docker Compose for local stack
- PostgreSQL container
- Redis container
- Vector DB container (Qdrant)
- Stateless application containers

### AWS Deployment
- **ECS/EKS**: Container orchestration
- **RDS PostgreSQL**: Primary database
- **ElastiCache Redis**: Caching layer
- **ECR**: Docker image registry
- **S3**: Artifacts and backups
- **CloudWatch**: Logging and metrics

### Image Management
- Build images locally or via CI
- Push to AWS ECR
- Versioned tags (prod, staging, v1.2.0)
- Never deploy from local-only images

## Failure Handling

### Retry Policies
- Exponential backoff for API calls
- Configurable retry limits
- Dead letter queues for failed items
- Progress tracking tables

### Resilience
- Graceful degradation
- Partial failure handling
- Checkpoint-based recovery
- Idempotent operations

## External Dependencies

All external dependencies and credentials are managed through the centralized configuration file (`config/config.yaml`). See Configuration Management section for details.

### Portkey AI
- **API Key**: Configured in `config/config.yaml` under `portkey.api_key`
  - Loaded from environment variable `PORTKEY_API_KEY` or AWS Secrets Manager
- **Models**: Configured in `config/config.yaml` under `models.*`
  - `@openai/text-embedding-3-small` (primary embedding)
  - `@openai/text-embedding-3-large` (fallback embedding)
  - `@openai/gpt-4o-2024-08-06` (canonicalization)
  - `@anthropic/claude-3-5-sonnet-latest` (code-heavy prompts)
  - `@openai/o1-mini` (reasoning)
  - `@openai/text-moderation-latest` (safety)

### AWS Services
- **ECR**: Configured in `config/config.yaml` under `aws.ecr.*`
  - Repository: `429441944860.dkr.ecr.us-east-2.amazonaws.com/portkeyaibuilderchallenge`
  - Region: `us-east-2`
  - Credentials: AWS IAM role or credentials file (not in config)
- **S3**: Configured in `config/config.yaml` under `aws.s3.*`
  - Bucket name from environment variable `S3_BUCKET_NAME`
- **Secrets Manager**: Configured in `config/config.yaml` under `aws.secrets_manager.*`
  - Secret name: `portkey-prompt-parser/secrets`
  - Used for production credential management

### Infrastructure Services
All infrastructure credentials configured in `config/config.yaml`:
- **PostgreSQL**: `database.postgresql.*` (RDS or managed)
- **Redis**: `database.redis.*` (ElastiCache or managed)
- **Vector DB**: `database.vector_db.*` (Qdrant/Elastic/Pinecone)
  - Type selected via `database.vector_db.type`
  - Credentials for selected type under respective section

## Output Format

### Canonical Template Structure
```json
{
  "cluster_id": "string",
  "canonical_template": "string",
  "slots": [
    {
      "name": "string",
      "type": "string",
      "example_values": ["string"],
      "confidence": 0.0-1.0
    }
  ],
  "confidence": 0.0-1.0,
  "explanation": "string",
  "version": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### Cluster Assignment Response
```json
{
  "prompt_id": "string",
  "cluster_id": "string",
  "similarity_score": 0.0-1.0,
  "reasoning": "string",
  "template_version": "string"
}
```

## Success Criteria

1. Successfully cluster semantically equivalent prompts with >90% accuracy
2. Extract canonical templates with variable slots
3. Track prompt family evolution over time
4. Process 100k+ prompts incrementally without full reprocessing
5. Provide explainable clustering decisions for all merges
6. Enforce confidence thresholds (configurable, default 0.85)
7. Deploy to AWS ECS/EKS successfully
8. Achieve <500ms p95 latency for prompt ingestion
9. Maintain >99.9% uptime
10. Cost-optimized model usage (track and optimize token consumption)

## Non-Functional Requirements

- **Scalability**: Handle 100k+ prompts with linear scaling
- **Reliability**: 99.9% uptime SLA
- **Performance**: <500ms p95 latency for ingestion
- **Cost**: Optimize for cost/quality ratio
- **Security**: SOC 2 compatible security practices
- **Observability**: Full traceability of decisions
- **Maintainability**: Modular, testable architecture

## Open Questions

1. Preferred vector DB choice (Qdrant vs Elastic vs Pinecone)?
2. Initial confidence threshold values?
3. Batch size optimization (50-200 range)?
4. Retry policy configuration?
5. Monitoring/alerting thresholds?

