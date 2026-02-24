# Implementation Plan: Smart Prompt Parser & Canonicalisation Engine

**Spec ID**: SPEC-2025-001  
**JIRA ID**: PE-9999  
**Status**: Approved  
**Created**: 2025-01-27  
**Approved**: 2025-01-27

---

## Architecture Overview

### System Components

1. **API Service** (FastAPI)
   - RESTful API for prompt ingestion and querying
   - Health checks and metrics endpoints
   - Rate limiting and authentication

2. **Ingestion Pipeline** (Async Workers)
   - Moderation check service
   - Embedding generation service
   - Clustering service
   - Canonicalization service

3. **Data Layer**
   - PostgreSQL for metadata and relationships
   - Vector DB (Qdrant) for embeddings and similarity search
   - Redis for caching and checkpoints

4. **Model Orchestration Layer**
   - Portkey AI client wrapper
   - Model routing logic
   - Batch processing coordinator

5. **Evolution Tracking Service**
   - Template versioning
   - Drift detection
   - Family relationship tracking

### Technology Stack

- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Async Framework**: asyncio, aiohttp
- **Database**: PostgreSQL 15+ (via SQLAlchemy async)
- **Vector DB**: Qdrant (primary), Elasticsearch/Pinecone (alternatives)
- **Cache**: Redis (via aioredis)
- **AI SDK**: Portkey AI SDK (Python)
- **Config Management**: PyYAML, pydantic-settings
- **Testing**: pytest, pytest-asyncio
- **Containerization**: Docker, Docker Compose
- **Deployment**: AWS ECS/EKS

---

## Implementation Phases

### Phase 1: Foundation & Infrastructure (Week 1)

**Goal**: Set up project structure, configuration management, and core infrastructure

**Deliverables**:
- Project scaffolding
- Configuration management system
- Database schema design and migrations
- Docker Compose for local development
- Basic health check endpoints

**Key Tasks**:
1. Initialize Python project with proper structure
2. Create configuration management (`config/config.yaml`, `config/config.example.yaml`)
3. Set up PostgreSQL schema (prompts, clusters, templates, evolution tracking)
4. Set up Qdrant collection structure
5. Create Docker Compose with PostgreSQL, Redis, Qdrant
6. Implement configuration loader with validation
7. Create basic FastAPI app with health endpoints

### Phase 2: Model Integration & Core Services (Week 2)

**Goal**: Integrate Portkey AI models and build core processing services

**Deliverables**:
- Portkey AI client wrapper
- Moderation service
- Embedding service with caching
- Model routing logic
- Batch processing coordinator

**Key Tasks**:
1. Create Portkey AI client wrapper with retry logic
2. Implement moderation service (text-moderation-latest)
3. Implement embedding service (text-embedding-3-small/large)
4. Add Redis caching for embeddings
5. Create model router for code-heavy prompts (Claude)
6. Implement batch processing coordinator (50-200 items)
7. Add error handling and retry policies

### Phase 3: Clustering & Similarity (Week 3)

**Goal**: Implement semantic clustering and similarity search

**Deliverables**:
- Vector similarity search service
- Clustering algorithm with confidence scoring
- Cluster assignment service
- Explainable grouping logic

**Key Tasks**:
1. Implement vector similarity search using Qdrant
2. Create clustering service with configurable thresholds
3. Implement confidence scoring for cluster assignments
4. Add reasoning generation for clustering decisions
5. Create cluster assignment service
6. Add similarity score caching in Redis
7. Implement incremental clustering (no full reprocessing)

### Phase 4: Canonicalization Engine (Week 4)

**Goal**: Extract canonical templates with variable slots

**Deliverables**:
- Template extraction service (GPT-4o)
- Variable slot detection
- Code-heavy prompt handler (Claude)
- Template versioning system

**Key Tasks**:
1. Implement diff-based template extraction using GPT-4o
2. Create variable slot detection with type inference
3. Add Claude Sonnet integration for code-heavy prompts
4. Implement template normalization and deduplication
5. Create template versioning system
6. Store templates in PostgreSQL with version history
7. Add JSON schema validation for template outputs

