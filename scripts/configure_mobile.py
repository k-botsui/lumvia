"""Prepare an optional same-owner Wi-Fi origin. Does not start a network listener."""

import argparse

from configure_compose import configure
from private_paths import lan_address


def prepare(address):
    address = lan_address(address)
    target = configure()
    lines = [
        line
        for line in target.read_text(encoding="utf-8").splitlines()
        if not line.startswith("MOBILE_BIND_IP=")
    ]
    target.write_text("\n".join([*lines, f"MOBILE_BIND_IP={address}"]) + "\n", encoding="utf-8")
    target.chmod(0o600)
    return f"https://{address}:8443"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_ip", help="Your PC's Wi-Fi IPv4 address; no public IP or hostname")
    args = parser.parse_args()
    try:
        print(f"Prepared {prepare(args.private_ip)}. No listener started. See docs/development/MOBILE.md.")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
