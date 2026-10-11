from app.auth.service import Principal, require_user
from app.config import settings
from app.db import get_db
from app.media.serializers import cell_list, media_list, record
from app.models import AnalysisEvent, AnalysisRun, Asset, Cell, Collection, Media, Shelf
from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Search"])


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    match = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    media_stmt = select(Media).where(
        Media.library_id == p.library.id,
        or_(Media.title.ilike(match), Media.note.ilike(match), cast(Media.tags, String).ilike(match)),
    )
    cell_stmt = select(Cell).where(
        Cell.library_id == p.library.id,
        or_(Cell.title.ilike(match), Cell.note.ilike(match), cast(Cell.tags, String).ilike(match)),
    )
    event_stmt = (
        select(AnalysisEvent, Media.title)
        .join(Media)
        .join(AnalysisRun, AnalysisEvent.analysis_run_id == AnalysisRun.id)
        .where(
            Media.library_id == p.library.id,
            AnalysisRun.status == "COMPLETED",
            AnalysisRun.analyzer == "scenes",
            AnalysisEvent.label.ilike(match),
        )
    )
    counts = {
        name: db.scalar(select(func.count()).select_from(stmt.subquery()))
        for name, stmt in [
            ("media", media_stmt),
            ("cells", cell_stmt),
            ("events", event_stmt),
        ]
    }
    counts["transcripts"] = 0
    return {
        "media": media_list(
            db, list(db.scalars(media_stmt.order_by(Media.created_at.desc()).offset(offset).limit(limit)))
        ),
        "cells": cell_list(
            db, list(db.scalars(cell_stmt.order_by(Cell.created_at.desc()).offset(offset).limit(limit)))
        ),
        "transcripts": [],
        "events": [
            {**record(e, ["id", "media_id", "start_ms", "end_ms", "label"]), "media_title": title}
            for e, title in db.execute(
                event_stmt.order_by(AnalysisEvent.start_ms).offset(offset).limit(limit)
            )
        ],
        "counts": counts,
        "total": sum(counts.values()),
        "offset": offset,
        "limit": limit,
    }


@router.get("/library/stats")
def stats(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    count, size, duration = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(Media.size_bytes), 0),
            func.coalesce(func.sum(Media.duration_ms), 0),
        ).where(Media.library_id == p.library.id)
    ).one()
    assets_size = db.scalar(
        select(func.coalesce(func.sum(Asset.size_bytes), 0))
        .join(Media)
        .where(Media.library_id == p.library.id)
    )
    return {
        "media_count": count,
        "size_bytes": size,
        "stored_bytes": assets_size,
        "duration_ms": duration,
        "managed_count": db.scalar(
            select(func.count())
            .select_from(Media)
            .where(Media.library_id == p.library.id, Media.storage_mode == "MANAGED")
        ),
        "reference_count": db.scalar(
            select(func.count())
            .select_from(Media)
            .where(Media.library_id == p.library.id, Media.storage_mode == "REFERENCE")
        ),
        "limits": {
            "managed": settings.max_managed_items,
            "references": settings.max_reference_items,
            "cells": settings.max_cells,
            "cells_per_media": settings.max_cells_per_media,
            "clip_ms": settings.max_clip_ms,
            "analysis_runs": settings.max_analysis_runs,
        },
        "cell_count": db.scalar(
            select(func.count()).select_from(Cell).where(Cell.library_id == p.library.id)
        ),
        "shelf_count": db.scalar(
            select(func.count()).select_from(Shelf).where(Shelf.library_id == p.library.id)
        ),
        "collection_count": db.scalar(
            select(func.count()).select_from(Collection).where(Collection.library_id == p.library.id)
        ),
    }
