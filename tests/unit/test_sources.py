from unittest.mock import Mock

import pytest
from app.sources import network
from app.sources.adapters import fetch_metadata, parse_reference
from fastapi import HTTPException


@pytest.mark.parametrize(
    "url,provider,identifier,start",
    [
        ("https://youtu.be/dQw4w9WgXcQ?si=tracking&t=1m2s", "youtube", "dQw4w9WgXcQ", 62000),
        ("youtube.com/watch?v=dQw4w9WgXcQ&list=abc#t=12", "youtube", "dQw4w9WgXcQ", 12000),
        ("https://m.youtube.com/shorts/dQw4w9WgXcQ", "youtube", "dQw4w9WgXcQ", 0),
        ("https://www.youtube.com/live/dQw4w9WgXcQ?start=90", "youtube", "dQw4w9WgXcQ", 90000),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "youtube", "dQw4w9WgXcQ", 0),
        ("https://twitter.com/nico_nico_news/status/123456789/video/1?s=20", "x", "123456789", 0),
        ("https://x.com/i/web/status/123456789", "x", "123456789", 0),
        ("https://www.instagram.com/reel/Ab_1-c/?igsh=secret", "instagram", "Ab_1-c", 0),
        ("https://instagram.com/p/Ab_1-c/", "instagram", "Ab_1-c", 0),
        (
            "https://www.tiktok.com/@scout2015/video/6718335390845095173?lang=ja",
            "tiktok",
            "6718335390845095173",
            0,
        ),
        ("https://www.tiktok.com/@test/photo/123456789", "tiktok", "123456789", 0),
    ],
)
def test_normalize_supported_links(url, provider, identifier, start):
    ref = parse_reference(url)
    assert (ref.provider, ref.external_id, ref.start_ms) == (provider, identifier, start)
    assert ref.url.startswith("https://")
    assert "tracking" not in ref.url and "igsh" not in ref.url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "file:///etc/passwd",
        "https://x.com@evil.test/status/123",
        "https://user:password@youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=bad",
        "https://www.youtube.com/playlist?list=abc",
        "https://x.com/home?lang=ja",
        "https://www.instagram.com/?hl=ja",
        "https://www.tiktok.com/ja-JP/",
        "https://t.co/abc",
        "https://www.tiktok.com/@test",
        "https://youtu.be/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&v=second",
        "https://x.com/abc/status/123%0a",
        "https://x.com\\@127.0.0.1/",
        "https://x.com/abc/status/123\nhttp://evil.test",
    ],
)
def test_reject_untrusted_links_without_fetch(url, monkeypatch):
    fetch = Mock(side_effect=AssertionError("Untrusted URL must never be fetched"))
    monkeypatch.setattr(network, "request", fetch)
    with pytest.raises(HTTPException) as exc:
        parse_reference(url)
    assert exc.value.status_code == 422
    fetch.assert_not_called()


def test_tiktok_short_validates_every_redirect(monkeypatch):
    fetch = Mock(
        return_value=(
            302,
            {"location": "https://www.tiktok.com/@scout2015/video/6718335390845095173?tracking=123"},
            b"",
        )
    )
    monkeypatch.setattr(network, "request", fetch)
    ref = parse_reference("https://vt.tiktok.com/ZAb123/?tracking=secret")
    assert ref.external_id == "6718335390845095173"
    fetch.assert_called_once_with("https://vt.tiktok.com/ZAb123/", method="HEAD")
    fetch.reset_mock()
    fetch.return_value = (302, {"location": "http://127.0.0.1/secret"}, b"")
    with pytest.raises(HTTPException):
        parse_reference("https://vm.tiktok.com/ZAb123/")
    assert fetch.call_count == 1


def test_short_link_loop_bounded(monkeypatch):
    fetch = Mock(return_value=(302, {"location": "https://vt.tiktok.com/ZLoop/"}, b""))
    monkeypatch.setattr(network, "request", fetch)
    with pytest.raises(HTTPException):
        parse_reference("https://vt.tiktok.com/ZLoop/")
    assert fetch.call_count == 3


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.2", "169.254.169.254", "::1", "::ffff:127.0.0.1", "fe80::1"]
)
def test_dns_rejects_any_private_address(address, monkeypatch):
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", (address, 443))],
    )
    with pytest.raises(network.FetchError):
        network.public_addresses("www.youtube.com")


