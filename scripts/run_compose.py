"""Portable Docker launcher for Windows, macOS, and Linux. No public listener."""

import argparse
import os
import shutil
import subprocess
import webbrowser

from configure_compose import configure
from private_paths import ROOT, STATE_ROOT, lan_address


def compose_command(action, executable="docker", config=None, mobile=False):
    config = config or STATE_ROOT / "compose.env"
    arguments = {
        "start": ["up", "--remove-orphans", "--build", "--wait", "--wait-timeout", "300"],
        "stop": ["down", "--remove-orphans"],  # Never remove volumes when stopping.
        "status": ["ps"],
    }
    overlay = (
        ["-f", str(ROOT / "compose.yaml"), "-f", str(ROOT / "infrastructure/docker/mobile.compose.yaml")]
        if mobile
        else []
    )
    return [
        executable,
        "compose",
        "--project-directory",
        str(ROOT),
        "--env-file",
        str(config),
        *overlay,
        *arguments[action],
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "login"])
    parser.add_argument(
        "--mobile", action="store_true", help="Explicitly enable the optional HTTPS Wi-Fi gateway"
    )
    args = parser.parse_args()
    if args.action == "login":
        login = STATE_ROOT / "Dockerログイン情報.txt"
        if not login.is_file():
            raise RuntimeError("Start Lumvia first. Login information has not been generated.")
        if os.name == "nt":
            os.startfile(str(login))
        elif shutil.which("open"):
            subprocess.run(["open", str(login)], check=True)
        else:
            subprocess.run(["xdg-open", str(login)], check=True)
        return
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Install and start Docker Desktop (Compose v2.20+ is required).")
    subprocess.run([docker, "compose", "version"], check=True, cwd=ROOT)
    config = configure() if args.action == "start" else STATE_ROOT / "compose.env"
    if not config.is_file():
        raise RuntimeError("No Lumvia container installation found. Start it first.")
    address = None
    if args.mobile:
        values = dict(
            line.split("=", 1)
            for line in config.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.startswith("#")
        )
        address = lan_address(values.get("MOBILE_BIND_IP", ""))
    subprocess.run(compose_command(args.action, docker, config, args.mobile), check=True, cwd=ROOT)
    if args.action == "start":
        print(f"Lumvia is ready. Login information: {STATE_ROOT / 'Dockerログイン情報.txt'}")
        webbrowser.open(f"https://{address}:8443" if address else "http://127.0.0.1:3000")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
