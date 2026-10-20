import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import config
from .db import initialize
from .models import Application, Board, Document, Event, Job, Profile, Settings, Task
from .schemas import Applicant, BoardInput, Policy


@asynccontextmanager
async def lifespan(app):
    app.state.sessions = initialize()
    yield


app = FastAPI(title="AutoApply AI", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or not secrets.compare_digest(credentials.credentials, config().api_token):
        raise HTTPException(401, "Valid API token required", headers={"WWW-Authenticate": "Bearer"})


def session(request: Request):
    with request.app.state.sessions() as db:
        yield db


def policy(db):
    row = db.get(Settings, 1)
    return Policy.model_validate(row.data if row else {})


def get_or_404(db, model, identifier):
    row = db.get(model, identifier)
    if not row:
        raise HTTPException(404, "Record not found")
    return row


def enqueue(db, kind, target):
    existing = db.scalar(
        select(Task).where(
            Task.kind == kind, Task.target_id == target, Task.status.in_(["pending", "running"])
        )
    )
    if existing:
        return existing
    task = Task(kind=kind, target_id=target)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/profile", dependencies=[Depends(authorize)])
def read_profile(db=Depends(session)):
    row = db.get(Profile, 1)
    return row.data if row else Applicant().model_dump()


@app.put("/api/profile", dependencies=[Depends(authorize)])
def save_profile(value: Applicant, db=Depends(session)):
    db.merge(Profile(id=1, data=value.model_dump()))
    db.commit()
    return value


@app.get("/api/settings", dependencies=[Depends(authorize)])
def read_settings(db=Depends(session)):
    return policy(db)


@app.put("/api/settings", dependencies=[Depends(authorize)])
def save_settings(value: Policy, db=Depends(session)):
    if value.auto_submit or not value.dry_run:
        raise HTTPException(422, "Live submissions are unavailable in this release; keep dry-run enabled")
    db.merge(Settings(id=1, data=value.model_dump()))
    db.commit()
    return value


@app.post("/api/stop", dependencies=[Depends(authorize)])
def stop(db=Depends(session)):
    value = policy(db).model_copy(update={"enabled": False, "emergency_stop": True})
    db.merge(Settings(id=1, data=value.model_dump()))
    db.add(Event(kind="emergency_stop", message="Automation stopped by user"))
    db.commit()
    return value


@app.get("/api/boards", dependencies=[Depends(authorize)])
def boards(db=Depends(session)):
    return list(db.scalars(select(Board).order_by(Board.id)))


@app.post("/api/boards", dependencies=[Depends(authorize)], status_code=201)
def add_board(value: BoardInput, db=Depends(session)):
    row = Board(**value.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Board already configured") from None
    db.refresh(row)
    return row


@app.post("/api/boards/{identifier}/discover", dependencies=[Depends(authorize)], status_code=202)
def queue_discovery(identifier: int, db=Depends(session)):
    get_or_404(db, Board, identifier)
    if policy(db).emergency_stop:
        raise HTTPException(409, "Clear emergency stop in settings first")
    return enqueue(db, "discovery", identifier)


@app.get("/api/jobs", dependencies=[Depends(authorize)])
def jobs(q: str = "", limit: int = 100, db=Depends(session)):
    statement = select(Job).order_by(Job.id.desc()).limit(min(max(limit, 1), 500))
    if q:
        statement = statement.where(Job.title.ilike(f"%{q}%") | Job.employer.ilike(f"%{q}%"))
    return list(db.scalars(statement))


@app.post("/api/jobs/{identifier}/score", dependencies=[Depends(authorize)], status_code=202)
def queue_score(identifier: int, db=Depends(session)):
    get_or_404(db, Job, identifier)
    if not db.get(Profile, 1):
        raise HTTPException(409, "Save your profile first")
    if policy(db).emergency_stop:
        raise HTTPException(409, "Clear emergency stop first")
    return enqueue(db, "matching", identifier)


@app.post("/api/jobs/{identifier}/prepare", dependencies=[Depends(authorize)], status_code=202)
def queue_prepare(identifier: int, db=Depends(session)):
    get_or_404(db, Job, identifier)
    profile = db.get(Profile, 1)
    if not profile or not Applicant.model_validate(profile.data).verified:
        raise HTTPException(409, "Verify and save your profile first")
    if policy(db).emergency_stop:
        raise HTTPException(409, "Clear emergency stop first")
    return enqueue(db, "documents", identifier)


@app.get("/api/documents", dependencies=[Depends(authorize)])
def documents(db=Depends(session)):
    return [
        {"id": d.id, "job_id": d.job_id, "created_at": d.created_at}
        for d in db.scalars(select(Document).order_by(Document.id.desc()))
    ]


@app.post("/api/jobs/{identifier}/dry-run", dependencies=[Depends(authorize)], status_code=202)
def queue_browser(identifier: int, db=Depends(session)):
    from .browser import validate_url

    job = get_or_404(db, Job, identifier)
    current = policy(db)
    profile = db.get(Profile, 1)
    if current.emergency_stop or not profile or not Applicant.model_validate(profile.data).verified:
        raise HTTPException(409, "Clear emergency stop and verify your profile first")
    if job.expired:
        raise HTTPException(409, "Posting is expired")
    try:
        validate_url(job.url, job.provider, current.allowed_hosts)
    except (ValueError, OSError):
        raise HTTPException(
            422, "Set an authorized supported ATS hostname before running browser inspection"
        ) from None
    return enqueue(db, "browser", identifier)


@app.get("/api/documents/{identifier}/download", dependencies=[Depends(authorize)])
def download(identifier: int, db=Depends(session)):
    doc = get_or_404(db, Document, identifier)
    return FileResponse(doc.path, media_type="application/pdf", filename=f"resume-{doc.id}.pdf")


@app.get("/api/applications", dependencies=[Depends(authorize)])
def applications(db=Depends(session)):
    return list(db.scalars(select(Application).order_by(Application.id.desc()).limit(500)))


@app.get("/api/activity", dependencies=[Depends(authorize)])
def activity(db=Depends(session)):
    return {
        "tasks": list(db.scalars(select(Task).order_by(Task.id.desc()).limit(100))),
        "events": list(db.scalars(select(Event).order_by(Event.id.desc()).limit(100))),
    }


@app.get("/api/overview", dependencies=[Depends(authorize)])
def overview(db=Depends(session)):
    jobs = list(db.scalars(select(Job)))
    apps = list(db.scalars(select(Application)))
    return {
        "discovered": len(jobs),
        "matched": sum(bool(j.match and j.match["score"] >= 65) for j in jobs),
        "prepared": len(apps),
        "submitted": sum(a.status == "submitted" for a in apps),
        "mode": "Dry run",
        "emergency_stop": policy(db).emergency_stop,
    }