### Phase 5: Evolution Tracking & Reasoning (Week 5)

**Goal**: Track prompt family evolution and handle edge cases

**Deliverables**:
- Evolution tracking service
- Drift detection using o1-mini
- Family relationship mapping
- Edge case handling service

**Key Tasks**:
1. Implement evolution tracking for template changes
2. Create drift detection service using o1-mini
3. Implement family split/merge decision logic
4. Create relationship mapping between prompt families
5. Add edge case classification service
6. Store evolution history in PostgreSQL
7. Create evolution analysis endpoints

### Phase 6: API & Integration (Week 6)

**Goal**: Build RESTful API and integrate all services

**Deliverables**:
- Complete REST API with all endpoints
- Authentication and rate limiting
- Request validation and error handling
- API documentation (OpenAPI/Swagger)

**Key Tasks**:
1. Create prompt ingestion endpoint (POST /api/v1/prompts)
2. Create cluster query endpoints (GET /api/v1/clusters)
3. Create template endpoints (GET /api/v1/templates)
4. Create evolution tracking endpoints
5. Implement API authentication (API Key)
6. Add rate limiting middleware
7. Create OpenAPI documentation
8. Add request/response validation with Pydantic

### Phase 7: Observability & Production Readiness (Week 7)

**Goal**: Add logging, metrics, monitoring, and production configurations

**Deliverables**:
- Structured logging (JSON)
- Prometheus metrics
- CloudWatch integration
- Production Dockerfiles
- AWS deployment configurations

**Key Tasks**:
1. Implement structured JSON logging
2. Add request ID and correlation ID tracking
3. Create Prometheus metrics endpoint
4. Add CloudWatch logging integration
5. Create production Dockerfile
6. Add AWS ECS task definition
7. Create deployment scripts
8. Add health check and readiness probes

### Phase 8: Testing & Optimization (Week 8)

**Goal**: Comprehensive testing and performance optimization

**Deliverables**:
- Unit tests for all services
- Integration tests for pipeline
- Performance benchmarks
- Cost optimization analysis

**Key Tasks**:
1. Write unit tests for all core services
2. Create integration tests for full pipeline
3. Add performance benchmarks
4. Optimize batch sizes and concurrency
5. Analyze and optimize token usage costs
6. Load testing and scaling validation
7. Documentation updates

---

## File Structure

```
Backend/
├── src/
│   ├── __init__.py
│   ├── main.py                          # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── prompts.py              # Prompt ingestion endpoints
│   │   │   ├── clusters.py             # Cluster query endpoints
│   │   │   ├── templates.py            # Template endpoints
│   │   │   └── evolution.py             # Evolution tracking endpoints
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  # Authentication middleware
│   │   │   ├── rate_limit.py            # Rate limiting middleware
│   │   │   └── logging.py               # Request logging middleware
│   │   └── dependencies.py             # API dependencies
│   ├── services/
│   │   ├── __init__.py
│   │   ├── moderation.py                # Content moderation service
│   │   ├── embedding.py                 # Embedding generation service
│   │   ├── clustering.py                # Clustering service
│   │   ├── canonicalization.py          # Template extraction service
│   │   ├── evolution.py                 # Evolution tracking service
│   │   └── reasoning.py                 # Edge case reasoning service
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py                  # SQLAlchemy models
│   │   ├── schemas.py                   # Pydantic schemas
│   │   └── vector.py                    # Vector DB models
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── portkey.py                   # Portkey AI client wrapper
│   │   ├── postgres.py                  # PostgreSQL client
│   │   ├── redis.py                     # Redis client
│   │   └── qdrant.py                    # Qdrant client
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                  # Configuration loader
│   │   └── models.py                    # Config Pydantic models
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── batch_processor.py          # Batch processing utilities
│   │   ├── retry.py                     # Retry logic utilities
│   │   └── validators.py               # Input validation utilities
│   └── workers/
│       ├── __init__.py
│       └── ingestion.py                 # Async ingestion workers
├── config/
│   ├── config.example.yaml              # Configuration template (committed)
│   └── config.yaml                      # Actual config (gitignored)
├── migrations/
│   └── alembic/                          # Database migrations
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_services.py
│   │   ├── test_clients.py
│   │   └── test_utils.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   └── fixtures/
│       └── sample_prompts.py
├── docker/
│   ├── Dockerfile                        # Production Dockerfile
│   ├── Dockerfile.dev                    # Development Dockerfile
│   └── docker-compose.yml               # Local development stack
├── scripts/
│   ├── setup.sh                          # Setup script
│   ├── migrate.sh                        # Migration script
│   └── deploy.sh                         # Deployment script
├── requirements.txt                      # Python dependencies
├── requirements-dev.txt                 # Development dependencies
├── .env.example                          # Environment variables template
├── .gitignore
├── README.md
└── pyproject.toml                        # Python project configuration
```

