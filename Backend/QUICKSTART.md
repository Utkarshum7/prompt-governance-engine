# Quick Start Guide

Get the Smart Prompt Parser running locally in minutes!

## Prerequisites

- Python 3.11+ installed
- Docker and Docker Compose installed
- Portkey API key

## Option 1: Using Makefile (Recommended)

### One Command Setup

```bash
make quickstart
```

Then:
1. Copy `config/config.example.yaml` to `config/config.yaml`
2. Add your Portkey API key to `config/config.yaml`
3. Run `make dev`

### Step by Step

```bash
# 1. Setup (creates venv and installs dependencies)
make setup

# 2. Configure (copy and edit config)
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml and add your PORTKEY_API_KEY

# 3. Start Docker services
make up

# 4. Run migrations
make migrate

# 5. Start application
make dev
```

## Option 2: Using Startup Script

```bash
# Run the startup script
./scripts/start.sh
```

This will:
- Check/create virtual environment
- Start Docker services
- Run migrations
- Start the application

**Note**: You still need to configure `config/config.yaml` with your Portkey API key.

## Option 3: Manual Setup

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Configure
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml

# 4. Start Docker services
cd docker && docker-compose up -d && cd ..

# 5. Run migrations
alembic upgrade head

# 6. Start application
uvicorn src.main:app --reload
```

## Configuration

Minimum required configuration in `config/config.yaml`:

```yaml
portkey:
  api_key: "your-portkey-api-key-here"
```

For local development with Docker, database defaults are:
- PostgreSQL: `localhost:5432`, user: `postgres`, password: `postgres`, db: `portkey_prompt_parser`
- Redis: `localhost:6379`, no password
- Qdrant: `localhost:6333`, no API key needed

## Access the Application

Once running:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Frontend**: http://localhost:8000

## Common Commands

```bash
make help          # Show all available commands
make up            # Start Docker services
make down          # Stop Docker services
make migrate       # Run database migrations
make dev           # Start app in development mode
make test          # Run tests
make clean         # Clean generated files
```

## Troubleshooting

### Port already in use
Change the port in `config/config.yaml`:
```yaml
app:
  api:
    port: 8001  # Change to available port
```

### Docker services not starting
```bash
make down    # Stop services
make up      # Restart services
```

### Database connection errors
Make sure Docker services are running:
```bash
make up
# Wait a few seconds for services to be ready
make migrate
```

### Virtual environment issues
```bash
make clean-all  # Clean everything
make setup      # Re-setup
```

## Next Steps

1. **Test the API**: Visit http://localhost:8000/docs
2. **Ingest a prompt**: Use the frontend at http://localhost:8000/ingest-prompt
3. **View clusters**: http://localhost:8000/clusters
4. **View templates**: http://localhost:8000/templates

## Need Help?

Check the main [README.md](README.md) for detailed documentation.

