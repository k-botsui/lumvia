"""Portable link lists. Import never executes data or fetches external URLs."""

import hashlib
import hmac
import json
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.service import Principal, audit, owned, rate_limit, require_user
from app.cells.routes import validate_range
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.models import (
    Cell,
    Collection,
    Library,
    LinkShareImport,
    Media,
    Shelf,
    Source,
    collection_cells,
    collection_media,
    shelf_cells,
    shelf_media,
)
from app.schemas import Strict, Tags, Title
from app.sources.adapters import parse_reference

router = APIRouter(prefix="/link-shares", tags=["Link sharing"])
MAX_BYTES = 2 * 1024 * 1024
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9]{0,31}$")]


class LinkEntry(Strict):
    key: Key
    url: str = Field(max_length=2048)
    title: Title
    tags: Tags = []
    note: str = Field(default="", max_length=10000)
    favorite: bool = False

    @field_validator("url")
    @classmethod
    def safe_reference(cls, value):
        return parse_reference(value, resolve=False).url


class MomentEntry(Strict):
    key: Key
    link: Key
    title: Title
    start_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(gt=0, strict=True)
    tags: Tags = []
    note: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def interval(self):
        if not self.start_ms < self.end_ms <= settings.max_duration_ms:
            raise ValueError("Invalid interval")
        if self.end_ms - self.start_ms > settings.max_clip_ms:
            raise ValueError("Cell exceeds maximum duration")
        return self


class GroupEntry(Strict):
    key: Key
    kind: Literal["shelves", "collections"]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    description: str = Field(default="", max_length=500)
    color: str = Field(default="#4f7bff", pattern=r"^#[0-9a-fA-F]{6}$")
    links: list[Key] = Field(default_factory=list, max_length=2000)
    cells: list[Key] = Field(default_factory=list, max_length=2000)


class LinkList(Strict):
    format: Literal["lumvia-link-list"]
    version: Literal[1]
    links: list[LinkEntry] = Field(min_length=1, max_length=2000)
    cells: list[MomentEntry] = Field(default_factory=list, max_length=2000)
    groups: list[GroupEntry] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def references(self):
        links = {entry.key for entry in self.links}
        cells = {entry.key for entry in self.cells}
        if len(links) != len(self.links) or len(cells) != len(self.cells):
            raise ValueError("Duplicate keys")
        if len({g.key for g in self.groups}) != len(self.groups):
            raise ValueError("Duplicate group keys")
        identities = [identity(link.url) for link in self.links]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate link identities")
        intervals = [(c.link, c.start_ms, c.end_ms) for c in self.cells]
        if len(set(intervals)) != len(intervals):
            raise ValueError("Duplicate Cell intervals")
        if any(c.link not in links for c in self.cells):
            raise ValueError("Missing parent link")
        if any(not set(g.links) <= links or not set(g.cells) <= cells for g in self.groups):
            raise ValueError("Invalid group membership")
        if len(encoded(self)) > MAX_BYTES:
            raise ValueError("Link list too large")
        return self


class ExportSelection(Strict):
    kind: Literal["library", "shelves", "collections"] = "library"
    group_id: str | None = Field(default=None, max_length=36)
    media_ids: list[str] | None = Field(default=None, max_length=100)
    cell_ids: list[str] | None = Field(default=None, max_length=100)
    include_notes: bool = False


class ImportConfirmation(Strict):
    bundle: LinkList
    confirmed: Literal[True]


def encoded(bundle):
    value = bundle.model_dump() if isinstance(bundle, LinkList) else bundle
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def identity(url):
    ref = parse_reference(url, resolve=False)
    return ref.provider, ref.external_id


def fingerprint(bundle):
    # Portable keys and ordering do not make an otherwise identical list a new import.
    urls = {link.key: identity(link.url) for link in bundle.links}
    moments = {cell.key: (urls[cell.link], cell.start_ms, cell.end_ms) for cell in bundle.cells}
    content = {
        "links": [
            link.model_dump(exclude={"key", "url"}) | {"identity": urls[link.key]} for link in bundle.links
        ],
        "cells": [
            cell.model_dump(exclude={"key", "link"}) | {"identity": urls[cell.link]} for cell in bundle.cells
        ],
        "groups": [
            group.model_dump(exclude={"key", "links", "cells"})
            | {
                "links": sorted({urls[key] for key in group.links}),
                "cells": sorted({moments[key] for key in group.cells}),
            }
            for group in bundle.groups
        ],
    }
    for entries in content.values():
        entries.sort(key=lambda entry: json.dumps(entry, sort_keys=True))
    return hmac.new(settings.secret_key.encode(), encoded(content), hashlib.sha256).hexdigest()


