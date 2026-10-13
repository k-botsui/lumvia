import pytest
from app.db import SessionLocal
from app.models import Cell, Media, Shelf, Source, shelf_cells, shelf_media
from app.sources import network
from sqlalchemy import select


def seed(accounts, owner=0, suffix="0", mode="REFERENCE"):
    with SessionLocal() as db:
        source = Source(
            library_id=accounts[owner][1],
            kind="youtube",
            original_name="Video",
            external_url="https://www.youtube.com/watch?v=abcdefghij" + suffix,
            external_id="abcdefghij" + suffix,
        )
        db.add(source)
        db.flush()
        media = Media(
            library_id=accounts[owner][1],
            source_id=source.id,
            title="Video " + suffix,
            storage_mode=mode,
            status="READY",
        )
        db.add(media)
        db.flush()
        cell = Cell(library_id=accounts[owner][1], media_id=media.id, title="Moment", start_ms=0, end_ms=1000)
        shelf = Shelf(library_id=accounts[owner][1], name="Saved " + suffix, description="", color="#4f7bff")
        db.add_all([cell, shelf])
        db.flush()
        db.execute(shelf_media.insert().values(shelf_id=shelf.id, media_id=media.id))
        db.execute(shelf_cells.insert().values(shelf_id=shelf.id, cell_id=cell.id))
        db.commit()
        return media.id, cell.id, shelf.id


@pytest.fixture
def statuses(monkeypatch):
    status = {"head": 404, "get": 404, "online": True}

    def request(url, method="GET", status_only=False):
        if not status["online"]:
            raise network.FetchError("Offline")
        if url.endswith(".com/"):
            return 200, {}, b""
        return status["head" if method == "HEAD" else "get"], {}, b""

    monkeypatch.setattr(network, "request", request)
    return status


def check(client, media_id):
    response = client.post("/api/v1/library/link-check", json={"media_ids": [media_id]})
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


def test_inventory_ownership_and_managed_protection(client, other, accounts, statuses):
    item, _, _ = seed(accounts)
    seed(accounts, owner=1, suffix="1")
    seed(accounts, suffix="2", mode="MANAGED")
    assert client.get("/api/v1/library/link-check/targets").json() == {"media_ids": [item]}
    assert other.post("/api/v1/library/link-check", json={"media_ids": [item]}).status_code == 409
    managed = client.get("/api/v1/media?limit=100").json()["items"]
    managed = next(m["id"] for m in managed if m["storage_mode"] == "MANAGED")
    assert client.post("/api/v1/library/link-check", json={"media_ids": [managed]}).status_code == 409


def test_check_is_read_only_then_confirmed_cleanup_cascades(client, accounts, statuses):
    media, cell, shelf = seed(accounts)
    result = check(client, media)
    assert result["status"] == "broken" and result["proof"]
    assert result["cell_count"] == 1 and result["shelf_names"] == ["Saved 0"]
    assert client.get("/api/v1/media/" + media).status_code == 200
    assert (
        client.post("/api/v1/library/link-check/delete", json={"proofs": [result["proof"]]}).status_code
        == 204
    )
    with SessionLocal() as db:
        assert db.get(Media, media) is None and db.get(Cell, cell) is None
        assert db.get(Shelf, shelf) is not None
        assert list(db.execute(select(shelf_cells))) == []
        assert list(db.execute(select(shelf_media))) == []


@pytest.mark.parametrize("code", [200, 403, 429, 500])
def test_non_broken_responses_never_offer_deletion(client, accounts, statuses, code):
    media, _, _ = seed(accounts)
    statuses["head"] = code
    result = check(client, media)
    assert result["status"] == ("reachable" if code == 200 else "unknown")
    assert result["proof"] is None


def test_head_404_is_not_enough(client, accounts, statuses):
    media, _, _ = seed(accounts)
    statuses["get"] = 200
    assert check(client, media)["status"] == "unknown"


def test_offline_cannot_check_or_delete(client, accounts, statuses):
    media, cell, _ = seed(accounts)
    proof = check(client, media)["proof"]
    statuses["online"] = False
    assert client.get("/api/v1/library/link-check/targets").status_code == 503
    assert client.post("/api/v1/library/link-check", json={"media_ids": [media]}).status_code == 503
    assert client.post("/api/v1/library/link-check/delete", json={"proofs": [proof]}).status_code == 503
    with SessionLocal() as db:
        assert db.get(Media, media) and db.get(Cell, cell)


def test_restored_link_and_changed_impact_abort_entire_cleanup(client, accounts, statuses):
    media, _, _ = seed(accounts)
    other_media, _, _ = seed(accounts, suffix="1")
    proofs = [check(client, item)["proof"] for item in [media, other_media]]
    statuses["head"] = 200
    assert client.post("/api/v1/library/link-check/delete", json={"proofs": proofs}).status_code == 409
    statuses["head"] = 404
    with SessionLocal() as db:
        db.add(
            Cell(library_id=accounts[0][1], media_id=media, title="New moment", start_ms=1000, end_ms=2000)
        )
        db.commit()
    assert client.post("/api/v1/library/link-check/delete", json={"proofs": proofs}).status_code == 409
    with SessionLocal() as db:
        assert db.get(Media, media) and db.get(Media, other_media)


def test_forged_cross_library_and_expired_evidence_rejected(client, other, accounts, statuses, monkeypatch):
    media, _, _ = seed(accounts)
    proof = check(client, media)["proof"]
    assert client.post("/api/v1/library/link-check/delete", json={"proofs": [proof + "0"]}).status_code == 409
    assert other.post("/api/v1/library/link-check/delete", json={"proofs": [proof]}).status_code == 409
    import time

    now = time.time()
    monkeypatch.setattr("app.link_checks.time.time", lambda: now + 601)
    assert client.post("/api/v1/library/link-check/delete", json={"proofs": [proof]}).status_code == 409


def test_rejects_unsafe_destinations_and_login_redirects(monkeypatch):
    from app.link_checks import inspect_link

    def request(*args, **kwargs):
        raise AssertionError("Unsafe URL must never be requested")

    monkeypatch.setattr(network, "request", request)
    assert inspect_link("https://127.0.0.1/private")[0] == "unknown"
    assert inspect_link("https://www.youtube.com@127.0.0.1/watch?v=abcdefghij0")[0] == "unknown"
    monkeypatch.setattr(
        network, "request", lambda *args, **kwargs: (302, {"location": "https://127.0.0.1/private"}, b"")
    )
    assert inspect_link("https://www.youtube.com/watch?v=abcdefghij0")[0] == "unknown"
