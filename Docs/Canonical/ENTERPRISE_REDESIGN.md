# ForgeOS Enterprise Redesign

**Status:** Canonical target-state specification  
**Date:** August 6, 2026  
**Scope:** ForgeOS enterprise information architecture, user experience, and supporting API contracts  
**Design source:** UI/UX Pro Max v2.0, constrained by ForgeOS canonical architecture and
The-Dome separation rules

This document defines the ForgeOS transition to a dark enterprise, AI-minimal,
network-operations platform. It distinguishes:

- **Existing Fact:** verified in the repository or host diagnostics.
- **Assumption:** an inference that requires validation.
- **Architecture Gap:** a required capability for which no current interface exists.
- **Implemented:** delivered in the current redesign.
- **Target State:** specified but intentionally not invented in code.

The redesign does not collapse the Knowledge Layer into the Execution Layer. ForgeOS
inventory, people, reports, monitoring definitions, and diagnostic snapshots remain
knowledge and operational context. A future AgentOS runtime remains a separate execution
bounded context accessed through explicit contracts.

## 1. SYSTEM DIAGNOSTICS & AUDIT

### Existing Facts

#### Application stack

- ForgeOS is a Python 3.12 local-first application using FastAPI, SQLAlchemy, Pydantic,
  and SQLite.
- The application serves one Alpine.js single-page interface from
  `Backend/app/static/index.html`.
- Tailwind CSS and Alpine.js are currently loaded from public CDNs. There is no compiled
  frontend bundle, frontend lockfile, or local static dependency pipeline.
- FastAPI starts an in-process monitoring scheduler during application lifespan.
- The documented deployment constraint is one application process while the scheduler is
  enabled.
- SQLite migrations are additive and idempotent. Alembic is not configured.
- Authentication uses local users, scrypt password hashes, and short-lived HMAC-signed
  bearer tokens.
- Implemented roles are exactly `ADMIN` and `VIEW`.
- Backend dependencies enforce mutations with `require_admin`; authenticated reads use
  `get_current_user`.
- Monitoring supports website and network targets, latest status, latency, bounded event
  history, and explicit private-network opt-in for website checks.
- AI integration is asset-scoped through
  `GET /api/v1/assets/{asset_id}/ai_insights`. Without an application-provided backend it
  returns deterministic structured context.
- Export history records successful Excel and PDF exports with a user identifier and
  username.
- `.kilo/package.json` contains `@kilocode/plugin` version `7.4.17`. This is repository
  tooling configuration, not evidence that the ForgeOS application runtime is Node.js.
- The available toolchain reports Node.js `v24.18.1`, npm `11.16.0`, Python `3.12.3`, and
  Git `2.43.0`.

#### Host and display facts

Native Windows diagnostics collected on August 6, 2026 report:

- Windows 10 Enterprise LTSC, build `19044`, on an ASUS X550ZE.
- AMD A10-7400P, four logical CPUs, approximately 2.5 GHz.
- 16 GB installed RAM.
- AMD Radeon R6 graphics, DirectX 12, WDDM 2.0.
- Internal 1366 × 768 display at 60 Hz.
- Multiple physical, Hyper-V, VPN, and WSL network adapters.

The WSL 2 development environment reports:

- Four logical CPUs.
- 7.2 GB WSL-visible RAM.
- The ForgeOS hardware profiler selects the conservative `minimal` profile with one
  worker, no parallel builds, and indexing disabled.

Native Windows capacity is authoritative for Windows deployment planning. WSL-visible
capacity is authoritative for current Linux-side development and validation. The low
1366 × 768 viewport and older integrated GPU justify:

- Minimal blur and shadow use.
- SVG topology only for small graphs.
- No continuous ambient animation.
- Dense layouts that remain usable at 768 vertical pixels.
- A Canvas topology threshold above 100 nodes and clustering before 500 nodes.

#### Implemented redesign facts

- The application shell uses Deep Carbon, Obsidian, Muted Slate, Steel Grey, Electric
  Cyan, and Signal Green semantic tokens.
