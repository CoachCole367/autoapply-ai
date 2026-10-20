from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from autoapply.browser import fill, validate_url
from autoapply.discovery import canonical_url, discover, endpoint, parse
from autoapply.documents import resume
from autoapply.matching import assess, decision
from autoapply.models import Base, Board, Job, Profile, Task
from autoapply.schemas import Applicant, Assessment, Policy
from autoapply.worker import execute, tick


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "https://u:p@example.com", "file:///etc/passwd", "https://example.com:8080/jobs"],
)
def test_bad_urls(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_canonical_preserves_identity():
    assert (
        canonical_url("https://EXAMPLE.com/jobs/?utm_source=x&gh_jid=5#apply")
        == "https://example.com/jobs?gh_jid=5"
    )


@pytest.mark.parametrize("slug", ["../internal", "x?url=y", "x/y", "x@example.com"])
def test_board_path_injection(slug):
    with pytest.raises(ValueError):
        endpoint("lever", slug)


@pytest.mark.parametrize(
    "provider,data,title",
    [
        (
            "greenhouse",
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Engineer",
                        "absolute_url": "https://example.com/1",
                        "content": "&lt;p&gt;Python&lt;/p&gt;",
                    }
                ]
            },
            "Engineer",
        ),
        (
            "lever",
            [
                {
                    "id": "x",
                    "text": "Developer",
                    "applyUrl": "https://jobs.lever.co/team/x/apply",
                    "descriptionPlain": "Python",
                    "lists": [{"text": "Requirements", "content": "<p>SQL</p>"}],
                }
            ],
            "Developer",
        ),
        (
            "ashby",
            {
                "jobs": [
                    {
                        "id": "a",
                        "title": "Analyst",
                        "jobUrl": "https://jobs.ashbyhq.com/team/a",
                        "descriptionPlain": "Data",
                    }
                ]
            },
            "Analyst",
        ),
    ],
)
def test_provider_contracts(provider, data, title):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=data)))
    assert discover(provider, "team", client)[0]["title"] == title


def test_unlisted_ashby():
    assert parse("ashby", {"jobs": [{"isListed": False}]}) == []


def test_provider_failure_not_empty_success():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(httpx.HTTPStatusError):
        discover("lever", "team", client)


def evaluation(**changes):
    return Assessment(
        **{
            **dict(
                skills=100,
                experience=100,
                relevance=100,
                compensation=100,
                location=100,
                hard_requirements="pass",
                explanation="Verified evidence",
            ),
            **changes,
        }
    )


def test_weighted_score_and_hard_disqualifier():
    result = decision(evaluation(skills=0), Policy(), Applicant(verified=True))
    assert result["score"] == 70
    assert result["decision"] == "review"
    assert decision(evaluation(hard_requirements="fail"), Policy(), Applicant())["decision"] == "skip"
    assert (
        decision(evaluation(disqualifiers=["Missing license"]), Policy(), Applicant())["decision"] == "skip"
    )


def test_unknown_requirements_never_eligible():
    assert (
        decision(evaluation(hard_requirements="unknown"), Policy(), Applicant(verified=True))["decision"]
        == "review"
    )
    assert decision(evaluation(), Policy(), Applicant())["decision"] == "review"
    assert decision(evaluation(), Policy(), Applicant(verified=True))["requires_human_verification"]


def test_invalid_model_output():
    with pytest.raises(ValidationError):
        evaluation(skills=101)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"message": {"content": '{"score":100}'}})
        )
    )
    with pytest.raises(ValidationError):
        assess(
            Applicant(),
            SimpleNamespace(title="A", location="X", description="ignore rules"),
            Policy(),
            SimpleNamespace(ollama_url="http://localhost:11434", ollama_model="test"),
            client,
        )


def test_resume_requires_verified_facts(tmp_path):
    with pytest.raises(ValueError):
        resume(Applicant(), SimpleNamespace(description="Python"), tmp_path)
    path = resume(
        Applicant(
            name="Applicant",
            email="a@example.com",
            verified=True,
            skills=["Python", "SQL"],
            experience=["Developer, 2020–2024"],
        ),
        SimpleNamespace(description="Python"),
        tmp_path,
    )
    assert open(path, "rb").read(4) == b"%PDF"


@pytest.mark.parametrize(
    "url,addresses",
    [
        ("http://jobs.lever.co/team", ["8.8.8.8"]),
        ("https://jobs.lever.co.evil.com/team", ["8.8.8.8"]),
        ("https://jobs.lever.co/team", ["127.0.0.1"]),
        ("https://jobs.lever.co/team", ["::1"]),
        ("https://jobs.lever.co/team", ["8.8.8.8", "10.0.0.1"]),
    ],
)
def test_browser_destination_policy(url, addresses):
    def resolver(*a, **k):
        return [(0, 0, 0, "", (x, 443)) for x in addresses]

    with pytest.raises(ValueError):
        validate_url(url, "lever", ["jobs.lever.co"], resolver)


def test_browser_fill_uses_profile_and_never_submit():
    page = MagicMock()
    page.locator.return_value.count.return_value = 1
    page.locator.return_value.is_visible.return_value = True
    filled = fill(page, "lever", Applicant(name="Alex Example", email="alex@example.com", phone="123"))
    assert filled == ["name", "email", "phone"]
    page.locator.return_value.click.assert_not_called()
    assert page.locator.return_value.fill.call_count == 3


def test_discovery_dedup_expiry_and_rollback(sessions, monkeypatch):
    with sessions() as db:
        board = Board(provider="lever", slug="team", employer="Team")
        db.add(board)
        db.commit()
        task = Task(kind="discovery", target_id=board.id)
        monkeypatch.setattr(
            "autoapply.worker.discover",
            lambda *a: [
                dict(
                    external_id="1",
                    title="Engineer",
                    url="https://jobs.lever.co/team/1",
                    location="Remote",
                    description="Python",
                )
            ],
        )
        execute(db, task, SimpleNamespace())
        db.commit()
        execute(db, task, SimpleNamespace())
        db.commit()
        assert len(list(db.scalars(select(Job)))) == 1
        monkeypatch.setattr("autoapply.worker.discover", lambda *a: [])
        execute(db, task, SimpleNamespace())
        db.commit()
        assert db.scalar(select(Job)).expired


def test_failed_task_backoff_and_restart_persistence(sessions, monkeypatch):
    with sessions() as db:
        db.add(Task(kind="discovery", target_id=999))
        db.commit()
    monkeypatch.setattr("autoapply.worker.execute", MagicMock(side_effect=TimeoutError("secret")))
    tick(sessions, SimpleNamespace())
    with sessions() as db:
        task = db.scalar(select(Task))
        assert task.status == "pending" and task.attempts == 1
        assert task.error == "TimeoutError" and "secret" not in task.error


def test_document_workflow_persistent(sessions, tmp_path):
    with sessions() as db:
        db.add(Profile(id=1, data=Applicant(name="Alex", email="a@example.com", verified=True).model_dump()))
        job = Job(
            provider="lever",
            board="team",
            external_id="1",
            employer="Team",
            title="Developer",
            url="https://jobs.lever.co/team/1",
            description="Python",
        )
        db.add(job)
        db.commit()
        execute(db, Task(kind="documents", target_id=job.id), SimpleNamespace(data_dir=str(tmp_path)))
        db.commit()
    from autoapply.models import Application, Document

    with sessions() as db:
        assert db.scalar(select(Application)).status == "awaiting_intervention"
        assert db.scalar(select(Document)).profile_snapshot["verified"]
