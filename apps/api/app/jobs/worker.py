import json
import logging
import time
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from app.analysis.analyzers import SceneAnalyzer
from app.analysis.processing import (
    Cancelled,
    ProcessingError,
    can_remux,
    ffmpeg,
    probe,
    run_command,
    video_encoding,
)
from app.config import settings
from app.db import SessionLocal
from app.jobs.service import transition
from app.models import (
    AnalysisEvent,
    AnalysisRun,
    Asset,
    Deletion,
    Job,
    Media,
    Session,
    Source,
    Transcript,
    now,
)
from app.storage.service import storage
from celery import Celery
from sqlalchemy import delete, select

logger = logging.getLogger("lumvia.worker")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def job_log(event, job_id, request_id, **details):
    logger.info(json.dumps({"event": event, "job_id": job_id, "request_id": request_id, **details}))


celery = Celery("lumvia", broker=settings.broker_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    worker_enable_remote_control=False,
    worker_send_task_events=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_timer_precision=0.5,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    broker_pool_limit=0,
    broker_heartbeat=30,
    broker_transport_options={"confirm_publish": True, "read_timeout": 4, "write_timeout": 4},
    beat_max_loop_interval=5,
    task_soft_time_limit=settings.processing_timeout_seconds + 90,
    task_time_limit=settings.processing_timeout_seconds + 120,
    beat_schedule={
        "dispatch-outbox": {"task": "lumvia.dispatch", "schedule": 5.0, "options": {"expires": 10}}
    },
)


