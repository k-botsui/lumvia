"""Check the exact Git index for private files, local identifiers and stale content."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {".env", "config.env", "compose.env", "credentials.json", ".DS_Store", ".dev.vars"}
PRIVATE_PARTS = {
    "marketing",
    "private",
    ".local",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".wrangler",
}
PRIVATE_SUFFIXES = {
    ".log",
    ".key",
    ".pem",
    ".pfx",
    ".p12",
    ".dump",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".dmg",
    ".pkg",
}
TEXT = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".swift"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    failures = []
    paths = [p.decode() for p in git("ls-files", "-z").split(b"\0") if p]
    untracked = [
        p.decode() for p in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p
    ]
    failures.extend(f"Unstaged publication file: {name}" for name in untracked)
    if not paths:
        failures.append("No files in the index; stage the publication set first")
    for name in paths:
        path = Path(name)
        if (
            path.name in PRIVATE
            or (path.name.startswith(".env.") and path.name != ".env.example")
            or PRIVATE_PARTS.intersection(path.parts)
            or any(part.endswith(".app") for part in path.parts)
            or path.suffix in PRIVATE_SUFFIXES
            or (name.startswith("docs/") and path.suffix in {".png", ".jpg"})
            or (
                path.suffix in {".mp4", ".mov", ".webm", ".wav", ".mp3", ".sf2"}
                and name not in {"apps/web/public/sample.mp4", "demo/lumvia-trailer-v7-preview.mp4"}
            )
        ):
            failures.append(f"Private/generated file in index: {name}")
        blob = git("show", f":{name}")
        working = ROOT / name
        if not working.is_file() or working.read_bytes() != blob:
            failures.append(f"Index differs from current file: {name}")
        if path.suffix not in TEXT:
            continue
        source = blob.decode("utf-8", errors="replace")
        # Split literals so this checker does not flag its own implementation.
        local = re.compile(r"/" + r"Users/[^\s/]+|/" + r"home/[^\s/]+")
        for line, value in enumerate(source.splitlines(), 1):
            if local.search(value):
                failures.append(f"Local user path: {name}:{line}")
    if failures:
        print("Publication check failed:\n" + "\n".join(failures))
        return 1
    print(f"Publication check passed: {len(paths)} indexed files; current content matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
