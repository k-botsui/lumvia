"""Private, isolated lifecycle for the self-contained macOS application."""

import fcntl
import hashlib
import json
import os
import secrets
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

RESOURCES = Path(__file__).resolve().parent
APP = RESOURCES / "app"
STATE = Path(
    os.environ.get("LUMVIA_DESKTOP_STATE", Path.home() / "Library/Application Support/Lumvia Desktop")
)
RUNTIME = RESOURCES / "runtime"
PROCESSES = []
STOPPED = False
LOCK_FILE = None


def private_write(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write(content)
    path.chmod(0o600)


def available_ports():
    sockets = []
    try:
        for _ in range(4):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def start(name, command, env, cwd=APP):
    with (STATE / (name + ".log")).open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    PROCESSES.append((name, process))
    return process


def run(command, env):
    with (STATE / "setup.log").open("ab") as log:
        subprocess.run(command, env=env, cwd=APP, stdout=log, stderr=log, check=True, timeout=180)


def ready(url, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not STOPPED:
        if any(proc.poll() is not None for _, proc in PROCESSES):
            raise RuntimeError("A bundled service stopped")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Startup did not complete")


def wait_port(port, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not STOPPED:
        if any(proc.poll() is not None for _, proc in PROCESSES):
            raise RuntimeError("A bundled service stopped")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Local service did not start")


def stop():
    # Signal only process groups created by this supervisor. Never use name-based kill.
    for name, process in reversed(PROCESSES):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT if name == "postgres" else signal.SIGTERM)
                process.wait(timeout=10)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                # Media commands run in their own sessions. Bound their lifetime
                # too, using the current parent tree rather than executable names.
                rows = subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,pgid="], text=True)
                descendants = {process.pid}
                records = [tuple(map(int, row.split())) for row in rows.splitlines() if row.strip()]
                while True:
                    found = {pid for pid, parent, _ in records if parent in descendants}
                    if found.issubset(descendants):
                        break
                    descendants.update(found)
                groups = {group for pid, _, group in records if pid in descendants and group > 1}
                for group in groups - {process.pid}:
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def interrupted(*_):
    global STOPPED
    STOPPED = True


def main():
    global LOCK_FILE
    os.umask(0o077)
    STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    STATE.chmod(0o700)
    lock = (STATE / "app.lock").open("a")
    LOCK_FILE = lock
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("Lumvia is already running") from None
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupted)
    credentials_path = STATE / "credentials.json"
    if not credentials_path.exists():
        private_write(
            credentials_path,
            json.dumps(
                {
                    "database_password": secrets.token_urlsafe(32),
                    "admin_email": "owner@lumvia.local",
                    "admin_password": secrets.token_urlsafe(24),
                    "secret_key": secrets.token_urlsafe(48),
                }
            ),
        )
    credentials = json.loads(credentials_path.read_text())
    web_port, api_port, pg_port, cache_port = available_ports()
    origin = f"http://127.0.0.1:{web_port}"
    bin_dir = RUNTIME / "bin"
    python = str(RUNTIME / "python/bin/python3")
    env = {
        "HOME": str(Path.home()),
        "LANG": "en_US.UTF-8",
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "PYTHONPATH": str(APP / "apps/api"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LUMVIA_STATE_ROOT": str(STATE),
        "DATABASE_URL": f"postgresql+psycopg://lumvia:{credentials['database_password']}@127.0.0.1:{pg_port}/lumvia",
        "SECRET_KEY": credentials["secret_key"],
        "APP_URL": origin,
        "ENVIRONMENT": "development",
        "JOB_EXECUTOR": "desktop",
        "VIDEO_ENCODER": "h264_videotoolbox",
        "REDIS_URL": f"redis://127.0.0.1:{cache_port}/0",
        "FFMPEG_BIN": str(bin_dir / "ffmpeg"),
        "FFPROBE_BIN": str(bin_dir / "ffprobe"),
        "API_INTERNAL_URL": f"http://127.0.0.1:{api_port}",
        "HOSTNAME": "127.0.0.1",
        "PORT": str(web_port),
        "NEXT_TELEMETRY_DISABLED": "1",
        "TMPDIR": str(STATE / "tmp"),
    }
    (STATE / "tmp").mkdir(mode=0o700, exist_ok=True)
    for prefix in ("lumvia-process-", "lumvia-clip-", "lumvia-ingest-"):
        for path in (STATE / "tmp").glob(prefix + "*"):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
    pg = RUNTIME / "postgres/bin"
    pgdata = STATE / "postgres"
    if not (pgdata / "PG_VERSION").exists():
        password_file = STATE / "pg-password"
        private_write(password_file, credentials["database_password"])
        try:
            run(
                [
                    str(pg / "initdb"),
                    "-D",
                    str(pgdata),
                    "-U",
                    "lumvia",
                    "--auth=scram-sha-256",
                    f"--pwfile={password_file}",
                    "--encoding=UTF8",
                    "--locale=C",
                ],
                env,
            )
        finally:
            password_file.unlink(missing_ok=True)
    start(
        "postgres",
        [
            str(pg / "postgres"),
            "-D",
            str(pgdata),
            "-h",
            "127.0.0.1",
            "-p",
            str(pg_port),
            "-c",
            "unix_socket_directories=",
        ],
        env,
    )
    wait_port(pg_port)
    database_env = {**env, "PGPASSWORD": credentials["database_password"]}
    psql = [str(pg / "psql"), "-h", "127.0.0.1", "-p", str(pg_port), "-U", "lumvia", "-d", "postgres"]
    exists = subprocess.check_output(
        [*psql, "-tAc", "SELECT 1 FROM pg_database WHERE datname='lumvia'"], env=database_env, text=True
    )
    if exists.strip() != "1":
        run([*psql, "-c", "CREATE DATABASE lumvia"], database_env)
    start(
        "cache",
        [
            str(bin_dir / "valkey-server"),
            "--bind",
            "127.0.0.1",
            "--port",
            str(cache_port),
            "--protected-mode",
            "yes",
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(STATE),
        ],
        env,
    )
    wait_port(cache_port)
    run([python, "-m", "alembic", "-c", str(APP / "apps/api/alembic.ini"), "upgrade", "head"], env)
    run([python, str(APP / "scripts/bootstrap.py")], env)
    start(
        "api",
        [
            python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
            "--no-access-log",
        ],
        env,
    )
    start("worker", [python, "-m", "app.jobs.desktop"], env)
    # Next.js may write caches. Keep its runtime copy outside the signed app bundle.
    web_source = APP / "web"
    build_id = (web_source / "apps/web/.next/BUILD_ID").read_bytes()
    web_runtime = STATE / "web-runtime" / hashlib.sha256(build_id).hexdigest()[:20]
    if not web_runtime.exists():
        web_runtime.parent.mkdir(mode=0o700, exist_ok=True)
        temporary_web = web_runtime.with_name(web_runtime.name + ".partial")
        if temporary_web.exists():
            shutil.rmtree(temporary_web)
        shutil.copytree(web_source, temporary_web, symlinks=True)
        temporary_web.rename(web_runtime)
    start(
        "web", [str(bin_dir / "node"), str(web_runtime / "apps/web/server.js")], env, web_runtime / "apps/web"
    )
    ready(origin + "/api/v1/health")
    print(json.dumps({"url": origin, "credentials_path": str(credentials_path)}), flush=True)
    while not STOPPED:
        if any(proc.poll() is not None for _, proc in PROCESSES):
            raise RuntimeError("A bundled service stopped")
        if select.select([sys.stdin], [], [], 0.5)[0]:
            # Closing the native window or losing its parent stops all private services.
            sys.stdin.readline()
            break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not place credentials or raw local exception details in UI/stdout.
        diagnostic = traceback.format_exc()
        credentials_file = STATE / "credentials.json"
        if credentials_file.exists():
            for key, value in json.loads(credentials_file.read_text()).items():
                if ("password" in key or "key" in key) and value:
                    diagnostic = diagnostic.replace(value, "[redacted]")
        if STATE.is_dir():
            private_write(STATE / "startup-error.log", diagnostic)
        print(
            json.dumps({"error": "Lumviaを起動できませんでした。設定やデータは削除されていません。"}),
            flush=True,
        )
        sys.exit(1)
    finally:
        stop()
        if LOCK_FILE:
            LOCK_FILE.close()
