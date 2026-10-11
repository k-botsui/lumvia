import pytest
from app.analysis.processing import ProcessingError
from app.db import SessionLocal
from app.jobs.worker import analyze
from app.models import AnalysisEvent, AnalysisRun, Cell, Job, Media
from sqlalchemy import select


def test_models_not_exposed_and_saved_cells_survive(client, sample):
    response = client.post("/api/v1/media", files={"file": ("sample.mp4", sample.read_bytes(), "video/mp4")})
    media = response.json()
    # Metadata is enough to exercise the schema and old-run visibility without loading any model.
    with SessionLocal() as db:
        item = db.get(Media, media["id"])
        item.status, item.duration_ms = "READY", 12000
        old = AnalysisRun(media_id=item.id, analyzer="persons", model_version="retired", status="COMPLETED")
        db.add(old)
        db.flush()
        db.add(
            AnalysisEvent(
                media_id=item.id,
                analysis_run_id=old.id,
                event_type="person_match",
                start_ms=0,
                end_ms=1000,
                label="historical",
            )
        )
        job = Job(
            library_id=item.library_id,
            media_id=item.id,
            kind="persons",
            state="FAILED",
            attempt=1,
            analysis_run_id=old.id,
        )
        db.add(job)
        saved = Cell(
            library_id=item.library_id,
            media_id=item.id,
            title="好きな瞬間",
            start_ms=0,
            end_ms=1000,
            origin="analysis_accepted",
            analysis_run_id=old.id,
        )
        db.add(saved)
        db.flush()
        job_id, cell_id, run_id = job.id, saved.id, old.id
        db.commit()
    capabilities = client.get("/api/v1/analysis/capabilities").json()["items"]
    assert [entry["id"] for entry in capabilities] == ["scenes"]
    assert client.get("/api/v1/person-targets").status_code == 404
    for kind in ["persons", "objects", "transcription"]:
        assert (
            client.post(f"/api/v1/media/{media['id']}/analysis", json={"analyzer": kind}).status_code == 422
        )
    results = client.get(f"/api/v1/media/{media['id']}/analysis").json()
    assert results["runs"] == results["events"] == results["transcripts"] == []
    assert client.get("/api/v1/search?q=historical").json()["total"] == 0
    assert client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 409
    saved = client.get("/api/v1/cells/" + cell_id).json()
    assert saved["title"] == "好きな瞬間"
    assert saved["origin"] == "analysis_accepted" and saved["analysis_run_id"] == run_id
    # Older history is not destructively dropped, which also preserves Cell provenance.
    with SessionLocal() as db:
        assert db.scalar(select(AnalysisRun).where(AnalysisRun.media_id == media["id"])) is not None


@pytest.mark.parametrize("kind", ["persons", "objects", "transcription"])
def test_old_queued_model_job_cannot_run(kind):
    with pytest.raises(ProcessingError, match="現行版"):
        analyze("unused-job", "unused-media", "unused-run", kind, lambda: False)
