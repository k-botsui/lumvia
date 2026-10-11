# Lumvia — Product & Engineering Constitution

> 長期構想を含む設計資料です。現行の公開仕様・対応機能・利用条件はREADME、LICENSE、ADRを優先してください。

> **Status:** Living Architecture Document  
> **Audience:** Developers, AI coding agents, reviewers, maintainers  
> **Purpose:** Define the long-term product vision, engineering principles, architectural boundaries, security requirements, and implementation standards for Lumvia.

---

## 1. Document Role

This document is the primary engineering and product reference for Lumvia.

It is intentionally **not** a temporary implementation prompt, sprint memo, or one-time scaffold specification. It should remain useful as the product evolves.

When implementing, modifying, reviewing, or refactoring Lumvia:

1. Preserve the product principles in this document.
2. Prefer maintainability and clear boundaries over short-term convenience.
3. Do not introduce architecture solely because it is fashionable.
4. Do not prematurely optimize or prematurely distribute the system.
5. New features must fit the existing domain model or explicitly justify changes to it.
6. Security, accessibility, data ownership, and user experience are requirements, not optional polish.
7. When implementation and this document disagree, determine whether the implementation is wrong or this document genuinely needs revision. Do not silently diverge.
8. Significant architectural decisions should be recorded as ADRs.

---

# 2. Product Identity

## 2.1 Name

**Lumvia**

Lumvia is a modern video library and analysis platform.

It helps users:

> **Collect videos, understand their contents, organize meaningful moments, and find them again.**

The product must not present itself primarily as an "AI tool." AI is an enabling layer behind the experience.

The user-facing value is collecting, organizing, discovering, searching, revisiting, and understanding video.

## 2.2 Core Product Idea

Most video systems organize information at the file level. Lumvia treats video as searchable, structured information.

```text
Source
  ↓
Media
  ↓
Analysis
  ↓
Moment
  ↓
Cell
  ↓
Shelf / Collection
  ↓
Search & Discovery
```

The central product promise is:

> **Your own searchable video library.**

---

# 3. Product Principles

## 3.1 Simple on the Surface

Advanced technology must not create a complicated interface.

A normal user should not need to understand machine-learning model names, confidence thresholds, codecs, inference settings, frame sampling, queues, workers, embeddings, or object detection terminology.

These concepts may exist in an **Advanced** area for expert users. Default workflows must remain simple.

## 3.2 The Library Comes Before AI

Lumvia must remain useful even when AI analysis is unavailable.

The foundation is media ingestion, playback, Cells, Shelves, Collections, tags, notes, favorites, and search. AI enhances these capabilities; it does not define them.

## 3.3 Progressive Disclosure

Expose complexity only when needed. A simple `Analyze` action is preferable to exposing model, confidence, frame interval, and device settings by default.

## 3.4 Fast Perceived Interaction

Long-running work must happen asynchronously. Use optimistic updates where safe, skeleton states, progress indicators, cancel controls where feasible, clear failure states, retry actions, and non-blocking navigation.

Never freeze the application while analyzing media.

## 3.5 User Ownership

Users must understand what is stored, referenced, temporary, deletable, and where analysis results came from. Avoid hidden persistence.

---

# 4. Experience Direction

Lumvia should feel calm, precise, spacious, modern, lightweight, premium, and content-first.

Avoid cyberpunk dashboards, excessive neon, dense enterprise-style tables as the default, unnecessary gradients, visual noise, excessive borders, and AI-themed visual clichés.

Primary experience: light background, white cards, soft gray surfaces, dark neutral typography, restrained accent color, generous whitespace. Dark mode may be supported but must not define the brand.

Support desktop, laptop, tablet, and mobile. Desktop may expose richer multi-pane workflows. Mobile should prioritize viewing, adding, searching, saving Cells, organizing, and sharing into Lumvia.

---

# 5. Information Architecture

Keep primary navigation intentionally small:

```text
Home
Add
Library
Collections
Settings
```

Do not create a new top-level destination for every feature. Advanced and administrative functionality belongs under contextual menus or Settings.

---

# 6. Core Domain Model

The domain model must remain independent from specific AI models and external services.

## Library

The user's primary media space. Future multi-user workspaces may own Libraries, so ownership must not be hard-coded in a way that prevents later evolution.

