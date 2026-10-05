# Email Assistant Chat

A local, chat-based assistant that searches, triages, drafts, composes and organises your Gmail — acting on the mailbox only after you approve.

See [CLAUDE.md](CLAUDE.md) and [context/](context/) for the product, architecture and build specs.

## Prerequisites
Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22 LTS, pnpm 9+, Docker Desktop.

## Setup
```bash
cp .env.example .env
make db
make install
```

## Run
In two terminals:
```bash
make dev-backend   # http://localhost:8001
make dev-frontend  # http://localhost:5173
```
Open http://localhost:5173.

## Checks
```bash
make test
make lint
```
