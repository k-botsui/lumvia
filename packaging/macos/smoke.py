"""Exercise the bundled app with no user database and no development PATH."""

import argparse
import http.cookiejar
import json
import select
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener


def launch(resources, state):
    process = subprocess.Popen(
        [str(resources / "runtime/python/bin/python3"), str(resources / "supervisor.py")],
        env={
            "HOME": str(Path.home()),
            "PATH": "/usr/bin:/bin",
            "LUMVIA_DESKTOP_STATE": str(state),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if not select.select([process.stdout], [], [], 180)[0]:
        process.stdin.write(b"stop\n")
        process.stdin.flush()
        raise RuntimeError("Bundled app did not become ready")
    message = json.loads(process.stdout.readline())
    if "url" not in message:
        process.wait(timeout=60)
        raise RuntimeError("Bundled app startup failed")
    return process, message["url"], json.loads(Path(message["credentials_path"]).read_text())


def shutdown(process):
    if process.poll() is None:
        process.stdin.write(b"stop\n")
        process.stdin.flush()
        process.wait(timeout=60)
    assert process.returncode == 0


def smoke(app):
    resources = app.resolve() / "Contents/Resources"
    with tempfile.TemporaryDirectory(prefix="lumvia-app-smoke-") as temporary:
        state = Path(temporary) / "state"
        process, origin, credentials = launch(resources, state)
        try:
            cookies = http.cookiejar.CookieJar()
            opener = build_opener(HTTPCookieProcessor(cookies))

            def request(path, data=None, content_type="application/json"):
                headers = {"Origin": origin}
                if data is not None:
                    headers["Content-Type"] = content_type
                    csrf = next((cookie.value for cookie in cookies if cookie.name == "lumvia_csrf"), None)
                    if csrf:
                        headers["X-CSRF-Token"] = csrf
                if isinstance(data, dict):
                    data = json.dumps(data).encode()
                with opener.open(Request(origin + path, data=data, headers=headers), timeout=150) as response:
                    body = response.read()
                    return json.loads(body) if "json" in response.headers.get("Content-Type", "") else body

            request(
                "/api/v1/auth/login",
                {"email": credentials["admin_email"], "password": credentials["admin_password"]},
            )
            assert request("/api/v1/auth/me")["name"] == "オーナー"
            boundary = "LumviaSmokeBoundary"
            sample = (resources / "app/web/apps/web/public/sample.mp4").read_bytes()
            multipart = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
                + sample
                + f"\r\n--{boundary}--\r\n".encode()
            )
            media = request("/api/v1/media", multipart, "multipart/form-data; boundary=" + boundary)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                media = request("/api/v1/media/" + media["id"])
                if media["status"] == "READY":
                    break
                assert media["status"] != "FAILED", "Bundled video processing failed"
                time.sleep(1)
            assert media["status"] == "READY", "Desktop durable queue did not complete"
            cell = request(
                "/api/v1/cells",
                {"media_id": media["id"], "title": "動作確認", "start_ms": 1000, "end_ms": 3000},
            )
            clip = request("/api/v1/cells/" + cell["id"] + "/clip", b"")
            assert len(clip) > 1000
            assert (state / "credentials.json").stat().st_mode & 0o077 == 0
            identifier = media["id"]
        finally:
            shutdown(process)
        # Restart uses the same durable data even though all service ports change.
        process, origin, _ = launch(resources, state)
        try:
            cookies.clear()
            request(
                "/api/v1/auth/login",
                {"email": credentials["admin_email"], "password": credentials["admin_password"]},
            )
            assert request("/api/v1/media/" + identifier)["status"] == "READY"
        finally:
            shutdown(process)
    print("Bundled smoke passed: startup, login, upload, durable processing, clip, shutdown, restart.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    smoke(parser.parse_args().app)
