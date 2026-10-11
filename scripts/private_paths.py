"""Make the API's dependency-free native paths available to launcher scripts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.local_network import lan_address  # noqa: E402, F401
from app.local_paths import CONFIG_FILE, ROOT, STATE_ROOT  # noqa: E402, F401
