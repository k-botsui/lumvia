"""Bounded HTTPS to approved platform endpoints, with DNS pinning and no automatic redirects.

The selected public IP is used for the socket; TLS still verifies the approved hostname.
No cookies, authentication, environment proxies, video downloads, or upstream HTML execution.
"""

import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import urlsplit

import certifi

HOSTS = {
    "www.youtube.com",
    "publish.x.com",
    "www.tiktok.com",
    "tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}
MAX_BYTES = 65536


class FetchError(Exception):
    pass


def public_addresses(host):
    addresses = list(
        dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
    )
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise FetchError("Unsafe DNS destination")
    return sorted(addresses, key=lambda ip: ":" in ip)


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=4, context=ssl.create_default_context(cafile=certifi.where()))
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def valid_image_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return bool(
            parts.scheme == "https"
            and parts.port in {None, 443}
            and not parts.username
            and not parts.password
            and len(url) <= 2048
            and not any(ord(char) < 32 or char == "\\" for char in url)
            and (
                host == "i.ytimg.com"
                or any(
                    host.endswith("." + domain)
                    for domain in ["tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com"]
                )
            )
        )
    except ValueError:
        return False


def request(url: str, method="GET", image=False):
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or (not valid_image_url(url) if image else parts.hostname not in HOSTS)
        or parts.port not in {None, 443}
        or parts.username
        or parts.password
    ):
        raise FetchError("Unsupported endpoint")
    connection = None
    try:
        addresses = public_addresses(parts.hostname)
        connection = PinnedHTTPS(parts.hostname, addresses[0])
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        connection.request(
            method,
            path,
            headers={
                "Accept": "image/jpeg,image/png,image/webp" if image else "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "Lumvia/0.1 (link metadata)",
            },
        )
        response = connection.getresponse()
        headers = dict((key.lower(), value) for key, value in response.getheaders())
        if method == "HEAD":
            return response.status, headers, b""
        maximum = 2 * 1024 * 1024 if image else MAX_BYTES
        if int(headers.get("content-length", "0")) > maximum:
            raise FetchError("Metadata too large")
        # A slow trickle must not keep a request alive indefinitely.
        deadline = time.monotonic() + 8
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError("Metadata timeout")
            if connection.sock:
                connection.sock.settimeout(min(4, remaining))
            chunk = response.read1(min(8192, maximum + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > maximum:
                raise FetchError("Metadata too large")
            chunks.append(chunk)
        body = b"".join(chunks)
        return response.status, headers, body
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise FetchError("Platform unavailable") from exc
    finally:
        if connection:
            connection.close()


def json_metadata(url):
    status, headers, body = request(url)
    if status != 200 or "application/json" not in headers.get("content-type", ""):
        raise FetchError("No metadata")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise FetchError("Invalid metadata") from exc
    if not isinstance(data, dict):
        raise FetchError("Invalid metadata")
    return data
