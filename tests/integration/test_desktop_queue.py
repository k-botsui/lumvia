from datetime import timedelta

from app.config import settings
from app.db import SessionLocal
from app.jobs.service import dispatch
from app.jobs.worker import dispatch_pending, process
from app.models import Job, now
from sqlalchemy import select


def test_desktop_outbox_recovers_deferred_job_once(client, sample, monkeypatch):
    monkeypatch.setattr(settings, "job_executor", "desktop")
    calls = []
    monkeypatch.setattr("app.jobs.worker.celery.send_task", lambda *args, **kwargs: calls.append(args))
    result = client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes(), "video/mp4")})
    assert result.status_code == 201
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.media_id == result.json()["id"]))
        identifier = job.id
        job.updated_at = now() - timedelta(seconds=20)
        db.commit()
    dispatch(identifier)
    assert calls == []
    delivered = []
    dispatch_pending.run(deliver=delivered.append, limit=1)
    assert delivered == [identifier]
    dispatch_pending.run(deliver=delivered.append, limit=1)
    assert delivered == [identifier]  # The dispatch lease bounds duplicate delivery.
    process.run(identifier)
    process.run(identifier)  # A duplicate cannot process a completed row again.
    with SessionLocal() as db:
        job = db.get(Job, identifier)
        assert job.state == "COMPLETED"
        assert job.attempt == 1


def test_desktop_interrupt_keeps_retryable_job(client, sample, monkeypatch):
    monkeypatch.setattr(settings, "processing_timeout_seconds", 1)
    result = client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes(), "video/mp4")})
    assert result.status_code == 201
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.media_id == result.json()["id"]))
        identifier = job.id
        job.state = "RUNNING"
        job.updated_at = now() - timedelta(seconds=200)
        db.commit()
    dispatch_pending.run(deliver=lambda _: None, limit=1)
    with SessionLocal() as db:
        job = db.get(Job, identifier)
        assert job.state == "TIMED_OUT"
        assert job.error_code == "WORKER_INTERRUPTED"
    assert client.post(f"/api/v1/jobs/{identifier}/retry").status_code == 200
