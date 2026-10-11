"""Redacted Gitleaks scan of the index and every local Git blob, including dangling blobs."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    if not shutil.which("gitleaks"):
        print("Install Gitleaks before publication (macOS: brew install gitleaks)")
        return 1
    chunks, locations = [], []
    line = 1
    paths = [p.decode() for p in git("ls-files", "-z").split(b"\0") if p]
    inputs = [(name, git("show", f":{name}")) for name in paths]
    objects = git("cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)")
    for item in objects.decode().splitlines():
        oid, kind = item.split()
        if kind == "blob":
            inputs.append((f"Git blob {oid}", git("cat-file", "blob", oid)))
    for name, content in inputs:
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        source = source.rstrip("\n") + "\n"
        count = source.count("\n")
        locations.append((line, line + count - 1, name))
        chunks.append(source)
        line += count
    with tempfile.TemporaryDirectory(prefix="lumvia-secret-scan-") as directory:
        report = Path(directory) / "report.json"
        result = subprocess.run(
            [
                "gitleaks",
                "stdin",
                "--redact",
                "--no-banner",
                "--report-format",
                "json",
                "--report-path",
                str(report),
            ],
            input="".join(chunks),
            text=True,
            capture_output=True,
            cwd=ROOT,
        )
        if result.returncode not in {0, 1}:
            print("Gitleaks could not complete; publication is blocked")
            return 1
        findings = json.loads(report.read_text()) if report.exists() else []
        for finding in findings:
            position = finding["StartLine"]
            for first, last, name in locations:
                if first <= position <= last:
                    print(f"{finding['RuleID']}: {name}:{position - first + 1} (value redacted)")
                    break
        if result.returncode or findings:
            print("Secret scan failed; review findings before publication")
            return 1
    print(f"Secret scan passed: {len(paths)} indexed files and all local Git blobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
