"""Private runtime data lives outside the source checkout and synced Documents."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def private_directory(platform: str, home: Path, environ: dict) -> Path:
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Lumvia"
    if platform == "win32":
        return Path(environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Lumvia"
    return Path(environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "lumvia"


STATE_ROOT = (
    Path(os.environ["LUMVIA_STATE_ROOT"]).expanduser().resolve()
    if os.environ.get("LUMVIA_STATE_ROOT")
    else private_directory(sys.platform, Path.home(), os.environ)
)
CONFIG_FILE = STATE_ROOT / "config.env"
