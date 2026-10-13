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


def test_selected_frame_cover_is_server_decoded_and_private(client, other, sample):
    media = ready_video(client, sample)
    endpoint = f"/api/v1/media/{media['id']}/frame-cover"
    assert other.post(endpoint, json={"position_ms": 2000}).status_code == 404
    assert client.post(endpoint, json={"position_ms": -1}).status_code == 422
    assert client.post(endpoint, json={"position_ms": 12000}).status_code == 422
    colors = []
    urls = []
    for position in (2000, 6000):
        response = client.post(endpoint, json={"position_ms": position})
        assert response.status_code == 200, response.text
        urls.append(response.json()["assets"]["thumbnail"])
        content = client.get(response.json()["assets"]["thumbnail"]).content
        with Image.open(BytesIO(content)) as image:
            assert image.mode == "RGB" and not image.getexif()
            colors.append(image.resize((1, 1)).getpixel((0, 0)))
        assert other.get(response.json()["assets"]["thumbnail"]).status_code == 404
    assert sum(abs(a - b) for a, b in zip(*colors)) > 80
    assert urls[0] != urls[1]


def test_upload_larger_than_old_256mb_limit(client, sample, tmp_path):
    assert client.get("/api/v1/media/upload-limits").json()["max_upload_bytes"] == 2 * 1024**3
    large = tmp_path / "large.mp4"
    with large.open("wb") as file:
        file.write(sample.read_bytes())
        file.truncate(257 * 1024**2)
    with large.open("rb") as file:
        response = client.post("/api/v1/media", files={"file": ("large.mp4", file, "video/mp4")})
    assert response.status_code == 201, response.text
    assert response.json()["size_bytes"] == 257 * 1024**2


def test_repair_preview_preserves_original_cells_and_has_new_url(client, other, sample):
    media = ready_video(client, sample)
    before = client.get("/api/v1/media/" + media["id"]).json()
    original = client.get(before["assets"]["original"]).content
    cell = client.post(
        "/api/v1/cells", json={"media_id": media["id"], "title": "kept", "start_ms": 1000, "end_ms": 2500}
    ).json()
    endpoint = f"/api/v1/media/{media['id']}/repair-preview"
    assert other.post(endpoint).status_code == 404
    request = client.post(endpoint)
    assert request.status_code == 202
    job = request.json()["job_id"]
    assert client.post(endpoint).json()["job_id"] == job
    process(job)
    after = client.get("/api/v1/media/" + media["id"]).json()
    assert after["status"] == "READY"
    assert before["assets"]["preview"] != after["assets"]["preview"]
    assert client.get(after["assets"]["original"]).content == original
    assert client.get("/api/v1/cells/" + cell["id"]).status_code == 200


def test_high_resolution_preview_uses_compatible_video_and_keeps_audio(client, tmp_path, monkeypatch):
    import json
    import subprocess
    import sys

    source = tmp_path / "high-resolution.mp4"
    subprocess.run(
        [
            settings.ffmpeg_bin,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "smptebars=size=1920x1080:rate=60",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    if sys.platform == "darwin":
        monkeypatch.setattr(settings, "video_encoder", "h264_videotoolbox")
    media = ready_video(client, source)
    ready = client.get("/api/v1/media/" + media["id"]).json()
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(client.get(ready["assets"]["preview"]).content)
    streams = json.loads(
        subprocess.check_output(
            [settings.ffprobe_bin, "-v", "error", "-show_streams", "-of", "json", str(preview)]
        )
    )["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert video["codec_name"] == "h264" and video["profile"] in {"Baseline", "Constrained Baseline"}
    assert video["width"] == 1280 and video["height"] == 720 and video["level"] == 31
    assert video["pix_fmt"] == "yuv420p" and video["r_frame_rate"] == "30/1"
    assert any(stream["codec_type"] == "audio" and stream["codec_name"] == "aac" for stream in streams)
    assert client.get(ready["assets"]["original"]).content == source.read_bytes()
