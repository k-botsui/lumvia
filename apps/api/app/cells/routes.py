from app.auth.service import Principal, audit, owned, require_user
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.media.serializers import cell_list
from app.models import (
    AnalysisEvent,
    Cell,
    Library,
    Media,
    Shelf,
    collection_cells,
    collection_media,
    shelf_cells,
    shelf_media,
)
from app.schemas import CellInput, CellPatch
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

router = APIRouter(prefix="/cells", tags=["Cells"])


def validate_range(media, start_ms, end_ms):
    if media.status != "READY":
        problem(409, "MEDIA_NOT_READY", "動画の準備が完了してからCellを作成してください。")
    maximum = media.duration_ms if media.storage_mode == "MANAGED" else settings.max_duration_ms
    if not 0 <= start_ms < end_ms <= maximum:
        problem(422, "INVALID_RANGE", "開始と終了を動画の長さの範囲内で指定してください。")
    if end_ms - start_ms > settings.max_clip_ms:
        problem(422, "CLIP_TOO_LONG", "Cellは5分以内の区間で保存してください。")


@router.get("")
def list_cells(
    media_id: str | None = None,
    collection_id: str | None = None,
    shelf_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    p: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    stmt = select(Cell).where(Cell.library_id == p.library.id)
    if media_id:
        owned(db, Media, media_id, p)
        stmt = stmt.where(Cell.media_id == media_id)
    if collection_id:
        stmt = stmt.where(
            Cell.id.in_(
                select(collection_cells.c.cell_id).where(collection_cells.c.collection_id == collection_id)
            )
        )
    if shelf_id:
        owned(db, Shelf, shelf_id, p)
        stmt = stmt.where(
            Cell.id.in_(select(shelf_cells.c.cell_id).where(shelf_cells.c.shelf_id == shelf_id))
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = (
        stmt.order_by(Cell.start_ms, Cell.id) if media_id else stmt.order_by(Cell.created_at.desc(), Cell.id)
    )
    return {"items": cell_list(db, list(db.scalars(stmt.offset(offset).limit(limit)))), "total": total}


@router.post("", status_code=201)
def create_cell(data: CellInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    db.scalar(select(Library).where(Library.id == p.library.id).with_for_update())
    media = owned(db, Media, data.media_id, p)
    validate_range(media, data.start_ms, data.end_ms)
    existing = db.scalar(
        select(Cell).where(
            Cell.media_id == media.id, Cell.start_ms == data.start_ms, Cell.end_ms == data.end_ms
        )
    )
    if existing:
        return cell_list(db, [existing])[0]
    total = db.scalar(select(func.count()).select_from(Cell).where(Cell.library_id == p.library.id))
    per_media = db.scalar(select(func.count()).select_from(Cell).where(Cell.media_id == media.id))
    if total >= settings.max_cells or per_media >= settings.max_cells_per_media:
        problem(
            413,
            "CELL_LIMIT",
            "Cellは動画ごとに100件、ライブラリ全体で2000件までです。不要なCellを削除してください。",
        )
    values = data.model_dump(exclude={"event_id"})
    if data.event_id:
        event = db.get(AnalysisEvent, data.event_id)
        if not event or event.media_id != media.id:
            problem(404, "NOT_FOUND", "候補が見つかりません。")
        values.update(origin="analysis_accepted", analysis_run_id=event.analysis_run_id)
    cell = Cell(library_id=p.library.id, **values)
    db.add(cell)
    db.flush()
    # A saved moment starts in its video's Shelves; users can change it independently later.
    for media_table, cell_table, key in [
        (shelf_media, shelf_cells, "shelf_id"),
        (collection_media, collection_cells, "collection_id"),
    ]:
        for group_id in db.scalars(select(media_table.c[key]).where(media_table.c.media_id == media.id)):
            db.execute(
                insert(cell_table).values(**{key: group_id, "cell_id": cell.id}).on_conflict_do_nothing()
            )
    audit(db, p.user.id, "cell.created", media.id)
    db.commit()
    return cell_list(db, [cell])[0]


@router.get("/{cell_id}")
def get_cell(cell_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    return cell_list(db, [owned(db, Cell, cell_id, p)])[0]


@router.patch("/{cell_id}")
def update_cell(
    cell_id: str, data: CellPatch, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    cell = owned(db, Cell, cell_id, p)
    media = owned(db, Media, cell.media_id, p)
    validate_range(media, data.start_ms, data.end_ms)
    for key, value in data.model_dump().items():
        setattr(cell, key, value)
    audit(db, p.user.id, "cell.updated", cell.id)
    db.commit()
    return cell_list(db, [cell])[0]


@router.delete("/{cell_id}", status_code=204)
def delete_cell(cell_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    cell = owned(db, Cell, cell_id, p)
    audit(db, p.user.id, "cell.deleted", cell.id)
    db.delete(cell)
    db.commit()
