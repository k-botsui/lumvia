import copy
from concurrent.futures import ThreadPoolExecutor

from app.db import SessionLocal
from app.models import Cell, Media, Shelf, Source, shelf_cells, shelf_media
from sqlalchemy import func, select

PREFIX = "/api/v1/link-shares"


def bundle():
    return {
        "format": "lumvia-link-list",
        "version": 1,
        "links": [
            {
                "key": "m0",
                "url": "https://youtu.be/abcdefghijk?si=tracking",
                "title": "共有動画",
                "tags": ["猫"],
                "note": "共有メモ",
            }
        ],
        "cells": [{"key": "c0", "link": "m0", "title": "お気に入りの瞬間", "start_ms": 1000, "end_ms": 4000}],
        "groups": [{"key": "g0", "kind": "shelves", "name": "猫", "links": ["m0"], "cells": ["c0"]}],
    }


def seed(accounts):
    library = accounts[0][1]
    with SessionLocal() as db:
        source = Source(
            library_id=library,
            kind="youtube",
            external_id="abcdefghijk",
            external_url="https://youtu.be/abcdefghijk?si=private",
            original_name="PRIVATE original name",
            metadata_json={"secret": "NEVER EXPORT"},
        )
        local_source = Source(library_id=library, original_name="private.mp4")
        db.add_all([source, local_source])
        db.flush()
        reference = Media(
            library_id=library,
            source_id=source.id,
            storage_mode="REFERENCE",
            title="リンク",
            note="PRIVATE note",
            tags=["猫"],
            status="READY",
        )
        local = Media(
            library_id=library, source_id=local_source.id, title="私的動画", status="READY", duration_ms=5000
        )
        db.add_all([reference, local])
        db.flush()
        cell = Cell(
            library_id=library,
            media_id=reference.id,
            title="区間",
            start_ms=1000,
            end_ms=4000,
            note="PRIVATE cell",
        )
        local_cell = Cell(library_id=library, media_id=local.id, title="私的区間", start_ms=1000, end_ms=4000)
        group = Shelf(
            library_id=library, name="猫", description="PRIVATE description", header_key="PRIVATE path"
        )
        db.add_all([cell, local_cell, group])
        db.flush()
        for m in [reference, local]:
            db.execute(shelf_media.insert().values(shelf_id=group.id, media_id=m.id))
        for c in [cell, local_cell]:
            db.execute(shelf_cells.insert().values(shelf_id=group.id, cell_id=c.id))
        db.commit()
        return reference.id, local.id, group.id


def test_export_excludes_uploads_private_paths_and_notes_and_roundtrips(client, other, accounts, monkeypatch):
    reference, local, group = seed(accounts)
    monkeypatch.setattr(
        "app.sources.network.request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no fetch"))
    )
    response = client.post(PREFIX + "/export-preview", json={})
    assert response.status_code == 200
    data = response.json()
    exported = data["bundle"]
    assert len(exported["links"]) == len(exported["cells"]) == len(exported["groups"]) == 1
    assert len(data["excluded"]) == data["excluded_cells"] == 1
    assert "PRIVATE" not in str(exported) and local not in str(exported) and reference not in str(exported)
    assert exported["links"][0]["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert "si=" not in str(exported)
    preview = other.post(PREFIX + "/import-preview", json=exported)
    assert preview.status_code == 200 and preview.json()["summary"]["new_links"] == 1
    assert other.get("/api/v1/media").json()["total"] == 0
    result = other.post(PREFIX + "/import", json={"bundle": exported, "confirmed": True})
    assert result.status_code == 200 and not result.json()["duplicate"]
    imported = other.get("/api/v1/media").json()
    assert imported["total"] == 1
    assert imported["items"][0]["source"]["thumbnail_url"] is None
    assert len(other.get("/api/v1/shelves").json()["items"]) == 1
    assert other.get("/api/v1/cells").json()["total"] == 1
    notes = client.post(
        PREFIX + "/export-preview", json={"kind": "shelves", "group_id": group, "include_notes": True}
    ).json()["bundle"]
    assert notes["links"][0]["note"] == "PRIVATE note"
    assert notes["groups"][0]["description"] == "PRIVATE description"


def test_repeated_and_reordered_imports_preserve_existing_values_and_shelves(client, accounts):
    seed(accounts)
    data = bundle()
    first = client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True})
    assert first.status_code == 200 and first.json()["summary"]["new_links"] == 0
    assert client.get("/api/v1/media").json()["total"] == 2
    media = client.get("/api/v1/media").json()["items"]
    assert next(m for m in media if m["storage_mode"] == "REFERENCE")["note"] == "PRIVATE note"
    data["links"][0]["url"] = "https://www.youtube.com/watch?v=abcdefghijk&tracking=removed"
    assert client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True}).json()["duplicate"]
    assert len(client.get("/api/v1/shelves").json()["items"]) == 2
    assert client.get("/api/v1/cells").json()["total"] == 2


def test_same_list_concurrent_import_is_idempotent_and_can_restore_deleted_link(client, accounts):
    data = bundle()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True}), range(2)
            )
        )
    assert all(r.status_code == 200 for r in responses)
    assert sum(not r.json()["duplicate"] for r in responses) == 1
    assert client.get("/api/v1/media").json()["total"] == 1
    assert len(client.get("/api/v1/shelves").json()["items"]) == 1
    with SessionLocal() as db:
        media = db.scalar(select(Media).where(Media.library_id == accounts[0][1]))
        db.delete(media)
        db.commit()
    assert not client.post(PREFIX + "/import-preview", json=data).json()["duplicate"]
    assert client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True}).status_code == 200
    assert client.get("/api/v1/media").json()["total"] == 1
    assert len(client.get("/api/v1/shelves").json()["items"]) == 1


