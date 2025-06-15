.PHONY: install test lint format clean build up down restart logs db-shell api-shell worker-shell frontend-shell

# Install dependencies
install:
	poetry install
	cd frontend && npm install

# Run tests
test:
	poetry run pytest tests/

# Lint code
lint:
	poetry run ruff check .
	poetry run black --check .
	cd frontend && npm run lint

# Format code
format:
	poetry run ruff check --fix .
	poetry run black .
	cd frontend && npm run format

# Clean up
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache/ .coverage htmlcov/
	find . -name '*.pyc' -exec rm -f {} \;
	find . -name '*.pyo' -exec rm -f {} \;
	find . -name '*~' -exec rm -f {} \;
	find . -name '__pycache__' -exec rm -rf {} \;

# Build containers
build:
	docker compose build

# Start services
up:
	docker compose up -d

# Stop services
down:
	docker compose down

# Restart services
restart:
	docker compose restart

# View logs
logs:
	docker compose logs -f

# Database shell
db-shell:
	docker compose exec postgres psql -U postgres -d evals

# API shell
api-shell:
	docker compose exec api bash

# Worker shell
worker-shell:
	docker compose exec worker bash

# Frontend shell
frontend-shell:
	docker compose exec frontend sh

# Run migrations
migrate:
	docker compose exec api alembic upgrade head

# Create new migration
migration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"