- Fabricated uptime, request-count, and node-load values were removed.
- The Global Telemetry Console derives metrics from current assets, assignments,
  monitored targets, latencies, and warnings.
- A keyboard-accessible command palette opens with `Ctrl+K`.
- The asset register supports search, multi-column sorting, row selection, select-all,
  and safe client-side JSON export.
- The topology viewport uses monitored endpoints and a local ForgeOS control node, with
  the existing target table as the accessible alternative.
- The Agent Execution workspace exposes only the implemented asset-insight context and
  disables unimplemented runtime controls.
- The Security & Governance workspace shows permission mapping, operator state where
  authorized, export evidence, and explicit security gaps.
- The Warehouse API provides searchable stock records, low-stock state, linked assets,
  and an auditable movement ledger with backend-authoritative administrator mutations.
- The Reference Archive API provides validated private uploads, searchable metadata,
  safe downloads, and explicit preview capability without exposing storage paths.
- Asset selection now drives server-validated PDF and XLSX exports instead of a
  client-generated JSON-only artifact.

### Assumptions

- ForgeOS will remain a local or single-site control plane during the prototype phase.
- A future The-Dome deployment may expose ForgeOS knowledge to AgentOS through a
  versioned gateway, not through direct database access.
- Multi-organization support will require a tenant or organization identifier on every
  mutable domain record and every authorization decision.
- Real-time topology consumers will require resumable events, ordering guarantees, and
  snapshot recovery rather than unstructured WebSocket messages.
- PostgreSQL is the likely persistence target before horizontal application scaling.
- A compiled and self-hosted frontend asset pipeline will be required before isolated,
  air-gapped, or strict Content Security Policy deployment.

### Architectural Gaps

#### Runtime and data contracts

- Canonical metadata conflicts on migrations: `FORGE_CANON.md` lists Alembic in the
  current stack, while `ARCHITECTURE.md` states that Alembic is not configured. This
  redesign makes no migration-strategy change; the canonical sources require a separate
  clarification.
- No AgentOS service interface, task queue, run state, tool-call state, cancellation
  contract, approval contract, or idempotency-key policy exists.
- No token usage, model attribution, price book, budget, or cost-allocation contract
  exists.
- No node-to-node discovery, edge model, dependency map, route model, or topology
  ownership contract exists. Current monitoring is endpoint reachability only.
- No WebSocket or Server-Sent Events endpoint exists. The current UI polls monitoring
  state every 15 seconds while the NOC or topology workspace is active.
- No multi-tenant organization model or request context exists.
- No high-fidelity audit-event model exists. Export history is not a general audit log.
- No server-side session revocation store exists.
- No optimistic-concurrency version, entity tag, or idempotency key is enforced on
  mutations.

#### Synchronization and reliability

- The dashboard summary and target list are separate requests and do not share a
  consistent snapshot version.
- Monitoring events have timestamps but no stream sequence, correlation identifier, or
  causation identifier.
- A multi-process FastAPI deployment would duplicate the in-process scheduler.
- Client polling can observe intermediate states across separate API calls.
- The frontend has no offline state cache or reconnect replay.

#### UX and platform

- Multi-tenant navigation is represented as a disabled local workspace selector because
  tenant switching is not implemented.
- The topology graph can visualize reachability but cannot claim physical or logical
  node-to-node communication.
- Natural-language command routing is local navigation intent matching, not AgentOS
  command execution.
- Public CDN dependencies conflict with offline-first and strict enterprise CSP goals.
- The current single-file SPA concentrates presentation and state logic. Component
  extraction is justified only when a compiled frontend pipeline is adopted; gratuitous
  framework migration is not justified now.

## 2. ENTERPRISE DATA & INFORMATION ARCHITECTURE (IA)

The workspace hierarchy is strict and maps to bounded contexts.