## Source

Describes where media originated: local upload, authorized remote URL, external platform, camera stream, or future connector.

Source is not Media. One source may expose multiple media objects.

## Media

Represents a logical video, image, or supported audiovisual item. Identity must not depend on a filesystem path.

## Asset

Represents a stored physical object associated with Media: original upload, temporary analysis copy, thumbnail, preview, waveform, or transcoded representation.

## Cell

**Cell is a first-class Lumvia concept.**

A Cell represents a meaningful time interval inside a video.

```text
Media: video_123
Start: 01:20.000
End:   02:15.500
Title: Favorite scene
```

Store temporal boundaries as integer milliseconds. A Cell references its Media rather than duplicating video by default.

Possible origins: user-created, AI-suggested, imported, system-generated. AI suggestions and user decisions must remain distinguishable. Users must be able to edit AI-suggested Cells.

## Shelf

A user-controlled organizational structure such as Travel, Favorites, Cats, Concerts, or Research.

## Collection

Groups Media and/or Cells across the Library. Design many-to-many relationships where appropriate.

## Analysis Run

Records a specific execution of analysis, including analyzer type, model/version, configuration, timestamps, status, and relevant provenance.

Never make the Library depend directly on a particular model.

## Analysis Event

Normalize machine-generated results into model-independent events.

```json
{
  "media_id": "video_001",
  "event_type": "object_detection",
  "start_ms": 82000,
  "end_ms": 84500,
  "label": "person",
  "confidence": 0.94,
  "analyzer": "object_detector",
  "model_version": "..."
}
```

## Transcript

Transcripts must preserve timestamps and provenance. At minimum support start time, end time, text, language when known, and analysis origin.

## Batch and Job

A Batch represents a user-level group operation. A Job represents executable work. The UI should present meaningful user-level progress rather than infrastructure terminology.

---

# 7. Recommended Technology Stack

## Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
shadcn/ui
Radix UI
TanStack Query
React Hook Form
Zod
Motion
```

Use an accessible drag-and-drop library such as dnd-kit where appropriate.

Principles: TypeScript strict mode, accessible semantic HTML, keyboard navigation, reusable components, deliberate server/client boundaries, and minimal global state.

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy 2.x
Alembic
```

Do not place heavy video analysis directly in request handlers.

API handlers should generally validate, authorize, perform lightweight domain operations, enqueue heavy work if necessary, and return.

## Database

Use **PostgreSQL** as the system of record for durable application state.

Do not use Redis as authoritative storage for users, jobs, media, Cells, permissions, or analysis history. Use migrations for every schema change.

## Cache and Ephemeral State

Use **Redis** for caching, rate-limit state, temporary coordination, and appropriate short-lived state.

## Async Processing

Default:

```text
Celery
RabbitMQ
```

Potential logical worker boundaries: ingestion, video-processing, audio-processing, analysis, maintenance.

Do not prematurely deploy every logical worker as a separate service.

## Media Processing

Use FFmpeg and FFprobe. Media is untrusted input. Apply restricted privileges, resource limits, timeouts, isolated temporary directories, controlled network access, and safe argument construction.

Never build shell commands by concatenating untrusted strings.

## Analysis

Initial analyzers may include object detection, tracking, speech recognition, scene detection, and metadata extraction.

Potential implementations include YOLO-family detectors and faster-whisper, but core interfaces must remain generic and model-replaceable.

## Object Storage

Use an S3-compatible abstraction. Keep objects private by default. Protected media should use controlled access such as short-lived signed URLs where appropriate.

---

# 8. Repository Architecture

```text
lumvia/
├── apps/
│   ├── web/
│   └── api/
├── workers/
│   ├── ingestion/
│   ├── video/
│   ├── audio/
│   └── analysis/
├── packages/
│   ├── ui/
│   ├── api-client/
│   └── shared-types/
├── infrastructure/
│   ├── docker/
│   ├── database/
│   └── observability/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── security/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── api/
│   ├── security/
│   ├── product/
│   └── development/
├── .github/
│   └── workflows/
├── compose.yaml
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
└── .env.example
```

Begin as a modular monolith with separate asynchronous workers, not a microservice fleet.

---

# 9. Backend Module Boundaries

Prefer domain-oriented modules:

