# Architecture

## Layers

- Bootstrap
- Runtime
- Services
- Applications
- Infrastructure

---

## Backend

FastAPI

---

## Database

SQLite

Future

PostgreSQL

ForgeOS currently uses additive, idempotent SQLite migrations in
`Backend/app/db/migrations.py`. Alembic is not configured in the prototype.

## Monitoring

Website and network checks run through a lightweight in-process FastAPI
lifespan scheduler. Checks execute outside request handlers, retain bounded
event history, and are limited to one application process.

Website monitoring accepts HTTP(S) only and rejects private, loopback,
link-local, multicast, unspecified, and reserved destinations by default.
Private-network monitoring requires an explicit target opt-in.

## Authentication and AI

ForgeOS uses local users with `ADMIN` and `VIEW` roles. Passwords use Python's
built-in scrypt implementation and API access uses short-lived HMAC-signed
bearer tokens. The frontend removes tokens on logout; server-side revocation
can be added when a persistent session store is introduced.

AI augmentation is isolated in `Backend/app/services/ai_agent.py`. It builds a
structured asset context and can delegate to an OpenRouter-compatible backend
without logging or persisting `OPENROUTER_API_KEY`. The default implementation
returns deterministic context until an application-provided backend is enabled.

---

## Core Components

- Bootstrap
- Logger
- Configuration
- Runtime
- Registry
- Event Bus
- Plugin Loader

---

## Goals

- Modular
- Replaceable
- Testable
- Observable