```text
ForgeOS
├── Global Telemetry Console
│   ├── Operational health
│   ├── Monitored target counts
│   ├── Average observed latency
│   ├── Managed asset counts
│   ├── Open operational exceptions
│   ├── Latest probe events
│   └── Architecture capability status
│
├── Agent Execution Plane
│   ├── AI context workspace                     [Implemented: asset context only]
│   ├── Human validation gate                    [Implemented: UX control state]
│   ├── Agent run queue                          [Architecture Gap]
│   ├── Task lifecycle and cancellation          [Architecture Gap]
│   ├── Tool-call evidence                       [Architecture Gap]
│   ├── Token and model usage                    [Architecture Gap]
│   └── Cost allocation and budgets              [Architecture Gap]
│
├── Network / Topology Engine
│   ├── Reachability map                         [Implemented]
│   ├── Target status and latency                [Implemented]
│   ├── Probe history                            [Implemented]
│   ├── Accessible topology table                [Implemented]
│   ├── Node-to-node edges                       [Architecture Gap]
│   ├── Dependency paths                         [Architecture Gap]
│   └── Streaming topology events                [Architecture Gap]
│
├── Knowledge Workspace
│   ├── Asset registry
│   ├── People and custodians
│   ├── Assignments
│   ├── System diagnostic intake
│   ├── System snapshots
│   └── Reports and exports
│
└── Security & Governance Workspace
    ├── Session identity
    ├── ADMIN / VIEW permission map
    ├── Operator management                      [ADMIN]
    ├── Export evidence                          [Partial audit evidence]
    ├── High-fidelity audit log                  [Architecture Gap]
    ├── Policy decision records                  [Architecture Gap]
    ├── Tenant isolation                         [Architecture Gap]
    └── Session revocation                       [Architecture Gap]
```

### Layer alignment

| Layer | ForgeOS responsibility | Boundary rule |
|---|---|---|
| Knowledge Layer | Assets, people, assignments, diagnostics, reports, monitoring definitions | Owns durable operational context |
| Execution Layer | Agent runs, tools, approvals, cancellation, token/cost accounting | Owned by AgentOS; not stored as invented ForgeOS records |
| Integration Boundary | Versioned commands, events, and read models | No direct cross-layer database access |
| Presentation Layer | NOC, topology, context review, governance state | Renders capability status and permissions without bypassing backend policy |

## 3. COMPONENT SYSTEM SPECIFICATION (FRONTEND)

### Design foundation

#### Color system: 60–30–10

- 60% Deep Carbon / Obsidian: `#0D0E11`, `#13151A`.
- 30% Muted Slate / Steel Grey: `#232730`, `#2E3440`, border `#3B4252`.
- 10% Electric Cyan `#00E5FF` for focus and primary interaction; Signal Green
  `#00E676` for healthy state.
- Amber and rose are reserved for warning and destructive states.
- State never relies on color alone; every status includes text, shape, or icon.

#### Typography

- Inter for navigation, labels, controls, and explanatory text.
- JetBrains Mono for telemetry, identifiers, timestamps, status codes, latency, and
  command scope.
- Vazirmatn remains in the fallback chain for Persian localization.
- Tabular numeric features are enabled to prevent telemetry layout shift.

#### Motion and effects

- Interaction transitions: 80–150 ms.
- No bounce, spring, scroll reveal, parallax, or ambient blob animation.
- Status glow is limited to small state indicators.
- One-pixel structural borders define hierarchy.
- `prefers-reduced-motion` collapses transition and animation duration.
- Focus uses a two-pixel Electric Cyan ring with offset.

### App Shell & Collapsible Multi-tenant Navigation

#### Styling

- Fixed 248-pixel desktop rail; 72-pixel collapsed rail.
- Carbon background, Steel Grey separators, compact 40-pixel navigation rows.
- The current workspace is shown as `Local Workspace / Single Tenant / Local Node`.
- The workspace selector is disabled and explains the tenant-context gap.

#### Behavior

- Collapse state persists in local storage.
- Navigation labels disappear in collapsed mode; every icon retains a semantic tooltip.
- Mobile uses a horizontal destination strip rather than a competing second navigation
  hierarchy.
