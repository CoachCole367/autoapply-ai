# Architecture and implementation plan

## Decisions

Use a small monorepo: `backend/src/autoapply` for API, schemas, persistence and independent discovery/matching/documents/browser modules; `backend/tests` for synthetic contracts and integration tests; `frontend/src` for the React dashboard; `docs` for design decisions. Compose runs PostgreSQL, API, one worker and an nginx-served dashboard. Ollama runs on the GPU host.

SQLAlchemy owns durable domain state. A database-backed queue avoids introducing Redis/Celery until concurrency requires them. One worker avoids lease races. Feed discovery, matching and document creation have independent task types. The browser receives verified data and deterministic field mappings; job descriptions are never executable instructions. AI assessments are advisory and cannot change policy or mark an application submitted.

The empty repository had no conventions or dependencies. FastAPI, React, SQLAlchemy and Playwright follow the requested architecture. Plain CSS keeps the foundation small; Tailwind, shadcn, charting and AI browser frameworks are deferred until justified by product needs. No upstream source code is copied.

## Milestones and dependencies

1. **Foundation (implemented):** API bearer authentication, profile/settings, board configuration, SQLite/PostgreSQL models, public ATS discovery, expiry detection, source-level deduplication, persistent worker tasks, React workspace, Compose and CI.
2. **Intelligence (partial; depends on 1):** structured Ollama matching with saved explanations, weighted scoring, verified single-column resume PDFs and document snapshots implemented. Next: typed work history with dates, compensation/country normalization, deterministic hard requirements, configurable weights, answer-bank editor, cover letters, PDF extraction tests and model evaluation fixtures. Do not promote a model's legal/eligibility claim to verified evidence.
3. **Browser automation (experimental dry-run only; depends on 1–2):** isolated Chromium context, strict host policy, recognized contact-field filling, screenshots and intervention records implemented. Next: local employer test sites, uploads, dynamic fields, multi-step checkpoints, validation checks, adapter-specific confirmations and no-duplicate submission transactions. Greenhouse/Lever/Ashby live forms are unvalidated; current contact-field selectors are conservative starting points.
4. **Authorized submission (pending; depends on 3):** independently verified hard requirements, per-host consent, per-job approval policy, daily caps, atomic claim/lease, submission intent record before click, receipt-based verification, unresolved outcome state with no automatic replay, state-transition audit and crash tests. Only then enable live submit in API/UI. No CAPTCHA/MFA bypass.
5. **Advanced ATS (pending; depends on 3–4):** Workday account/session handoffs, encrypted credential/session vault, manual MFA recovery. Evaluate a narrowly sandboxed Browser Use fallback only after deterministic adapters pass contract tests. Add remaining ATS providers incrementally.
6. **Full orchestration (partial; depends on 1–5):** scheduling and task activity implemented. Next: OAuth Gmail/Graph ingestion, message correlation, LinkedIn/Indeed alert import, outcome tracking, analytics, retention/deletion, migrations, per-source throttling, multi-worker leases, backups/restore automation and monitoring.

## Release gates

Foundation: mocked discovery/matching and persistent database workflow tests, authenticated API integration tests, lint and TypeScript production build. Deployment: Compose image build, PostgreSQL smoke test and a real local Ollama schema response. Browser: simulated forms with uploads, validation, redirects, CAPTCHA/MFA pauses and crash recovery. Live submission: deterministic confirmations, duplicate and unknown-outcome tests, host authorization, egress restrictions and explicit opt-in.

## Known limits

This release cannot meet the final autonomous-submission success criterion yet. There are no live submission, OAuth, Workday or generic AI browser adapters. Match categories are validated numbers but their accuracy depends on the local model and profile completeness. HTTP fixtures validate parser behavior, not continuing compatibility with public services. Browser interruption checks occur between tasks; emergency stop cannot instantly cancel an already-running browser or model operation. The API is single-user; application-level credential encryption and multi-user authorization are deferred because no third-party credentials are accepted.