def receipt_valid(db, p, receipt):
    if not receipt:
        return False
    content = receipt.summary
    for model, field in [(Media, "media_ids"), (Cell, "cell_ids")]:
        for ident in content[field]:
            item = db.get(model, ident)
            if not item or item.library_id != p.library.id:
                return False
    for item in content["group_items"]:
        model, mt, ct, key = (
            (Shelf, shelf_media, shelf_cells, "shelf_id")
            if item["kind"] == "shelves"
            else (Collection, collection_media, collection_cells, "collection_id")
        )
        group = db.get(model, item["id"])
        if not group or group.library_id != p.library.id:
            return False
        if not set(item["media_ids"]) <= set(db.scalars(select(mt.c.media_id).where(mt.c[key] == group.id))):
            return False
        if not set(item["cell_ids"]) <= set(db.scalars(select(ct.c.cell_id).where(ct.c[key] == group.id))):
            return False
    return True


@router.post("/export-preview")
def export_preview(
    data: ExportSelection, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    rate_limit(f"link-export:{p.user.id}", 30, 3600)
    media = list(db.scalars(select(Media).where(Media.library_id == p.library.id).order_by(Media.id)))
    cells = list(db.scalars(select(Cell).where(Cell.library_id == p.library.id).order_by(Cell.id)))
    groups = []
    memberships = {}
    for kind, model, mt, ct, key in [
        ("shelves", Shelf, shelf_media, shelf_cells, "shelf_id"),
        ("collections", Collection, collection_media, collection_cells, "collection_id"),
    ]:
        for group in db.scalars(select(model).where(model.library_id == p.library.id).order_by(model.id)):
            groups.append((kind, group))
            memberships[group.id] = (
                set(db.scalars(select(mt.c.media_id).where(mt.c[key] == group.id))),
                set(db.scalars(select(ct.c.cell_id).where(ct.c[key] == group.id))),
            )
    if data.kind != "library":
        if not data.group_id:
            problem(422, "GROUP_REQUIRED", "共有するShelfを選んでください。")
        owned(db, Shelf if data.kind == "shelves" else Collection, data.group_id, p)
        mids, cids = memberships[data.group_id]
        cells = [c for c in cells if c.id in cids]
        media = [m for m in media if m.id in mids or m.id in {c.media_id for c in cells}]
        groups = [(k, g) for k, g in groups if g.id == data.group_id]
    if data.media_ids is not None or data.cell_ids is not None:
        for mid in data.media_ids or []:
            owned(db, Media, mid, p)
        for cid in data.cell_ids or []:
            owned(db, Cell, cid, p)
        selected_media, selected_cells = set(data.media_ids or []), set(data.cell_ids or [])
        cells = [c for c in cells if c.id in selected_cells or c.media_id in selected_media]
        parents = {c.media_id for c in cells}
        media = [m for m in media if m.id in selected_media or m.id in parents]
    excluded = []
    links, mapping = [], {}
    seen = {}
    for m in media:
        source = db.get(Source, m.source_id)
        if m.storage_mode != "REFERENCE" or source.library_id != p.library.id:
            excluded.append({"title": m.title, "reason": "アップロードした動画・画像"})
            continue
        try:
            ref = parse_reference(source.external_url or "", resolve=False)
        except HTTPException:
            excluded.append({"title": m.title, "reason": "共有に対応していないリンク"})
            continue
        ident = (ref.provider, ref.external_id)
        key = seen.get(ident)
        if not key:
            key = f"m{len(links)}"
            seen[ident] = key
            links.append(
                dict(
                    key=key,
                    url=ref.url,
                    title=m.title,
                    tags=m.tags,
                    note=m.note if data.include_notes else "",
                    favorite=m.favorite,
                )
            )
        mapping[m.id] = key
    moments, cmapping, intervals = [], {}, {}
    for c in cells:
        if c.media_id not in mapping:
            continue
        interval = (mapping[c.media_id], c.start_ms, c.end_ms)
        key = intervals.get(interval)
        if not key:
            key = f"c{len(moments)}"
            intervals[interval] = key
            moments.append(
                dict(
                    key=key,
                    link=mapping[c.media_id],
                    title=c.title,
                    start_ms=c.start_ms,
                    end_ms=c.end_ms,
                    tags=c.tags,
                    note=c.note if data.include_notes else "",
                )
            )
        cmapping[c.id] = key
    portable_groups = []
    for kind, g in groups:
        mids, cids = memberships[g.id]
        members = sorted({mapping[mid] for mid in mids if mid in mapping})
        moments_in_group = sorted({cmapping[cid] for cid in cids if cid in cmapping})
        if members or moments_in_group:
            portable_groups.append(
                dict(
                    key=f"g{len(portable_groups)}",
                    kind=kind,
                    name=g.name,
                    description=g.description if data.include_notes else "",
                    color=g.color,
                    links=members,
                    cells=moments_in_group,
                )
            )
    bundle = dict(format="lumvia-link-list", version=1, links=links, cells=moments, groups=portable_groups)
    if links:
        try:
            bundle = LinkList.model_validate(bundle).model_dump()
        except ValidationError:
            problem(
                413,
                "SHARE_TOO_LARGE",
                "共有内容が大きすぎます。メモを除くか、共有する項目を減らしてください。",
            )
    return {
        "bundle": bundle,
        "excluded": excluded,
        "excluded_cells": sum(c.media_id not in mapping for c in cells),
        "notes_included": data.include_notes,
    }


def plan(db, p, bundle):
    sources = list(
        db.execute(
            select(Source, Media)
            .join(Media, Media.source_id == Source.id)
            .where(Media.library_id == p.library.id, Media.storage_mode == "REFERENCE")
        )
    )
    existing = {(s.kind, s.external_id): m for s, m in sources}
    links = {entry.key: existing.get(identity(entry.url)) for entry in bundle.links}
    cells = {}
    for entry in bundle.cells:
        media = links[entry.link]
        cells[entry.key] = (
            db.scalar(
                select(Cell).where(
                    Cell.media_id == media.id, Cell.start_ms == entry.start_ms, Cell.end_ms == entry.end_ms
                )
            )
            if media
            else None
        )
    new_links = sum(m is None for m in links.values())
    new_cells = sum(c is None for c in cells.values())
    reference_count = db.scalar(
        select(func.count())
        .select_from(Media)
        .where(Media.library_id == p.library.id, Media.storage_mode == "REFERENCE")
    )
    if reference_count + new_links > settings.max_reference_items:
        problem(
            413,
            "REFERENCE_LIMIT",
            "リンクの保存上限に達します。不要なリンクを削除してから読み込んでください。",
        )
    total_cells = db.scalar(select(func.count()).select_from(Cell).where(Cell.library_id == p.library.id))
    if total_cells + new_cells > settings.max_cells:
        problem(413, "CELL_LIMIT", "Cellの保存上限に達します。")
    for key, media in links.items():
        count = (
            db.scalar(select(func.count()).select_from(Cell).where(Cell.media_id == media.id)) if media else 0
        )
        additional = sum(c.link == key and cells[c.key] is None for c in bundle.cells)
        if count + additional > settings.max_cells_per_media:
            problem(413, "CELL_LIMIT", "1つのリンクに保存できるCellの上限に達します。")
    return (
        links,
        cells,
        {
            "new_links": new_links,
            "existing_links": len(links) - new_links,
            "new_cells": new_cells,
            "groups": len(bundle.groups),
        },
    )


@router.post("/import-preview")
def import_preview(bundle: LinkList, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"link-preview:{p.user.id}", 30, 3600)
    receipt = db.scalar(
        select(LinkShareImport).where(
            LinkShareImport.library_id == p.library.id, LinkShareImport.fingerprint == fingerprint(bundle)
        )
    )
    if receipt_valid(db, p, receipt):
        return {"duplicate": True, "summary": receipt.summary["counts"], "bundle": bundle.model_dump()}
    _, _, summary = plan(db, p, bundle)
    return {"duplicate": False, "summary": summary, "bundle": bundle.model_dump()}


@router.post("/import")
def import_list(
    data: ImportConfirmation, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    rate_limit(f"link-import:{p.user.id}", 20, 3600)
    db.scalar(select(Library).where(Library.id == p.library.id).with_for_update())
    bundle = data.bundle
    digest = fingerprint(bundle)
    receipt = db.scalar(
        select(LinkShareImport).where(
            LinkShareImport.library_id == p.library.id, LinkShareImport.fingerprint == digest
        )
    )
    if receipt_valid(db, p, receipt):
        return {"duplicate": True, "summary": receipt.summary["counts"]}
    previous_groups = {item["key"]: item for item in receipt.summary["group_items"]} if receipt else {}
    if receipt:
        db.delete(receipt)
        db.flush()
    links, cells, summary = plan(db, p, bundle)
    for entry in bundle.links:
        if links[entry.key]:
            continue
        ref = parse_reference(entry.url, resolve=False)
        source = db.scalar(
            select(Source).where(
                Source.library_id == p.library.id,
                Source.kind == ref.provider,
                Source.external_id == ref.external_id,
            )
        )
        if not source:
            source = Source(
                library_id=p.library.id,
                kind=ref.provider,
                external_id=ref.external_id,
                external_url=ref.url,
                original_name=entry.title,
                metadata_json={"metadata_available": False, "shared_import": True},
            )
            db.add(source)
            db.flush()
        else:
            source.metadata_json = {**source.metadata_json, "shared_import": True}
        media = Media(
            library_id=p.library.id,
            source_id=source.id,
            title=entry.title,
            note=entry.note,
            tags=entry.tags,
            favorite=entry.favorite,
            storage_mode="REFERENCE",
            status="READY",
        )
        db.add(media)
        db.flush()
        links[entry.key] = media
    for entry in bundle.cells:
        if cells[entry.key]:
            continue
        media = links[entry.link]
        validate_range(media, entry.start_ms, entry.end_ms)
        cell = Cell(
            library_id=p.library.id,
            media_id=media.id,
            title=entry.title,
            note=entry.note,
            tags=entry.tags,
            start_ms=entry.start_ms,
            end_ms=entry.end_ms,
            origin="imported",
        )
        db.add(cell)
        db.flush()
        cells[entry.key] = cell
    group_items = []
    for entry in bundle.groups:
        model, mt, ct, key = (
            (Shelf, shelf_media, shelf_cells, "shelf_id")
            if entry.kind == "shelves"
            else (Collection, collection_media, collection_cells, "collection_id")
        )
        member_ids = sorted({links[k].id for k in entry.links})
        cell_ids = sorted({cells[k].id for k in entry.cells})
        old = previous_groups.get(entry.key)
        group = db.get(model, old["id"]) if old and old["kind"] == entry.kind else None
        if group and group.library_id != p.library.id:
            group = None
        if not group:
            for candidate in db.scalars(select(model).where(model.library_id == p.library.id)):
                suffix = re.search(r"（共有[0-9]+）$", candidate.name)
                same_name = candidate.name == entry.name or bool(
                    suffix and candidate.name == entry.name[: 100 - len(suffix[0])] + suffix[0]
                )
                if (
                    same_name
                    and set(member_ids)
                    == set(db.scalars(select(mt.c.media_id).where(mt.c[key] == candidate.id)))
                    and set(cell_ids)
                    == set(db.scalars(select(ct.c.cell_id).where(ct.c[key] == candidate.id)))
                ):
                    group = candidate
                    break
        if not group:
            name, n = entry.name.strip() or "共有リンク", 1
            while db.scalar(select(model.id).where(model.library_id == p.library.id, model.name == name)):
                n += 1
                suffix = f"（共有{n}）"
                name = entry.name[: 100 - len(suffix)] + suffix
            group = model(
                library_id=p.library.id, name=name, description=entry.description, color=entry.color
            )
            db.add(group)
            db.flush()
        for mid in member_ids:
            db.execute(insert(mt).values(**{key: group.id, "media_id": mid}).on_conflict_do_nothing())
        for cid in cell_ids:
            db.execute(insert(ct).values(**{key: group.id, "cell_id": cid}).on_conflict_do_nothing())
        group_items.append(
            {
                "key": entry.key,
                "kind": entry.kind,
                "id": group.id,
                "media_ids": member_ids,
                "cell_ids": cell_ids,
            }
        )
    recorded = {
        "counts": summary,
        "media_ids": sorted({m.id for m in links.values()}),
        "cell_ids": sorted({c.id for c in cells.values()}),
        "group_items": group_items,
    }
    db.add(LinkShareImport(library_id=p.library.id, fingerprint=digest, summary=recorded))
    audit(db, p.user.id, "link_list.imported", p.library.id)
    db.commit()
    return {"duplicate": False, "summary": summary}
