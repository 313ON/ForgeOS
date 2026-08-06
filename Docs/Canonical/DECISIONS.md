# Architecture Decisions

## DEC-0001

Database

SQLite

Reason

Fast prototyping.

---

## DEC-0002

ORM

SQLAlchemy

Reason

Future PostgreSQL migration.

---

## DEC-0003

Framework

FastAPI

Reason

Performance and OpenAPI support.

---

## DEC-0004

Architecture

AI First

Reason

Every module must be AI-compatible.

---

## DEC-0005

Design

Prototype First

Reason

Ship early, improve continuously.

---

## DEC-0006

Migration Strategy

Additive SQLite migrations

Reason

The current prototype has no Alembic environment. Migrations must preserve
existing populated databases and remain replaceable for a future PostgreSQL
deployment. SQLite table reconstruction for new constraints is intentionally
deferred.

---

## DEC-0007

Monitoring Execution

In-process FastAPI lifespan scheduler

Reason

Provides operational checks without introducing Celery, Redis, or another
large infrastructure dependency. Production deployments should use one
process or an external scheduler before horizontal scaling.

---

## DEC-0008

Monitoring SSRF Policy

Private destinations denied by default

Reason

Website targets are user-configurable and could otherwise reach internal
services. Enterprise internal monitoring requires explicit per-target opt-in.

---

## DEC-0009

Authentication and AI integration

Local scrypt password hashes and signed bearer tokens provide a dependency-light
prototype auth boundary. OpenRouter is a future-compatible HTTP provider
abstraction, while credentials remain environment-only and the AI service is
mockable without network calls.

---

## DEC-0010

Enterprise command-center experience

ForgeOS uses a dark, high-density command-center information architecture while
preserving the current FastAPI and Alpine.js implementation boundary.

Reason

The redesign must improve operational clarity without introducing an unrelated frontend
framework migration. Detailed component decisions and trade-offs are recorded as
ADR-E01 through ADR-E08 in `ENTERPRISE_REDESIGN.md`.

---

## DEC-0011

Knowledge and execution separation

ForgeOS owns durable operational knowledge and context. AgentOS owns agent runs, tools,
approvals, cancellation, token usage, and cost accounting.

Reason

Execution records must not be invented inside ForgeOS without an accepted integration
contract. The UI exposes missing runtime interfaces as architecture gaps.

---

## DEC-0012

Telemetry evolution

The prototype uses bounded 15-second polling only while operational monitoring views are
active. Resumable Server-Sent Events are the preferred next telemetry transport.

Reason

Polling is compatible with the current single-process backend. SSE provides a simpler
future one-way event model than WebSockets, but requires sequence, replay, authentication,
and snapshot recovery contracts before implementation.
