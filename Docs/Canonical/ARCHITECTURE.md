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
New Warehouse and Reference Archive tables are created additively through the
existing SQLAlchemy `create_all` startup pattern; existing tables and data are not reset.

## Operations Modules

- Warehouse stock is changed only through an append-only receive, issue, or adjustment
  movement record. Administrative authorization is required for mutations.
- Reference documents are stored under private backend data storage with generated names.
  API authorization is required for metadata and file access; storage paths are never
  returned to clients.
- Asset PDF/XLSX exports accept repeated `asset_id` query parameters for server-validated
  selected exports. Missing selected identifiers fail the whole export.

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

## Enterprise Experience Boundary

The enterprise command-center information architecture, UX contracts, architecture
gaps, target telemetry envelopes, RBAC mapping, and AgentOS integration boundary are
defined in `Docs/Canonical/ENTERPRISE_REDESIGN.md`.

The current implementation remains one FastAPI application with a static Alpine.js
interface. The redesigned UI may expose target-state workspaces, but it must not claim
that AgentOS execution, multi-tenancy, topology discovery, streaming telemetry, or
high-fidelity audit services exist until their backend contracts are implemented.

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