def test_connect_pins_ip_but_verifies_tls_hostname(monkeypatch):
    sock = Mock()
    create = Mock(return_value=sock)
    monkeypatch.setattr(network.socket, "create_connection", create)
    connection = network.PinnedHTTPS("www.youtube.com", "8.8.8.8")
    context = Mock()
    connection._context = context
    connection.connect()
    create.assert_called_once_with(("8.8.8.8", 443), timeout=4)
    context.wrap_socket.assert_called_once_with(sock, server_hostname="www.youtube.com")
    connection.close()


def test_network_no_redirects_and_response_bound(monkeypatch):
    monkeypatch.setattr(network, "public_addresses", lambda _: ["8.8.8.8"])
    response = Mock()
    response.status = 302
    response.getheaders.return_value = [
        ("Location", "http://127.0.0.1"),
        ("Content-Type", "application/json"),
    ]
    response.read1.side_effect = [b"{}", b""]
    connection = Mock()
    connection.getresponse.return_value = response
    factory = Mock(return_value=connection)
    monkeypatch.setattr(network, "PinnedHTTPS", factory)
    with pytest.raises(network.FetchError):
        network.json_metadata("https://www.youtube.com/oembed")
    assert factory.call_count == 1
    connection.close.assert_called_once()
    response.status = 200
    response.getheaders.return_value = [("Content-Length", "65537")]
    with pytest.raises(network.FetchError):
        network.request("https://www.youtube.com/oembed")
    response.getheaders.return_value = []
    response.read1.side_effect = [b"x" * 65537]
    with pytest.raises(network.FetchError):
        network.request("https://www.youtube.com/oembed")


def test_metadata_html_is_plain_text_and_untrusted_urls_ignored(monkeypatch):
    monkeypatch.setattr(
        network,
        "json_metadata",
        lambda _: {
            "html": "<p>Hello <b>world</b><script>evil()</script></p><script>other()</script>",
            "author_name": "Author",
            "thumbnail_url": "http://127.0.0.1/private",
        },
    )
    ref = parse_reference("https://x.com/abc/status/123456")
    metadata = fetch_metadata(ref)
    assert metadata["title"] == "Hello world"
    assert "thumbnail_url" not in metadata and "html" not in metadata


@pytest.mark.parametrize(
    "body,content_type",
    [(b"<html>login</html>", "text/html"), (b"not JSON", "application/json"), (b"[]", "application/json")],
)
def test_bad_metadata_fails_cleanly(monkeypatch, body, content_type):
    monkeypatch.setattr(network, "request", lambda _: (200, {"content-type": content_type}, body))
    with pytest.raises(network.FetchError):
        network.json_metadata("https://www.youtube.com/oembed")


def test_metadata_failure_keeps_reference(monkeypatch):
    monkeypatch.setattr(network, "json_metadata", Mock(side_effect=network.FetchError("offline")))
    assert not fetch_metadata(parse_reference("https://youtu.be/dQw4w9WgXcQ"))["metadata_available"]


@pytest.mark.parametrize(
    "url",
    [
        "https://tiktokcdn.com.evil.test/cover.jpg",
        "https://evil.test/tiktokcdn.com/cover.jpg",
        "http://p16.tiktokcdn.com/cover.jpg",
        "https://user:password@p16.tiktokcdn.com/cover.jpg",
        "https://p16.tiktokcdn.com:8443/cover.jpg",
        "https://p16.tiktokcdn.com/cover.jpg\n",
        "https://p16.tiktokcdn.com\\@127.0.0.1/cover.jpg",
    ],
)
def test_image_urls_do_not_expand_network_boundary(url):
    assert not network.valid_image_url(url)


def test_cdn_image_fetch_rejects_private_dns(monkeypatch):
    assert network.valid_image_url("https://p16.tiktokcdn.com/cover.jpg")
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    connect = Mock(side_effect=AssertionError("Private address must never be connected"))
    monkeypatch.setattr(network, "PinnedHTTPS", connect)
    with pytest.raises(network.FetchError):
        network.request("https://p16.tiktokcdn.com/cover.jpg", image=True)
    connect.assert_not_called()
