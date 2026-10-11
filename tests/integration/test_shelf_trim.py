from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest
from app.db import SessionLocal
from app.jobs.worker import process
from app.models import Asset, Job, Media
from PIL import Image
from sqlalchemy import func, select


def group(client, kind="shelves", name="思い出"):
    response = client.post("/api/v1/" + kind, json={"name": name})
    assert response.status_code == 201
    return response.json()


def reference(client, monkeypatch):
    monkeypatch.setattr("app.sources.routes.fetch_metadata", lambda _: {"metadata_available": False})
    return client.post(
        "/api/v1/imports", json={"url": "https://x.com/jack/status/20", "title": "残した動画"}
    ).json()["media"]


def cell(client, media, start=2000, end=4000):
    response = client.post(
        "/api/v1/cells", json={"media_id": media["id"], "title": "瞬間", "start_ms": start, "end_ms": end}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_destination_is_atomic_and_private(client, other, sample, monkeypatch):
    selected = group(client)
    foreign = group(other)
    monkeypatch.setattr("app.sources.routes.fetch_metadata", lambda _: {"metadata_available": False})
    for invalid in [
        {"shelf_id": foreign["id"]},
        {"shelf_id": selected["id"], "collection_id": selected["id"]},
    ]:
        expected = 404 if "collection_id" not in invalid else 422
        assert (
            client.post(
                "/api/v1/media", data=invalid, files={"file": ("sample.mp4", sample.read_bytes())}
            ).status_code
            == expected
        )
        assert (
            client.post(
                "/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ", **invalid}
            ).status_code
            == expected
        )
    assert client.get("/api/v1/media").json()["total"] == 0
    uploaded = client.post(
        "/api/v1/media",
        data={"shelf_id": selected["id"]},
        files={"file": ("sample.mp4", sample.read_bytes())},
    ).json()
    assert uploaded["shelf_ids"] == [selected["id"]]
    assert client.get("/api/v1/media", params={"shelf_id": selected["id"]}).json()["total"] == 1


def test_existing_link_can_join_another_shelf_without_overwrite(client, monkeypatch):
    original = reference(client, monkeypatch)
    selected = group(client)
    legacy = group(client, "collections", "以前の整理先")
    for kind, destination in [("shelf_id", selected), ("collection_id", legacy)]:
        result = client.post(
            "/api/v1/imports",
            json={
                "url": "https://twitter.com/another/status/20?s=20",
                "title": "変更しない",
                kind: destination["id"],
            },
        )
        assert result.status_code == 200 and not result.json()["created"]
        assert result.json()["media"]["id"] == original["id"]
        assert result.json()["media"]["title"] == original["title"]
    assert client.get("/api/v1/media").json()["total"] == 1
    edited = client.patch(
        "/api/v1/shelves/" + selected["id"],
        json={"name": "推し", "color": "#7487b8", "description": "登場シーン"},
    )
    assert edited.status_code == 200 and edited.json()["name"] == "推し"
    assert client.delete(f"/api/v1/shelves/{selected['id']}/items/{original['id']}").status_code == 204
    assert client.get("/api/v1/media/" + original["id"]).json()["shelf_ids"] == []
    assert client.get("/api/v1/media/" + original["id"]).json()["collection_ids"] == [legacy["id"]]


def test_shelf_cells_private_counts_export_and_delete(client, other, monkeypatch):
    media = reference(client, monkeypatch)
    moment = cell(client, media)
    selected = group(client)
    endpoint = f"/api/v1/shelves/{selected['id']}/items"
    assert other.put(endpoint, json={"cell_id": moment["id"]}).status_code == 404
    for _ in range(2):
        assert client.put(endpoint, json={"cell_id": moment["id"]}).status_code == 204
    assert other.get("/api/v1/cells", params={"shelf_id": selected["id"]}).status_code == 404
    items = client.get("/api/v1/cells", params={"shelf_id": selected["id"]}).json()
    assert items["total"] == 1 and items["items"][0]["shelf_ids"] == [selected["id"]]
    assert client.get("/api/v1/shelves").json()["items"][0]["cell_count"] == 1
    exported = client.get("/api/v1/library/export").json()
    assert exported["shelf_cells"] == [{"shelf_id": selected["id"], "cell_id": moment["id"]}]
    assert exported["cells"][0]["shelf_ids"] == [selected["id"]]
    assert client.delete("/api/v1/shelves/" + selected["id"]).status_code == 204
    assert client.get("/api/v1/cells").json()["items"][0]["shelf_ids"] == []
    assert client.get("/api/v1/media/" + media["id"]).status_code == 200


