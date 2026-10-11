from io import BytesIO
from uuid import uuid4

import pytest
from app.db import SessionLocal
from app.models import Deletion, Job, Shelf
from app.storage.service import storage
from PIL import Image
from sqlalchemy import select


def link(client, monkeypatch, external_id=20):
    monkeypatch.setattr("app.sources.routes.fetch_metadata", lambda _: {"metadata_available": False})
    result = client.post("/api/v1/imports", json={"url": f"https://x.com/jack/status/{external_id}"})
    assert result.status_code == 201
    return result.json()["media"]


def moment(client, media):
    response = client.post(
        "/api/v1/cells",
        json={"media_id": media["id"], "title": "残した区間", "start_ms": 1000, "end_ms": 2000},
    )
    assert response.status_code == 201
    return response.json()


def test_batch_delete_rejects_foreign_and_missing_items_atomically(client, other, monkeypatch):
    owned = link(client, monkeypatch)
    foreign = link(other, monkeypatch)
    cell = moment(client, owned)
    for invalid in [foreign["id"], str(uuid4())]:
        response = client.post(
            "/api/v1/library/delete-batch",
            json={"media_ids": [owned["id"], invalid], "cell_ids": [cell["id"]]},
        )
        assert response.status_code == 404
        assert client.get("/api/v1/media/" + owned["id"]).status_code == 200
        assert client.get("/api/v1/cells/" + cell["id"]).status_code == 200
    foreign_cell = moment(other, foreign)
    assert (
        client.post(
            "/api/v1/library/delete-batch",
            json={"media_ids": [owned["id"]], "cell_ids": [foreign_cell["id"]]},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/media/" + owned["id"]).status_code == 200


def test_batch_delete_mixed_deduplicates_and_preserves_unselected_video(client, monkeypatch):
    removed = link(client, monkeypatch)
    retained = link(client, monkeypatch, 21)
    cascaded = moment(client, removed)
    standalone = moment(client, retained)
    group = client.post("/api/v1/shelves", json={"name": "整理先"}).json()
    client.put(
        f"/api/v1/shelves/{group['id']}/batch",
        json={"media_ids": [removed["id"], retained["id"]], "cell_ids": [cascaded["id"], standalone["id"]]},
    )
    assert (
        client.post(
            "/api/v1/library/delete-batch",
            json={
                "media_ids": [removed["id"], removed["id"]],
                "cell_ids": [cascaded["id"], standalone["id"]],
            },
        ).status_code
        == 204
    )
    assert client.get("/api/v1/media/" + removed["id"]).status_code == 404
    assert client.get("/api/v1/cells/" + cascaded["id"]).status_code == 404
    assert client.get("/api/v1/cells/" + standalone["id"]).status_code == 404
    assert client.get("/api/v1/media/" + retained["id"]).status_code == 200
    assert client.get("/api/v1/shelves").json()["items"][0]["media_count"] == 1
    assert client.get("/api/v1/shelves").json()["items"][0]["cell_count"] == 0


def test_batch_delete_processing_blocks_entire_selection(client, sample, monkeypatch):
    uploaded = client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes())}).json()
    reference = link(client, monkeypatch)
    payload = {"media_ids": [reference["id"], uploaded["id"]]}
    assert client.post("/api/v1/library/delete-batch", json=payload).status_code == 409
    assert client.get("/api/v1/media/" + reference["id"]).status_code == 200
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.media_id == uploaded["id"]))
        job.state = "CANCELLED"
        db.commit()
    assert client.post("/api/v1/library/delete-batch", json=payload).status_code == 204
    assert client.get("/api/v1/library/stats").json()["size_bytes"] == 0


