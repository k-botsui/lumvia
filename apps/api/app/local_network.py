"""An optional private-Wi-Fi origin, never a public address or arbitrary hostname."""

from ipaddress import IPv4Address, IPv4Network
from urllib.parse import urlsplit

LAN_RANGES = tuple(IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def lan_address(value: str) -> str:
    address = IPv4Address(value)
    if not any(address in network for network in LAN_RANGES):
        raise ValueError("Use the PC's private Wi-Fi IPv4 address (RFC1918).")
    return str(address)


def is_lan_origin(value: str) -> bool:
    try:
        parts = urlsplit(value)
        lan_address(parts.hostname or "")
        return bool(
            parts.scheme == "https"
            and parts.port == 8443
            and not parts.username
            and not parts.password
            and parts.path in {"", "/"}
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        return False