- Route changes update the URL hash and move focus to the main workspace.
- A skip link bypasses navigation.

#### States

- Active: cyan border, cyan text, low-opacity cyan surface.
- Hover: structural surface and visible border.
- Focus: explicit cyan ring.
- Unavailable: disabled semantics plus explanatory title.
- Role restricted: hidden for convenience only when the backend already enforces the
  same dependency.

#### Trade-off

The UI presents a multi-tenant-ready shell without pretending a tenant contract exists.
This prevents future IA churn but leaves tenant switching disabled.

### Interactive Network Topology Viewports

#### Rendering policy

- Up to 100 nodes: SVG for crisp labels and accessible focus targets.
- 101–500 nodes: Canvas with clustering and level of detail.
- More than 500 nodes: server-side aggregation is mandatory before rendering.
- The current implementation renders at most 12 monitored endpoints around the ForgeOS
  control node.

#### Behavior

- Keyboard and pointer activation select a target and load its history.
- Edge lines are directional-neutral because the current model represents reachability,
  not traffic flow.
- Latency is always visible as text.
- PASS, WARNING, FAILED, and UNKNOWN use text and distinct state markers.
- The high-density target table is the required accessible fallback.

#### Architecture limitation

The viewport must be labeled “Reachability Map” or “Monitoring Topology” until an edge
contract exists. It must not be labeled a discovered network graph.

### High-Density Data Tables

#### Styling

- Compact 48–56 pixel data rows.
- Monospace identifiers and serial values.
- Sticky or visually separated headers when datasets grow.
- Horizontal scrolling is allowed inside the table shell, never at the page level.

#### Behavior

- Search filters the current client read model.
- Column headers use `aria-sort`.
- A normal click replaces the current sort.
- `Shift+click` adds or changes a secondary sort.
- Row selection exposes a bulk-action drawer.
- Current safe bulk action is client-side JSON export.

#### Target-state bulk mutations

Bulk mutations require:

- A dedicated backend command.
- An idempotency key.
- Per-item result status.
- Authorization evaluated for every item.
- A preview or dry-run mode for destructive actions.
- One audit event for the command plus child outcome events.

### Command Palette (`Ctrl+K`)

#### Current behavior

- Matches natural-language-like terms against a local command registry.
- Routes to the Global Console, topology, AI context, assets, governance, intake, or
  refresh.
- Exposes administrator-only commands only to administrators.
- Enter executes the first match; Escape closes the palette.

#### Target-state behavior

Natural-language system control requires an AgentOS command endpoint that returns a
proposed plan before execution. The palette must not directly execute privileged tools.

Required flow:

```text
operator intent
  -> parse/propose
  -> policy evaluation
  -> human validation
  -> idempotent execution command
  -> streamed run events
  -> terminal outcome + audit evidence
```

### Context-Aware AI Workspace Panels

#### Current behavior

- Selects a real asset.
- Calls the implemented asset-insight endpoint.
- Displays the summary, warnings, and structured context envelope.
- Shows a human validation gate.
- Keeps run, cancel, token, cost, and idempotency controls disabled.

#### Target-state validation triggers

Human validation is mandatory when:

- A command mutates infrastructure or durable knowledge.
- A tool crosses a trust boundary.
- The estimated cost exceeds a configured budget.
- The model confidence is below policy threshold.
- The requested action affects more than one tenant or bounded context.
- The action has no verified rollback strategy.

## 4. BACKEND INTEGRATION & CONTRACT ALIGNMENT

This section specifies required contracts. It does not assert that they exist.

### Real-time Telemetry

#### Recommended transport

Use Server-Sent Events first for one-way operational telemetry:

- Simpler proxy and reconnect behavior than WebSockets.
- Native ordered event stream with `Last-Event-ID`.
- Appropriate for topology, target health, and agent-run observation.

Use WebSockets only when interactive low-latency bidirectional control is required, such
as terminal sessions or collaborative topology editing.

#### Proposed endpoint

```text
GET /api/v1/telemetry/stream?scope=monitoring,agents,governance
Accept: text/event-stream
Authorization: Bearer <token>
Last-Event-ID: <sequence>
```