```text
app/
├── auth/
├── users/
├── libraries/
├── media/
├── sources/
├── cells/
├── shelves/
├── collections/
├── search/
├── analysis/
├── jobs/
├── audit/
└── integrations/
```

Avoid giant route files, giant service classes, and generic `utils.py` modules with unclear ownership.

---

# 10. API Standards

Base path:

```text
/api/v1
```

Representative resources:

```text
POST   /media
GET    /media
GET    /media/{id}
PATCH  /media/{id}
DELETE /media/{id}

POST   /imports
POST   /batches

GET    /jobs/{id}
POST   /jobs/{id}/cancel

GET    /cells
POST   /cells
PATCH  /cells/{id}
DELETE /cells/{id}

GET    /shelves
POST   /shelves

GET    /collections
POST   /collections

GET    /search
```

Requirements: versioned surface, consistent error envelope, pagination, explicit validation, resource-level authorization, OpenAPI documentation, idempotency where needed, request IDs, safe retry semantics, stable identifiers, UTC timestamps, and a deprecation strategy.

Use a generated or strongly typed frontend API client where practical. Backend validation remains authoritative.

---

# 11. External Source Architecture

External integrations must use adapters:

```text
Source Resolver
      │
      ├── LocalUploadAdapter
      ├── DirectUrlAdapter
      ├── ExternalPlatformAdapter
      └── CameraAdapter
```

Adapters expose normalized capabilities such as metadata, embed, import, and analyze.

Never assume that because metadata can be retrieved, media may also be downloaded.

Respect platform terms, API policies, authentication requirements, copyright, privacy, rate limits, and user authorization.

Platform-specific behavior must not leak throughout core domain code.

---

# 12. Import Security

Remote URL ingestion is a high-risk boundary. Protect against SSRF.

At minimum: accept supported schemes, reject malformed URLs, resolve DNS safely, block loopback/link-local/private/internal destinations unless explicitly required by a trusted feature, validate redirects, limit redirects and response size, apply timeouts, restrict protocols, isolate remote fetching, log security-relevant failures, and control egress where possible.

Do not rely solely on string matching.

---

# 13. Upload Security

Every upload is untrusted.

Validate authenticated ownership, file size, permitted media types, actual file characteristics, extension versus detected format, and processing limits.

Generate server-side object names. Never trust a user-provided filename as a storage path.

---

# 14. Authentication and Authorization

Prefer standards-based authentication such as OIDC. Do not invent a custom authentication protocol without compelling reason.

Browser sessions should use secure properties appropriate to the chosen model, including Secure and HttpOnly cookies and CSRF protection where applicable.

Authorization is application-owned and resource-specific.

Never assume an authenticated user may access a resource because they know its ID.

Protect Media, Assets, Cells, Shelves, Collections, Jobs, Analysis Runs, transcripts, generated files, and administrative operations.

Design so future Workspace roles can be introduced without rewriting every endpoint:

```text
Workspace
 ├── Owner
 ├── Admin
 ├── Editor
 └── Viewer
```

Do not implement complex enterprise tenancy prematurely.

---

# 15. Job Architecture

Durable job state belongs in PostgreSQL.

Representative lifecycle:

```text
PENDING
QUEUED
RUNNING
COMPLETED
FAILED
RETRYING
CANCEL_REQUESTED
CANCELLED
TIMED_OUT
```

State transitions must be explicit and validated. Workers must assume messages may be delivered more than once, so operations should be idempotent where feasible.

Record job ID, type, owner, state, progress, attempt count, timestamps, error category, sanitized error detail, and correlation identifiers.

Never expose raw internal exceptions to users.

---

# 16. Batch Processing and Progress

Batch operation is first-class.

```text
63 items
48 complete
10 processing
3 queued
2 failed
```

Support partial success and explicit retries.

Prefer SSE for server-driven progress when it fits. Use WebSockets only when bidirectional real-time communication provides meaningful value. Polling may remain a fallback.

---

# 17. Search Architecture

Begin with PostgreSQL search capabilities.

Search media title, description, tags, notes, Cell titles, transcript text, and normalized analysis labels.

Timestamped results should navigate directly to the relevant moment.

Do not introduce a dedicated search cluster until scale or requirements justify it, but preserve the ability to add one later.

