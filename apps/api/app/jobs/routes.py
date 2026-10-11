from app.auth.service import Principal, audit, owned, require_user
from app.db import get_db
from app.errors import problem
from app.jobs.service import ACTIVE, dispatch, ensure_capacity, transition
from app.media.serializers import JOB_FIELDS, record
from app.models import AnalysisRun, Batch, Job, Media
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Progress"])


@router.get("/jobs")
def jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Job, Media.title).join(Media, Job.media_id == Media.id).where(Job.library_id == p.library.id)
    )
    return {
        "items": [
            {**record(j, JOB_FIELDS), "media_title": title}
            for j, title in db.execute(stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit))
        ],
        "total": db.scalar(select(func.count()).select_from(Job).where(Job.library_id == p.library.id)),
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    return record(owned(db, Job, job_id, p), JOB_FIELDS)


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    job = owned(db, Job, job_id, p)
    db.refresh(job, with_for_update=True)
    if job.state in {"PENDING", "QUEUED", "RETRYING"}:
        transition(job, "CANCELLED")
        if job.kind == "ingest":
            db.get(Media, job.media_id).status = "FAILED"
        if job.analysis_run_id:
            db.get(AnalysisRun, job.analysis_run_id).status = "CANCELLED"
    elif job.state == "RUNNING":
        transition(job, "CANCEL_REQUESTED")
    audit(db, p.user.id, "job.cancel_requested", job.id)
    db.commit()
    return record(job, JOB_FIELDS)


@router.post("/jobs/{job_id}/retry")
def retry(job_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    ensure_capacity(db, p.library.id)
    job = owned(db, Job, job_id, p)
    db.refresh(job, with_for_update=True)
    if job.state not in {"FAILED", "TIMED_OUT", "CANCELLED"}:
        problem(409, "JOB_NOT_RETRYABLE", "この処理は再試行できません。")
    if job.attempt >= 3:
        problem(409, "RETRY_LIMIT", "再試行の上限に達しました。動画や解析設定を確認してください。")
    if db.scalar(
        select(Job).where(Job.media_id == job.media_id, Job.kind == job.kind, Job.state.in_(ACTIVE))
    ):
        problem(409, "PROCESSING_ACTIVE", "すでに同じ処理が進行中です。")
    if job.kind not in {"ingest", "scenes"}:
        problem(409, "FEATURE_REMOVED", "この解析機能は現行版では利用できません。")
    transition(job, "RETRYING")
    job.progress, job.error_code, job.error_message = 0, None, None
    if job.kind == "ingest":
        db.get(Media, job.media_id).status = "PROCESSING"
    if job.analysis_run_id:
        db.get(AnalysisRun, job.analysis_run_id).status = "PENDING"
    audit(db, p.user.id, "job.retried", job.id)
    db.commit()
    dispatch(job.id)
    return record(job, JOB_FIELDS)


@router.post("/batches", status_code=201)
def create_batch(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    batch = Batch(library_id=p.library.id)
    db.add(batch)
    db.commit()
    return {"id": batch.id}


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    owned(db, Batch, batch_id, p)
    counts = dict(
        db.execute(select(Job.state, func.count()).where(Job.batch_id == batch_id).group_by(Job.state)).all()
    )
    return {"id": batch_id, "total": sum(counts.values()), "states": counts}
