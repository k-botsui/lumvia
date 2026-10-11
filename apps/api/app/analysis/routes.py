from app.analysis.analyzers import SceneAnalyzer, capabilities
from app.auth.service import Principal, audit, owned, require_user
from app.config import settings
from app.context import request_id
from app.db import get_db
from app.errors import problem
from app.jobs.service import ACTIVE, dispatch, ensure_capacity
from app.media.serializers import JOB_FIELDS, record
from app.models import AnalysisEvent, AnalysisRun, Job, Media
from app.schemas import AnalyzeInput
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Analysis"])


@router.get("/analysis/capabilities")
def get_capabilities(p: Principal = Depends(require_user)):
    return {"items": capabilities()}


@router.post("/media/{media_id}/analysis", status_code=202)
def analyze(
    media_id: str, data: AnalyzeInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    ensure_capacity(db, p.library.id)
    media = owned(db, Media, media_id, p)
    if media.storage_mode != "MANAGED":
        problem(
            409,
            "REFERENCE_UNSUPPORTED",
            "リンクで追加した動画では解析できません。動画ファイルを追加すると利用できます。",
        )
    db.scalar(select(Media).where(Media.id == media_id).with_for_update())
    if media.status != "READY":
        problem(409, "MEDIA_NOT_READY", "動画の準備が完了するまでお待ちください。")
    if not next(c for c in capabilities() if c["id"] == data.analyzer)["available"]:
        problem(409, "ANALYZER_UNAVAILABLE", "この解析はまだ設定されていません。")
    existing = db.scalar(
        select(Job).where(Job.media_id == media_id, Job.kind == data.analyzer, Job.state.in_(ACTIVE))
    )
    if existing:
        return record(existing, JOB_FIELDS)
    if (
        db.scalar(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.media_id == media_id, AnalysisRun.analyzer == "scenes")
        )
        >= settings.max_analysis_runs
    ):
        problem(413, "ANALYSIS_LIMIT", "解析履歴は動画ごとに10件までです。不要な履歴を削除してください。")
    run = AnalysisRun(
        media_id=media_id,
        analyzer=data.analyzer,
        model_version=SceneAnalyzer.version,
        configuration=SceneAnalyzer.configuration,
    )
    db.add(run)
    db.flush()
    job = Job(
        library_id=p.library.id,
        media_id=media_id,
        kind=data.analyzer,
        analysis_run_id=run.id,
        request_id=request_id.get(),
    )
    db.add(job)
    audit(db, p.user.id, "analysis.requested", media_id)
    db.commit()
    dispatch(job.id)
    return record(job, JOB_FIELDS)


@router.get("/media/{media_id}/analysis")
def results(
    media_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    owned(db, Media, media_id, p)
    runs = list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.media_id == media_id, AnalysisRun.analyzer == "scenes")
            .order_by(AnalysisRun.created_at.desc())
            .limit(50)
        )
    )
    completed = [r.id for r in runs if r.status == "COMPLETED"]
    events = list(
        db.scalars(
            select(AnalysisEvent)
            .where(AnalysisEvent.media_id == media_id, AnalysisEvent.analysis_run_id.in_(completed))
            .order_by(AnalysisEvent.start_ms)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    return {
        "runs": [
            record(
                r,
                ["id", "analyzer", "model_version", "configuration", "status", "created_at", "completed_at"],
            )
            for r in runs
        ],
        "events": [
            record(e, ["id", "analysis_run_id", "event_type", "start_ms", "end_ms", "label", "confidence"])
            for e in events[:limit]
        ],
        "transcripts": [],
        "has_more": len(events) > limit,
    }


@router.delete("/media/{media_id}/analysis/{run_id}", status_code=204)
def delete_run(
    media_id: str, run_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    owned(db, Media, media_id, p)
    run = db.get(AnalysisRun, run_id)
    if not run or run.media_id != media_id:
        problem(404, "NOT_FOUND", "解析が見つかりません。")
    if db.scalar(select(Job).where(Job.analysis_run_id == run_id, Job.state.in_(ACTIVE))):
        problem(409, "PROCESSING_ACTIVE", "処理を停止してから削除してください。")
    audit(db, p.user.id, "analysis.deleted", run_id)
    db.execute(delete(AnalysisRun).where(AnalysisRun.id == run_id))
    db.commit()
