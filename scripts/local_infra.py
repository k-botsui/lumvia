"""Project-owned local services. No login items or system services are registered."""

import json
import os
import secrets
import signal
import socket
import subprocess
import time
from pathlib import Path

from private_paths import CONFIG_FILE, STATE_ROOT

LOCAL = STATE_ROOT
LOCAL.mkdir(mode=0o700, parents=True, exist_ok=True)
LOCAL.chmod(0o700)
PG = Path("/opt/homebrew/opt/postgresql@17/bin")


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def write_secret(path, value):
    path.write_text(value)
    path.chmod(0o600)


def owned_redis():
    if not listening(6381):
        return False
    result = subprocess.run(
        ["/opt/homebrew/bin/redis-cli", "-p", "6381", "--raw", "CONFIG", "GET", "dir"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip().splitlines() == ["dir", str(LOCAL)]


def owned_rabbit():
    prefix = "[" + ",".join(str(ord(char)) for char in str(LOCAL / "rabbitmq") + "/") + "]"
    result = subprocess.run(
        [
            "/opt/homebrew/opt/rabbitmq/sbin/rabbitmqctl",
            "--node",
            "lumvia@localhost",
            "-q",
            "eval",
            f"lists:prefix({prefix}, rabbit:data_dir()).",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def stop():
    subprocess.run([str(PG / "pg_ctl"), "-D", str(LOCAL / "postgres"), "stop", "-m", "fast"], check=False)
    if owned_redis():
        subprocess.run(["/opt/homebrew/bin/redis-cli", "-p", "6381", "shutdown", "nosave"], check=False)
    if listening(5679) and owned_rabbit():
        pid_file = LOCAL / "rabbitmq.pid"
        pid = int(pid_file.read_text()) if pid_file.is_file() else None
        try:
            subprocess.run(
                ["/opt/homebrew/opt/rabbitmq/sbin/rabbitmqctl", "--node", "lumvia@localhost", "stop"],
                check=False,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            # Ownership was checked before shutdown; only bound the recorded Lumvia node.
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGTERM)
                    for _ in range(10):
                        time.sleep(0.5)
                        os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def start():
    credentials = LOCAL / "credentials.json"
    if not credentials.exists():
        write_secret(
            credentials,
            json.dumps(
                {
                    "database_password": secrets.token_urlsafe(32),
                    "admin_email": "owner@lumvia.local",
                    "admin_password": secrets.token_urlsafe(18),
                },
                indent=2,
            ),
        )
    data = json.loads(credentials.read_text())
    password = data["database_password"]
    if not CONFIG_FILE.exists():
        write_secret(
            CONFIG_FILE,
            f"""DATABASE_URL=postgresql+psycopg://lumvia:{password}@127.0.0.1:55432/lumvia
SECRET_KEY={secrets.token_urlsafe(48)}
APP_URL=http://127.0.0.1:3000
BROKER_URL=amqp://guest:guest@127.0.0.1:5679//
REDIS_URL=redis://127.0.0.1:6381/0
FFMPEG_BIN=/opt/homebrew/bin/ffmpeg
FFPROBE_BIN=/opt/homebrew/bin/ffprobe
""",
        )
    access = f"Lumvia ローカル版\n\nURL: http://127.0.0.1:3000\nメールアドレス: {data['admin_email']}\nパスワード: {data['admin_password']}\n\n初回ログイン後、設定でパスワードを変更できます。変更後、この初期パスワードは使えません。\n"
    write_secret(LOCAL / "ログイン情報.txt", access)
    pgdata = LOCAL / "postgres"
    if not (pgdata / "PG_VERSION").exists():
        write_secret(LOCAL / "pg-password", password)
        subprocess.run(
            [
                str(PG / "initdb"),
                "-D",
                str(pgdata),
                "-U",
                "lumvia",
                "--auth=scram-sha-256",
                "--pwfile=" + str(LOCAL / "pg-password"),
                "--encoding=UTF8",
                "--locale=C",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with (pgdata / "postgresql.conf").open("a") as f:
            f.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\nunix_socket_directories = ''\n")
    if not listening(55432):
        subprocess.run(
            [str(PG / "pg_ctl"), "-D", str(pgdata), "-l", str(LOCAL / "postgres.log"), "start"], check=True
        )
    elif subprocess.run([str(PG / "pg_ctl"), "-D", str(pgdata), "status"], capture_output=True).returncode:
        raise RuntimeError("Port 55432 is occupied by another PostgreSQL. No process was stopped.")
    pg_env = {**os.environ, "PGPASSWORD": password}
    exists = subprocess.check_output(
        [
            str(PG / "psql"),
            "-h",
            "127.0.0.1",
            "-p",
            "55432",
            "-U",
            "lumvia",
            "-d",
            "postgres",
            "-tAc",
            "SELECT 1 FROM pg_database WHERE datname='lumvia'",
        ],
        env=pg_env,
        text=True,
    )
    if exists.strip() != "1":
        subprocess.run(
            [str(PG / "createdb"), "-h", "127.0.0.1", "-p", "55432", "-U", "lumvia", "lumvia"],
            env=pg_env,
            check=True,
        )
    if listening(6381) and not owned_redis():
        raise RuntimeError("Port 6381 is occupied by another Redis. No process was stopped.")
    if not listening(6381):
        subprocess.run(
            [
                "/opt/homebrew/bin/redis-server",
                "--bind",
                "127.0.0.1",
                "--port",
                "6381",
                "--protected-mode",
                "yes",
                "--daemonize",
                "yes",
                "--dir",
                str(LOCAL),
                "--save",
                "",
                "--appendonly",
                "no",
                "--pidfile",
                str(LOCAL / "redis.pid"),
                "--logfile",
                str(LOCAL / "redis.log"),
            ],
            check=True,
        )
    if listening(5679) and not owned_rabbit():
        raise RuntimeError("Port 5679 is occupied by another RabbitMQ. No process was stopped.")
    if not listening(5679):
        config = LOCAL / "rabbitmq.conf"
        config.write_text(
            "listeners.tcp.1 = 127.0.0.1:5679\nmanagement.tcp.ip = 127.0.0.1\nmanagement.tcp.port = 15679\ndistribution.listener.interface = 127.0.0.1\ndistribution.listener.port_range.min = 25679\ndistribution.listener.port_range.max = 25679\n"
        )
        env = {
            **os.environ,
            "RABBITMQ_CONFIG_FILE": str(config.with_suffix("")),
            "RABBITMQ_NODENAME": "lumvia@localhost",
            "RABBITMQ_MNESIA_BASE": str(LOCAL / "rabbitmq"),
            "RABBITMQ_LOG_BASE": str(LOCAL / "rabbitmq-logs"),
            "RABBITMQ_PID_FILE": str(LOCAL / "rabbitmq.pid"),
            "ERL_EPMD_ADDRESS": "127.0.0.1",
        }
        subprocess.run(["/opt/homebrew/opt/rabbitmq/sbin/rabbitmq-server", "-detached"], env=env, check=True)
        for _ in range(100):
            if listening(5679):
                break
            time.sleep(0.3)
        else:
            raise RuntimeError(f"RabbitMQ did not start; inspect {LOCAL / 'rabbitmq-logs'}")
    print("PostgreSQL, RabbitMQ, Redis are ready on loopback interfaces.")


if __name__ == "__main__":
    start()
