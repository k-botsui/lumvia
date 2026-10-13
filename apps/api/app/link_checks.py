"""Read-only link checks and explicit deletion backed by short-lived evidence."""

import base64
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import Principal, rate_limit, require_user
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.media.batch import delete_batch
from app.models import (
    Cell,
    Collection,
    Media,
    Shelf,
    Source,
    collection_cells,
    collection_media,
    shelf_cells,
    shelf_media,
)
from app.schemas import BatchMembership, Strict
from app.sources import network
from app.sources.adapters import parse_reference

router = APIRouter(prefix="/library/link-check", tags=["Link checks"])
Id = Annotated[str, Field(pattern=r"^[a-f0-9-]{36}$")]


class CheckInput(Strict):
    media_ids: list[Id] = Field(min_length=1, max_length=20)


class DeleteInput(Strict):
    proofs: list[Annotated[str, Field(max_length=2048)]] = Field(min_length=1, max_length=100)


def require_online():
    for url in ("https://www.youtube.com/", "https://www.tiktok.com/"):
        try:
            status, _, _ = network.request(url, method="HEAD")
            if 200 <= status < 500:
                return
        except network.FetchError:
            pass
    problem(
        503, "LINK_CHECK_OFFLINE", "オンライン接続を確認できず、実行できませんでした。削除は行っていません。"
    )


def inspect_link(url):
    try:
        reference = parse_reference(url, resolve=False)
        current = reference.url
        for _ in range(3):
            status, headers, _ = network.request(current, method="HEAD")
            if status in {301, 302, 303, 307, 308}:
                target = parse_reference(urljoin(current, headers.get("location", "")), resolve=False)
                if (target.provider, target.external_id) != (
                    reference.provider,
                    reference.external_id,
                ) or target.url == current:
                    return "unknown", "ログイン画面や別のページへの移動を確認しました。"
                current = target.url
                continue
            if status in {404, 410}:
                # HEAD alone can be unsupported. Confirm using GET without loading its body.
                confirmed, _, _ = network.request(current, status_only=True)
                if confirmed in {404, 410}:
                    return "broken", f"投稿のページが見つかりませんでした（{confirmed}）。"
                return "unknown", "サービスの応答が一致せず、確認できませんでした。"
            if 200 <= status < 300:
                return "reachable", "リンク先に到達できました。"
            return "unknown", "サービスの制限やエラーにより確認できませんでした。"
    except (network.FetchError, HTTPException):
        return "unknown", "通信エラーやサービスの制限により確認できませんでした。"
    return "unknown", "リンク先の移動を確認できませんでした。"


def links(db, p, ids=None, lock=False):
    query = (
        select(Media, Source)
        .join(Source, Source.id == Media.source_id)
        .where(
            Media.library_id == p.library.id,
            Source.library_id == p.library.id,
            Media.storage_mode == "REFERENCE",
            Source.external_url.is_not(None),
        )
        .order_by(Media.id)
    )
    if ids is not None:
        query = query.where(Media.id.in_(ids))
    if lock:
        query = query.with_for_update(of=Media)
    return list(db.execute(query))