def test_reference_cell_ranges_and_export_require_file(client, monkeypatch):
    media = reference(client, monkeypatch)
    moment = cell(client, media)
    duplicate = cell(client, media)
    assert duplicate["id"] == moment["id"]
    assert (
        client.post(
            "/api/v1/cells",
            json={"media_id": media["id"], "title": "長すぎる", "start_ms": 0, "end_ms": 300001},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/cells",
            json={"media_id": media["id"], "title": "範囲外", "start_ms": 3599000, "end_ms": 3600001},
        ).status_code
        == 422
    )
    response = client.post(f"/api/v1/cells/{moment['id']}/clip")
    assert response.status_code == 409 and response.json()["error"]["code"] == "REFERENCE_UNSUPPORTED"


def test_cell_detail_stays_private_and_tracks_edits(client, other, monkeypatch):
    media = reference(client, monkeypatch)
    moment = cell(client, media)
    endpoint = f"/api/v1/cells/{moment['id']}"
    detail = client.get(endpoint).json()
    assert {key: value for key, value in detail.items() if key != "created_at"} == {
        key: value for key, value in moment.items() if key != "created_at"
    }
    assert datetime.fromisoformat(detail["created_at"]) == datetime.fromisoformat(moment["created_at"])
    assert other.get(endpoint).status_code == 404
    assert client.get("/api/v1/cells/missing").status_code == 404
    update = {"title": "切り取った瞬間", "start_ms": 3000, "end_ms": 4500, "note": "自分だけ", "tags": []}
    assert client.patch(endpoint, json=update).status_code == 200
    saved = client.get(endpoint).json()
    assert saved["start_ms"] == 3000 and saved["end_ms"] == 4500
    assert saved["media_id"] == media["id"] and saved["title"] == update["title"]
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).status_code == 404
    assert client.get("/api/v1/media/" + media["id"]).status_code == 200


@pytest.mark.parametrize("kind", ["shelves", "collections"])
def test_batch_membership_atomic_private_idempotent_and_bounded(client, other, monkeypatch, kind):
    first = reference(client, monkeypatch)
    second = client.post("/api/v1/imports", json={"url": "https://youtu.be/M7lc1UVf-VE"}).json()["media"]
    moment = cell(client, first)
    foreign = reference(other, monkeypatch)
    selected = group(client, kind)
    endpoint = f"/api/v1/{kind}/{selected['id']}/batch"
    assert other.put(endpoint, json={"media_ids": [foreign["id"]]}).status_code == 404
    assert (
        client.put(
            endpoint, json={"media_ids": [first["id"], foreign["id"]], "cell_ids": [moment["id"]]}
        ).status_code
        == 404
    )
    counts = client.get("/api/v1/" + kind).json()["items"][0]
    assert counts["media_count"] == counts["cell_count"] == 0
    values = {"media_ids": [first["id"], second["id"], first["id"]], "cell_ids": [moment["id"]]}
    for _ in range(2):
        assert client.put(endpoint, json=values).status_code == 204
    counts = client.get("/api/v1/" + kind).json()["items"][0]
    assert counts["media_count"] == 2 and counts["cell_count"] == 1
    assert client.put(endpoint, json={}).status_code == 422
    assert client.put(endpoint, json={"media_ids": [str(uuid4()) for _ in range(101)]}).status_code == 422
    assert (
        client.put(
            endpoint, json={"media_ids": [str(uuid4()) for _ in range(100)], "cell_ids": [moment["id"]]}
        ).status_code
        == 422
    )


