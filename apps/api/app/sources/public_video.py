"""Anonymous, bounded platform HTTPS. All hops use a DNS-pinned public socket."""

import gzip
import http.client
import http.cookiejar
import io
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request as CookieRequest

from app.sources.network import FetchError, PinnedHTTPS, public_addresses

DOMAINS = (
    "youtube.com",
    "youtube-nocookie.com",
    "googlevideo.com",
    "ytimg.com",
    "tiktok.com",
    "tiktokcdn.com",
    "tiktokcdn-us.com",
    "tiktokcdn-eu.com",
    "tiktokv.com",
    "ibyteimg.com",
    "ibytedtos.com",
    "byteoversea.com",
    "x.com",
    "twitter.com",
    "twimg.com",
    "instagram.com",
    "cdninstagram.com",
    "fbcdn.net",
)
MAX_VIDEO = 32 * 1024 * 1024
MAX_METADATA = 4 * 1024 * 1024


def approved_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return bool(
            parts.scheme == "https"
            and parts.port in {None, 443}
            and not parts.username
            and not parts.password
            and len(url) <= 16384
            and not any(ord(c) < 32 or c == "\\" for c in url)
            and any(host == domain or host.endswith("." + domain) for domain in DOMAINS)
        )
    except ValueError:
        return False


class PublicVideoHTTPS:
    def __init__(self):
        self.deadline = time.monotonic() + 65
        self.requests = 0
        self.metadata_bytes = 0
        self.cookies = http.cookiejar.CookieJar()

    def fetch(self, url, *, headers=None, method="GET", data=None, output=None):
        maximum = MAX_VIDEO if output else MAX_METADATA
        if method not in {"GET", "HEAD", "POST"} or (data and len(data) > 65536):
            raise FetchError("Unsupported request")
        for hop in range(4):
            if not approved_url(url) or self.requests >= 40:
                raise FetchError("Unsupported destination")
            self.requests += 1
            parts = urlsplit(url)
            # Validate every address, then connect to the validated IP with hostname TLS.
            addresses = public_addresses(parts.hostname)
            connection = PinnedHTTPS(parts.hostname, addresses[0])
            try:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise FetchError("Preview timeout")
                connection.timeout = min(4, remaining)
                outgoing = {
                    k.lower(): v
                    for k, v in (headers or {}).items()
                    if k.lower() in {"user-agent", "accept", "content-type", "referer", "origin"}
                }
                outgoing.update(
                    {"Accept-Encoding": "identity", "User-Agent": outgoing.pop("user-agent", "Lumvia/0.1")}
                )
                # Only anonymous cookies issued during this public fetch; never browser cookies.
                cookie_request = CookieRequest(url, headers=outgoing)
                self.cookies.add_cookie_header(cookie_request)
                if cookie_request.has_header("Cookie"):
                    outgoing["Cookie"] = cookie_request.get_header("Cookie")
                connection.request(
                    method,
                    (parts.path or "/") + ("?" + parts.query if parts.query else ""),
                    body=data,
                    headers=outgoing,
                )
                response = connection.getresponse()
                self.cookies.extract_cookies(response, cookie_request)
                received = {k.lower(): v for k, v in response.getheaders()}
                if response.status in {301, 302, 303, 307, 308}:
                    if hop == 3 or "location" not in received:
                        raise FetchError("Redirect limit")
                    url = urljoin(url, received["location"])
                    if response.status == 303:
                        method, data = "GET", None
                    continue
                if int(received.get("content-length", "0")) > maximum:
                    raise FetchError("Preview size limit")
                sink = output or io.BytesIO()
                size = 0
                if method != "HEAD":
                    while True:
                        remaining = self.deadline - time.monotonic()
                        if remaining <= 0:
                            raise FetchError("Preview timeout")
                        if connection.sock:
                            connection.sock.settimeout(min(4, remaining))
                        chunk = response.read1(min(65536, maximum + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > maximum:
                            raise FetchError("Preview size limit")
                        sink.write(chunk)
                if output:
                    if received.get("content-encoding", "identity") != "identity" or response.status != 200:
                        raise FetchError("Video unavailable")
                    return response.status, received, b"", url
                body = sink.getvalue()
                encoding = received.get("content-encoding", "identity")
                if encoding == "gzip":
                    with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                        body = compressed.read(maximum + 1)
                elif encoding != "identity":
                    raise FetchError("Unsupported encoding")
                self.metadata_bytes += len(body)
                if len(body) > maximum or self.metadata_bytes > 16 * 1024 * 1024:
                    raise FetchError("Metadata size limit")
                return response.status, received, body, url
            except (OSError, ValueError, http.client.HTTPException) as exc:
                raise FetchError("Platform unavailable") from exc
            finally:
                connection.close()
        raise FetchError("Redirect limit")