Do not place long-lived bearer tokens in query parameters. If `EventSource` is retained,
move authentication to secure same-site cookies or issue a short-lived, single-purpose
stream ticket.

#### Event envelope

```json
{
  "event_id": "01J4Z4ZQ8G8M6P5YF0R7N9W2VB",
  "sequence": 18422,
  "event_type": "monitoring.target.updated",
  "occurred_at": "2026-08-06T20:31:44.381Z",
  "tenant_id": null,
  "source": "forgeos.monitoring",
  "correlation_id": "01J4Z4ZJ3W4M7E4V9YPMN2C89A",
  "causation_id": "01J4Z4ZJ2G0B2KMCZP0DSY7X34",
  "schema_version": 1,
  "payload": {}
}
```

#### Monitoring target update payload

```json
{
  "target": {
    "id": 42,
    "name": "Primary Gateway",
    "target_type": "network",
    "status": "WARNING",
    "latency_ms": 148.2,
    "last_checked_at": "2026-08-06T20:31:44.200Z",
    "message": "Latency exceeded 120 ms threshold"
  },
  "changed_fields": ["status", "latency_ms", "last_checked_at", "message"]
}
```

#### Topology snapshot payload

```json
{
  "snapshot_id": "topology-2026-08-06T20:31:44Z",
  "generated_at": "2026-08-06T20:31:44.381Z",
  "nodes": [
    {
      "node_id": "target:42",
      "kind": "monitored_target",
      "label": "Primary Gateway",
      "status": "WARNING"
    }
  ],
  "edges": [
    {
      "edge_id": "reachability:forgeos:target:42",
      "source_node_id": "forgeos:local",
      "target_node_id": "target:42",
      "kind": "probe_reachability",
      "latency_ms": 148.2,
      "state": "degraded"
    }
  ]
}
```

Clients must:

- Apply events in sequence order.
- Ignore duplicate event identifiers.
- Request a new snapshot when a sequence gap is detected.
- Keep a bounded 60–300 second chart buffer.
- Pause visual animation for reduced-motion users while continuing textual updates.

### AgentOS Integration Contract

ForgeOS must not create AgentOS database tables without an accepted execution boundary.
The minimum proposed interface is:

```text
POST /agentos/v1/runs/proposals
POST /agentos/v1/runs
POST /agentos/v1/runs/{run_id}/cancel
GET  /agentos/v1/runs/{run_id}
GET  /agentos/v1/runs/{run_id}/events
```

Every run-creation request requires:

- `Idempotency-Key`.
- Authenticated actor and tenant context.
- Knowledge-context references, not copied unrestricted records.
- Requested model and budget ceiling.
- Policy decision or approval reference.
- Correlation and trace identifiers.

ForgeOS consumes a read model; AgentOS owns execution state.

### Audit Logging

#### Proposed schema

```text
audit_events
├── id                         integer / bigint primary key
├── event_id                   UUID or ULID, globally unique
├── occurred_at                timezone-aware timestamp
├── actor_type                 USER | AGENT | SERVICE
├── actor_id                   stable actor identifier
├── actor_display              denormalized display value
├── tenant_id                  organization scope
├── action                     canonical verb, e.g. asset.update
├── resource_type              asset | target | user | agent_run
├── resource_id                stable resource identifier
├── outcome                    ALLOWED | DENIED | SUCCEEDED | FAILED
├── reason_code                machine-readable policy/outcome code
├── correlation_id             request/workflow grouping
├── causation_id               direct parent event
├── trace_id                   distributed trace identifier
├── idempotency_key_hash       non-secret request identity
├── policy_decision_id         authorization decision reference
├── before_json                redacted prior state
├── after_json                 redacted resulting state
├── diff_json                  redacted field-level change
├── metadata_json              bounded non-secret context
└── schema_version             event schema version
```

#### Rules

