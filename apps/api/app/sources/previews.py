"""Private, disposable scene-selection videos; never permanent library assets."""

import fcntl
import hashlib
import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.analysis.processing import ProcessingError, run_command
from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.models import Media, Source
from app.sources.public_video import MAX_VIDEO

router = APIRouter(prefix="/media", tags=["Media"])
TTL = 1800
MAX_CACHE = 256 * 1024 * 1024


def cache_root():
    root = settings.reference_preview_root
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


@contextmanager
def cache_lock():
    with (cache_root() / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            problem(429, "PREVIEW_BUSY", "別の動画の場面画像を準備しています。少し待ってからお試しください。")
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def read_entry(media_id, source_url):
    path = cache_root() / media_id
    try:
        data = json.loads((path / "info.json").read_text())
        if (
            data["expires_at"] <= time.time()
            or data["fingerprint"] != hashlib.sha256(source_url.encode()).hexdigest()
        ):
            return None
        video = path / "preview.mp4"
        if not video.is_file() or video.stat().st_size > MAX_VIDEO:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def prune_locked(reserve=0):
    entries = []
    for directory in cache_root().iterdir():
        if not directory.is_dir():
            continue
        try:
            data = json.loads((directory / "info.json").read_text())
            if data["expires_at"] <= time.time():
                raise ValueError("Expired")
            size = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
            entries.append((data["expires_at"], size, directory))
        except (OSError, ValueError, KeyError, TypeError):
            shutil.rmtree(directory, ignore_errors=True)
    size = sum(item[1] for item in entries)
    for _, amount, directory in sorted(entries):
        if size + reserve <= MAX_CACHE:
            break
        shutil.rmtree(directory, ignore_errors=True)
        size -= amount


def purge_previews():
    # Worker calls this even when the UI is closed. Skip an active fetch rather than interrupt it.
    from fastapi import HTTPException

    try:
        with cache_lock():
            prune_locked()
    except HTTPException:
        pass


def describe(media_id, entry):
    return {key: entry[key] for key in ("duration_ms", "width", "height", "expires_at")} | {
        "url": f"/api/v1/media/{media_id}/reference-preview",
    }


def reference(db, media_id, p):
    media = owned(db, Media, media_id, p)
    source = db.get(Source, media.source_id)
    if media.storage_mode != "REFERENCE" or source.kind not in {"youtube", "tiktok", "x", "instagram"}:
        problem(409, "PREVIEW_UNSUPPORTED", "この項目には一時プレビューを作成できません。")
    return media, source.external_url


@router.post("/{media_id}/reference-preview")
def prepare(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    media, source_url = reference(db, media_id, p)
    if entry := read_entry(media.id, source_url):
        return describe(media.id, entry)
    with cache_lock():
        if entry := read_entry(media.id, source_url):
            return describe(media.id, entry)
        rate_limit(f"reference-preview:{p.user.id}", 8, 3600)
        prune_locked(reserve=MAX_VIDEO * 2 + 65536)
        with TemporaryDirectory(prefix="fetch-", dir=cache_root()) as directory:
            try:
                output, _ = run_command(
                    [
                        sys.executable,
                        Path(__file__).with_name("preview_runner.py"),
                        source_url,
                        directory,
                        settings.ffmpeg_bin,
                        settings.ffprobe_bin,
                    ],
                    timeout=90,
                )
                info = json.loads(output)
                video = Path(directory) / "preview.mp4"
                if not video.is_file() or video.stat().st_size > MAX_VIDEO:
                    raise ValueError("Invalid preview")
            except (ProcessingError, ValueError, OSError):
                problem(
                    422,
                    "PUBLIC_PREVIEW_UNAVAILABLE",
                    "この公開動画を一時取得できませんでした。ログインが必要な投稿や配信形式によっては対応できません。元動画ファイルを追加すると場面画像を使えます。",
                )
            # A concurrent deletion or upload must not leave a new orphaned preview.
            db.expire_all()
            current, current_url = reference(db, media_id, p)
            if current_url != source_url:
                problem(409, "SOURCE_CHANGED", "リンクが更新されました。もう一度お試しください。")
            entry = info | {
                "expires_at": int(time.time()) + TTL,
                "fingerprint": hashlib.sha256(source_url.encode()).hexdigest(),
            }
            target = cache_root() / current.id
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir(mode=0o700)
            video.chmod(0o600)
            video.replace(target / "preview.mp4")
            metadata = target / "info.json"
            metadata.write_text(json.dumps(entry))
            metadata.chmod(0o600)
        audit(db, p.user.id, "reference.previewed", media_id)
        db.commit()
        return describe(media_id, entry)


@router.get("/{media_id}/reference-preview")
def get_preview(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    media, source_url = reference(db, media_id, p)
    if not read_entry(media.id, source_url):
        problem(
            404, "PREVIEW_EXPIRED", "一時プレビューの保存期限が切れました。場面画像を読み込み直してください。"
        )
    return FileResponse(
        cache_root() / media.id / "preview.mp4",
        media_type="video/mp4",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{media_id}/reference-preview/info")
def preview_info(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    media, source_url = reference(db, media_id, p)
    if entry := read_entry(media.id, source_url):
        return describe(media.id, entry)
    problem(404, "PREVIEW_EXPIRED", "一時プレビューは保存されていません。")
