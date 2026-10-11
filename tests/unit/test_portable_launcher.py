import importlib
from pathlib import Path

from app.local_paths import private_directory


def test_private_paths_for_supported_desktops():
    home = Path("/users/owner")
    assert private_directory("darwin", home, {}) == home / "Library/Application Support/Lumvia"
    assert private_directory("win32", home, {}) == home / "AppData/Local/Lumvia"
    assert private_directory("win32", home, {"LOCALAPPDATA": "/local-user"}) == Path("/local-user/Lumvia")
    assert private_directory("linux", home, {}) == home / ".local/share/lumvia"
    assert private_directory("linux", home, {"XDG_DATA_HOME": "/private-data"}) == Path(
        "/private-data/lumvia"
    )


def test_compose_credentials_survive_repeated_starts(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("configure_compose")
    monkeypatch.setattr(module, "STATE_ROOT", tmp_path / "private with spaces")
    config = module.configure()
    original = config.read_bytes()
    assert module.configure() == config and config.read_bytes() == original
    assert "ADMIN_PASSWORD=" in original.decode()
    assert not (Path(__file__).resolve().parents[2] / "compose.env").exists()


def test_portable_commands_preserve_volumes_and_quote_paths(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("run_compose")
    config = tmp_path / "private with spaces" / "compose.env"
    command = module.compose_command("stop", config=config)
    assert (
        "down" in command
        and "--remove-orphans" in command
        and "-v" not in command
        and "--volumes" not in command
    )
    assert command[command.index("--env-file") + 1] == str(config)
    assert module.compose_command("start", config=config)[-4:] == [
        "--build",
        "--wait",
        "--wait-timeout",
        "300",
    ]


def test_mobile_requires_explicit_overlay_and_private_ip(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    launcher = importlib.import_module("run_compose")
    config = tmp_path / "compose.env"
    regular = launcher.compose_command("start", config=config)
    mobile = launcher.compose_command("start", config=config, mobile=True)
    assert "-f" not in regular and "-f" in mobile
    assert str(Path(__file__).resolve().parents[2] / "infrastructure/docker/mobile.compose.yaml") in mobile
    module = importlib.import_module("configure_compose")
    monkeypatch.setattr(module, "STATE_ROOT", tmp_path / "private")
    prepare = importlib.import_module("configure_mobile").prepare
    credentials = module.configure().read_text()
    assert prepare("192.168.10.22") == "https://192.168.10.22:8443"
    assert module.configure().read_text().startswith(credentials)
    assert "MOBILE_BIND_IP=192.168.10.22" in module.configure().read_text()