- Append-only after commit.
- Never store secrets, bearer tokens, credential content, or uploaded report bodies.
- Record denied privileged attempts.
- Redact fields centrally by resource schema.
- Use an outbox table if delivery to an external audit sink is required.
- Retention and export policies must be explicit per tenant.

### RBAC / Context Isolation

#### Direct mapping

| Frontend state | Backend requirement | Rule |
|---|---|---|
| Read inventory and monitoring | `get_current_user` | UI may show read controls only after authenticated identity is loaded |
| Mutate assets, people, assignments | `require_admin` | Hidden or disabled in UI; backend remains authoritative |
| Run or configure monitoring checks | `require_admin` | Never infer permission from cached UI state |
| Manage users | `require_admin` | User list is not fetched for VIEW |
| Future tenant switch | `require_tenant_role(permission)` | Every query and mutation must include server-derived tenant scope |

Frontend permission states are usability affordances, not security controls. A request
that bypasses the UI must still receive `401` or `403`.

#### Target-state middleware

```text
authenticate request
  -> resolve active session
  -> resolve tenant membership
  -> evaluate permission and resource scope
  -> attach immutable RequestContext
  -> execute handler
  -> persist audit outcome
```

The client must never submit an authoritative role or tenant identifier. It may submit a
requested tenant, which the backend validates against membership.

## 5. ARCHITECTURAL DECISIONS & TRADE-OFFS (ADRs)

### ADR-E01: Command-Center Information Architecture

**Problem Statement**

The previous interface centered separate inventory screens and displayed fabricated
operational telemetry, preventing operators from distinguishing verified state from
demonstration content.

**Proposed Solution**

Use a Global Telemetry Console with real asset, assignment, target, latency, event, and
warning data. Place execution, topology, knowledge, and governance in separate
workspaces.

**Trade-offs Considered**

- Density improves operational scanning but increases novice cognitive load.
- A unified NOC improves situational awareness but can expose gaps more visibly.
- Deriving metrics from multiple endpoints can produce short-lived inconsistency.

**Mitigation Strategy**

- Use consistent panel headers and metric labels.
- Mark unavailable capabilities as Architecture Gaps.
- Add a future snapshot version to synchronize read models.

### ADR-E02: Preserve the Existing Frontend Stack

**Problem Statement**

The single-file Alpine/Tailwind interface is difficult to scale, but a framework rewrite
would be high-risk and unrelated to the immediate enterprise redesign.

**Proposed Solution**

Implement the enterprise shell in the current stack and isolate reusable visual behavior
through semantic CSS tokens and focused Alpine methods.

**Trade-offs Considered**

- Minimal change lowers migration risk but retains a large HTML file.
- A React or Vue rewrite could improve component boundaries but adds build tooling,
  dependencies, routing changes, and regression risk.

**Mitigation Strategy**

- Defer framework migration until the frontend needs compiled assets, component testing,
  or offline packaging.
- Treat the current redesign as the visual and interaction contract for any later
  implementation.

### ADR-E03: Polling Now, SSE Target State

**Problem Statement**

The backend has no real-time stream, while the operations UI needs fresh target state.

**Proposed Solution**

Poll every 15 seconds only while the Global Console or topology workspace is active.
Specify resumable SSE as the next contract.

**Trade-offs Considered**

- Polling is simple and compatible but duplicates payloads and can show inconsistent
  snapshots.
- SSE improves efficiency and ordering but requires authentication, replay, and proxy
  policy.
- WebSockets add bidirectional capability but impose unnecessary complexity for current
  telemetry.

**Mitigation Strategy**

- Scope polling to active pages.
- Keep payloads bounded.
- Introduce SSE only with event identifiers, sequence recovery, and secure stream
  authentication.

### ADR-E04: SVG Reachability Map with Table Fallback

**Problem Statement**

Operators need a topology view, but the database contains monitored endpoints rather than
node-to-node edges.

**Proposed Solution**

Render an SVG hub-to-target reachability map for up to 12 current nodes and retain the
high-density target table as the accessible source of exact values.

**Trade-offs Considered**

