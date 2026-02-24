# Smart Prompt Parser & Canonicalisation Engine - Backend

Production-grade AI system for clustering semantically equivalent prompts, extracting canonical templates with variable slots, and tracking prompt family evolution.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Make (optional, but recommended)

### One-Command Setup

```bash
make quickstart
```

This will:
1. Create virtual environment
2. Install all dependencies
3. Start Docker services (PostgreSQL, Redis, Qdrant)
4. Run database migrations
5. Set up configuration

**Note**: After running `make quickstart`, you still need to:
1. Copy `config/config.example.yaml` to `config/config.yaml`
2. Update `config/config.yaml` with your Portkey API key
3. Run `make dev` to start the application

### Step-by-Step Setup

#### 1. Initial Setup

```bash
# Create virtual environment and install dependencies
make setup

# Or manually:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

#### 2. Configure Application

```bash
# Copy config template
cp config/config.example.yaml config/config.yaml

# Edit config/config.yaml and add your Portkey API key
# At minimum, update: portkey.api_key
```

#### 3. Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, and Qdrant
make up

# Or manually:
cd docker && docker-compose up -d
```

#### 4. Initialize Database

```bash
# Run migrations
make migrate

# Or manually:
alembic upgrade head
```

#### 5. Start Application

```bash
# Development mode (with auto-reload)
make dev

# Or manually:
uvicorn src.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Frontend**: http://localhost:8000

## Makefile Commands

### Setup & Installation
- `make setup` - Complete setup (venv + dependencies)
- `make venv` - Create virtual environment
- `make install` - Install dependencies
- `make install-prod` - Install production dependencies only

### Docker Services
- `make up` - Start Docker services (PostgreSQL, Redis, Qdrant)
- `make down` - Stop Docker services
- `make logs` - View Docker service logs

### Database
- `make migrate` - Run database migrations
- `make migrate-create MESSAGE="description"` - Create new migration
- `make db-shell` - Open PostgreSQL shell

### Running Application
- `make dev` - Run in development mode (auto-reload)
- `make run` - Run in production mode
- `make start` - Start everything (services + migrations + app)
- `make quickstart` - Complete setup and start

### Development Tools
- `make test` - Run tests
- `make test-cov` - Run tests with coverage
- `make lint` - Run linters
- `make format` - Format code
- `make format-check` - Check code formatting
- `make shell` - Open Python shell with app context

### Utilities
- `make check` - Check if everything is set up correctly
- `make clean` - Clean generated files and caches
- `make clean-all` - Clean everything including venv
- `make redis-cli` - Open Redis CLI
- `make qdrant-ui` - Open Qdrant UI (http://localhost:6333/dashboard)

## Project Structure

```
Backend/
├── src/                    # Source code
│   ├── api/               # API endpoints
│   │   ├── v1/           # API v1 routes
│   │   └── middleware/   # Middleware (auth, rate limit, logging)
│   ├── clients/          # External client wrappers
│   ├── config/           # Configuration management
│   ├── models/           # Database models and schemas
│   ├── services/         # Business logic services
│   ├── utils/            # Utility functions
│   ├── workers/          # Async workers
│   └── templates/        # Jinja2 templates (frontend)
├── config/               # Configuration files
├── migrations/           # Database migrations
├── tests/                # Test files
├── docker/               # Docker configuration
├── scripts/              # Utility scripts
├── Makefile             # Development commands
└── requirements.txt     # Production dependencies
```

## Configuration

Configuration is managed through `config/config.yaml`. See `config/config.example.yaml` for all available options.

**Minimum required configuration:**
- `portkey.api_key` - Your Portkey API key

**For local development with Docker:**
- Database settings use defaults (localhost, postgres/postgres)
- Redis uses defaults (localhost, no password)
- Qdrant uses defaults (localhost, no API key)

## Environment Variables

You can override config values using environment variables. See `.env.example` for available variables.

## API Documentation

Once the application is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Health Checks

- Basic health: `GET /health`
- Readiness: `GET /health/ready` (checks database connectivity)
- Metrics: `GET /metrics` (Prometheus metrics)

## Development Workflow

1. **Start services**: `make up`
2. **Run migrations**: `make migrate`
3. **Start app**: `make dev`
4. **Make changes** - Auto-reload enabled
5. **Run tests**: `make test`
6. **Format code**: `make format`

## Troubleshooting

### Virtual environment issues
```bash
make clean-all  # Clean everything
make setup      # Re-setup
```

### Database connection issues
```bash
make down       # Stop services
make up         # Restart services
make migrate    # Re-run migrations
```

### Port already in use
```bash
# Check what's using the port
lsof -i :8000

# Or change port in config/config.yaml
```

## Production Deployment

See `docker/Dockerfile` and `docker/ecs-task-definition.json` for production deployment configuration.

Deploy to AWS ECS:
```bash
./scripts/deploy.sh [tag]
```

## License

MIT