def test_batch_delete_requires_nonempty_bounded_selection_and_csrf(client):
    for payload in [
        {},
        {"media_ids": [str(uuid4()) for _ in range(101)]},
        {"media_ids": [str(uuid4()) for _ in range(60)], "cell_ids": [str(uuid4()) for _ in range(41)]},
    ]:
        assert client.post("/api/v1/library/delete-batch", json=payload).status_code == 422
    assert (
        client.post(
            "/api/v1/library/delete-batch",
            json={"media_ids": [str(uuid4())]},
            headers={"X-CSRF-Token": "invalid"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("kind", ["shelves", "collections"])
def test_header_images_are_private_bounded_and_removable(client, other, kind):
    group = client.post("/api/v1/" + kind, json={"name": "好きな場面", "description": "説明"}).json()
    endpoint = f"/api/v1/{kind}/{group['id']}/header"
    image = BytesIO()
    Image.effect_noise((6000, 1000), 100).convert("RGB").save(image, format="JPEG", quality=98)
    data = image.getvalue()
    assert len(data) > 2 * 1024**2
    assert other.put(endpoint, files={"file": ("header.png", data)}).status_code == 404
    assert client.put(endpoint, files={"file": ("fake.jpg", b"not an image")}).status_code == 415
    assert client.put(endpoint, files={"file": ("large.png", b"x" * (50 * 1024**2 + 1))}).status_code == 413
    saved = client.put(endpoint, files={"file": ("header.png", data)})
    assert saved.status_code == 200
    url = saved.json()["header_url"]
    assert other.get(url).status_code == 404
    response = client.get(url)
    assert response.status_code == 200 and "no-store" in response.headers["cache-control"]
    result = Image.open(BytesIO(response.content))
    assert result.format == "JPEG" and result.width <= 1600 and result.height <= 900
    assert (
        client.patch(
            f"/api/v1/{kind}/{group['id']}", json={"name": "名前を変更", "description": "説明を変更"}
        ).json()["header_url"]
        == url
    )
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).status_code == 404
    assert client.get("/api/v1/" + kind).json()["items"][0]["header_url"] is None


def test_shelf_header_replace_and_shelf_delete_queue_cleanup(client):
    group = client.post("/api/v1/shelves", json={"name": "ヘッダー"}).json()
    endpoint = f"/api/v1/shelves/{group['id']}/header"
    image = BytesIO()
    Image.new("RGB", (100, 50), "white").save(image, format="JPEG")
    assert client.put(endpoint, files={"file": ("header.jpg", image.getvalue())}).status_code == 200
    with SessionLocal() as db:
        first = db.get(Shelf, group["id"]).header_key
    assert client.put(endpoint, files={"file": ("header.jpg", image.getvalue())}).status_code == 200
    with SessionLocal() as db:
        second = db.get(Shelf, group["id"]).header_key
        assert first != second
        assert db.scalar(select(Deletion).where(Deletion.key == first))
    assert client.delete(f"/api/v1/shelves/{group['id']}").status_code == 204
    with SessionLocal() as db:
        assert db.scalar(select(Deletion).where(Deletion.key == second))
    from app.jobs.worker import purge_assets

    purge_assets()
    assert not storage.path(first).exists() and not storage.path(second).exists()


@pytest.mark.parametrize("kind", ["shelves", "collections"])
def test_header_frame_is_private_persistent_and_does_not_crop_image(client, other, kind):
    group = client.post("/api/v1/" + kind, json={"name": "表示位置"}).json()
    endpoint = f"/api/v1/{kind}/{group['id']}/header"
    chosen = {"x": 33.4, "y": 92.7, "zoom": 1.8}
    assert group["header_frame"] == {"x": 50, "y": 50, "zoom": 1}
    assert client.patch(endpoint, json=chosen).status_code == 409
    image = BytesIO()
    Image.new("RGB", (400, 800), "white").save(image, format="JPEG")
    saved = client.put(endpoint, files={"file": ("portrait.jpg", image.getvalue())}).json()
    original = client.get(saved["header_url"]).content
    assert other.patch(endpoint, json=chosen).status_code == 404
    assert client.patch(endpoint, json=chosen, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    assert client.patch(endpoint, json=chosen).json()["header_frame"] == chosen
    for invalid in [
        {**chosen, "x": -1},
        {**chosen, "y": 101},
        {**chosen, "zoom": 0.99},
        {**chosen, "zoom": 3.01},
        {**chosen, "zoom": "NaN"},
        {**chosen, "header_key": "another-file.jpg"},
    ]:
        assert client.patch(endpoint, json=invalid).status_code == 422
    assert client.get("/api/v1/" + kind).json()["items"][0]["header_frame"] == chosen
    edited = client.patch(f"/api/v1/{kind}/{group['id']}", json={"name": "名前を編集"}).json()
    assert edited["header_frame"] == chosen and edited["header_url"] == saved["header_url"]
    assert client.get(edited["header_url"]).content == original
    replaced = client.put(endpoint, files={"file": ("portrait.jpg", image.getvalue())}).json()
    assert replaced["header_frame"] == {"x": 50, "y": 50, "zoom": 1}
    assert client.patch(endpoint, json=chosen).status_code == 200
    assert client.delete(endpoint).status_code == 204
    assert client.get("/api/v1/" + kind).json()["items"][0]["header_frame"] == {"x": 50, "y": 50, "zoom": 1}
