import logging

from app.config import settings
from app.errors import problem
from app.models import Job, Library, now
from sqlalchemy import func, select

ACTIVE = {"PENDING", "QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"}
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
TRANSITIONS = {
    "PENDING": {"QUEUED", "RUNNING", "CANCELLED"},
    "QUEUED": {"RUNNING", "CANCELLED"},
    "RETRYING": {"QUEUED", "RUNNING", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "TIMED_OUT", "CANCEL_REQUESTED"},
    "CANCEL_REQUESTED": {"CANCELLED", "FAILED", "TIMED_OUT"},
    "FAILED": {"RETRYING"},
    "TIMED_OUT": {"RETRYING"},
    "CANCELLED": {"RETRYING"},
    "COMPLETED": set(),
}


def transition(job, state):
    if state not in TRANSITIONS.get(job.state, set()):
        raise ValueError(f"Invalid transition {job.state} -> {state}")
    job.state = state
    job.updated_at = now()
    if state in TERMINAL:
        job.completed_at = now()


def ensure_capacity(db, library_id):
    db.scalar(select(Library).where(Library.id == library_id).with_for_update())
    count = db.scalar(
        select(func.count()).select_from(Job).where(Job.library_id == library_id, Job.state.in_(ACTIVE))
    )
    if count >= settings.max_concurrent_jobs:
        problem(429, "QUEUE_FULL", "処理中の動画が多いため、完了後に追加してください。")


def dispatch(job_id):
    # The committed PostgreSQL row is the outbox. Beat retries delivery if the broker is unavailable.
    from app.jobs.worker import celery

    try:
        celery.send_task("lumvia.process", args=[job_id], retry=False)
    except Exception:
        logging.getLogger("lumvia").warning("job_dispatch_deferred", extra={"job_id": job_id})
