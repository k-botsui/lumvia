"""Create a separate PostgreSQL test database; never run destructive fixtures on the application DB."""

import os
import subprocess
import sys

import psycopg
from dotenv import dotenv_values
from private_paths import CONFIG_FILE, ROOT, STATE_ROOT
from psycopg import sql

config = {**dotenv_values(CONFIG_FILE), **os.environ}
url = config["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
admin_url = url.rsplit("/", 1)[0] + "/postgres"
test_url = url.rsplit("/", 1)[0] + "/lumvia_test"
with psycopg.connect(admin_url, autocommit=True) as db:
    if not db.execute("SELECT 1 FROM pg_database WHERE datname=%s", ("lumvia_test",)).fetchone():
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("lumvia_test")))
env = {
    **os.environ,
    "DATABASE_URL": test_url.replace("postgresql://", "postgresql+psycopg://"),
    "PYTHONPATH": str(ROOT / "apps/api"),
    "STORAGE_ROOT": str(STATE_ROOT / "test-storage"),
    "SECRET_KEY": "test-only-" + "x" * 48,
    "REDIS_URL": config.get("REDIS_URL", "redis://127.0.0.1:6381/0"),
}
subprocess.run(
    [str(ROOT / ".venv/bin/alembic"), "-c", str(ROOT / "apps/api/alembic.ini"), "upgrade", "head"],
    env=env,
    cwd=ROOT,
    check=True,
)
raise SystemExit(
    subprocess.call([str(ROOT / ".venv/bin/python"), "-m", "pytest", *sys.argv[1:]], env=env, cwd=ROOT)
)
