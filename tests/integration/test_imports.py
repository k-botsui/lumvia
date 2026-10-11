from unittest.mock import Mock

import pytest
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import Asset, Job, Media, Source
from app.sources import network
from fastapi.testclient import TestClient
from sqlalchemy import func, select


@pytest.fixture
def metadata(monkeypatch):
    fetch = Mock(
        return_value={"title": "共有した動画", "author_name": "投稿者", "html": "<p>共有したポスト</p>"}
    )
    monkeypatch.setattr(network, "json_metadata", fetch)
    return fetch


def test_reference_library_flow_and_ownership(client, other, metadata, monkeypatch):
    r = client.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ?t=42"})
    assert r.status_code == 201, r.text
    result = r.json()
    media = result["media"]
    assert media["storage_mode"] == "REFERENCE" and media["status"] == "READY"
    assert media["assets"] == {} and media["duration_ms"] == 0 and media["size_bytes"] == 0
    assert media["source"]["start_ms"] == 42000
    assert media["source"]["capabilities"] == {
        "embed": True,
        "download": False,
        "cells": True,
        "analyze": False,
    }
    metadata.reset_mock()
    again = client.post(
        "/api/v1/imports", json={"url": "https://youtube.com/shorts/dQw4w9WgXcQ", "title": "Do not overwrite"}
    )
    assert again.status_code == 200 and not again.json()["created"]
    assert again.json()["media"]["id"] == media["id"] and again.json()["media"]["title"] == media["title"]
    metadata.assert_not_called()
    other_result = other.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert other_result.status_code == 201 and other_result.json()["media"]["id"] != media["id"]
    for method in ["get", "patch", "delete"]:
        kwargs = {"json": {"favorite": True}} if method == "patch" else {}
        assert getattr(other, method)("/api/v1/media/" + media["id"], **kwargs).status_code == 404
    edited = client.patch(
        "/api/v1/media/" + media["id"],
        json={"title": "犬の海", "note": "また見る", "tags": ["海"], "favorite": True},
    ).json()
    assert edited["favorite"] and edited["tags"] == ["海"]
    shelf = client.post("/api/v1/shelves", json={"name": "リンク"}).json()
    collection = client.post("/api/v1/collections", json={"name": "好きな動画"}).json()
    for kind, group in [("shelves", shelf), ("collections", collection)]:
        assert (
            client.put(f"/api/v1/{kind}/{group['id']}/items", json={"media_id": media["id"]}).status_code
            == 204
        )
    assert client.get("/api/v1/media?favorite=true").json()["total"] == 1
    assert client.get("/api/v1/search?q=また見る").json()["media"][0]["id"] == media["id"]
    exported = client.get("/api/v1/library/export").json()
    assert exported["schema_version"] == 2
    assert exported["media"][0]["source"]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert exported["media"][0]["shelf_ids"] == [shelf["id"]]
    bookmark = client.post(
        "/api/v1/cells",
        json={"media_id": media["id"], "title": "リンクの区間", "start_ms": 0, "end_ms": 1000},
    )
    assert bookmark.status_code == 201 and bookmark.json()["storage_mode"] == "REFERENCE"
    for endpoint in [f"/api/v1/media/{media['id']}/analysis", f"/api/v1/cells/{bookmark.json()['id']}/clip"]:
        r = client.post(endpoint, json={"analyzer": "scenes"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "REFERENCE_UNSUPPORTED"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(Job)) == 0
    delete = Mock(side_effect=AssertionError("Reference deletion must never delete files"))
    monkeypatch.setattr("app.media.routes.storage.delete", delete)
    assert client.delete("/api/v1/media/" + media["id"]).status_code == 204
    delete.assert_not_called()
    with SessionLocal() as db:
        assert db.get(Media, media["id"]) is None
        assert db.scalar(select(func.count()).select_from(Source)) == 1  # Other owner's reference survives.


@pytest.mark.parametrize(
    "url,provider",
    [
        ("https://x.com/nico_nico_news/status/123456789", "x"),
        ("https://instagram.com/reel/ABC-def_1/?igsh=tracking", "instagram"),
        ("https://www.tiktok.com/@scout2015/video/6718335390845095173", "tiktok"),
    ],
)
def test_each_platform_fallback_and_duplicate(client, metadata, url, provider):
    metadata.side_effect = network.FetchError("No metadata")
    result = client.post("/api/v1/imports", json={"url": url, "title": "私の動画"})
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["media"]["title"] == "私の動画" and data["media"]["source"]["provider"] == provider
    assert not data["metadata_available"]
    duplicate = client.post(
        "/api/v1/imports", json={"url": url.replace("nico_nico_news", "another").replace("/reel/", "/p/")}
    )
    assert duplicate.status_code == 200 and duplicate.json()["media"]["id"] == data["media"]["id"]


def test_import_requires_auth_csrf_and_bounded_library(client, metadata, monkeypatch):
    with TestClient(app) as anonymous:
        assert (
            anonymous.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 401
        )
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    monkeypatch.setattr(settings, "max_reference_items", 1)
    assert client.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 201
    assert client.post("/api/v1/imports", json={"url": "https://instagram.com/reel/ABC1/"}).status_code == 413
    assert client.post("/api/v1/imports", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 200
