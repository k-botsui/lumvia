import json
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from app import support
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import SupportSubmission
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def connected(monkeypatch):
    monkeypatch.setattr(settings, "support_github_repository", "example/lumvia")
    monkeypatch.setattr(settings, "support_gateway_url", "")
    monkeypatch.setattr(settings, "support_operator_delivery", True)
    monkeypatch.setattr(support, "github_account", lambda: "tester")
    calls = []

    def create(arguments, payload=None):
        calls.append((arguments, payload))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"number": 12, "html_url": "https://github.com/example/lumvia/issues/12"}),
        )

    monkeypatch.setattr(support, "github", create)
    return calls


def message():
    return {
        "request_id": str(uuid4()),
        "subject": "  再生について  ",
        "body": "  操作の説明です。  ",
    }


def test_submission_posts_only_input_and_replay_does_not_create_duplicate(client, connected):
    data = message()
    for _ in range(2):
        result = client.post("/api/v1/support", json=data)
        assert result.status_code == 201
        assert result.json() == {
            "issue_url": "https://github.com/example/lumvia/issues/12",
            "issue_number": 12,
        }
    assert len(connected) == 1
    assert connected[0][0] == ["repos/example/lumvia/issues", "--method", "POST", "--input", "-"]
    assert connected[0][1] == {"title": "再生について", "body": "操作の説明です。"}
    with SessionLocal() as db:
        receipt = db.scalar(select(SupportSubmission))
        assert receipt.state == "sent"
        assert not hasattr(receipt, "body") and not hasattr(receipt, "subject")
    changed = {**data, "body": "別の内容"}
    assert client.post("/api/v1/support", json=changed).status_code == 409
    assert len(connected) == 1


def test_support_auth_csrf_origin_and_extra_fields_are_rejected(client, connected):
    data = message()
    with TestClient(app) as unauthenticated:
        assert unauthenticated.post("/api/v1/support", json=data).status_code == 401
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/support", json=data).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert (
        client.post("/api/v1/support", json=data, headers={"Origin": "https://evil.test"}).status_code == 403
    )
    assert client.post("/api/v1/support", json={**data, "logs": "private"}).status_code == 422
    assert not connected


@pytest.mark.parametrize(
    "field,value", [("subject", " "), ("body", " "), ("subject", "x" * 201), ("body", "x" * 10001)]
)
def test_support_validates_message_before_any_public_write(client, connected, field, value):
    assert client.post("/api/v1/support", json={**message(), field: value}).status_code == 422
    assert not connected


def test_common_gateway_sends_without_user_github_credentials(client, connected, monkeypatch):
    monkeypatch.setattr(settings, "support_gateway_url", "https://support.example.test")
    monkeypatch.setattr(settings, "support_operator_delivery", False)
    monkeypatch.setattr(support, "github_account", lambda: None)
    calls = []

    def gateway(path, payload=None):
        calls.append((path, payload))
        if path == "/status":
            return httpx.Response(200, json={"repository": "example/lumvia", "can_submit": True})
        return httpx.Response(
            201, json={"issue_url": "https://github.com/example/lumvia/issues/23", "issue_number": 23}
        )

    monkeypatch.setattr(support, "gateway_request", gateway)
    assert client.get("/api/v1/support").json()["can_submit"] is True
    data = message()
    response = client.post("/api/v1/support", json=data)
    assert response.status_code == 201 and response.json()["issue_number"] == 23
    assert calls[-1] == (
        "/issues",
        {"request_id": data["request_id"], "subject": "再生について", "body": "操作の説明です。"},
    )
    assert not connected


def test_timeout_preserves_uncertain_receipt_and_blocks_resending(client, connected, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("gh", 30)

    monkeypatch.setattr(support, "github", timeout)
    data = message()
    assert client.post("/api/v1/support", json=data).status_code == 502
    assert client.post("/api/v1/support", json=data).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(SupportSubmission)).state == "uncertain"


def test_unconfigured_or_disconnected_support_cannot_send(client, connected, monkeypatch):
    monkeypatch.setattr(settings, "support_github_repository", "")
    assert client.post("/api/v1/support", json=message()).status_code == 503
    monkeypatch.setattr(settings, "support_github_repository", "example/lumvia")
    monkeypatch.setattr(support, "github_account", lambda: None)
    assert client.post("/api/v1/support", json=message()).status_code == 503
    assert not connected