def test_auth_csrf_ownership_validation_and_atomic_limits(client, other, accounts, monkeypatch):
    from app.config import settings

    reference, local, group = seed(accounts)
    assert (
        other.post(PREFIX + "/export-preview", json={"kind": "shelves", "group_id": group}).status_code == 404
    )
    assert other.post(PREFIX + "/export-preview", json={"media_ids": [reference]}).status_code == 404
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post(PREFIX + "/import", json={"bundle": bundle(), "confirmed": True}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    for mutate in [
        lambda b: b.update(version=3),
        lambda b: b.update(secret="x"),
        lambda b: b["links"][0].update(url="https://127.0.0.1/private"),
        lambda b: b["cells"][0].update(link="missing"),
        lambda b: b["cells"][0].update(end_ms=400000),
        lambda b: b["groups"][0].update(header_key="private"),
        lambda b: b["links"].append(dict(b["links"][0], key="m1")),
    ]:
        data = copy.deepcopy(bundle())
        mutate(data)
        assert other.post(PREFIX + "/import-preview", json=data).status_code == 422
    assert other.post(PREFIX + "/import", json={"bundle": bundle(), "confirmed": False}).status_code == 422
    monkeypatch.setattr(settings, "max_reference_items", 0)
    assert other.post(PREFIX + "/import", json={"bundle": bundle(), "confirmed": True}).status_code == 413
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(Media).where(Media.library_id == accounts[1][1])) == 0
        )
        assert (
            db.scalar(select(func.count()).select_from(Shelf).where(Shelf.library_id == accounts[1][1])) == 0
        )
    assert (
        other.post(
            PREFIX + "/import-preview",
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_portable_key_changes_and_order_do_not_duplicate_list(client):
    data = bundle()
    data["links"].append({"key": "m1", "url": "https://x.com/example/status/12345", "title": "別の投稿"})
    data["groups"][0]["links"].append("m1")
    assert client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True}).status_code == 200
    altered = copy.deepcopy(data)
    altered["links"] = list(reversed(altered["links"]))
    for link in altered["links"]:
        link["key"] = {"m0": "a", "m1": "b"}[link["key"]]
    altered["cells"][0].update(key="z", link="a")
    altered["groups"][0].update(key="other", links=["b", "a"], cells=["z"])
    result = client.post(PREFIX + "/import", json={"bundle": altered, "confirmed": True})
    assert result.status_code == 200 and result.json()["duplicate"]
    assert client.get("/api/v1/media").json()["total"] == 2
    assert len(client.get("/api/v1/shelves").json()["items"]) == 1


def test_image_bundle_roundtrip_metadata_strip_and_no_overwrite(client, other, monkeypatch):
    import base64
    from io import BytesIO

    from PIL import Image

    monkeypatch.setattr(
        "app.sources.network.request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Import must not fetch images")),
    )
    image = Image.new("RGB", (160, 90), "#1279c4")
    exif = Image.Exif()
    exif[271] = "private camera metadata"
    stream = BytesIO()
    image.save(stream, format="JPEG", exif=exif)
    data = bundle()
    data["version"] = 2
    data["links"][0]["cover_jpeg"] = base64.b64encode(stream.getvalue()).decode()
    data["groups"][0].update(
        header_jpeg=data["links"][0]["cover_jpeg"], header_frame={"x": 30, "y": 60, "zoom": 1.2}
    )
    imported = client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True})
    assert imported.status_code == 200, imported.text
    media = client.get("/api/v1/media").json()["items"][0]
    thumbnail = client.get(media["assets"]["thumbnail"])
    with Image.open(BytesIO(thumbnail.content)) as decoded:
        assert not decoded.getexif()
    assert other.get(media["assets"]["thumbnail"]).status_code == 404
    exported = client.post(PREFIX + "/export-preview", json={"include_images": True}).json()["bundle"]
    assert exported["version"] == 2 and exported["links"][0]["cover_jpeg"]
    with Image.open(BytesIO(base64.b64decode(exported["links"][0]["cover_jpeg"]))) as decoded:
        assert not decoded.getexif()
    assert exported["groups"][0]["header_frame"] == {"x": 30.0, "y": 60.0, "zoom": 1.2}
    second = other.post(PREFIX + "/import", json={"bundle": exported, "confirmed": True})
    assert second.status_code == 200, second.text
    assert other.get("/api/v1/media").json()["items"][0]["assets"]["thumbnail"]
    invalid = copy.deepcopy(data)
    invalid["links"][0]["cover_jpeg"] = "not-an-image"
    assert client.post(PREFIX + "/import-preview", json=invalid).status_code == 422
    old_format = copy.deepcopy(data)
    old_format["version"] = 1
    assert client.post(PREFIX + "/import-preview", json=old_format).status_code == 422
    replacement = Image.new("RGB", (160, 90), "#fb1111")
    newer = BytesIO()
    replacement.save(newer, format="JPEG")
    data["links"][0]["cover_jpeg"] = base64.b64encode(newer.getvalue()).decode()
    assert client.post(PREFIX + "/import", json={"bundle": data, "confirmed": True}).status_code == 200
    assert client.get(media["assets"]["thumbnail"]).content == thumbnail.content
