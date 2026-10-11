from uuid import uuid4

from app.db import SessionLocal
from app.jobs.worker import process
from app.main import app
from app.models import Asset, Job
from fastapi.testclient import TestClient
from sqlalchemy import select


def upload(client, sample, key=None, name="sample.mp4"):
    with sample.open("rb") as f:
        r = client.post(
            "/api/v1/media",
            files={"file": (name, f, "video/mp4")},
            headers={"Idempotency-Key": key} if key else {},
        )
    assert r.status_code == 201, r.text
    return r.json()


def process_media(identifier):
    with SessionLocal() as db:
        job_id = db.scalar(select(Job.id).where(Job.media_id == identifier, Job.kind == "ingest"))
    process(job_id)
    return job_id


def test_end_to_end_library(client, sample):
    media = upload(client, sample)
    job_id = process_media(media["id"])
    ready = client.get("/api/v1/media/" + media["id"]).json()
    assert ready["status"] == "READY"
    assert ready["duration_ms"] == 12000
    assert set(ready["assets"]) == {"original", "thumbnail", "preview"}
    preview = client.get(ready["assets"]["preview"], headers={"Range": "bytes=0-99"})
    assert preview.status_code == 206 and len(preview.content) == 100
    payload = {
        "media_id": media["id"],
        "title": "旅のハイライト",
        "start_ms": 1250,
        "end_ms": 3750,
        "tags": ["旅"],
        "note": "覚えておく瞬間",
    }
    cell = client.post("/api/v1/cells", json=payload)
    assert cell.status_code == 201, cell.text
    cell = cell.json()
    assert cell["origin"] == "user"
    shelf = client.post("/api/v1/shelves", json={"name": "旅"}).json()
    collection = client.post("/api/v1/collections", json={"name": "ハイライト"}).json()
    for kind, group, target in [
        ("shelves", shelf, {"media_id": media["id"]}),
        ("collections", collection, {"cell_id": cell["id"]}),
    ]:
        assert client.put(f"/api/v1/{kind}/{group['id']}/items", json=target).status_code == 204
        assert client.put(f"/api/v1/{kind}/{group['id']}/items", json=target).status_code == 204
    assert client.get("/api/v1/media?shelf_id=" + shelf["id"]).json()["total"] == 1
    assert client.get("/api/v1/cells?collection_id=" + collection["id"]).json()["total"] == 1
    search = client.get("/api/v1/search", params={"q": "覚えておく"}).json()
    assert search["cells"][0]["start_ms"] == 1250
    changed = client.patch(
        "/api/v1/cells/" + cell["id"],
        json={
            k: v for k, v in {**payload, "start_ms": 1500, "title": "編集した瞬間"}.items() if k != "media_id"
        },
    )
    assert changed.status_code == 200 and changed.json()["start_ms"] == 1500
    assert (
        client.patch("/api/v1/media/" + media["id"], json={"favorite": True, "note": "旅の記録"}).status_code
        == 200
    )
    assert client.get("/api/v1/media?favorite=true").json()["total"] == 1
    exported = client.get("/api/v1/library/export").json()
    assert exported["cells"][0]["title"] == "編集した瞬間"
    assert len(exported["collection_cells"]) == 1
    # Duplicate delivery must not reprocess a completed job or duplicate assets.
    process(job_id)
    assert client.get("/api/v1/jobs/" + job_id).json()["attempt"] == 1
    assert client.delete("/api/v1/shelves/" + shelf["id"]).status_code == 204
    assert client.get("/api/v1/media/" + media["id"]).status_code == 200
    assert client.delete("/api/v1/media/" + media["id"]).status_code == 204
    assert client.get("/api/v1/cells").json()["total"] == 0
    assert client.get(ready["assets"]["original"]).status_code == 404


