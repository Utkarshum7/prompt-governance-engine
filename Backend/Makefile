.PHONY: help setup install dev up down migrate run test clean lint format

# Variables
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn
ALEMBIC = $(VENV)/bin/alembic
DOCKER_COMPOSE = docker/docker-compose.yml

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)Smart Prompt Parser - Makefile Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup & Installation:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

setup: venv install ## Complete setup: create venv and install dependencies
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Copy config/config.example.yaml to config/config.yaml"
	@echo "  2. Update config/config.yaml with your settings"
	@echo "  3. Run 'make up' to start Docker services"
	@echo "  4. Run 'make migrate' to set up database"
	@echo "  5. Run 'make dev' to start the application"

venv: ## Create virtual environment
	@echo "$(YELLOW)Checking Python version...$(NC)"
	@PYTHON_CMD=$$(which python3.11 2>/dev/null || which python3.12 2>/dev/null || which python3.13 2>/dev/null || which python3); \
	if [ -z "$$PYTHON_CMD" ]; then \
		echo "$(RED)Error: Python 3.11+ not found. Please install Python 3.11 or higher.$(NC)"; \
		exit 1; \
	fi; \
	PYTHON_VERSION=$$($$PYTHON_CMD --version 2>&1); \
	echo "Using: $$PYTHON_VERSION"; \
	echo "$(YELLOW)Creating virtual environment...$(NC)"; \
	$$PYTHON_CMD -m venv $(VENV); \
	mkdir -p $(VENV)/pip; \
	cp pip.conf $(VENV)/pip/pip.conf 2>/dev/null || true; \
	echo "$(GREEN)✓ Virtual environment created$(NC)"

install: venv ## Install dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	@$(PIP) install --upgrade pip --index-url https://pypi.org/simple --trusted-host pypi.org
	@$(PIP) install -r requirements-dev.txt --index-url https://pypi.org/simple --trusted-host pypi.org --no-deps || $(PIP) install -r requirements-dev.txt --index-url https://pypi.org/simple --trusted-host pypi.org
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-prod: venv ## Install production dependencies only
	@echo "$(YELLOW)Installing production dependencies...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Production dependencies installed$(NC)"

up: ## Start Docker services (PostgreSQL, Redis, Qdrant)
	@echo "$(YELLOW)Starting Docker services...$(NC)"
	@cd docker && docker-compose up -d
	@echo "$(GREEN)✓ Docker services started$(NC)"
	@echo "$(YELLOW)Waiting for services to be ready...$(NC)"
	@sleep 5
	@echo "$(GREEN)✓ Services ready$(NC)"

down: ## Stop Docker services
	@echo "$(YELLOW)Stopping Docker services...$(NC)"
	@cd docker && docker-compose down
	@echo "$(GREEN)✓ Docker services stopped$(NC)"

logs: ## View Docker service logs
	@cd docker && docker-compose logs -f

migrate: ## Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	@cd migrations && ../$(ALEMBIC) upgrade head
	@echo "$(GREEN)✓ Migrations completed$(NC)"

migrate-create: ## Create a new migration (usage: make migrate-create MESSAGE="description")
	@if [ -z "$(MESSAGE)" ]; then \
		echo "$(RED)Error: MESSAGE is required$(NC)"; \
		echo "Usage: make migrate-create MESSAGE=\"your migration description\""; \
		exit 1; \
	fi
	@echo "$(YELLOW)Creating migration: $(MESSAGE)$(NC)"
	@cd migrations && ../$(ALEMBIC) revision --autogenerate -m "$(MESSAGE)"
	@echo "$(GREEN)✓ Migration created$(NC)"

run: ## Run the application (production mode)
	@echo "$(YELLOW)Starting application...$(NC)"
	@$(UVICORN) src.main:app --host 0.0.0.0 --port 8000