@celery.task(name="lumvia.dispatch")
def dispatch_pending(deliver=None, limit=50):
    with SessionLocal() as db:
        # A lease timeout recovers workers killed between durable state and broker acknowledgement.
        stale = list(
            db.scalars(
                select(Job)
                .where(
                    Job.state.in_(["RUNNING", "CANCEL_REQUESTED"]),
                    Job.updated_at < now() - timedelta(seconds=settings.processing_timeout_seconds + 180),
                )
                .with_for_update(skip_locked=True)
            )
        )
        for job in stale:
            transition(job, "CANCELLED" if job.state == "CANCEL_REQUESTED" else "TIMED_OUT")
            job.error_code, job.error_message = "WORKER_INTERRUPTED", "処理が中断されました。再試行できます。"
            if job.kind == "ingest":
                db.get(Media, job.media_id).status = "FAILED"
            if job.analysis_run_id:
                db.get(AnalysisRun, job.analysis_run_id).status = job.state
        db.execute(delete(Session).where(Session.expires_at < now()))
        db.commit()
        pending = list(
            db.scalars(
                select(Job)
                .where(
                    Job.state.in_(["PENDING", "RETRYING", "QUEUED"]),
                    Job.updated_at < now() - timedelta(seconds=10),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for job in pending:
            if job.state != "QUEUED":
                transition(job, "QUEUED")
            job.updated_at = now()
        ids = [j.id for j in pending]
        db.commit()
    for identifier in ids:
        if deliver is None:
            celery.send_task("lumvia.process", args=[identifier], retry=False)
        else:
            deliver(identifier)
    purge_assets()
    from app.sources.previews import purge_previews

    purge_previews()


def purge_assets():
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(Deletion).order_by(Deletion.created_at).limit(50).with_for_update(skip_locked=True)
            )
        )
        for entry in rows:
            try:
                storage.delete(entry.key)
                db.delete(entry)
            except Exception:
                entry.attempts += 1
                logger.warning("asset_cleanup_deferred", extra={"deletion_id": entry.id})
        db.commit()


def cancelled(job_id):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        return job is None or job.state == "CANCEL_REQUESTED"


def progress(job_id, amount):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job:
            job.progress = amount
            job.updated_at = now()
            db.commit()


def save_asset(db, media_id, role, key, path, mime):
    storage.put(key, path, mime)
    asset = db.scalar(select(Asset).where(Asset.media_id == media_id, Asset.role == role))
    if asset:
        if asset.key != key:
            db.add(Deletion(key=asset.key))
        asset.key, asset.mime, asset.size_bytes = key, mime, path.stat().st_size
    else:
        db.add(Asset(media_id=media_id, role=role, key=key, mime=mime, size_bytes=path.stat().st_size))


@celery.task(name="lumvia.process")
def process(job_id):
    started = time.monotonic()
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.state not in {"PENDING", "QUEUED", "RETRYING"}:
            return
        transition(job, "RUNNING")
        job.attempt += 1
        job.started_at = now()
        job.error_code = job.error_message = None
        if job.analysis_run_id:
            db.get(AnalysisRun, job.analysis_run_id).status = "RUNNING"
        media_id, kind, run_id = job.media_id, job.kind, job.analysis_run_id
        correlation = job.request_id
        db.commit()

    job_log("job_started", job_id, correlation, kind=kind)

    def check():
        return cancelled(job_id)

    try:
        if kind == "ingest":
            ingest(job_id, media_id, check)
        else:
            analyze(job_id, media_id, run_id, kind, check)
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.state == "CANCEL_REQUESTED":
                raise Cancelled()
            transition(job, "COMPLETED")
            job.progress = 100
            if kind == "ingest":
                db.get(Media, media_id).status = "READY"
            if run_id:
                run = db.get(AnalysisRun, run_id)
                run.status, run.completed_at = "COMPLETED", now()
            db.commit()
        job_log("job_completed", job_id, correlation, duration_ms=round((time.monotonic() - started) * 1000))
    except Cancelled:
        job_log("job_cancelled", job_id, correlation)
        fail(job_id, "CANCELLED", None, None)
    except ProcessingError as exc:
        job_log("job_processing_failed", job_id, correlation, error_code=exc.code)
        fail(job_id, "TIMED_OUT" if exc.code == "TIMED_OUT" else "FAILED", exc.code, exc.message)
    except Exception:
        # Raw exceptions can contain private storage paths, URLs, or media details.
        job_log("job_failed", job_id, correlation)
        fail(job_id, "FAILED", "PROCESSING_FAILED", "処理を完了できませんでした。再試行できます。")


def fail(job_id, state, code, message):
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job:
            return
        if job.state == "CANCEL_REQUESTED":
            state = "CANCELLED"
        transition(job, state)
        job.error_code, job.error_message = code, message
        if job.kind == "ingest":
            db.get(Media, job.media_id).status = "FAILED"
        if job.analysis_run_id:
            run = db.get(AnalysisRun, job.analysis_run_id)
            run.status, run.completed_at = state, now()
            db.execute(delete(AnalysisEvent).where(AnalysisEvent.analysis_run_id == run.id))
            db.execute(delete(Transcript).where(Transcript.analysis_run_id == run.id))
        db.commit()


def ingest(job_id, media_id, check):
    with SessionLocal() as db:
        asset = db.scalar(select(Asset).where(Asset.media_id == media_id, Asset.role == "original"))
        media = db.get(Media, media_id)
        prefix = f"{media.library_id}/{media.id}"
        key = asset.key
    with storage.materialize(key) as source, TemporaryDirectory(prefix="lumvia-ingest-") as directory:
        info = probe(source, check)
        progress(job_id, 15)
        thumbnail, preview = Path(directory) / "thumbnail.jpg", Path(directory) / "preview.mp4"
        run_command(
            ffmpeg(
                source,
                "-ss",
                min(1, info["duration_ms"] / 3000),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                "-q:v",
                "3",
                thumbnail,
            ),
            check,
            60,
        )
        progress(job_id, 35)
        if can_remux(source, check):
            run_command(
                ffmpeg(
                    source,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-sn",
                    "-dn",
                    "-map_metadata",
                    "-1",
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    "-fs",
                    settings.max_upload_bytes * 2,
                    preview,
                ),
                check,
            )
        else:
            run_command(
                ffmpeg(
                    source,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-sn",
                    "-dn",
                    "-map_metadata",
                    "-1",
                    "-vf",
                    r"scale=trunc(min(1280\,iw)/2)*2:-2",
                    *video_encoding(),
                    "-pix_fmt",
                    "yuv420p",
                    "-threads",
                    "2",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    "-fs",
                    settings.max_upload_bytes * 2,
                    preview,
                ),
                check,
            )
        # An output truncated by -fs is not a successful import.
        preview_info = probe(preview, check)
        if abs(preview_info["duration_ms"] - info["duration_ms"]) > 1500:
            raise ProcessingError(
                "PREVIEW_LIMIT", "プレビューのサイズ上限に達しました。短い動画でお試しください。"
            )
        if check():
            raise Cancelled()
        progress(job_id, 90)
        with SessionLocal() as db:
            media = db.get(Media, media_id)
            for field, value in info.items():
                setattr(media, field, value)
            source_record = db.get(Source, media.source_id)
            if not source_record.metadata_json.get("custom_cover"):
                save_asset(db, media_id, "thumbnail", prefix + "/thumbnail.jpg", thumbnail, "image/jpeg")
            save_asset(db, media_id, "preview", prefix + "/preview.mp4", preview, "video/mp4")
            db.commit()


def analyze(job_id, media_id, run_id, kind, check):
    # Reject previously queued model jobs as well as new requests. Never load a model.
    if kind != "scenes":
        raise ProcessingError("FEATURE_REMOVED", "この解析機能は現行版では利用できません。")
    with SessionLocal() as db:
        media = db.get(Media, media_id)
        duration = media.duration_ms
        asset = db.scalar(select(Asset).where(Asset.media_id == media_id, Asset.role == "preview"))
        key = asset.key
    with storage.materialize(key) as source:
        progress(job_id, 10)
        results = SceneAnalyzer().analyze(source, duration, check)
        if check():
            raise Cancelled()
        with SessionLocal() as db:
            db.execute(delete(AnalysisEvent).where(AnalysisEvent.analysis_run_id == run_id))
            for event in results:
                db.add(
                    AnalysisEvent(
                        media_id=media_id,
                        analysis_run_id=run_id,
                        event_type=event.event_type,
                        start_ms=event.start_ms,
                        end_ms=event.end_ms,
                        label=event.label,
                        confidence=event.confidence,
                        details=event.details or {},
                    )
                )
            db.commit()
