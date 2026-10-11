from io import BytesIO

from app.config import settings
from app.db import SessionLocal
from app.jobs.worker import process, purge_assets
from app.models import Asset, Job, Media
from app.storage.service import storage
from PIL import Image
from sqlalchemy import select


def ready_video(client, sample):
    response = client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes(), "video/mp4")})
    assert response.status_code == 201
    media = response.json()
    with SessionLocal() as db:
        job = db.scalar(select(Job.id).where(Job.media_id == media["id"]))
    process(job)
    assert client.get("/api/v1/media/" + media["id"]).json()["status"] == "READY"
    return media


def image_bytes():
    stream = BytesIO()
    Image.new("RGB", (400, 250), "#0071e3").save(stream, format="PNG")
    return stream.getvalue()


def test_cover_validation_and_private_access(client, other, sample, monkeypatch):
    monkeypatch.setattr("app.sources.routes.fetch_metadata", lambda _: {"metadata_available": False})
    media = client.post("/api/v1/imports", json={"url": "https://x.com/jack/status/20"}).json()["media"]
    endpoint = "/api/v1/media/" + media["id"] + "/cover"
    assert other.put(endpoint, files={"file": ("image.png", image_bytes())}).status_code == 404
    assert client.put(endpoint, files={"file": ("image.png", b"<svg/>")}).status_code == 415
    oversized = BytesIO()
    Image.new("RGB", (4097, 10)).save(oversized, format="PNG")
    assert client.put(endpoint, files={"file": ("image.png", oversized.getvalue())}).status_code == 415
    assert (
        client.put(endpoint, files={"file": ("image.jpg", b"x" * (2 * 1024 * 1024 + 1))}).status_code == 413
    )
    result = client.put(endpoint, files={"file": ("image.png", image_bytes())})
    assert result.status_code == 200, result.text
    url = result.json()["assets"]["thumbnail"]
    assert client.get(url).headers["content-type"] == "image/jpeg"
    assert other.get(url).status_code == 404
    with SessionLocal() as db:
        old = db.scalar(select(Asset.key).where(Asset.media_id == media["id"]))
    # Replacement adds cleanup for the obsolete cover, including references.
    assert client.put(endpoint, files={"file": ("image.png", image_bytes())}).status_code == 200
    purge_assets()
    with storage.materialize(old) as path:
        assert not path.exists()
    assert client.delete("/api/v1/media/" + media["id"]).status_code == 204
    purge_assets()
    assert client.get(url).status_code == 404


def test_cell_duplicate_limits_and_clip_export(client, other, sample, monkeypatch, tmp_path):
    media = ready_video(client, sample)
    monkeypatch.setattr(settings, "max_cells_per_media", 1)
    data = {"media_id": media["id"], "title": "保存した瞬間", "start_ms": 1250, "end_ms": 3750}
    first = client.post("/api/v1/cells", json=data).json()
    second = client.post("/api/v1/cells", json={**data, "title": "二重クリック"}).json()
    assert first["id"] == second["id"] and second["title"] == "保存した瞬間"
    assert client.post("/api/v1/cells", json={**data, "start_ms": 2000}).status_code == 413
    endpoint = "/api/v1/cells/" + first["id"] + "/clip"
    assert other.post(endpoint).status_code == 404
    client.headers.pop("X-CSRF-Token")
    assert client.post(endpoint).status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies["lumvia_csrf"]
    clip = client.post(endpoint)
    assert clip.status_code == 200, clip.text
    assert "attachment" in clip.headers["content-disposition"]
    from app.analysis.processing import probe

    output = tmp_path / "clip.mp4"
    output.write_bytes(clip.content)
    assert abs(probe(output, lambda: False)["duration_ms"] - 2500) < 150
    assert client.get("/api/v1/media/" + media["id"]).json()["cell_count"] == 1
    with SessionLocal() as db:
        m = db.get(Media, media["id"])
        m.duration_ms = 400000
        db.commit()
    assert client.post("/api/v1/cells", json={**data, "start_ms": 0, "end_ms": 300001}).status_code == 422


def test_media_and_analysis_limits(client, sample, monkeypatch):
    monkeypatch.setattr(settings, "max_managed_items", 1)
    media = ready_video(client, sample)
    assert (
        client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes())}).status_code == 413
    )
    monkeypatch.setattr(settings, "max_analysis_runs", 1)
    endpoint = "/api/v1/media/" + media["id"] + "/analysis"
    job = client.post(endpoint, json={"analyzer": "scenes"}).json()
    process(job["id"])
    assert client.post(endpoint, json={"analyzer": "scenes"}).status_code == 413
    run = client.get(endpoint).json()["runs"][0]
    assert client.delete(endpoint + "/" + run["id"]).status_code == 204
    assert client.post(endpoint, json={"analyzer": "scenes"}).status_code == 202
