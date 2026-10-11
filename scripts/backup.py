"""Consistent private native backup, verified by restoration into a fresh scratch DB."""

import hashlib
import json
import os
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from private_paths import CONFIG_FILE, STATE_ROOT
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from run_local import owned_pid, start, stop

PG = Path("/opt/homebrew/opt/postgresql@17/bin")


def backup():
    config = {**dotenv_values(CONFIG_FILE), **os.environ}
    if config.get("STORAGE_BACKEND", "local") != "local":
        raise RuntimeError("This script backs up native local storage only, not S3.")
    url = config["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    info = conninfo_to_dict(url)
    if info.get("dbname") != "lumvia" or info.get("port") != "55432":
        raise RuntimeError("Refusing to operate outside the Lumvia native database.")
    running = any(owned_pid(name) for name in ["web", "api", "worker", "beat"])
    scratch = "lumvia_verify_" + uuid4().hex[:12]
    admin = {**info, "dbname": "postgres"}
    environment = {
        **os.environ,
        "PGPASSWORD": info["password"],
        "PGHOST": info["host"],
        "PGPORT": info["port"],
        "PGUSER": info["user"],
    }
    created = False
    try:
        if running:
            stop()
        with psycopg.connect(url) as db:
            active = db.execute(
                "SELECT count(*) FROM jobs WHERE state IN "
                "('PENDING','QUEUED','RUNNING','RETRYING','CANCEL_REQUESTED')"
            ).fetchone()[0]
            if active:
                raise RuntimeError("Wait for processing to finish/cancel, then run backup again.")
            expected = {
                table: db.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in [
                    "users",
                    "media",
                    "cells",
                    "assets",
                    "jobs",
                    "person_targets",
                    "shelves",
                    "collections",
                    "shelf_media",
                    "shelf_cells",
                    "collection_media",
                    "collection_cells",
                ]
            }
            revision = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        base = STATE_ROOT / "backups"
        base.mkdir(mode=0o700, exist_ok=True)
        target = base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target.mkdir(mode=0o700)
        dump = target / "database.dump"
        subprocess.run(
            [str(PG / "pg_dump"), "-Fc", "-d", "lumvia", "-f", str(dump)], env=environment, check=True
        )
        dump.chmod(0o600)
        storage = Path(config.get("STORAGE_ROOT") or STATE_ROOT / "storage")
        archive = target / "storage.tar.gz"
        with archive.open("xb") as output:
            archive.chmod(0o600)
            with tarfile.open(fileobj=output, mode="w:gz") as tar:
                if storage.exists():
                    tar.add(storage, arcname="storage", recursive=True)
        with psycopg.connect(**admin, autocommit=True) as db:
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(scratch)))
            created = True
        subprocess.run(
            [str(PG / "pg_restore"), "--exit-on-error", "--no-owner", "-d", scratch, str(dump)],
            env=environment,
            check=True,
        )
        with psycopg.connect(**{**info, "dbname": scratch}) as db:
            actual = {
                table: db.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in expected
            }
            if actual != expected:
                raise RuntimeError("Restored table counts differ. Backup is not verified.")
        manifest = {
            "schema_revision": revision,
            "database_restore_verified": True,
            "table_counts": expected,
            "sha256": {
                file.name: hashlib.file_digest(file.open("rb"), "sha256").hexdigest()
                for file in [dump, archive]
            },
            "secrets_included": False,
        }
        metadata = target / "manifest.json"
        metadata.write_text(json.dumps(manifest, indent=2) + "\n")
        metadata.chmod(0o600)
        print(f"Verified private backup: {target}")
    finally:
        if created:
            with psycopg.connect(**admin, autocommit=True) as db:
                db.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(scratch)))
        if running:
            start()


if __name__ == "__main__":
    backup()
