"""Single persistent worker. Run exactly one instance until database leases are implemented."""

import signal
import time
from datetime import timedelta

from sqlalchemy import select

from .browser import dry_run
from .config import config
from .db import initialize
from .discovery import discover
from .documents import resume
from .main import policy
from .matching import assess
from .models import Application, Board, Document, Event, Job, Profile, Task, now
from .schemas import Applicant


def execute(db, task, settings):
    current = policy(db)
    if current.emergency_stop:
        return False
    if task.kind == "discovery":
        board = db.get(Board, task.target_id)
        rows = discover(board.provider, board.slug)
        existing = {
            j.external_id: j
            for j in db.scalars(select(Job).where(Job.provider == board.provider, Job.board == board.slug))
        }
        seen = set()
        for value in rows:
            seen.add(value["external_id"])
            job = existing.get(value["external_id"])
            if job:
                changed = any(getattr(job, k) != v for k, v in value.items())
                for key, val in value.items():
                    setattr(job, key, val)
                job.expired = False
                if changed:
                    job.match = None
            else:
                job = Job(provider=board.provider, board=board.slug, employer=board.employer, **value)
                db.add(job)
            db.flush()
            if (
                current.enabled
                and job.match is None
                and board.employer.casefold() not in {x.casefold() for x in current.blocked_employers}
                and db.get(Profile, 1)
            ):
                if not db.scalar(
                    select(Task).where(
                        Task.kind == "matching",
                        Task.target_id == job.id,
                        Task.status.in_(["pending", "running"]),
                    )
                ):
                    db.add(Task(kind="matching", target_id=job.id))
        for identifier, job in existing.items():
            if identifier not in seen:
                job.expired = True
        db.add(Event(kind="discovery", message=f"Board {board.id}: {len(rows)} postings synchronized"))
    elif task.kind == "matching":
        job = db.get(Job, task.target_id)
        profile = Applicant.model_validate(db.get(Profile, 1).data)
        job.match = assess(profile, job, current, settings)
        db.add(Event(kind="matching", message=f"Job {job.id}: match evaluation saved"))
    elif task.kind == "documents":
        job = db.get(Job, task.target_id)
        profile = Applicant.model_validate(db.get(Profile, 1).data)
        path = resume(profile, job, settings.data_dir)
        db.add(Document(job_id=job.id, profile_snapshot=profile.model_dump(), path=path))
        app = db.scalar(select(Application).where(Application.job_id == job.id))
        if not app:
            app = Application(
                job_id=job.id, status="awaiting_intervention", details={"reason": "Resume ready for review"}
            )
            db.add(app)
            db.flush()
        db.add(Event(application_id=app.id, kind="documents", message="Verified resume version generated"))
    elif task.kind == "browser":
        job = db.get(Job, task.target_id)
        if job.expired:
            raise ValueError("Expired job")
        profile = Applicant.model_validate(db.get(Profile, 1).data)
        app = db.scalar(select(Application).where(Application.job_id == job.id))
        if app and app.status in {"submitted", "submission_unverified"}:
            raise ValueError("Application already submitted or unresolved")
        result = dry_run(job, profile, current, settings.data_dir)
        if not app:
            app = Application(job_id=job.id)
            db.add(app)
        app.status = "awaiting_intervention"
        app.details = result
        app.updated_at = now()
        db.flush()
        db.add(Event(application_id=app.id, kind="browser", message="Dry run paused for manual review"))
    else:
        raise ValueError("Unknown task kind")
    return True


def tick(sessions, settings):
    with sessions() as db:
        if policy(db).emergency_stop:
            return
        current = policy(db)
        if current.enabled:
            for board in db.scalars(select(Board)):
                latest = db.scalar(
                    select(Task)
                    .where(Task.kind == "discovery", Task.target_id == board.id)
                    .order_by(Task.id.desc())
                )
                # Compare naive UTC because SQLite does not preserve timezone metadata.
                due = not latest or (
                    latest.status in {"done", "failed"}
                    and latest.available_at.replace(tzinfo=None)
                    < (now() - timedelta(hours=current.interval_hours)).replace(tzinfo=None)
                )
                if due:
                    db.add(Task(kind="discovery", target_id=board.id))
            db.commit()
        task = db.scalar(
            select(Task)
            .where(Task.status == "pending", Task.available_at <= now())
            .order_by(Task.id)
            .limit(1)
        )
        if not task:
            return
        task.status = "running"
        task.attempts += 1
        db.commit()
        identifier = task.id
        try:
            if execute(db, task, settings):
                task.status = "done"
                task.error = None
            else:
                task.status = "pending"
            db.commit()
        except Exception as exc:
            db.rollback()
            task = db.get(Task, identifier)
            task.error = type(exc).__name__  # No URLs, prompts or PII in logs.
            task.status = "failed" if task.attempts >= 3 or task.kind == "browser" else "pending"
            task.available_at = now() + timedelta(seconds=30 * 2**task.attempts)
            db.add(Event(kind="task_error", message=f"Task {identifier}: {type(exc).__name__}"))
            db.commit()


def main():
    settings = config()
    sessions = initialize()
    # Only read-only discovery, evaluation and document generation are replayed.
    with sessions() as db:
        for task in db.scalars(select(Task).where(Task.status == "running")):
            task.status = "failed" if task.kind == "browser" else "pending"
        db.commit()
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        tick(sessions, settings)
        for _ in range(50):
            if not running:
                break
            time.sleep(0.1)


if __name__ == "__main__":
    main()
