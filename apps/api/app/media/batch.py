from app.auth.service import Principal, audit, require_user
from app.db import get_db
from app.errors import problem
from app.jobs.service import ACTIVE
from app.models import Asset, Cell, Deletion, Job, Media, Source
from app.schemas import BatchMembership
from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/library", tags=["Library"])


@router.post("/delete-batch", status_code=204)
def delete_batch(data: BatchMembership, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    media_ids, cell_ids = set(data.media_ids), set(data.cell_ids)
    if not 1 <= len(media_ids) + len(cell_ids) <= 100:
        problem(422, "INVALID_BATCH", "一度に1〜100件を選択してください。")
    # Lock in a fixed order and validate all ownership before any deletion.
    media = list(
        db.scalars(
            select(Media)
            .where(Media.id.in_(media_ids), Media.library_id == p.library.id)
            .order_by(Media.id)
            .with_for_update()
        )
    )
    cells = list(
        db.scalars(
            select(Cell)
            .where(Cell.id.in_(cell_ids), Cell.library_id == p.library.id)
            .order_by(Cell.id)
            .with_for_update()
        )
    )
    if {m.id for m in media} != media_ids or {c.id for c in cells} != cell_ids:
        problem(404, "NOT_FOUND", "選択した項目が見つかりません。選び直してください。")
    if db.scalar(select(Job.id).where(Job.media_id.in_(media_ids), Job.state.in_(ACTIVE)).limit(1)):
        problem(
            409,
            "PROCESSING_ACTIVE",
            "処理中の動画が含まれています。処理をキャンセルし、停止してから削除してください。",
        )
    keys = set(db.scalars(select(Asset.key).where(Asset.media_id.in_(media_ids))))
    for item in media:
        if item.storage_mode == "MANAGED":
            prefix = f"{item.library_id}/{item.id}"
            keys.update({prefix + "/original", prefix + "/thumbnail.jpg", prefix + "/preview.mp4"})
        audit(db, p.user.id, "media.deleted", item.id)
    for item in cells:
        audit(db, p.user.id, "cell.deleted", item.id)
    for key in keys:
        db.add(Deletion(key=key))
    if cell_ids:
        db.execute(delete(Cell).where(Cell.id.in_(cell_ids)))
    if media_ids:
        source_ids = {m.source_id for m in media}
        db.execute(delete(Media).where(Media.id.in_(media_ids)))
        db.execute(delete(Source).where(Source.id.in_(source_ids), ~Source.id.in_(select(Media.source_id))))
    db.commit()
    if keys:
        from app.jobs.worker import purge_assets

        purge_assets()
