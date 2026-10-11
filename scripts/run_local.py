"""Start/stop only Lumvia-owned processes; do not register macOS login items."""

import argparse
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from private_paths import ROOT, STATE_ROOT

LOCAL = STATE_ROOT
NODE_FALLBACK = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


def command_for(pid):
    try:
        return subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True).strip()
    except subprocess.CalledProcessError:
        return ""


def owned_pid(name):
    pid_file = LOCAL / (name + ".pid")
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text())
    except ValueError:
        return None
    command = command_for(pid)
    if str(ROOT) in command:
        return pid
    # Next.js changes its process title after startup, so verify its working directory too.
    if name == "web" and command.startswith("next-server"):
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True
        )
        if "n" + str(ROOT / "apps/web") in result.stdout.splitlines():
            return pid
    return None


def node_binary():
    candidate = os.environ.get("LUMVIA_NODE") or shutil.which("node") or str(NODE_FALLBACK)
    if not Path(candidate).is_file():
        raise RuntimeError("Node.js 20.9+ is required. Set LUMVIA_NODE to its executable.")
    return candidate


def start(dev=False):
    if (LOCAL / "migration-pending").exists():
        raise RuntimeError("The data migration is incomplete. The original library was preserved.")
    from local_infra import start as infrastructure

    infrastructure()
    python = ROOT / ".venv/bin/python"
    node = node_binary()
    temporary = LOCAL / "tmp"
    temporary.mkdir(mode=0o700, exist_ok=True)
    if not owned_pid("api"):
        # A terminated API cannot have an active clip stream; reclaim interrupted exports.
        for path in temporary.glob("lumvia-clip-*"):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "apps/api"),
        "PATH": str(Path(node).parent) + ":/opt/homebrew/bin:" + os.environ["PATH"],
        "NEXT_TELEMETRY_DISABLED": "1",
        "TMPDIR": str(temporary),
    }
    if not dev and not (ROOT / "apps/web/.next/BUILD_ID").exists():
        print("初回起動用に画面をビルドしています。")
        subprocess.run(
            [node, str(ROOT / "apps/web/node_modules/next/dist/bin/next"), "build"],
            cwd=ROOT / "apps/web",
            env=env,
            check=True,
        )
    subprocess.run(
        [str(ROOT / ".venv/bin/alembic"), "-c", str(ROOT / "apps/api/alembic.ini"), "upgrade", "head"],
        check=True,
        cwd=ROOT,
        env=env,
    )
    subprocess.run([str(python), str(ROOT / "scripts/bootstrap.py")], check=True, cwd=ROOT, env=env)
    processes = {
        "api": (
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                str(ROOT / "apps/api"),
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            ROOT,
        ),
        "worker": (
            [
                str(ROOT / ".venv/bin/celery"),
                "-A",
                "app.jobs.worker",
                "worker",
                "--without-mingle",
                "--without-gossip",
                "--pool=threads",
                "--concurrency=2",
                "--loglevel=WARNING",
            ],
            ROOT,
        ),
        "beat": (
            [
                str(ROOT / ".venv/bin/celery"),
                "-A",
                "app.jobs.worker",
                "beat",
                "--loglevel=WARNING",
                "--schedule",
                str(LOCAL / "celerybeat"),
            ],
            ROOT,
        ),
        "web": (
            [
                node,
                str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                "dev" if dev else "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            ROOT / "apps/web",
        ),
    }
    from local_infra import listening

    for name, (command, cwd) in processes.items():
        if owned_pid(name):
            continue
        port = {"api": 8000, "web": 3000}.get(name)
        if port and listening(port):
            raise RuntimeError(f"Port {port} is occupied by another process. No process was terminated.")
        with (LOCAL / (name + ".log")).open("ab") as log:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        (LOCAL / (name + ".pid")).write_text(str(proc.pid))
    for _ in range(60):
        try:
            with urlopen("http://127.0.0.1:3000/api/v1/health", timeout=2) as response:
                if response.status == 200:
                    print("Lumvia: http://127.0.0.1:3000")
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Lumvia did not become ready. Inspect logs in {LOCAL}")


def stop(all_services=False):
    pids = []
    for name in ["web", "beat", "worker", "api"]:
        pid = owned_pid(name)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
                pids.append(pid)
            except ProcessLookupError:
                pass
        (LOCAL / (name + ".pid")).unlink(missing_ok=True)
    for _ in range(40):
        if not any(command_for(pid) for pid in pids):
            break
        time.sleep(0.25)
    # Celery's warm shutdown can wait indefinitely for a large video. Keep stop bounded;
    # durable leases turn interrupted work into a retryable state after the next startup.
    for pid in pids:
        if command_for(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if all_services:
        from local_infra import stop as stop_infrastructure

        stop_infrastructure()
    print("Lumviaを停止しました。データは保存されています。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    start(args.dev) if args.action == "start" else stop(args.all)
