import shutil
from pathlib import Path

import pytest
from app.auth.service import passwords, redis
from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Library, User
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "reference_preview_root", tmp_path / "reference-previews")
    assert engine.url.database == "lumvia_test", "Refusing to run on a non-test database"
    with engine.begin() as db:
        tables = [
            t
            for t in db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars()
            if t != "alembic_version"
        ]
        for table in tables:
            db.execute(text(f'TRUNCATE "{table}" CASCADE'))
    for key in redis.scan_iter("login:testclient"):
        redis.delete(key)
    monkeypatch.setattr("app.media.routes.dispatch", lambda _: None)
    monkeypatch.setattr("app.analysis.routes.dispatch", lambda _: None)
    monkeypatch.setattr("app.jobs.routes.dispatch", lambda _: None)
    yield
    assert settings.storage_root.name == "test-storage"
    shutil.rmtree(settings.storage_root, ignore_errors=True)


@pytest.fixture
def accounts():
    result = []
    with SessionLocal() as db:
        for index in range(2):
            user = User(
                email=f"user{index}@example.test",
                name=f"User {index}",
                password_hash=passwords.hash("test-password-123"),
            )
            db.add(user)
            db.flush()
            library = Library(owner_id=user.id)
            db.add(library)
            db.flush()
            result.append((user.id, library.id))
        db.commit()
    return result


def client_for(index):
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login", json={"email": f"user{index}@example.test", "password": "test-password-123"}
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies["lumvia_csrf"]
    return client


@pytest.fixture
def client(accounts):
    with client_for(0) as c:
        yield c


@pytest.fixture
def other(accounts):
    with client_for(1) as c:
        yield c


@pytest.fixture
def sample():
    return Path(__file__).resolve().parents[1] / "apps/web/public/sample.mp4"
