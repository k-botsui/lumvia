"""Copy a stopped native library out of a potentially cloud-synced checkout.

Restore a logical PostgreSQL snapshot instead of moving its live cluster or
RabbitMQ files. The original remains recoverable throughout migration.
"""

import hashlib
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from private_paths import CONFIG_FILE, ROOT, STATE_ROOT
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

PG = Path("/opt/homebrew/opt/postgresql@17/bin")


def digest_tree(directory):
    files = {}
    for path in directory.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as source:
                files[str(path.relative_to(directory))] = hashlib.file_digest(source, "sha256").hexdigest()
    return files


def table_counts(url):
    with psycopg.connect(url) as db:
        names = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
        return {
            name: db.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]
            for (name,) in names
        }


def transfer_database(legacy):
    config = dotenv_values(CONFIG_FILE)
    url = config["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    info = conninfo_to_dict(url)
    if info.get("host") != "127.0.0.1" or info.get("port") != "55432" or info.get("dbname") != "lumvia":
        raise RuntimeError("Only the existing native loopback database can be migrated.")
    environment = {
        **os.environ,
        "PGPASSWORD": info["password"],
        "PGHOST": "127.0.0.1",
        "PGPORT": "55432",
        "PGUSER": info["user"],
    }
    snapshot = STATE_ROOT / "migration.dump"
    subprocess.run(
        [str(PG / "pg_ctl"), "-D", str(legacy / "postgres"), "-l", str(legacy / "postgres.log"), "start"],
        check=True,
        timeout=30,
    )
    try:
        expected = table_counts(url)
        snapshot.touch(mode=0o600, exist_ok=False)
        subprocess.run(
            [str(PG / "pg_dump"), "-Fc", "-d", "lumvia", "-f", str(snapshot)],
            env=environment,
            check=True,
            timeout=60,
        )
    finally:
        subprocess.run(
            [str(PG / "pg_ctl"), "-D", str(legacy / "postgres"), "stop", "-m", "fast"], check=True, timeout=30
        )
    subprocess.run([sys.executable, str(ROOT / "scripts/local_infra.py")], check=True, timeout=60)
    subprocess.run(
        [str(PG / "pg_restore"), "--exit-on-error", "--no-owner", "-d", "lumvia", str(snapshot)],
        env=environment,
        check=True,
        timeout=60,
    )
    if table_counts(url) != expected:
        raise RuntimeError("Database restore counts differ. The original library remains available.")
    print("Restored the original database and verified every table count.", flush=True)


def migrate():
    legacy, config = ROOT / ".local", ROOT / ".env"
    if not (legacy / "credentials.json").is_file() or not config.is_file():
        raise RuntimeError("No complete legacy native installation was found.")
    for port in [3000, 8000, 55432, 5679, 6381]:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                raise RuntimeError("Stop Lumvia and its native services with the old launcher first.")
        except OSError:
            pass
    if STATE_ROOT.exists():
        raise RuntimeError("The private data directory already exists; nothing was replaced.")
    STATE_ROOT.parent.mkdir(parents=True, exist_ok=True)
    assets = legacy / "storage"
    expected = digest_tree(assets)
    if STATE_ROOT.exists():
        raise RuntimeError("The private data directory appeared during inspection; nothing was moved.")
    STATE_ROOT.mkdir(mode=0o700)
    marker = STATE_ROOT / "migration-pending"
    marker.touch(mode=0o600)
    shutil.copytree(assets, STATE_ROOT / "storage")
    if digest_tree(STATE_ROOT / "storage") != expected:
        raise RuntimeError("File verification failed; the legacy directory was preserved.")
    shutil.copy2(legacy / "credentials.json", STATE_ROOT / "credentials.json")
    (STATE_ROOT / "credentials.json").chmod(0o600)
    CONFIG_FILE.write_text(config.read_text().replace(str(legacy), str(STATE_ROOT)))
    CONFIG_FILE.chmod(0o600)
    backups = ROOT / "backups"
    if backups.is_dir():
        shutil.copytree(backups, STATE_ROOT / "backups")
        if digest_tree(STATE_ROOT / "backups") != digest_tree(backups):
            raise RuntimeError("Backup verification failed. The original backups remain available.")
    transfer_database(legacy)
    marker.unlink()
    print(
        f"Verified {len(expected)} asset files and the private backups. Credentials were preserved.",
        flush=True,
    )
    print(f"Private data: {STATE_ROOT}", flush=True)
    print("The verified legacy copy remains in the checkout until explicitly cleaned up.", flush=True)


if __name__ == "__main__":
    migrate()
