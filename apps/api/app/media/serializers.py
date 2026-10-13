from hashlib import sha256

from app.models import (
    Asset,
    Cell,
    Media,
    Shelf,
    Source,
    collection_cells,
    collection_media,
    shelf_cells,
    shelf_media,
)
from app.sources.adapters import describe_source
from sqlalchemy import func, select


def record(item, fields):
    return {field: getattr(item, field) for field in fields}


MEDIA_FIELDS = [
    "id",
    "title",
    "note",
    "tags",
    "favorite",
    "status",
    "kind",
    "storage_mode",
    "duration_ms",
    "width",
    "height",
    "size_bytes",
    "created_at",
    "updated_at",
]
CELL_FIELDS = [
    "id",
    "media_id",
    "title",
    "note",
    "tags",
    "start_ms",
    "end_ms",
    "origin",
    "analysis_run_id",
    "created_at",
]
JOB_FIELDS = [
    "id",
    "media_id",
    "batch_id",
    "kind",
    "state",
    "progress",
    "attempt",
    "error_code",
    "error_message",
    "created_at",
]


def media_list(db, items):
    ids = [m.id for m in items]
    if not ids:
        return []
    assets = {}
    for asset in db.scalars(select(Asset).where(Asset.media_id.in_(ids))):
        url = "/api/v1/assets/" + asset.id
        if asset.role in {"thumbnail", "preview"}:
            url += "?v=" + sha256(asset.key.encode()).hexdigest()[:16]
        assets.setdefault(asset.media_id, {})[asset.role] = url
    counts = dict(
        db.execute(
            select(Cell.media_id, func.count()).where(Cell.media_id.in_(ids)).group_by(Cell.media_id)
        ).all()
    )
    shelves, collections = {}, {}
    for mid, sid in db.execute(
        select(shelf_media.c.media_id, shelf_media.c.shelf_id).where(shelf_media.c.media_id.in_(ids))
    ):
        shelves.setdefault(mid, []).append(sid)
    for mid, cid in db.execute(
        select(collection_media.c.media_id, collection_media.c.collection_id).where(
            collection_media.c.media_id.in_(ids)
        )
    ):
        collections.setdefault(mid, []).append(cid)
    sources = {s.id: s for s in db.scalars(select(Source).where(Source.id.in_({m.source_id for m in items})))}
    return [
        {
            "original_filename": sources[m.source_id].original_name,
            "source": media_source(sources[m.source_id], m.storage_mode),
            **record(m, MEDIA_FIELDS),
            "assets": assets.get(m.id, {}),
            "cell_count": counts.get(m.id, 0),
            "shelf_ids": shelves.get(m.id, []),
            "collection_ids": collections.get(m.id, []),
        }
        for m in items
    ]


def media_source(source, mode):
    result = describe_source(source)
    result["capabilities"].update(cells=True, download=mode == "MANAGED", analyze=mode == "MANAGED")
    return result


def cell_list(db, items):
    if not items:
        return []
    media = {m.id: m for m in db.scalars(select(Media).where(Media.id.in_({c.media_id for c in items})))}
    assets = {
        a.media_id: "/api/v1/assets/" + a.id + "?v=" + sha256(a.key.encode()).hexdigest()[:16]
        for a in db.scalars(select(Asset).where(Asset.media_id.in_(media), Asset.role == "thumbnail"))
    }
    memberships = {}
    shelves = {}
    for cid, gid in db.execute(
        select(shelf_cells.c.cell_id, shelf_cells.c.shelf_id).where(
            shelf_cells.c.cell_id.in_([c.id for c in items])
        )
    ):
        shelves.setdefault(cid, []).append(gid)
    for cid, gid in db.execute(
        select(collection_cells.c.cell_id, collection_cells.c.collection_id).where(
            collection_cells.c.cell_id.in_([c.id for c in items])
        )
    ):
        memberships.setdefault(cid, []).append(gid)
    return [
        {
            **record(c, CELL_FIELDS),
            "collection_ids": memberships.get(c.id, []),
            "shelf_ids": shelves.get(c.id, []),
            "storage_mode": media[c.media_id].storage_mode,
            "media_title": media[c.media_id].title,
            "thumbnail": assets.get(c.media_id),
        }
        for c in items
    ]


def group_list(db, model, library_id):
    groups = list(db.scalars(select(model).where(model.library_id == library_id).order_by(model.created_at)))
    table = shelf_media if model is Shelf else collection_media
    key = table.c.shelf_id if model is Shelf else table.c.collection_id
    counts = dict(
        db.execute(select(key, func.count()).where(key.in_([g.id for g in groups])).group_by(key)).all()
    )
    cell_table = shelf_cells if model is Shelf else collection_cells
    cell_key = cell_table.c.shelf_id if model is Shelf else cell_table.c.collection_id
    cell_counts = dict(db.execute(select(cell_key, func.count()).group_by(cell_key)).all())
    return [
        {
            **record(g, ["id", "name", "description", "color", "created_at"]),
            "header_url": f"/api/v1/{'shelves' if model is Shelf else 'collections'}/{g.id}/header?v={g.header_key.rsplit('/', 1)[-1]}"
            if g.header_key
            else None,
            "header_frame": g.header_frame,
            "media_count": counts.get(g.id, 0),
            "cell_count": cell_counts.get(g.id, 0),
        }
        for g in groups
    ]