---

# 18. Cell UX

Cell creation is a signature interaction.

Users should be able to play a video, select start and end points, preview the range, name it, tag it, save it, organize it, and reopen the source video at that range.

Future enhancements may include timeline drag handles, AI suggestions, transcript-based creation, event-based creation, sharing, and permitted export.

Cell editing must feel like a native product feature, not an administrative form.

---

# 19. Storage Modes

Distinguish media storage states conceptually:

```text
REFERENCE
TEMPORARY
MANAGED
```

REFERENCE stores metadata/reference. TEMPORARY exists for authorized processing and expires according to policy. MANAGED stores authorized/user-provided media.

The UI should make meaningful differences understandable.

---

# 20. Deletion and Privacy

Design deletion deliberately. Distinguish removing from Shelf/Collection, deleting a Cell, deleting analysis, deleting Media, deleting managed assets, deleting an account, and retaining security/audit records.

Use data minimization.

Avoid unnecessary biometric identity features. Object/person detection must not automatically become identity recognition. Future identity-related features require separate privacy, security, legal, and product review.

---

# 21. AI Principles

AI output is probabilistic.

Preserve provenance, model/version information, allow correction where appropriate, distinguish suggestions from user-authored truth, never silently overwrite user data, avoid presenting uncertain inference as certainty, and design for model replacement.

The UI should translate AI results into useful actions instead of exposing raw model mechanics by default.

---

# 22. Security Baseline

Continuously review against current secure-development and OWASP guidance.

Required categories include resource authorization, authentication security, rate limiting, resource consumption controls, SSRF prevention, injection prevention, XSS prevention, CSRF protection where applicable, secure headers, secret management, dependency management, least privilege, secure file handling, audit logging, error sanitization, and security testing.

Production uses HTTPS. Define intentional CSP, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, and frame restrictions where appropriate.

Do not globally allow CORS.

---

# 23. Secrets, Logging, Audit, Observability

Secrets must never be committed. `.env.example` contains names/documentation only. CI should perform secret scanning.

Prefer structured logs that correlate request → action → job → worker → analysis → failure.

Never intentionally log passwords, raw session secrets, access tokens, or private keys. Redact sensitive URLs/content where appropriate.

Audit security-relevant events separately from debugging logs.

Design for logs, metrics, and traces using vendor-neutral instrumentation such as OpenTelemetry. Track API latency, errors, queue depth, job duration/failure, worker saturation, storage/import failures, and analysis duration.

---

# 24. Resource Controls

Video processing consumes CPU, GPU, RAM, disk, and bandwidth.

Enforce limits on upload size, duration, resolution, concurrent jobs, queue depth, processing timeout, temporary disk, remote fetch size, and API rates.

Resource limits are security controls.

---

# 25. Frontend State and Accessibility

Prefer:

```text
server state → TanStack Query
form state   → React Hook Form
local UI     → React state
URL state    → URL/search parameters
```

Do not introduce large global state without demonstrated need.

Accessibility is required: keyboard navigation, visible focus, semantic controls, labels, contrast, accessible dialogs, drag-and-drop alternatives, reduced-motion consideration, and captions/transcripts where available.

Critical actions must not be gesture-only.

---

# 26. Performance

Frontend: lazy-load heavy components, virtualize large lists when needed, optimize thumbnails, avoid unnecessary full-video loads, and cache intentionally.

Backend: paginate, avoid N+1 queries, index from measured access patterns, stream large data where appropriate, and keep request handlers lightweight.

Media: generate previews asynchronously, avoid unnecessary transcoding, and support appropriate range/CDN behavior in deployment.

---

# 27. Testing Strategy

Unit tests cover domain rules, validation, authorization helpers, state transitions, adapters, and analysis normalization.

Integration tests cover database behavior, migrations, API+DB, queue boundaries, and storage adapters.

E2E core journey:

```text
sign in
→ upload
→ media appears
→ create Cell
→ organize
→ search
→ reopen at timestamp
```

Later:

```text
import
→ analyze
→ progress
→ results
→ create/edit suggested Cell
```

Security tests cover IDOR/BOLA, unauthorized asset access, malformed uploads, SSRF, rate limits, permission boundaries, redirect chains, invalid media, and destructive operations.

