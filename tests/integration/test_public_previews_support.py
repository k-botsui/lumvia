import json
import shutil
import time
from pathlib import Path

from app.analysis.processing import ProcessingError
from app.config import settings
from app.sources import previews

from tests.integration.test_batch_headers import link


def fake_preview(monkeypatch, sample):
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        shutil.copyfile(sample, Path(arguments[3]) / "preview.mp4")
        return json.dumps({"duration_ms": 12000, "width": 640, "height": 360}), ""

    monkeypatch.setattr(previews, "run_command", run)
    return calls


def test_preview_auth_csrf_cache_range_and_no_permanent_assets(client, other, monkeypatch, sample):
    media = link(client, monkeypatch)
    calls = fake_preview(monkeypatch, sample)
    path = f"/api/v1/media/{media['id']}/reference-preview"
    assert other.post(path).status_code == 404
    assert other.get(path).status_code == 404
    token = client.headers.pop("X-CSRF-Token")
    assert client.post(path).status_code == 403
    client.headers["X-CSRF-Token"] = token
    before = client.get("/api/v1/library/stats").json()
    result = client.post(path)
    assert result.status_code == 200
    assert result.json()["expires_at"] <= time.time() + previews.TTL
    assert client.post(path).json() == result.json()
    assert len(calls) == 1
    streamed = client.get(path, headers={"Range": "bytes=0-31"})
    assert streamed.status_code == 206 and streamed.content == sample.read_bytes()[:32]
    assert "no-store" in streamed.headers["cache-control"]
    assert client.get(path + "/info").json() == result.json()
    after = client.get("/api/v1/library/stats").json()
    for key in ["size_bytes", "stored_bytes", "media_count", "managed_count"]:
        assert before[key] == after[key]
    assert client.get("/api/v1/media/" + media["id"]).json()["storage_mode"] == "REFERENCE"
    metadata = settings.reference_preview_root / media["id"] / "info.json"
    data = json.loads(metadata.read_text())
    data["expires_at"] = time.time() - 1
    metadata.write_text(json.dumps(data))
    assert client.get(path).status_code == 404
    previews.purge_previews()
    assert not metadata.parent.exists()


def test_preview_failed_fetch_cleans_staging_and_capacity(client, monkeypatch):
    media = link(client, monkeypatch)

    def fail(arguments, **kwargs):
        (Path(arguments[3]) / "input.mp4").write_bytes(b"partial")
        raise ProcessingError("TIMED_OUT", "Timed out")

    monkeypatch.setattr(previews, "run_command", fail)
    result = client.post(f"/api/v1/media/{media['id']}/reference-preview")
    assert result.status_code == 422
    assert list(settings.reference_preview_root.iterdir()) == [settings.reference_preview_root / ".lock"]
    # Reserve space for both raw and converted files before any transfer.
    for index in range(3):
        directory = settings.reference_preview_root / str(index)
        directory.mkdir()
        (directory / "info.json").write_text(json.dumps({"expires_at": time.time() + 10 + index}))
        with (directory / "preview.mp4").open("wb") as out:
            out.truncate(100)
    monkeypatch.setattr(previews, "MAX_CACHE", 250)
    previews.prune_locked(reserve=100)
    assert len([p for p in settings.reference_preview_root.iterdir() if p.is_dir()]) == 1


def test_support_configuration_contains_no_account_or_library_data(client, monkeypatch):
    assert client.get("/api/v1/support").json() == {"github_url": None, "local_only": True}
    monkeypatch.setattr(settings, "support_github_repository", "example/lumvia")
    assert client.get("/api/v1/support").json() == {
        "github_url": "https://github.com/example/lumvia/issues/new",
        "local_only": True,
    }