dev: ## Run the application in development mode (with auto-reload)
	@echo "$(YELLOW)Starting application in development mode...$(NC)"
	@echo "$(GREEN)Application will be available at: http://localhost:8000$(NC)"
	@echo "$(GREEN)API docs: http://localhost:8000/docs$(NC)"
	@$(UVICORN) src.main:app --host 0.0.0.0 --port 8000 --reload

start: up migrate ## Start Docker services and run migrations (then run 'make dev' to start app)

run-all: up migrate dev ## Start everything: Docker services, migrations, and app

test: ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	@$(VENV)/bin/pytest

test-cov: ## Run tests with coverage
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	@$(VENV)/bin/pytest --cov=src --cov-report=html --cov-report=term

lint: ## Run linters
	@echo "$(YELLOW)Running linters...$(NC)"
	@$(VENV)/bin/ruff check src/
	@$(VENV)/bin/mypy src/

format: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	@$(VENV)/bin/black src/
	@$(VENV)/bin/ruff check --fix src/

format-check: ## Check code formatting without making changes
	@echo "$(YELLOW)Checking code formatting...$(NC)"
	@$(VENV)/bin/black --check src/
	@$(VENV)/bin/ruff check src/

shell: ## Open Python shell with app context
	@echo "$(YELLOW)Opening Python shell...$(NC)"
	@$(PYTHON) -i -c "from src.config.settings import get_settings; settings = get_settings(); print('Settings loaded. Use: settings')"

db-shell: ## Open PostgreSQL shell
	@echo "$(YELLOW)Opening PostgreSQL shell...$(NC)"
	@cd docker && docker-compose exec postgres psql -U postgres -d portkey_prompt_parser

redis-cli: ## Open Redis CLI
	@echo "$(YELLOW)Opening Redis CLI...$(NC)"
	@cd docker && docker-compose exec redis redis-cli

qdrant-ui: ## Open Qdrant UI (if available)
	@echo "$(YELLOW)Qdrant UI available at: http://localhost:6333/dashboard$(NC)"

clean: ## Clean up generated files and caches
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup completed$(NC)"

clean-all: clean ## Clean everything including venv and Docker volumes
	@echo "$(YELLOW)Cleaning everything...$(NC)"
	@rm -rf $(VENV)
	@cd docker && docker-compose down -v
	@echo "$(GREEN)✓ Everything cleaned$(NC)"

check: ## Check if everything is set up correctly
	@echo "$(YELLOW)Checking setup...$(NC)"
	@echo ""
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(RED)✗ Virtual environment not found$(NC)"; \
		echo "  Run: make setup"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Virtual environment exists$(NC)"; \
	fi
	@if [ ! -f "config/config.yaml" ]; then \
		echo "$(YELLOW)⚠ Config file not found$(NC)"; \
		echo "  Run: cp config/config.example.yaml config/config.yaml"; \
	else \
		echo "$(GREEN)✓ Config file exists$(NC)"; \
	fi
	@cd docker && docker-compose ps | grep -q "Up" && echo "$(GREEN)✓ Docker services running$(NC)" || echo "$(YELLOW)⚠ Docker services not running$(NC) - Run: make up"
	@echo ""
	@echo "$(GREEN)Setup check complete!$(NC)"

init-db: up migrate ## Initialize database (start services and run migrations)
	@echo "$(GREEN)✓ Database initialized$(NC)"

# Quick start command - does everything
quickstart: setup init-db ## Quick start: setup, start services, migrate, and run app
	@if [ ! -f "config/config.yaml" ]; then \
		echo "$(YELLOW)Creating config file...$(NC)"; \
		cp config/config.example.yaml config/config.yaml; \
		echo "$(YELLOW)⚠ Please update config/config.yaml with your Portkey API key!$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)  Quick Start Complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "$(GREEN)Application will be available at:$(NC)"
	@echo "  - API: http://localhost:8000"
	@echo "  - Docs: http://localhost:8000/docs"
	@echo "  - Frontend: http://localhost:8000"
	@echo ""
	@echo "$(YELLOW)Run 'make dev' to start the application$(NC)"