- SVG is crisp and keyboard-addressable but degrades with large graphs.
- Canvas scales better but requires a separate accessibility model.
- Calling the display a full network topology would misrepresent the data.

**Mitigation Strategy**

- Use explicit “Reachability Map” language.
- Switch to Canvas only after 100 nodes.
- Require clustering and a server topology contract before larger graphs.

### ADR-E05: Capability Gaps Instead of Simulated Agent Runtime

**Problem Statement**

The desired Agent Execution Plane requires contracts that do not exist.

**Proposed Solution**

Expose the implemented asset AI context, human validation concepts, and disabled runtime
controls. Label missing AgentOS, token, cost, cancellation, and idempotency interfaces.

**Trade-offs Considered**

- Disabled controls communicate the target model but can frustrate users.
- Simulated queue and cost values would create misleading product behavior.
- Hiding the workspace would defer important IA decisions.

**Mitigation Strategy**

- Explain each unavailable control.
- Keep the implemented asset context useful.
- Enable controls only when backend contracts and policy checks are verified.

### ADR-E06: Backend-Authoritative Permission States

**Problem Statement**

Frontend role checks can improve usability but cannot secure resources.

**Proposed Solution**

Map UI visibility directly to existing backend dependencies while treating the backend as
the sole authorization authority.

**Trade-offs Considered**

- Hiding inaccessible actions reduces noise but can obscure discoverability.
- Showing disabled actions explains capability but exposes product surface.
- Rechecking every action adds server work but prevents client bypass.

**Mitigation Strategy**

- Show Architecture Gap or permission explanations for strategic unavailable features.
- Hide routine administrator mutation controls from VIEW users.
- Preserve backend checks on every request.

### ADR-E07: High Density with Readability Guardrails

**Problem Statement**

Enterprise operators need high information density, while the host display is only
1366 × 768 and accessibility requires readable text and interaction targets.

**Proposed Solution**

Use compact panels, 8-pixel spacing rhythm, 48–56 pixel table rows, 40–44 pixel controls,
and monospace telemetry while retaining responsive stacking.

**Trade-offs Considered**

- Greater density reduces scrolling but can increase visual fatigue.
- Larger touch targets consume vertical space.
- Monospace improves numeric scanning but is less readable for prose.

**Mitigation Strategy**

- Reserve monospace for telemetry and identifiers.
- Keep explanatory text in Inter.
- Stack metrics at 1100 and 640 pixel breakpoints.
- Preserve visible focus and reduced-motion behavior.

### ADR-E08: Audit Event Model Before Audit UI Claims

**Problem Statement**

Export history exists, but it is insufficient for enterprise accountability.

**Proposed Solution**

Label current evidence as partial and specify an append-only, correlated, redacted audit
event schema before building a full audit browser.

**Trade-offs Considered**

- High-fidelity auditing increases storage and privacy obligations.
- Storing before/after values improves investigation but risks sensitive-data capture.
- Synchronous audit writes improve consistency but can add latency.

**Mitigation Strategy**

- Central redaction.
- Bounded metadata.
- Transactional outbox for external delivery.
- Explicit retention and tenant policies.

## 6. DETAILED COMPONENT WIREFRAMES (TEXT-BASED)

