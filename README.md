# AutoApply AI

Self-hosted job discovery, local AI matching and verified resume preparation. Python/FastAPI, React/TypeScript, PostgreSQL (Docker) or SQLite (local), and Ollama. No mandatory paid APIs.

**Release status:** functional foundation with an experimental browser dry run. Live submission is deliberately unavailable, including through the API. This is not yet the full autonomous application platform described in the project brief. See [the roadmap](docs/ROADMAP.md) and [evaluation](docs/REUSE.md).

## Quick start: Windows 11 / Ubuntu 24.04

Install Docker Compose and Ollama. Clone this repository, then:

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` on Ubuntu).
2. Replace both placeholder secrets. Use a random API token of at least 24 characters and a separate alphanumeric database password. The database password is interpolated into a connection URL, so URL-reserved characters require encoding.
3. Run `ollama pull qwen2.5:7b` on the host. Set `OLLAMA_MODEL` to another installed model if desired. The 7B model is a conservative starting point for the 16 GB GPU; actual latency and memory use must be measured.
4. Run `docker compose up --build -d`.
5. Open http://localhost:8080 and enter the `API_TOKEN` from `.env`. The token stays in browser memory only.
6. Save and verify your career profile. In Sources, add an employer's board slug, for example the portion after `jobs.lever.co/` in their board URL. Click Discover now, then inspect Activity.
7. Evaluate discovered jobs and prepare a resume from Jobs. Download generated versions from Applications.
8. Enable scheduled discovery in Settings to discover and evaluate every six hours. Manual discovery and evaluation work while scheduling is off. Emergency stop blocks new worker tasks; already-running read-only HTTP/AI calls can finish.

Ollama on Docker Desktop is reached through `host.docker.internal`. On Ubuntu configure Ollama to listen on an interface reachable from the Docker bridge, and firewall port 11434 to that bridge only. Never expose it publicly. Model downloads are explicit; Compose does not automatically pull a model. CPU fallback works but is slower. GPU inference runs in host Ollama, independent of the containers.

Dashboard binding defaults to loopback. For Tailscale access, use a private HTTPS reverse proxy on the host. Do not expose PostgreSQL, the API, or browser debugging ports. Use HTTPS for any remote dashboard access because the API token is a bearer credential.

## Local development

Python 3.12+, Node 22+:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e "./backend[dev]"
# Set API_TOKEN to a random value of at least 24 characters in .env.
uvicorn autoapply.main:app --reload --app-dir backend/src
```

In separate terminals from the repository root:

```powershell
python -m autoapply.worker
```

```powershell
cd frontend
npm ci
npm run dev
```

On Ubuntu activate with `source .venv/bin/activate`. SQLite defaults to `autoapply.db` in the current directory; use the same directory and environment for API and worker. `DATABASE_URL` may select PostgreSQL. Run exactly one worker; concurrent leases and multi-worker support are pending. On first install the schema is created automatically; migrations are required before future schema changes.

## Validation

```powershell
python -m pytest backend/tests
ruff check backend
cd frontend
npm run build
```

Tests use isolated SQLite databases, mocked feed/model responses and synthetic profiles. They never send an application. CI runs backend validation and frontend builds. Docker runtime, GPU inference and real employer form compatibility require deployment validation.

## Experimental browser dry run

Install Chromium locally with `python -m playwright install chromium`, or use the worker image. Set `allowed_hosts` through Settings API to an explicitly authorized supported host (`jobs.lever.co`, `jobs.eu.lever.co`, `boards.greenhouse.io`, `job-boards.greenhouse.io`, or `jobs.ashbyhq.com`). Then POST `/api/jobs/{id}/dry-run` with your bearer token. All `/api/` endpoints require it. Interactive API docs are available on the local development backend at `/docs`.

The adapter fills only recognized name, email and phone inputs. It blocks all non-GET browser requests, cross-host requests, private/reserved IP destinations, downloads and service workers; consequently many real ATS forms will require intervention or fail to load. It never clicks Submit, creates accounts, uploads files, answers screening questions or solves security challenges. It records a local screenshot and pauses for review. Browser failures are not retried automatically. Screenshot paths are diagnostic references in the application record; viewing them currently requires access to the data volume.

DNS checks are defense in depth, not full DNS-rebinding protection. An isolated worker network with an egress firewall is required before extending browser access to arbitrary career pages. No session cookies, mailbox tokens or employer passwords are stored in this release.

## Data and reliability

- Public ATS feeds: Greenhouse, Lever and Ashby (US Lever endpoint; EU discovery is pending). Source plus board plus external requisition ID prevent repeat imports. Cross-source deduplication is pending.
- Matching uses validated structured Ollama output and the brief's 30/25/20/15/10 weights. Hard failures override scores. Unknown evidence and all high-scoring matches require review. Scores do not authorize submission. Weights are currently fixed; thresholds are configurable.
- Resume generation preserves verified text and dates, reordering skills only. Each PDF retains a profile snapshot and target job. No invented claims or model-written resumes. Cover letters are pending.
- Worker tasks persist across restarts with bounded retries and backoff. Interrupted browser tasks fail for review. Repeated document generation can leave an orphan file if a process crashes before commit; no external submissions can be duplicated.
- Scheduled discovery is sequential, normally six-hourly. Provider errors are surfaced as task failures; no failed fetch is treated as an empty feed. Per-source Retry-After handling and distributed rate limiting are pending.
- Personal data, PDFs and screenshots reside in the database and `documents` volume. Protect host disks/backups with OS encryption and filesystem permissions. Application-level encryption, retention/deletion controls and OAuth integrations are pending.
- Back up PostgreSQL with `pg_dump` and the documents volume together while the worker is stopped. Test restoring into an isolated deployment. Never commit `.env`, profiles, generated documents or screenshots.

See [AGENTS.md](AGENTS.md) for project conventions and [docs/ROADMAP.md](docs/ROADMAP.md) for the remaining milestones.
