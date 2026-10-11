from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.db import get_db
from app.errors import problem
from app.media.images import jpeg, read_upload
from app.media.serializers import group_list
from app.models import (
    Cell,
    Collection,
    Deletion,
    Media,
    Shelf,
    collection_cells,
    collection_media,
    shelf_cells,
    shelf_media,
)
from app.schemas import BatchMembership, GroupInput, HeaderFrame, Membership
from app.storage.service import LocalStorage, storage
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

router = APIRouter(tags=["Organization"])


def group_type(kind):
    if kind not in {"shelves", "collections"}:
        problem(404, "NOT_FOUND", "項目が見つかりません。")
    return Shelf if kind == "shelves" else Collection


def build_router(kind, model):
    sub = APIRouter(prefix="/" + kind)

    @sub.get("")
    def groups(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
        return {"items": group_list(db, model, p.library.id)}

    @sub.post("", status_code=201)
    def create(data: GroupInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
        group = model(library_id=p.library.id, **data.model_dump())
        db.add(group)
        db.flush()
        audit(db, p.user.id, kind + ".created", group.id)
        db.commit()
        return next(g for g in group_list(db, model, p.library.id) if g["id"] == group.id)

    @sub.patch("/{group_id}")
    def update(
        group_id: str, data: GroupInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)
    ):
        group = owned(db, model, group_id, p)
        for key, value in data.model_dump().items():
            setattr(group, key, value)
        audit(db, p.user.id, kind + ".updated", group.id)
        db.commit()
        return next(g for g in group_list(db, model, p.library.id) if g["id"] == group.id)

    @sub.delete("/{group_id}", status_code=204)
    def remove(group_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
        group = owned(db, model, group_id, p)
        audit(db, p.user.id, kind + ".deleted", group.id)
        if group.header_key:
            db.add(Deletion(key=group.header_key))
        db.delete(group)
        db.commit()

    @sub.get("/{group_id}/header")
    def header(group_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
        group = owned(db, model, group_id, p)
        if not group.header_key:
            problem(404, "NOT_FOUND", "ヘッダー画像がありません。")
        if isinstance(storage, LocalStorage):
            path = storage.path(group.header_key)
            if not path.is_file():
                problem(404, "NOT_FOUND", "ヘッダー画像が見つかりません。")
            return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
        return RedirectResponse(storage.signed_url(group.header_key), status_code=307)

    @sub.put("/{group_id}/header")
    def upload_header(
        group_id: str,
        file: UploadFile = File(...),
        p: Principal = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        rate_limit(f"shelf-header:{p.user.id}", 30, 3600)
        group = owned(db, model, group_id, p)
        key = f"{p.library.id}/{kind}/{group.id}/header-{uuid4()}.jpg"
        with TemporaryDirectory(prefix="lumvia-header-") as directory:
            output = Path(directory) / "header.jpg"
            maximum = 50 * 1024 * 1024
            jpeg(
                read_upload(file, maximum),
                output,
                size=(1600, 900),
                max_bytes=maximum,
                max_dimension=12000,
                max_pixels=60_000_000,
            )
            db.scalar(select(model).where(model.id == group_id).with_for_update())
            db.refresh(group)
            try:
                storage.put(key, output, "image/jpeg")
                if group.header_key:
                    db.add(Deletion(key=group.header_key))
                group.header_key = key
                group.header_frame = {"x": 50, "y": 50, "zoom": 1}
                audit(db, p.user.id, kind + ".header_updated", group.id)
                db.commit()
            except Exception:
                db.rollback()
                storage.delete(key)
                raise
        return next(g for g in group_list(db, model, p.library.id) if g["id"] == group_id)

    @sub.patch("/{group_id}/header")
    def frame_header(
        group_id: str,
        data: HeaderFrame,
        p: Principal = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        group = owned(db, model, group_id, p)
        db.scalar(select(model).where(model.id == group_id).with_for_update())
        db.refresh(group)
        if not group.header_key:
            problem(409, "HEADER_MISSING", "先にヘッダー画像を選んでください。")
        group.header_frame = data.model_dump()
        audit(db, p.user.id, kind + ".header_framed", group.id)
        db.commit()
        return next(g for g in group_list(db, model, p.library.id) if g["id"] == group_id)

    @sub.delete("/{group_id}/header", status_code=204)
    def remove_header(group_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
        group = owned(db, model, group_id, p)
        db.scalar(select(model).where(model.id == group_id).with_for_update())
        db.refresh(group)
        if group.header_key:
            db.add(Deletion(key=group.header_key))
            group.header_key = None
            group.header_frame = {"x": 50, "y": 50, "zoom": 1}
            audit(db, p.user.id, kind + ".header_removed", group.id)
            db.commit()

    @sub.put("/{group_id}/items", status_code=204)
    def add(
        group_id: str, data: Membership, p: Principal = Depends(require_user), db: Session = Depends(get_db)
    ):
        owned(db, model, group_id, p)
        table, values = membership(kind, group_id, data, p, db)
        db.execute(insert(table).values(**values).on_conflict_do_nothing())
        audit(db, p.user.id, kind + ".item_added", group_id)
        db.commit()

    @sub.delete("/{group_id}/items/{item_id}", status_code=204)
    def discard(
        group_id: str, item_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)
    ):
        owned(db, model, group_id, p)
        tables = (
            [(shelf_media, "shelf_id", "media_id"), (shelf_cells, "shelf_id", "cell_id")]
            if kind == "shelves"
            else [
                (collection_media, "collection_id", "media_id"),
                (collection_cells, "collection_id", "cell_id"),
            ]
        )
        for table, group_key, item_key in tables:
            db.execute(delete(table).where(table.c[group_key] == group_id, table.c[item_key] == item_id))
        audit(db, p.user.id, kind + ".item_removed", group_id)
        db.commit()

    @sub.put("/{group_id}/batch", status_code=204)
    def add_batch(
        group_id: str,
        data: BatchMembership,
        p: Principal = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        owned(db, model, group_id, p)
        media_ids, cell_ids = set(data.media_ids), set(data.cell_ids)
        if not 1 <= len(media_ids) + len(cell_ids) <= 100:
            problem(422, "INVALID_BATCH", "一度に1〜100件を選択してください。")
        # Validate every item before any write: a foreign or missing item rolls back the whole batch.
        for item_model, ids in [(Media, media_ids), (Cell, cell_ids)]:
            if (
                ids
                and set(
                    db.scalars(
                        select(item_model.id).where(
                            item_model.id.in_(ids), item_model.library_id == p.library.id
                        )
                    )
                )
                != ids
            ):
                problem(404, "NOT_FOUND", "選択した項目が見つかりません。選び直してください。")
        key = "shelf_id" if kind == "shelves" else "collection_id"
        for table, item_key, ids in [
            (shelf_media if kind == "shelves" else collection_media, "media_id", media_ids),
            (shelf_cells if kind == "shelves" else collection_cells, "cell_id", cell_ids),
        ]:
            if ids:
                db.execute(
                    insert(table)
                    .values([{key: group_id, item_key: item_id} for item_id in sorted(ids)])
                    .on_conflict_do_nothing()
                )
        audit(db, p.user.id, kind + ".items_added", group_id)
        db.commit()

    return sub


def membership(kind, group_id, data, p, db):
    if bool(data.media_id) == bool(data.cell_id):
        problem(422, "INVALID_MEMBERSHIP", "保存する項目を1つ指定してください。")
    if data.media_id:
        owned(db, Media, data.media_id, p)
        table = shelf_media if kind == "shelves" else collection_media
        return table, {
            ("shelf_id" if kind == "shelves" else "collection_id"): group_id,
            "media_id": data.media_id,
        }
    owned(db, Cell, data.cell_id, p)
    table = shelf_cells if kind == "shelves" else collection_cells
    return table, {("shelf_id" if kind == "shelves" else "collection_id"): group_id, "cell_id": data.cell_id}


def destination(db, p, shelf_id, collection_id):
    if shelf_id and collection_id:
        problem(422, "INVALID_DESTINATION", "追加先のShelfは1つ選んでください。")
    if not shelf_id and not collection_id:
        return None
    kind, group_id = ("shelves", shelf_id) if shelf_id else ("collections", collection_id)
    owned(db, group_type(kind), group_id, p)
    return kind, group_id


def place_media(db, p, selected, media_id):
    if selected:
        kind, group_id = selected
        table, values = membership(kind, group_id, Membership(media_id=media_id), p, db)
        db.execute(insert(table).values(**values).on_conflict_do_nothing())
        audit(db, p.user.id, kind + ".item_added", group_id)


router.include_router(build_router("shelves", Shelf))
router.include_router(build_router("collections", Collection))