---

# 28. CI/CD and Dependencies

GitHub Actions should enforce formatting, lint, type-checking, tests, frontend build, backend checks, migration validation, dependency scanning, secret scanning, and container scanning as appropriate.

Required failing checks block merge.

Prefer mature, maintained dependencies. Evaluate maintenance, security history, license, ecosystem adoption, necessity, runtime cost, and replacement difficulty before adding one.

---

# 29. Database, Time, IDs, Configuration

Every schema change uses a migration. Test migrations against realistic data.

Persist timestamps in UTC and convert at the UI boundary.

Use stable opaque identifiers. Avoid unnecessarily exposing sequential IDs.

Use integer milliseconds for media positions unless future requirements justify greater precision.

Separate code, configuration, and secrets. Configuration must be typed and validated at startup.

---

# 30. Development and Public Repository Quality

A contributor should be able to predictably clone, configure, run Docker Compose, apply migrations, and start development.

Provide safe demo/seed data where useful.

Required repository documents:

```text
README.md
CONTRIBUTING.md
SECURITY.md
LICENSE
.env.example
```

README should eventually contain product explanation, screenshots, architecture, feature status, setup, development, testing, security notes, roadmap, and contribution guidance.

Do not claim unsupported capabilities.

Use ADRs for significant decisions.

---

# 31. Code Quality

Prefer explicit, typed, testable, readable, modular code.

Avoid clever abstractions without value, deep inheritance, hidden side effects, giant classes/routes, untyped dictionaries across boundaries, circular dependencies, and unclear generic helpers.

Comments explain **why**, not obvious code.

---

# 32. Architectural Rule: Modular Monolith First

Begin as a **modular monolith with separate asynchronous workers**, not a microservice fleet.

Extract modules only when justified by independent scaling, security isolation, deployment cadence, ownership, or reliability requirements.

Extraction is an optimization, not a starting goal.

---

# 33. Extensibility

New sources implement adapters rather than modifying Library behavior.

New analyzers implement analyzer contracts rather than changing Media semantics.

New storage providers implement storage interfaces.

New authentication providers use standards-based integration.

Extensibility comes from clear contracts, not speculative plugin frameworks.

Use feature flags for staged rollout or risky experiments when justified. Remove obsolete flags.

---

# 34. Compatibility and Analytics

Public APIs and durable data require compatibility discipline: assess migrations and clients, version appropriately, document deprecations, and provide transitions when external consumers exist.

If product analytics are introduced, minimize and document collection. Avoid collecting raw user media unnecessarily. Analytics must never silently become surveillance.

---

# 35. Development Sequence

These are sequencing guidelines, not a permanent roadmap.

## Foundation

Repository, frontend, backend, PostgreSQL, migrations, authentication foundation, object-storage abstraction, CI, tests, documentation.

## Library MVP

```text
upload
media library
playback
Cell creation/editing
Shelf organization
Collection organization
basic search
deletion
```

Lumvia must already be useful here.

## Async Media Pipeline

```text
jobs
workers
thumbnails
metadata extraction
progress
batch operations
```

## Analysis

Incrementally add transcription, object detection, scene analysis, and tracking where useful.

## External Sources

Add integrations only after the core Library is reliable. Evaluate each platform independently.

## Advanced Capabilities

Possible future areas: sharing, workspaces, browser extension, mobile share flow, camera/RTSP, semantic search, richer Cell suggestions, external API, webhooks.

Future features are not commitments.

---

# 36. Definition of Done

Before calling a feature complete, consider:

- product behavior
- UI states
- accessibility
- authentication
- authorization
- validation
- error/loading/empty states
- retry behavior
- observability
- tests
- documentation
- migrations
- security implications
- cleanup/deletion behavior

---

# 37. Coding-Agent Operating Rules

## Before Editing

1. Read this document.
2. Inspect relevant implementation.
3. Identify the domain boundary being changed.
4. Check related tests and documentation.
5. Avoid assuming missing architecture.
6. Prefer existing conventions unless they conflict with this constitution.

## During Implementation

1. Make the smallest coherent architectural change.
2. Keep public contracts explicit.
3. Add/update tests.
4. Preserve security boundaries.
5. Avoid unrelated refactors.
6. Do not silently introduce infrastructure.
7. Never hard-code secrets.
8. Never bypass authorization for convenience.
9. Never process untrusted media/URLs without required controls.
10. Keep user-facing terminology simple.

