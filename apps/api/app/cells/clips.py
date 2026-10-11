from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from app.analysis.processing import ProcessingError, ffmpeg, probe, run_command
from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.cells.routes import validate_range
from app.db import get_db
from app.errors import problem
from app.models import Asset, Cell, Media
from app.storage.service import storage
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/cells", tags=["Clips"])


@router.post("/{cell_id}/clip")
def export_clip(cell_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"clip:{p.user.id}", 8, 3600)
    cell = owned(db, Cell, cell_id, p)
    media = owned(db, Media, cell.media_id, p)
    if media.storage_mode != "MANAGED":
        problem(
            409,
            "REFERENCE_UNSUPPORTED",
            "MP4の書き出しには動画ファイルが必要です。リンクの詳細から動画ファイルを追加してください。",
        )
    validate_range(media, cell.start_ms, cell.end_ms)
    # A transaction-scoped lock bounds CPU work across all API processes.
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(740032)")):
        problem(429, "CLIP_BUSY", "クリップを書き出し中です。完了してからお試しください。")
    asset = db.scalar(select(Asset).where(Asset.media_id == media.id, Asset.role == "preview"))
    if not asset:
        problem(409, "MEDIA_NOT_READY", "再生用ファイルが見つかりません。")
    directory = TemporaryDirectory(prefix="lumvia-clip-")
    output = Path(directory.name) / "clip.mp4"
    try:
        with storage.materialize(asset.key) as source:
            run_command(
                ffmpeg(
                    source,
                    "-ss",
                    cell.start_ms / 1000,
                    "-t",
                    (cell.end_ms - cell.start_ms) / 1000,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-sn",
                    "-dn",
                    "-map_metadata",
                    "-1",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-threads",
                    "1",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "96k",
                    "-movflags",
                    "+faststart",
                    "-fs",
                    64 * 1024 * 1024,
                    output,
                ),
                timeout=120,
            )
        if output.stat().st_size > 64 * 1024 * 1024:
            problem(413, "CLIP_LIMIT", "クリップのサイズ上限に達しました。短い区間でお試しください。")
        info = probe(output, lambda: False)
        if abs(info["duration_ms"] - (cell.end_ms - cell.start_ms)) > 1500:
            problem(413, "CLIP_LIMIT", "クリップのサイズ上限に達しました。短い区間でお試しください。")
        filename = cell.title.replace("\r", "").replace("\n", "")[:100] + ".mp4"
        audit(db, p.user.id, "cell.clip_exported", cell.id)
        db.commit()
    except ProcessingError as exc:
        directory.cleanup()
        problem(422, exc.code, exc.message)
    except Exception:
        directory.cleanup()
        raise

    def stream():
        try:
            with output.open("rb") as file:
                while chunk := file.read(65536):
                    yield chunk
        finally:
            directory.cleanup()

    return StreamingResponse(
        stream(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "attachment; filename=clip.mp4; filename*=UTF-8''"
            + quote(filename, safe=""),
            "Content-Length": str(output.stat().st_size),
            "Cache-Control": "private, no-store",
        },
    )
