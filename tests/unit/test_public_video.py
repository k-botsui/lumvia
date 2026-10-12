from email.message import Message
from io import BytesIO
from unittest.mock import Mock

import pytest
from app.config import Settings
from app.sources import public_video
from app.sources.network import FetchError
from app.sources.preview_runner import choose_format


def test_public_https_rejects_private_dns_before_socket(monkeypatch):
    monkeypatch.setattr(
        public_video, "public_addresses", lambda _: (_ for _ in ()).throw(FetchError("Unsafe DNS"))
    )
    socket = Mock()
    monkeypatch.setattr(public_video, "PinnedHTTPS", socket)
    with pytest.raises(FetchError):
        public_video.PublicVideoHTTPS().fetch("https://www.tiktok.com/video/123")
    socket.assert_not_called()


def response(status=200, headers=None, data=b"ok"):
    r = Mock()
    r.status = status
    r.getheaders.return_value = (headers or {}).items()
    r.info.return_value = Message()
    stream = BytesIO(data)
    r.read1.side_effect = stream.read
    return r


def test_redirect_and_byte_caps_block_before_following_or_writing(monkeypatch):
    monkeypatch.setattr(public_video, "public_addresses", lambda _: ["8.8.8.8"])
    connection = Mock()
    monkeypatch.setattr(public_video, "PinnedHTTPS", lambda *_: connection)
    connection.getresponse.return_value = response(302, {"location": "https://127.0.0.1/secret"})
    with pytest.raises(FetchError):
        public_video.PublicVideoHTTPS().fetch("https://www.tiktok.com/video/123")
    assert connection.request.call_count == 1
    connection.getresponse.return_value = response(200, {"content-length": str(public_video.MAX_VIDEO + 1)})
    output = BytesIO()
    with pytest.raises(FetchError):
        public_video.PublicVideoHTTPS().fetch("https://v16.tiktok.com/file.mp4", output=output)
    assert output.getvalue() == b""
    monkeypatch.setattr(public_video, "MAX_METADATA", 3)
    connection.getresponse.return_value = response(data=b"1234")
    with pytest.raises(FetchError):
        public_video.PublicVideoHTTPS().fetch("https://www.tiktok.com/video/123")


def test_public_transport_never_forwards_supplied_authentication(monkeypatch):
    monkeypatch.setattr(public_video, "public_addresses", lambda _: ["8.8.8.8"])
    connection = Mock()
    monkeypatch.setattr(public_video, "PinnedHTTPS", lambda *_: connection)
    connection.getresponse.return_value = response()
    public_video.PublicVideoHTTPS().fetch(
        "https://www.tiktok.com/video/123",
        headers={"Authorization": "secret", "Cookie": "sessionid=private", "User-agent": "public-agent"},
    )
    headers = connection.request.call_args.kwargs["headers"]
    assert "Cookie" not in headers and "Authorization" not in headers
    assert headers["User-Agent"] == "public-agent"


def test_preview_disallows_drm_live_manifests_and_size_overflow():
    candidate = {
        "url": "https://v16.tiktok.com/file.mp4",
        "ext": "mp4",
        "vcodec": "h264",
        "acodec": "aac",
        "height": 480,
    }
    assert choose_format({"duration": 24, "formats": [candidate]}) == candidate
    for change in [
        {"has_drm": True},
        {"manifest_url": "https://v16.tiktok.com/live.m3u8"},
        {"filesize": public_video.MAX_VIDEO + 1},
        {"url": "https://127.0.0.1/file.mp4"},
    ]:
        with pytest.raises(FetchError):
            choose_format({"duration": 24, "formats": [candidate | change]})
    for change in [{"duration": 601}, {"is_live": True}, {"duration": float("nan")}, {"has_drm": True}]:
        with pytest.raises(FetchError):
            choose_format({"duration": 24, "formats": [candidate]} | change)


def test_local_only_config_rejects_cloud_and_unsafe_support_links():
    base = {"database_url": "postgresql://localhost/test", "secret_key": "x" * 32, "_env_file": None}
    assert Settings(**base).support_github_repository == "k-botsui/lumvia"
    assert Settings(**base).support_gateway_url == (
        "https://lumvia-support.lumvia-support-worker.workers.dev"
    )
    assert Settings(**(base | {"support_gateway_url": ""})).support_gateway_url == ""
    assert Settings(**base).support_operator_delivery is False
    for values in [
        {"app_url": "https://example.com"},
        {"storage_backend": "s3"},
        {"oidc_issuer": "https://example.com"},
        {"support_github_repository": "https://evil.test/?user=data"},
        {"database_url": "postgresql://remote.example/test"},
        {"broker_url": "amqp://remote.example/"},
        {"redis_url": "redis://remote.example/0"},
        {"reference_preview_root": Settings(**base).storage_root},
    ]:
        with pytest.raises(ValueError):
            Settings(**(base | values))


@pytest.mark.parametrize(
    "gateway",
    [
        "http://example.test",
        "https://user:pass@example.test",
        "https://example.test/path",
        "https://example.test/?token=x",
        "https://example.test/#x",
    ],
)
def test_support_gateway_is_a_fixed_https_origin(gateway):
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql://localhost/test",
            secret_key="x" * 32,
            _env_file=None,
            support_gateway_url=gateway,
        )
