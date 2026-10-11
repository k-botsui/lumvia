"""Private HTTPS must support local login without weakening session protections."""

from app.config import settings
from app.main import app
from fastapi.testclient import TestClient


def test_private_https_login_session_csrf_and_origin(accounts, monkeypatch):
    origin = "https://192.168.1.10:8443"
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "local_network", True)
    monkeypatch.setattr(settings, "app_url", origin)
    # The middleware's allowed host list is built at startup. Use its existing
    # testserver host while exercising the production cookies and Origin check.
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/v1/auth/options").json() == {"password": True, "oidc": False}
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": origin},
            json={"email": "user0@example.test", "password": "test-password-123"},
        )
        assert response.status_code == 200
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2 and all(
            "Secure" in cookie and "SameSite=lax" in cookie for cookie in cookies
        )
        assert "HttpOnly" in next(cookie for cookie in cookies if cookie.startswith("lumvia_session="))
        assert client.get("/api/v1/auth/me").status_code == 200
        assert client.post("/api/v1/auth/logout", headers={"Origin": origin}).status_code == 403
        csrf = client.cookies["lumvia_csrf"]
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"Origin": "https://example.test", "X-CSRF-Token": csrf}
            ).status_code
            == 403
        )
        assert (
            client.post("/api/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": csrf}).status_code
            == 204
        )
        assert client.get("/api/v1/auth/me").status_code == 401