---

## Dependencies

### Internal Dependencies

**None** - This is a greenfield project with no existing codebase dependencies.

### External Dependencies

#### Python Packages

**Core Framework**:
- `fastapi>=0.104.0` - Web framework
- `uvicorn[standard]>=0.24.0` - ASGI server
- `pydantic>=2.5.0` - Data validation
- `pydantic-settings>=2.1.0` - Settings management

**Database & Storage**:
- `sqlalchemy[asyncio]>=2.0.23` - PostgreSQL ORM
- `alembic>=1.12.0` - Database migrations
- `asyncpg>=0.29.0` - PostgreSQL async driver
- `aioredis>=2.0.1` - Redis async client
- `qdrant-client>=1.7.0` - Qdrant vector DB client

**AI/ML**:
- `portkey-ai>=0.1.0` - Portkey AI SDK
- `openai>=1.3.0` - OpenAI SDK (via Portkey)

**Configuration & Utilities**:
- `pyyaml>=6.0.1` - YAML config parsing
- `python-dotenv>=1.0.0` - Environment variable management
- `tenacity>=8.2.3` - Retry logic

**Observability**:
- `structlog>=23.2.0` - Structured logging
- `prometheus-client>=0.19.0` - Metrics
- `boto3>=1.29.0` - AWS SDK (CloudWatch)

**Testing**:
- `pytest>=7.4.3` - Testing framework
- `pytest-asyncio>=0.21.1` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `httpx>=0.25.2` - HTTP client for testing

**Development**:
- `black>=23.11.0` - Code formatting
- `ruff>=0.1.6` - Linting
- `mypy>=1.7.0` - Type checking

#### Infrastructure Services

**Database**:
- PostgreSQL 15+ (RDS or managed)
- Redis 7+ (ElastiCache or managed)
- Qdrant (self-hosted or cloud)

**Cloud Services (AWS)**:
- ECR: Docker image registry
- ECS/EKS: Container orchestration
- RDS: PostgreSQL database
- ElastiCache: Redis cache
- S3: Artifacts and backups
- CloudWatch: Logging and metrics
- Secrets Manager: Credential management

**Third-Party APIs**:
- Portkey AI API (for model access)

---

## External Dependencies Section

### Flagsmith Feature Flags

**None required** - No feature flags needed for initial implementation.

### Consul Keys

**None required** - Configuration managed via config file and AWS Secrets Manager.

### Environment Variables

**Required Environment Variables** (to be set in AWS ECS/EKS task definitions or Secrets Manager):

**Portkey AI**:
- `PORTKEY_API_KEY` - Portkey AI API key

**Database**:
- `DB_HOST` - PostgreSQL host
- `DB_NAME` - PostgreSQL database name
- `DB_USER` - PostgreSQL username
- `DB_PASSWORD` - PostgreSQL password (from Secrets Manager)

**Redis**:
- `REDIS_HOST` - Redis host
- `REDIS_PASSWORD` - Redis password (from Secrets Manager, optional)

**Vector DB**:
- `QDRANT_HOST` - Qdrant host
- `QDRANT_API_KEY` - Qdrant API key (if using cloud)