def impact(db, media, source):
    cells = sorted(db.scalars(select(Cell.id).where(Cell.media_id == media.id)))
    shelves = list(
        db.execute(
            select(Shelf.id, Shelf.name).where(
                Shelf.id.in_(select(shelf_media.c.shelf_id).where(shelf_media.c.media_id == media.id))
                | Shelf.id.in_(select(shelf_cells.c.shelf_id).where(shelf_cells.c.cell_id.in_(cells)))
            )
        )
    )
    collections = list(
        db.execute(
            select(Collection.id, Collection.name).where(
                Collection.id.in_(
                    select(collection_media.c.collection_id).where(collection_media.c.media_id == media.id)
                )
                | Collection.id.in_(
                    select(collection_cells.c.collection_id).where(collection_cells.c.cell_id.in_(cells))
                )
            )
        )
    )
    # Include memberships, not only counts, to reject changed cleanup previews.
    memberships = []
    for table in (shelf_media, collection_media, shelf_cells, collection_cells):
        column = table.c.media_id if "media_id" in table.c else table.c.cell_id
        values = [media.id] if "media_id" in table.c else cells
        memberships += [list(row) for row in db.execute(select(table).where(column.in_(values)))]
    snapshot = json.dumps(
        [media.id, source.external_url, media.title, cells, sorted(memberships)], sort_keys=True
    )
    return {
        "cell_count": len(cells),
        "shelf_names": sorted({row[1] for row in shelves + collections}),
        "fingerprint": hashlib.sha256(snapshot.encode()).hexdigest(),
    }


def evidence(p, media, affected):
    payload = json.dumps(
        {
            "library": p.library.id,
            "media": media.id,
            "snapshot": affected["fingerprint"],
            "expires": int(time.time()) + 600,
        },
        separators=(",", ":"),
    ).encode()
    data = base64.urlsafe_b64encode(payload).decode()
    signature = hmac.new(
        settings.secret_key.encode(), b"link-check:" + data.encode(), hashlib.sha256
    ).hexdigest()
    return data + "." + signature


def read_evidence(token, p):
    try:
        data, signature = token.rsplit(".", 1)
        expected = hmac.new(
            settings.secret_key.encode(), b"link-check:" + data.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        value = json.loads(base64.urlsafe_b64decode(data))
        if value["library"] != p.library.id or value["expires"] < time.time():
            raise ValueError
        return value
    except (ValueError, KeyError, TypeError):
        problem(409, "LINK_CHECK_EXPIRED", "点検結果が無効か期限切れです。もう一度点検してください。")


@router.get("/targets")
def targets(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"link-check-start:{p.user.id}", 10, 3600)
    require_online()
    return {"media_ids": [media.id for media, _ in links(db, p)]}


@router.post("")
def check(data: CheckInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"link-check:{p.user.id}", 300, 3600)
    require_online()
    rows = links(db, p, data.media_ids)
    if {media.id for media, _ in rows} != set(data.media_ids):
        problem(409, "LINK_CHECK_CHANGED", "点検対象が変更されました。もう一度点検してください。")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inspect_link, [source.external_url for _, source in rows]))
    require_online()
    items = []
    for (media, source), (status, reason) in zip(rows, results, strict=True):
        affected = impact(db, media, source)
        items.append(
            {
                "id": media.id,
                "title": media.title,
                "url": source.external_url,
                "status": status,
                "reason": reason,
                "cell_count": affected["cell_count"],
                "shelf_names": affected["shelf_names"],
                "proof": evidence(p, media, affected) if status == "broken" else None,
            }
        )
    return {"items": items}


@router.post("/delete", status_code=204)
def delete_checked(data: DeleteInput, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    rate_limit(f"link-check-delete:{p.user.id}", 10, 3600)
    proofs = [read_evidence(token, p) for token in data.proofs]
    expected = {value["media"]: value["snapshot"] for value in proofs}
    require_online()
    rows = links(db, p, expected.keys(), lock=True)
    if {media.id for media, _ in rows} != set(expected):
        problem(409, "LINK_CHECK_CHANGED", "対象が変更されました。削除せず、もう一度点検してください。")
    for media, source in rows:
        if (
            impact(db, media, source)["fingerprint"] != expected[media.id]
            or inspect_link(source.external_url)[0] != "broken"
        ):
            problem(
                409,
                "LINK_CHECK_CHANGED",
                "対象の内容や接続状態が変わりました。削除せず、もう一度点検してください。",
            )
    require_online()
    # Reuse the existing atomic, owned-library deletion and asset cleanup.
    delete_batch(BatchMembership(media_ids=list(expected), cell_ids=[]), p, db)
