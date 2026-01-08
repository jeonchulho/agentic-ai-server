.PHONY: help install dev test clean docker-up docker-down docker-logs format lint

help:
	@echo "Available commands:"
	@echo "  install      - Install dependencies"
	@echo "  dev          - Run development server"
	@echo "  test         - Run tests"
	@echo "  clean        - Clean temporary files"
	@echo "  docker-up    - Start all Docker services"
	@echo "  docker-down  - Stop all Docker services"
	@echo "  docker-logs  - View Docker logs"
	@echo "  format       - Format code with black"
	@echo "  lint         - Lint code with flake8"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f app

docker-dev-up:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

docker-dev-down:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml down

format:
	black app/ tests/

lint:
	flake8 app/ tests/ --max-line-length=120