**AWS**:
- `AWS_REGION` - AWS region (default: us-east-2)
- `AWS_ACCESS_KEY_ID` - AWS access key ID (stored in Secrets Manager)
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key (stored in Secrets Manager)
- `S3_BUCKET_NAME` - S3 bucket for artifacts
- `AWS_SECRETS_MANAGER_SECRET_NAME` - Secret name in Secrets Manager
- **Note**: AWS credentials (Access Key ID: `AKIAWH7F4BUOKM2W2SFO`) must be configured in AWS Secrets Manager or IAM roles. Never hardcode in environment variables or config files.

**Application**:
- `ENV` - Environment (dev, staging, prod)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `API_KEY` - API key for authentication (from Secrets Manager)

### Third-Party Service Configurations

**Portkey AI**:
- API endpoint: `https://api.portkey.ai`
- Models configured via Portkey dashboard
- API key stored in AWS Secrets Manager

**Qdrant**:
- Local development: Docker container
- Production: Qdrant Cloud or self-hosted instance
- Collection name: `prompt_embeddings`
- Vector size: 1536 (text-embedding-3-small)

**AWS Services**:
- ECR repository: `429441944860.dkr.ecr.us-east-2.amazonaws.com/portkeyaibuilderchallenge`
- Region: `us-east-2`
- Secrets Manager secret: `portkey-prompt-parser/secrets`
- **AWS Credentials**: 
  - Access Key ID: `AKIAWH7F4BUOKM2W2SFO`
  - Secret Access Key: Provided separately (stored in AWS Secrets Manager, not in code/config files)
  - **Security Note**: AWS credentials must be stored securely in AWS Secrets Manager or IAM roles. Never commit credentials to repository.

### Database Migrations

**Initial Migration** (`001_initial_schema.py`):

**Tables to Create**:
1. `prompts` - Raw prompt data
   - id (UUID, primary key)
   - content (TEXT)
   - embedding_id (UUID, foreign key to vector DB)
   - moderation_status (VARCHAR)
   - created_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

2. `clusters` - Prompt clusters
   - id (UUID, primary key)
   - name (VARCHAR)
   - centroid_embedding_id (UUID)
   - similarity_threshold (FLOAT)
   - confidence_score (FLOAT)
   - created_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

3. `cluster_assignments` - Prompt to cluster mappings
   - id (UUID, primary key)
   - prompt_id (UUID, foreign key)
   - cluster_id (UUID, foreign key)
   - similarity_score (FLOAT)
   - confidence_score (FLOAT)
   - reasoning (TEXT)
   - created_at (TIMESTAMP)

4. `canonical_templates` - Canonical templates
   - id (UUID, primary key)
   - cluster_id (UUID, foreign key)
   - template_content (TEXT)
   - version (VARCHAR)
   - slots (JSONB)
   - confidence_score (FLOAT)
   - created_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

5. `template_slots` - Variable slots in templates
   - id (UUID, primary key)
   - template_id (UUID, foreign key)
   - slot_name (VARCHAR)
   - slot_type (VARCHAR)
   - example_values (JSONB)
   - confidence_score (FLOAT)
   - created_at (TIMESTAMP)

6. `evolution_events` - Template evolution tracking
   - id (UUID, primary key)
   - template_id (UUID, foreign key)
   - event_type (VARCHAR) - CREATED, UPDATED, SLOT_ADDED, SLOT_REMOVED, DRIFT_DETECTED
   - previous_version (VARCHAR)
   - new_version (VARCHAR)
   - change_reason (TEXT)
   - detected_by (VARCHAR) - MODEL_NAME
   - created_at (TIMESTAMP)

7. `prompt_families` - Prompt family relationships
   - id (UUID, primary key)
   - parent_family_id (UUID, foreign key, nullable)
   - name (VARCHAR)
   - description (TEXT)
   - created_at (TIMESTAMP)

8. `family_cluster_mappings` - Family to cluster relationships
   - id (UUID, primary key)
   - family_id (UUID, foreign key)
   - cluster_id (UUID, foreign key)
   - created_at (TIMESTAMP)