def test_attach_preserves_identity_cells_source_and_custom_cover(client, other, monkeypatch, sample):
    media = reference(client, monkeypatch)
    moment = cell(client, media)
    selected = group(client)
    client.put(f"/api/v1/shelves/{selected['id']}/items", json={"media_id": media["id"]})
    client.put(f"/api/v1/shelves/{selected['id']}/items", json={"cell_id": moment["id"]})
    client.patch("/api/v1/media/" + media["id"], json={"note": "忘れない", "tags": ["推し"]})
    image = BytesIO()
    Image.new("RGB", (320, 240), "#74a48a").save(image, "PNG")
    cover = client.put(
        f"/api/v1/media/{media['id']}/cover", files={"file": ("cover.png", image.getvalue())}
    ).json()["assets"]["thumbnail"]
    values = {"reference_id": media["id"]}
    files = {"file": ("sample.mp4", sample.read_bytes())}
    assert other.post("/api/v1/media", data=values, files=files).status_code == 404
    key = str(uuid4())
    attached = client.post("/api/v1/media", data=values, files=files, headers={"Idempotency-Key": key})
    assert attached.status_code == 201, attached.text
    result = attached.json()
    assert result["id"] == media["id"] and result["storage_mode"] == "MANAGED"
    assert result["title"] == media["title"] and result["note"] == "忘れない" and result["tags"] == ["推し"]
    assert result["source"]["url"] == media["source"]["url"] and result["shelf_ids"] == [selected["id"]]
    # A retry must return the same video without generating a second job.
    assert (
        client.post("/api/v1/media", data=values, files=files, headers={"Idempotency-Key": key}).json()["id"]
        == media["id"]
    )
    with SessionLocal() as db:
        jobs = list(db.scalars(select(Job).where(Job.media_id == media["id"])))
        assert len(jobs) == 1
        job_id = jobs[0].id
    process(job_id)
    ready = client.get("/api/v1/media/" + media["id"]).json()
    assert ready["status"] == "READY" and ready["assets"]["thumbnail"] == cover
    kept = client.get("/api/v1/cells", params={"shelf_id": selected["id"]}).json()["items"][0]
    assert kept["id"] == moment["id"] and kept["storage_mode"] == "MANAGED"
    assert client.post(f"/api/v1/cells/{moment['id']}/clip").status_code == 200
    assert client.post("/api/v1/media", data=values, files=files).status_code == 409
    assert client.get("/api/v1/media").json()["total"] == 1


def test_short_attachment_rejected_without_mutation(client, monkeypatch, sample):
    media = reference(client, monkeypatch)
    cell(client, media, 12000, 13000)
    response = client.post(
        "/api/v1/media",
        data={"reference_id": media["id"]},
        files={"file": ("sample.mp4", sample.read_bytes())},
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "CELL_OUTSIDE_VIDEO"
    with SessionLocal() as db:
        assert db.get(Media, media["id"]).storage_mode == "REFERENCE"
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_new_cell_inherits_video_shelves_and_can_be_moved(client, monkeypatch):
    media = reference(client, monkeypatch)
    parent = group(client)
    second = group(client, name="推し")
    legacy = group(client, "collections", "以前のShelf")
    for kind, selected in [("shelves", parent), ("collections", legacy)]:
        client.put(f"/api/v1/{kind}/{selected['id']}/items", json={"media_id": media["id"]})
    moment = cell(client, media)
    assert moment["shelf_ids"] == [parent["id"]] and moment["collection_ids"] == [legacy["id"]]
    assert client.delete(f"/api/v1/shelves/{parent['id']}/items/{moment['id']}").status_code == 204
    assert (
        client.put(f"/api/v1/shelves/{second['id']}/items", json={"cell_id": moment["id"]}).status_code == 204
    )
    assert client.get("/api/v1/cells", params={"shelf_id": second["id"]}).json()["total"] == 1
    assert client.get("/api/v1/media/" + media["id"]).json()["shelf_ids"] == [parent["id"]]