### Global Network Operations Center (NOC) Dashboard

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ForgeOS / Local / Global Console     [ Navigate or enter system command...          Ctrl K ]│
│                                      [Refresh] [operator / ROLE] [Logout]                    │
├───────────────┬─────────────────────────────────────────────────────────────────────────────┤
│ LOCAL         │ GLOBAL TELEMETRY CONSOLE                         API HEALTHY · POLL 15S      │
│ WORKSPACE     │ Network operations center                        SYNC 20:31                  │
│               ├────────────────┬────────────────┬────────────────┬───────────────────────────┤
│ Global Console│ TARGET HEALTH  │ AVG LATENCY    │ MANAGED ASSETS │ OPEN EXCEPTIONS           │
│ Agent Execute │ 8 / 9          │ 42 ms          │ 126            │ 3                         │
│ Network Topo  │ passing        │ 9 measurements │ 111 assigned   │ monitoring + inventory     │
│ Asset Registry├───────────────────────────────────────────────┬─────────────────────────────┤
│ People        │ MONITORING TOPOLOGY                           │ OPERATIONAL EXCEPTIONS      │
│ Security      │                                               │ ● Gateway failed          1 │
│ System Intake │         ○ node-a       ○ node-b                │ ● Unassigned assets       2 │
│ Reports       │              \         /                      ├─────────────────────────────┤
│ Access Mgmt   │               ◎ FORGEOS                        │ LATEST PROBE EVENTS         │
│               │              /    |    \                       │ ● gateway  148ms    now     │
│ API ONLINE    │        ○ web-1  ○ db-1  ○ vpn-1                │ ● web-1     31ms    1m      │
│ FastAPI       │                                               │ ● vpn-1     PASS    2m      │
│ SQLite        ├───────────────────────────────────────────────┴─────────────────────────────┤
│               │ AGENT EXECUTION PLANE              │ SECURITY & GOVERNANCE                 │
│ [Collapse]    │ CONTRACT GAP                        │ ADMIN / VIEW                           │
│               │ queued N/A · running N/A            │ audit GAP · tenant isolation GAP       │
└───────────────┴──────────────────────────────────────┴────────────────────────────────────────┘

Accessibility alternative:
Target table with sortable columns: Name, Address, Type, Status, Latency, Last Check,
Actions. All topology state is available without interpreting the graph.
```

The numeric examples above illustrate layout only. Runtime UI values must come from API
responses and must never be hardcoded as operational truth.

### Interactive Agent Execution & Prompt Workspace

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT EXECUTION PLANE                                      HUMAN VALIDATION REQUIRED         │
│ AI context and validation workspace                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ ARCHITECTURE GAP: No AgentOS queue, run, token/cost, cancellation, or idempotency contract. │
├──────────────────────────────────────────────────────────┬──────────────────────────────────┤
│ PROMPT & RUN CONTROL                         READ ONLY    │ HUMAN VALIDATION GATE             │
│                                                          │                                  │
│ Natural-language instruction                             │ [✓] Context review               │
│ ┌──────────────────────────────────────────────────────┐ │ [ ] Action approval             │
│ │ Disabled until AgentOS proposal contract exists.     │ │ [ ] Rollback evidence           │
│ │                                                      │ │                                  │
│ └──────────────────────────────────────────────────────┘ │ Each disabled gate identifies    │
│                                                          │ the missing backend contract.     │
│ RUN ID        TOKEN / COST       IDEMPOTENCY             │                                  │
│ NOT ISSUED    NOT REPORTED       UNDEFINED               │                                  │
│                                                          │                                  │
│ [Start validated run - disabled] [Cancel - disabled]     │                                  │
├──────────────────────────────────────────────────────────┴──────────────────────────────────┤
│ IMPLEMENTED ASSET INTELLIGENCE                                       EXISTING CONTRACT      │
│                                                                                             │
│ Context asset                                                                               │
│ [ FOS-1001 · IT-STATION                                  v ] [Inspect asset context]         │
│                                                                                             │
│ Summary: AI backend is not configured; structured asset context is ready.                   │
│ Warnings: NONE REPORTED                                                                     │
│                                                                                             │
│ Context Envelope                                                                            │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ asset: { tag, type, manufacturer, model, RAM, CPU, GPU, hostname, status }             │ │
│ │ warranty: { vendor, end_date }                                                         │ │
│ │ monitoring: [ recent persisted monitoring events ]                                    │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Delivery Boundary

The current redesign changes presentation, client-side interaction, and adds SPA
deep-link aliases for the new workspaces. It does not:

- Add AgentOS services.
- Add tenant records.
- Add audit tables.
- Add SSE or WebSocket endpoints.
- Change database migrations.
- Change authentication semantics.
- Change monitoring scheduler behavior.

Those changes require separate implementation plans, schema review, tests, migration
strategy, and accepted ADRs.
