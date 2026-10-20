# AutoApply AI

Stack: Python 3.12, FastAPI, SQLAlchemy, SQLite/PostgreSQL, React, TypeScript, Vite, Ollama, Docker Compose.

- Backend install: `python -m pip install -e "./backend[dev]"`
- Backend dev: `uvicorn autoapply.main:app --reload --app-dir backend/src`
- Backend tests/lint: `python -m pytest backend/tests` / `ruff check backend`
- Frontend install/dev: `cd frontend`, `npm ci`, `npm run dev`
- Frontend build: `npm run build`
- Full environment: `docker compose up --build -d`

Keep discovery, matching, documents and browser execution separate. Validate all external data. Never log profiles or secrets. Never infer verified qualifications from model output. Never retry uncertain submissions. Use mock HTTP/browser fixtures in tests; no real applications in CI. No evasion or CAPTCHA bypass.

Done: relevant tests, lint and frontend build pass; documentation describes configuration and limitations; no secrets or generated personal data committed.
