import hashlib
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from app.analysis.processing import ProcessingError, probe
from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.collections.routes import destination, place_media
from app.config import settings
from app.context import request_id
from app.db import get_db
from app.errors import problem
from app.jobs.service import ACTIVE, dispatch, ensure_capacity
from app.media.serializers import media_list
from app.models import Asset, Batch, Cell, Deletion, Job, Media, Source, collection_media, shelf_media
from app.schemas import MediaPatch
from app.storage.service import storage
from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/media", tags=["Media"])


def validate_header(name: str, header: bytes):
    suffix = Path(name).suffix.lower()
    if header[4:8] == b"ftyp" and suffix in {".mp4", ".mov", ".m4v"}:
        return "video/mp4"
    if header[:4] == b"\x1aE\xdf\xa3" and suffix in {".webm", ".mkv"}:
        return "video/webm" if suffix == ".webm" else "video/x-matroska"
    if header[:4] == b"RIFF" and header[8:12] == b"AVI " and suffix == ".avi":
        return "video/x-msvideo"
    problem(
        415,
        "UNSUPPORTED_MEDIA",
        "MP4・MOV・WebM・MKV・AVI形式の動画を選んでください。拡張子と内容が一致する必要があります。",
    )


@router.get("")
def list_media(
    q: str = Query("", max_length=200),
    favorite: bool = False,
    shelf_id: str | None = None,
    collection_id: str | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest|title)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    statement = select(Media).where(Media.library_id == p.library.id)
    if q.strip():
        match = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        statement = statement.where(
            or_(Media.title.ilike(match), Media.note.ilike(match), cast(Media.tags, String).ilike(match))
        )
    if favorite:
        statement = statement.where(Media.favorite.is_(True))
    if shelf_id:
        statement = statement.where(
            Media.id.in_(select(shelf_media.c.media_id).where(shelf_media.c.shelf_id == shelf_id))
        )
    if collection_id:
        statement = statement.where(
            Media.id.in_(
                select(collection_media.c.media_id).where(collection_media.c.collection_id == collection_id)
            )
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    ordering = (
        Media.title.asc()
        if sort == "title"
        else Media.created_at.asc()
        if sort == "oldest"
        else Media.created_at.desc()
    )
    items = list(db.scalars(statement.order_by(ordering, Media.id).offset(offset).limit(limit)))
    return {"items": media_list(db, items), "total": total, "offset": offset, "limit": limit}


@router.post("", status_code=201)
def upload(
    file: UploadFile = File(...),
    batch_id: str | None = Form(None),
    shelf_id: str | None = Form(None, max_length=36),
    collection_id: str | None = Form(None, max_length=36),
    reference_id: str | None = Form(None, max_length=36),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    rate_limit(f"upload:{p.user.id}", 120, 3600)
    if idempotency_key:
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            problem(400, "INVALID_IDEMPOTENCY_KEY", "リクエストの識別子が無効です。")
    ensure_capacity(db, p.library.id)
    selected = destination(db, p, shelf_id, collection_id)
    reference = owned(db, Media, reference_id, p) if reference_id else None
    if batch_id:
        owned(db, Batch, batch_id, p)
    size = 0
    checksum = hashlib.sha256()
    original_name = Path((file.filename or "video.mp4").replace("\\", "/")).name[:255]
    with TemporaryDirectory(prefix="lumvia-upload-") as directory:
        temporary = Path(directory) / "upload"
        with temporary.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    problem(413, "UPLOAD_TOO_LARGE", "動画は256 MB以下で追加してください。")
                checksum.update(chunk)
                output.write(chunk)
        if size < 16:
            problem(415, "INVALID_MEDIA", "動画ファイルを読み取れません。")
        with temporary.open("rb") as stream:
            mime = validate_header(original_name, stream.read(32))
        if idempotency_key:
            existing = db.scalar(
                select(Media).where(
                    Media.library_id == p.library.id, Media.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.content_sha256 != checksum.hexdigest():
                    problem(409, "IDEMPOTENCY_CONFLICT", "同じ識別子で異なる動画は追加できません。")
                if reference_id and existing.id != reference_id:
                    problem(409, "IDEMPOTENCY_CONFLICT", "同じ識別子で別のリンクへ追加することはできません。")
                place_media(db, p, selected, existing.id)
                db.commit()
                return media_list(db, [existing])[0]
        if reference and reference.storage_mode != "REFERENCE":
            problem(409, "ALREADY_MANAGED", "このリンクには動画ファイルが追加済みです。")
        used = db.scalar(
            select(func.coalesce(func.sum(Media.size_bytes), 0)).where(Media.library_id == p.library.id)
        )
        count = db.scalar(
            select(func.count())
            .select_from(Media)
            .where(Media.library_id == p.library.id, Media.storage_mode == "MANAGED")
        )
        if count >= settings.max_managed_items:
            problem(413, "MEDIA_COUNT_LIMIT", "動画ファイルは500本までです。不要な動画を削除してください。")
        if used + size > settings.max_library_bytes:
            problem(413, "STORAGE_LIMIT", "保存容量の上限に達しています。不要な動画を削除してください。")
        if reference:
            last_cell = db.scalar(select(func.max(Cell.end_ms)).where(Cell.media_id == reference.id))
            if last_cell:
                try:
                    info = probe(temporary, lambda: False)
                except ProcessingError as exc:
                    problem(422, exc.code, exc.message)
                if last_cell > info["duration_ms"]:
                    problem(
                        422,
                        "CELL_OUTSIDE_VIDEO",
                        "保存済みCellより短い動画です。Cellの区間を編集するか、対応する動画を選んでください。",
                    )
            source = db.get(Source, reference.source_id)
            source.original_name = original_name
            media = reference
            media.storage_mode, media.status = "MANAGED", "PROCESSING"
            media.size_bytes, media.idempotency_key = size, idempotency_key
            media.content_sha256 = checksum.hexdigest()
        else:
            source = Source(library_id=p.library.id, original_name=original_name)
            db.add(source)
            db.flush()
            media = Media(
                library_id=p.library.id,
                source_id=source.id,
                title=Path(original_name).stem[:200] or "無題の動画",
                size_bytes=size,
                idempotency_key=idempotency_key,
                content_sha256=checksum.hexdigest(),
            )
            db.add(media)
        db.flush()
        place_media(db, p, selected, media.id)
        key = f"{p.library.id}/{media.id}/original"
        try:
            storage.put(key, temporary, mime)
            db.add(Asset(media_id=media.id, key=key, role="original", mime=mime, size_bytes=size))
            job = Job(
                library_id=p.library.id,
                media_id=media.id,
                batch_id=batch_id,
                kind="ingest",
                request_id=request_id.get(),
            )
            db.add(job)
            audit(db, p.user.id, "media.uploaded", media.id)
            db.commit()
        except Exception:
            db.rollback()
            storage.delete(key)
            raise
    dispatch(job.id)
    return media_list(db, [media])[0]


@router.get("/{media_id}")
def get_media(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    return media_list(db, [owned(db, Media, media_id, p)])[0]


@router.patch("/{media_id}")
def update_media(
    media_id: str, data: MediaPatch, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    media = owned(db, Media, media_id, p)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(media, key, value)
    audit(db, p.user.id, "media.updated", media.id)
    db.commit()
    return media_list(db, [media])[0]


@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    media = owned(db, Media, media_id, p)
    # Serialize with new analysis jobs; a running processor must finish/cancel before asset deletion.
    db.scalar(select(Media).where(Media.id == media_id).with_for_update())
    active = db.scalar(select(Job).where(Job.media_id == media_id, Job.state.in_(ACTIVE)))
    if active:
        problem(409, "PROCESSING_ACTIVE", "処理をキャンセルし、停止してから削除してください。")
    keys = {asset.key for asset in db.scalars(select(Asset).where(Asset.media_id == media_id))}
    prefix = f"{media.library_id}/{media.id}"
    if media.storage_mode == "MANAGED":
        keys.update({prefix + "/original", prefix + "/thumbnail.jpg", prefix + "/preview.mp4"})
    for key in keys:
        db.add(Deletion(key=key))
    source = db.get(Source, media.source_id)
    audit(db, p.user.id, "media.deleted", media.id)
    db.delete(media)
    db.flush()
    db.delete(source)
    db.commit()
    from app.jobs.worker import purge_assets

    if keys:
        purge_assets()