def test_scene_analysis_and_provenance(client, sample):
    m = upload(client, sample)
    process_media(m["id"])
    response = client.post(f"/api/v1/media/{m['id']}/analysis", json={"analyzer": "scenes"})
    assert response.status_code == 202
    process(response.json()["id"])
    result = client.get(f"/api/v1/media/{m['id']}/analysis").json()
    assert result["runs"][0]["status"] == "COMPLETED", result
    assert len(result["events"]) == 3
    assert client.get("/api/v1/cells").json()["total"] == 0
    event = result["events"][1]
    accepted = client.post(
        "/api/v1/cells",
        json={
            "media_id": m["id"],
            "title": "真ん中のシーン",
            "start_ms": event["start_ms"],
            "end_ms": event["end_ms"],
            "event_id": event["id"],
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["origin"] == "analysis_accepted"
    assert accepted.json()["analysis_run_id"] == result["runs"][0]["id"]
    assert client.delete(f"/api/v1/media/{m['id']}/analysis/{result['runs'][0]['id']}").status_code == 204
    assert client.get("/api/v1/cells").json()["total"] == 1


def test_resource_authorization(client, other, sample):
    m = upload(client, sample)
    process_media(m["id"])
    cell = client.post(
        "/api/v1/cells", json={"media_id": m["id"], "title": "Private", "start_ms": 0, "end_ms": 1000}
    ).json()
    shelf = client.post("/api/v1/shelves", json={"name": "Private shelf"}).json()
    job = client.get("/api/v1/jobs").json()["items"][0]
    for path in [
        "/media/" + m["id"],
        "/cells?media_id=" + m["id"],
        "/jobs/" + job["id"],
        "/media/" + m["id"] + "/analysis",
    ]:
        assert other.get("/api/v1" + path).status_code == 404, path
    for asset in client.get("/api/v1/media/" + m["id"]).json()["assets"].values():
        assert other.get(asset).status_code == 404
        assert TestClient(app).get(asset).status_code == 401
    assert other.patch("/api/v1/media/" + m["id"], json={"title": "hacked"}).status_code == 404
    assert other.delete("/api/v1/cells/" + cell["id"]).status_code == 404
    assert (
        other.put("/api/v1/shelves/" + shelf["id"] + "/items", json={"media_id": m["id"]}).status_code == 404
    )
    own_shelf = other.post("/api/v1/shelves", json={"name": "Own"}).json()
    assert (
        other.put("/api/v1/shelves/" + own_shelf["id"] + "/items", json={"media_id": m["id"]}).status_code
        == 404
    )
    assert other.get("/api/v1/search?q=Private").json()["total"] == 0
    assert other.get("/api/v1/library/export").json()["media"] == []


def test_upload_idempotency_and_validation(client, sample, tmp_path):
    key = str(uuid4())
    first = upload(client, sample, key)
    second = upload(client, sample, key)
    assert first["id"] == second["id"]
    assert client.get("/api/v1/media").json()["total"] == 1
    assert (
        client.post(
            "/api/v1/media", files={"file": ("fake.mp4", b"<html>not a video</html>", "video/mp4")}
        ).status_code
        == 415
    )
    with sample.open("rb") as f:
        assert (
            client.post("/api/v1/media", files={"file": ("payload.html", f, "text/html")}).status_code == 415
        )
    modified = tmp_path / "changed.mp4"
    modified.write_bytes(sample.read_bytes() + b"changed")
    with modified.open("rb") as f:
        assert (
            client.post(
                "/api/v1/media",
                files={"file": ("sample.mp4", f, "video/mp4")},
                headers={"Idempotency-Key": key},
            ).status_code
            == 409
        )
    assert (
        client.post("/api/v1/imports", json={"url": "http://169.254.169.254/latest/meta-data/"}).status_code
        == 422
    )


def test_cancel_retry_and_invalid_video(client, sample, tmp_path):
    m = upload(client, sample)
    job = client.get("/api/v1/jobs").json()["items"][0]
    assert client.delete("/api/v1/media/" + m["id"]).status_code == 409
    assert client.post("/api/v1/jobs/" + job["id"] + "/cancel").json()["state"] == "CANCELLED"
    process(job["id"])
    assert client.get("/api/v1/jobs/" + job["id"]).json()["attempt"] == 0
    assert client.post("/api/v1/jobs/" + job["id"] + "/retry").json()["state"] == "RETRYING"
    process(job["id"])
    assert client.get("/api/v1/media/" + m["id"]).json()["status"] == "READY"
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"X" * 100)
    invalid = upload(client, fake)
    invalid_job = process_media(invalid["id"])
    failure = client.get("/api/v1/jobs/" + invalid_job).json()
    assert failure["state"] == "FAILED"
    assert failure["error_code"] == "INVALID_MEDIA"
    assert "Traceback" not in failure["error_message"]


def test_session_csrf_and_invalidation(client, accounts):
    assert TestClient(app).get("/api/v1/media").status_code == 401
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/shelves", json={"name": "CSRF"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert (
        client.post(
            "/api/v1/shelves", json={"name": "Cross origin"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cell_range_validation(client, sample):
    m = upload(client, sample)
    process_media(m["id"])
    for a, b in [(0, 0), (2000, 1000), (-1, 500), (0, 12001), (0.5, 1000)]:
        response = client.post(
            "/api/v1/cells", json={"media_id": m["id"], "title": "invalid", "start_ms": a, "end_ms": b}
        )
        assert response.status_code == 422, (a, b, response.text)
    assert client.patch("/api/v1/media/" + m["id"], json={"title": None}).status_code == 422
    assert client.patch("/api/v1/media/" + m["id"], json={"title": "   "}).status_code == 422
    assert client.get("/api/v1/media?limit=99999").status_code == 422


def test_malicious_filename_never_becomes_storage_path(client, sample):
    m = upload(client, sample, name="../../outside.mp4")
    with SessionLocal() as db:
        asset = db.scalar(select(Asset).where(Asset.media_id == m["id"]))
        assert ".." not in asset.key and "outside" not in asset.key
    assert m["title"] == "outside"


def test_rate_limits_and_capacity(client, sample, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_concurrent_jobs", 1)
    upload(client, sample)
    with sample.open("rb") as f:
        response = client.post("/api/v1/media", files={"file": ("second.mp4", f, "video/mp4")})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUEUE_FULL"


def test_security_headers(client):
    r = client.get("/api/v1/auth/me")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["X-Request-ID"]
    assert "access-control-allow-origin" not in r.headers
