SHELL := /bin/bash

.PHONY: install dev-backend dev-frontend db test lint format build

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8001 --env-file ../.env

dev-frontend:
	cd frontend && pnpm dev

db:
	docker compose up -d db

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	cd frontend && pnpm lint && pnpm typecheck

format:
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && pnpm format

build:
	cd frontend && pnpm build