**Indexes**:
- Index on `prompts.created_at`
- Index on `cluster_assignments.prompt_id`
- Index on `cluster_assignments.cluster_id`
- Index on `canonical_templates.cluster_id`
- Index on `canonical_templates.version`
- Index on `evolution_events.template_id`
- Index on `evolution_events.created_at`
- GIN index on `canonical_templates.slots` (JSONB)
- GIN index on `template_slots.example_values` (JSONB)

### Cache Keys (Redis)

**Key Patterns**:
- `embedding:{prompt_hash}` - Cached embeddings (TTL: 7 days)
- `similarity:{prompt_id}:{cluster_id}` - Similarity scores (TTL: 1 day)
- `cluster:{cluster_id}:centroid` - Cluster centroid embedding (TTL: 1 day)
- `checkpoint:ingestion:{batch_id}` - Ingestion checkpoints (TTL: 24 hours)
- `rate_limit:{api_key}:{endpoint}` - Rate limiting counters (TTL: 1 minute)

### Other External Systems

**None** - No other external systems require configuration.

---

## Testing Strategy

### Unit Testing

**Coverage Target**: >80% for core services

**Test Areas**:
1. **Services**:
   - Moderation service (mock Portkey API)
   - Embedding service (mock Portkey API, test caching)
   - Clustering service (test similarity calculations)
   - Canonicalization service (mock GPT-4o, test template extraction)
   - Evolution service (test drift detection logic)

2. **Clients**:
   - Portkey client (mock HTTP responses)
   - PostgreSQL client (use test database)
   - Redis client (use fakeredis)
   - Qdrant client (mock Qdrant API)

3. **Utils**:
   - Batch processor (test chunking logic)
   - Retry logic (test exponential backoff)
   - Validators (test input validation)

### Integration Testing

**Test Scenarios**:
1. **Full Pipeline**:
   - Ingest prompt → moderation → embedding → clustering → canonicalization
   - Verify all steps complete successfully
   - Verify data stored correctly in all systems

2. **API Endpoints**:
   - Test all CRUD operations
   - Test authentication and rate limiting
   - Test error handling

3. **Database**:
   - Test migrations up and down
   - Test foreign key constraints
   - Test transaction rollbacks

### Performance Testing

**Benchmarks**:
- Single prompt ingestion: <500ms p95
- Batch ingestion (100 prompts): <30s p95
- Cluster query: <100ms p95
- Template extraction: <5s p95

**Load Testing**:
- 1000 concurrent requests
- Sustained load: 100 requests/second
- Burst load: 500 requests/second

### Test Data

**Fixtures**:
- Sample prompts (various types: text, code, multilingual)
- Pre-computed embeddings (for faster tests)
- Mock cluster assignments
- Sample canonical templates

---

## Risk Mitigation

### Technical Risks

1. **Model API Rate Limits**
   - Mitigation: Implement exponential backoff, batch processing, request queuing

2. **Vector DB Performance**
   - Mitigation: Use HNSW indexing, caching, batch queries

3. **Cost Overruns**
   - Mitigation: Token usage tracking, cost alerts, model selection optimization

4. **Data Consistency**
   - Mitigation: Transaction management, idempotent operations, checkpoint recovery

### Operational Risks

1. **Deployment Failures**
   - Mitigation: Blue-green deployments, health checks, rollback procedures

2. **Database Migrations**
   - Mitigation: Test migrations in staging, backup before migration, rollback scripts

3. **Secrets Management**
   - Mitigation: AWS Secrets Manager, rotation policies, audit logging

---

## Success Metrics

### Functional Metrics
- Clustering accuracy: >90%
- Template extraction success rate: >95%
- Evolution detection accuracy: >85%

### Performance Metrics
- API latency p95: <500ms
- Batch processing throughput: >100 prompts/second
- System uptime: >99.9%

### Cost Metrics
- Token usage per prompt: Tracked and optimized
- Infrastructure costs: Monitored via CloudWatch

---

## Next Steps After Plan Approval

1. Review and approve this plan
2. Create task breakdown (tasks.md)
3. Begin Phase 1 implementation
4. Set up development environment
5. Initialize project structure