## After Implementation

1. Run relevant tests.
2. Run lint/type checks.
3. Review migrations.
4. Review authorization.
5. Review error handling.
6. Review logs for sensitive data.
7. Update documentation when architecture/behavior changes.
8. Summarize changes and remaining risks.

---

# 38. Prohibited Shortcuts

Do not:

- replace PostgreSQL with an in-memory production architecture
- store critical business state only in Redis
- perform heavy analysis synchronously inside API requests
- trust client-side authorization
- trust MIME type or filename alone
- fetch arbitrary URLs from the application network
- interpolate user input into shell commands
- expose storage buckets publicly by default
- commit credentials
- disable TLS verification to make integrations work
- globally allow CORS
- suppress errors without observability
- expose raw exceptions to users
- couple Library semantics to one AI model
- treat AI suggestions as user-confirmed facts
- create a microservice when a module is sufficient
- introduce Kubernetes without operational need
- introduce dedicated search infrastructure before justified
- add identity recognition casually
- bypass external platform rules to make importing easier

---

# 39. Architecture Decision Test

When multiple solutions are possible, evaluate in this order:

1. User safety and security
2. Data ownership and privacy
3. User experience
4. Domain-model fit
5. Maintainability
6. Observability and testability
7. Evolvability
8. Justified operational complexity
9. Justified dependency/infrastructure cost

Prefer the simplest solution satisfying these constraints.

---

# 40. Long-Term Scalability and Reliability

Do not design for imaginary hyperscale. Do allow web, API, workers, database, object storage, search, analysis compute, and integrations to evolve independently.

Likely scaling path:

```text
single development stack
        ↓
separate web/API/workers
        ↓
horizontal worker scaling
        ↓
managed database/storage
        ↓
dedicated search if justified
        ↓
specialized GPU workers
        ↓
selective service extraction
```

Long-running jobs must tolerate worker restart, duplicate delivery, temporary storage/API failures, crashes, and timeouts. Use bounded retries and backoff; never retry permanent failures indefinitely.

Production architecture must eventually define database backups, storage durability, restoration procedures, retention, and recovery testing. Backups are incomplete until restoration is tested.

---

# 41. Future External API and Webhooks

A future public API should use explicit authentication, scopes, rate limits, versioning, stable contracts, documentation, revocation, and auditability.

Do not expose every internal endpoint publicly.

Future webhooks should sign payloads, support replay protection, retry safely, provide event IDs, document ordering guarantees, and avoid leaking unnecessary data.

---

# 42. Media Rights and External Platforms

Technical capability is not permission.

For external media, respect platform policies, authorization, copyright, and privacy. Clearly distinguish references from stored copies. Avoid promising import support that cannot be reliably or legitimately provided.

Integrations must degrade gracefully when platforms change.

---

# 43. Naming and Brand Principle

Prefer user concepts:

```text
Video
Moment
Cell
Shelf
Collection
Library
Analyze
```

Avoid exposing infrastructure terms such as broker, worker queue, inference pipeline, or database row.

Lumvia should communicate:

> **Technology quietly helping people rediscover video.**

Do not visually or verbally overstate AI. Avoid generic AI branding clichés such as glowing brains, circuit heads, robot imagery, excessive neon, or constant "powered by AI" messaging.

The intelligence should be visible through the quality of the experience.

---

# 44. Product North Star

A successful Lumvia experience should feel like this:

```text
I found a video.
I added it.
Lumvia understood enough to help.
I organized the part I cared about.
Months later, I searched for it.
Lumvia took me directly to the moment.
```

Everything else is supporting infrastructure.

---

# 45. Final Engineering Principle

Lumvia should make complex video technology feel simple.

The architecture may contain:

```text
queues
workers
models
storage
indexes
security boundaries
external APIs
media pipelines
```

but the user should experience:

```text
Add
Find
Save
Organize
Watch
```

When engineering complexity leaks into the normal user experience, treat it as a design problem.

When short-term implementation convenience damages security, maintainability, or product clarity, choose the durable solution.

**Build Lumvia as a product intended to live, evolve, and remain understandable for years.**
