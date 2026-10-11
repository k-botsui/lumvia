import importlib
from pathlib import Path

import pytest


@pytest.fixture
def migration(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("migrate_local_data")
    project, state = tmp_path / "checkout", tmp_path / "private" / "Lumvia"
    monkeypatch.setattr(module, "ROOT", project)
    monkeypatch.setattr(module, "STATE_ROOT", state)
    monkeypatch.setattr(module, "CONFIG_FILE", state / "config.env")
    monkeypatch.setattr(module, "transfer_database", lambda _: None)
    monkeypatch.setattr(
        module.socket, "create_connection", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    legacy = project / ".local"
    (legacy / "storage").mkdir(parents=True)
    (legacy / "storage" / "scene.mp4").write_bytes(b"private-test-asset")
    (legacy / "postgres").mkdir()
    (legacy / "postgres" / "PG_VERSION").write_text("17")
    (legacy / "credentials.json").write_text('{"test_account": true}')
    (project / ".env").write_text(f"STORAGE_ROOT={legacy / 'storage'}\n")
    (project / "backups").mkdir()
    (project / "backups" / "database.dump").write_bytes(b"test-backup")
    return module, project, legacy, state


def test_private_migration_preserves_files_and_original(migration):
    module, project, legacy, state = migration
    asset = legacy / "storage" / "scene.mp4"
    original = asset.read_bytes()
    module.migrate()
    assert legacy.exists() and (project / ".env").exists()
    moved = state / "storage" / "scene.mp4"
    assert moved.read_bytes() == original == b"private-test-asset"
    assert (state / "config.env").read_text() == f"STORAGE_ROOT={state / 'storage'}\n"
    assert (state / "backups" / "database.dump").read_bytes() == b"test-backup"
    assert state.stat().st_mode & 0o777 == 0o700
    assert (state / "config.env").stat().st_mode & 0o777 == 0o600


def test_private_migration_refuses_existing_destination(migration):
    module, project, legacy, state = migration
    state.mkdir(parents=True)
    marker = state / "owner-data"
    marker.write_text("keep")
    with pytest.raises(RuntimeError, match="already exists"):
        module.migrate()
    assert legacy.is_dir() and (project / ".env").is_file()
    assert marker.read_text() == "keep"


def test_private_migration_requires_stopped_services(migration, monkeypatch):
    module, _, legacy, state = migration

    class Connected:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(module.socket, "create_connection", lambda *_args, **_kwargs: Connected())
    with pytest.raises(RuntimeError, match="Stop Lumvia"):
        module.migrate()
    assert legacy.is_dir() and not state.exists()


def test_private_migration_detects_concurrent_destination(migration, monkeypatch):
    module, _, legacy, state = migration
    inspect = module.digest_tree

    def concurrent(directory):
        result = inspect(directory)
        state.mkdir()
        (state / "owner-data").write_text("keep")
        return result

    monkeypatch.setattr(module, "digest_tree", concurrent)
    with pytest.raises(RuntimeError, match="appeared during inspection"):
        module.migrate()
    assert legacy.is_dir() and (state / "owner-data").read_text() == "keep"


def test_private_migration_rolls_back_failed_verification(migration, monkeypatch):
    module, project, legacy, state = migration
    inspect = module.digest_tree
    calls = []

    def mismatched(directory):
        calls.append(directory)
        return inspect(directory) if len(calls) == 1 else {}

    monkeypatch.setattr(module, "digest_tree", mismatched)
    with pytest.raises(RuntimeError, match="legacy directory was preserved"):
        module.migrate()
    assert legacy.is_dir() and (state / "migration-pending").is_file() and (project / ".env").is_file()
