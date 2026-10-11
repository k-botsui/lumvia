from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.service import Principal, audit, rate_limit, require_user
from app.collections.routes import destination, place_media
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.media.covers import automatic_cover, save_cover
from app.media.serializers import media_list
from app.models import Library, Media, Source
from app.sources.adapters import fetch_metadata, parse_reference

router = APIRouter(tags=["Sources"])


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=200)
    shelf_id: str | None = Field(default=None, max_length=36)
    collection_id: str | None = Field(default=None, max_length=36)

    @field_validator("title")
    @classmethod
    def optional_title(cls, value):
        return value.strip() or None if value is not None else None


def existing_reference(db, library_id, ref):
    return db.scalar(
        select(Media)
        .join(Source)
        .where(
            Media.library_id == library_id, Source.kind == ref.provider, Source.external_id == ref.external_id
        )
    )


@router.post("/imports", status_code=201)
def import_link(
    data: ImportInput, response: Response, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    rate_limit(f"import:{p.user.id}", 60, 3600)
    selected = destination(db, p, data.shelf_id, data.collection_id)
    ref = parse_reference(data.url)
    existing = existing_reference(db, p.library.id, ref)
    if existing:
        place_media(db, p, selected, existing.id)
        db.commit()
        response.status_code = 200
        return {
            "media": media_list(db, [existing])[0],
            "created": False,
            "start_ms": ref.start_ms,
            "metadata_available": db.get(Source, existing.source_id).metadata_json.get(
                "metadata_available", False
            ),
        }
    metadata = fetch_metadata(ref)
    cover = automatic_cover(metadata)
    # Never hold a library lock during outbound network calls. Recheck under lock for races.
    db.scalar(select(Library).where(Library.id == p.library.id).with_for_update())
    existing = existing_reference(db, p.library.id, ref)
    if existing:
        place_media(db, p, selected, existing.id)
        db.commit()
        response.status_code = 200
        return {
            "media": media_list(db, [existing])[0],
            "created": False,
            "start_ms": ref.start_ms,
            "metadata_available": db.get(Source, existing.source_id).metadata_json.get(
                "metadata_available", False
            ),
        }
    count = db.scalar(
        select(func.count())
        .select_from(Media)
        .where(Media.library_id == p.library.id, Media.storage_mode == "REFERENCE")
    )
    if count >= settings.max_reference_items:
        problem(413, "REFERENCE_LIMIT", "リンクの保存上限に達しています。不要なリンクを削除してください。")
    title = data.title or metadata.get("title") or ref.fallback_title
    source = Source(
        library_id=p.library.id,
        kind=ref.provider,
        original_name=title,
        external_url=ref.url,
        external_id=ref.external_id,
        metadata_json=metadata,
    )
    db.add(source)
    db.flush()
    media = Media(
        library_id=p.library.id, source_id=source.id, title=title, storage_mode="REFERENCE", status="READY"
    )
    db.add(media)
    db.flush()
    audit(db, p.user.id, "source.referenced", media.id)
    place_media(db, p, selected, media.id)
    key = save_cover(db, media, cover) if cover else None
    try:
        db.commit()
    except Exception:
        db.rollback()
        if key:
            from app.storage.service import storage

            storage.delete(key)
        raise
    return {
        "media": media_list(db, [media])[0],
        "created": True,
        "start_ms": ref.start_ms,
        "metadata_available": metadata["metadata_available"],
    }
