from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin
from uuid import uuid4

from app.analysis.processing import ProcessingError, ffmpeg, run_command
from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.db import get_db
from app.errors import problem
from app.media.images import jpeg, read_upload
from app.media.serializers import media_list
from app.models import Asset, Deletion, Media, Source
from app.sources import network
from app.sources.adapters import fetch_metadata, parse_reference
from app.storage.service import storage
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

router = APIRouter(prefix="/media", tags=["Covers"])


class FrameCover(BaseModel):
    position_ms: int = Field(ge=0)


@router.post("/{media_id}/frame-cover")
def frame_cover(
    media_id: str, request: FrameCover, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    rate_limit(f"cover:{p.user.id}", 30, 3600)
    media = owned(db, Media, media_id, p)
    if media.status != "READY" or media.storage_mode != "MANAGED":
        problem(409, "MEDIA_NOT_READY", "保存済みの動画の準備が完了してから設定してください。")
    if request.position_ms >= media.duration_ms:
        problem(422, "INVALID_FRAME", "動画の範囲内の場面を選んでください。")
    asset = db.scalar(select(Asset).where(Asset.media_id == media.id, Asset.role == "original"))
    if not asset:
        problem(409, "MEDIA_NOT_READY", "元動画を確認できませんでした。")
    with storage.materialize(asset.key) as source, TemporaryDirectory(prefix="lumvia-cover-") as directory:
        output = Path(directory) / "cover.jpg"
        try:
            run_command(
                ffmpeg(
                    source,
                    "-ss",
                    request.position_ms / 1000,
                    "-map",
                    "0:v:0",
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=960:960:force_original_aspect_ratio=decrease",
                    "-pix_fmt",
                    "yuvj420p",
                    "-q:v",
                    "3",
                    output,
                ),
                timeout=60,
            )
        except ProcessingError:
            problem(422, "FRAME_UNAVAILABLE", "この場面を画像にできませんでした。別の場面を選んでください。")
        if not output.exists() or not output.stat().st_size:
            problem(422, "FRAME_UNAVAILABLE", "この場面を画像にできませんでした。別の場面を選んでください。")
        clean = Path(directory) / "clean.jpg"
        jpeg(output.read_bytes(), clean)
        key = save_cover(db, media, clean.read_bytes())
    try:
        db.get(Source, media.source_id).metadata_json = {
            **db.get(Source, media.source_id).metadata_json,
            "custom_cover": True,
        }
        audit(db, p.user.id, "cover.updated", media.id)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return media_list(db, [media])[0]


def automatic_cover(metadata):
    url = metadata.get("thumbnail_url")
    if not isinstance(url, str) or not network.valid_image_url(url):
        return None
    try:
        for _ in range(3):
            status, headers, body = network.request(url, image=True)
            if status == 200 and headers.get("content-type", "").startswith("image/"):
                with TemporaryDirectory(prefix="lumvia-cover-") as directory:
                    output = Path(directory) / "cover.jpg"
                    jpeg(body, output)
                    return output.read_bytes()
            if status not in {301, 302, 303, 307, 308}:
                break
            url = urljoin(url, headers.get("location", ""))
            if not network.valid_image_url(url):
                break
    except (network.FetchError, HTTPException):
        pass
    return None


def save_cover(db, media, data):
    # Media lock serializes replacement; cleanup records recover storage failures.
    db.scalar(select(Media).where(Media.id == media.id).with_for_update())
    old = db.scalar(select(Asset).where(Asset.media_id == media.id, Asset.role == "thumbnail"))
    key = f"{media.library_id}/{media.id}/cover-{uuid4()}.jpg"
    with TemporaryDirectory(prefix="lumvia-cover-") as directory:
        path = Path(directory) / "cover.jpg"
        path.write_bytes(data)
        try:
            storage.put(key, path, "image/jpeg")
            if old:
                db.add(Deletion(key=old.key))
                old.key, old.mime, old.size_bytes = key, "image/jpeg", len(data)
            else:
                db.add(
                    Asset(
                        media_id=media.id, role="thumbnail", key=key, mime="image/jpeg", size_bytes=len(data)
                    )
                )
            db.flush()
        except Exception:
            storage.delete(key)
            raise
    return key


@router.put("/{media_id}/cover")
def upload_cover(
    media_id: str,
    file: UploadFile = File(...),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    rate_limit(f"cover:{p.user.id}", 30, 3600)
    media = owned(db, Media, media_id, p)
    if media.status != "READY":
        problem(409, "MEDIA_NOT_READY", "動画の準備が完了してから設定してください。")
    with TemporaryDirectory(prefix="lumvia-cover-") as directory:
        output = Path(directory) / "cover.jpg"
        jpeg(read_upload(file), output)
        key = save_cover(db, media, output.read_bytes())
    try:
        source = db.get(Source, media.source_id)
        source.metadata_json = {**source.metadata_json, "custom_cover": True}
        audit(db, p.user.id, "cover.updated", media.id)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return media_list(db, [media])[0]


@router.post("/{media_id}/reference-cover")
def refresh_cover(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"cover:{p.user.id}", 30, 3600)
    media = owned(db, Media, media_id, p)
    if media.storage_mode != "REFERENCE":
        problem(409, "NOT_REFERENCE", "リンクとして保存した動画で利用できます。")
    source = db.get(Source, media.source_id)
    if source.metadata_json.get("custom_cover"):
        return media_list(db, [media])[0]
    metadata = fetch_metadata(parse_reference(source.external_url))
    data = automatic_cover(metadata)
    if not data:
        problem(
            409,
            "COVER_UNAVAILABLE",
            "画像を取得できませんでした。「カバーを選ぶ」で好きな画像を設定できます。",
        )
    # Recheck the custom-cover flag under lock so a slow fetch cannot overwrite the user's choice.
    db.scalar(select(Media).where(Media.id == media.id).with_for_update())
    db.refresh(source)
    if source.metadata_json.get("custom_cover"):
        return media_list(db, [media])[0]
    key = save_cover(db, media, data)
    try:
        source.metadata_json = {**source.metadata_json, **metadata}
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return media_list(db, [media])[0]
