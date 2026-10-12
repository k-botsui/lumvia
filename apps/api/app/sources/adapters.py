"""Platform adapters normalize references and capabilities without downloading media."""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from app.errors import problem
from app.sources import network

LABELS = {
    "youtube": "YouTube",
    "x": "X",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "local_upload": "ファイル",
}
YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
}
X_HOSTS = {
    "x.com",
    "www.x.com",
    "m.x.com",
    "mobile.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
}
IG_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
TK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}


@dataclass(frozen=True)
class Reference:
    provider: str
    external_id: str
    url: str
    fallback_title: str
    start_ms: int = 0


def invalid(message="YouTube・X・Instagram・TikTokの投稿や動画の共有リンクを貼ってください。"):
    problem(422, "UNSUPPORTED_URL", message)


def validated_url(value):
    value = value.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "https://" + value
    if len(value) > 2048 or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        invalid()
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or parts.port not in {None, 80, 443}
            or parts.username
            or parts.password
        ):
            invalid()
    except ValueError:
        invalid()
    if parts.hostname not in YT_HOSTS | X_HOSTS | IG_HOSTS | TK_HOSTS:
        invalid()
    return parts


def timestamp(value):
    if value.isdigit():
        return min(int(value), 86400) * 1000
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", value)
    if match and any(match.groups()):
        h, m, s = (int(v or 0) for v in match.groups())
        return min(h * 3600 + m * 60 + s, 86400) * 1000
    return 0


def is_tiktok_short(parts):
    return (
        parts.hostname in {"vm.tiktok.com", "vt.tiktok.com"}
        and bool(re.fullmatch(r"/[A-Za-z0-9]+/?", parts.path))
        or parts.hostname in TK_HOSTS
        and bool(re.fullmatch(r"/t/[A-Za-z0-9]+/?", parts.path))
    )


def resolve_short(parts):
    url = "https://" + parts.hostname + parts.path
    try:
        for _ in range(3):
            status, headers, _ = network.request(url, method="HEAD")
            if status not in {301, 302, 303, 307, 308}:
                break
            location = headers.get("location", "")
            if not location:
                break
            parts = validated_url(urljoin(url, location))
            if parts.hostname not in TK_HOSTS or parts.scheme != "https":
                raise network.FetchError("Unsafe redirect")
            # Only another supported short path or a concrete post may be requested.
            if re.fullmatch(r"/@[A-Za-z0-9_.]{1,64}/(?:video|photo)/[0-9]{1,25}/?", parts.path):
                return parse_reference("https://www.tiktok.com" + parts.path, resolve=False)
            if not is_tiktok_short(parts):
                raise network.FetchError("Unsupported redirect")
            url = "https://" + parts.hostname + parts.path
    except network.FetchError:
        pass
    invalid(
        "TikTokの短縮リンクを確認できませんでした。ブラウザで動画を開き、@ユーザー名/video/番号のURLをコピーしてください。"
    )


def parse_reference(value, resolve=True):
    parts = validated_url(value)
    path = parts.path.rstrip("/")
    query = parse_qs(parts.query)
    if parts.hostname in YT_HOSTS:
        video_id = None
        if parts.hostname == "youtu.be":
            video_id = path[1:]
        elif path == "/watch":
            ids = query.get("v", [])
            video_id = ids[0] if len(ids) == 1 else None
        else:
            match = re.fullmatch(r"/(shorts|live|embed)/([A-Za-z0-9_-]{11})", path)
            if match:
                video_id = match[2]
        if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            invalid(
                "YouTubeの動画の共有リンクを貼ってください。チャンネルや再生リストのURLは追加できません。"
            )
        start = timestamp(
            (query.get("t") or query.get("start") or parse_qs(parts.fragment).get("t") or ["0"])[0]
        )
        return Reference(
            "youtube", video_id, "https://www.youtube.com/watch?v=" + video_id, "YouTube · " + video_id, start
        )
    if parts.hostname in X_HOSTS:
        match = re.fullmatch(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{1,25})(?:/(?:video|photo)/[0-9]+)?", path)
        if match:
            handle, post_id = match[1], match[2]
            return Reference("x", post_id, f"https://x.com/{handle}/status/{post_id}", "X · @" + handle)
        match = re.fullmatch(r"/i/(?:web/)?status/([0-9]{1,25})", path)
        if match:
            return Reference("x", match[1], "https://x.com/i/status/" + match[1], "X · " + match[1])
        invalid(
            "Xのポストの「共有」→「リンクをコピー」を使ってください。ホームやプロフィールのURLは追加できません。"
        )
    if parts.hostname in IG_HOSTS:
        match = re.fullmatch(r"/(p|reel|reels|tv)/([A-Za-z0-9_-]{1,64})", path)
        if not match:
            invalid(
                "Instagramの投稿・リールの「共有」→「リンクをコピー」を使ってください。ログイン画面やプロフィールのURLは追加できません。"
            )
        kind = "reel" if match[1] == "reels" else match[1]
        return Reference(
            "instagram", match[2], f"https://www.instagram.com/{kind}/{match[2]}/", "Instagram · " + match[2]
        )
    if parts.hostname in TK_HOSTS:
        match = re.fullmatch(r"/@([A-Za-z0-9_.]{1,64})/(video|photo)/([0-9]{1,25})", path)
        if match:
            return Reference(
                "tiktok",
                match[3],
                f"https://www.tiktok.com/@{match[1]}/{match[2]}/{match[3]}",
                "TikTok · @" + match[1],
            )
        if resolve and is_tiktok_short(parts):
            return resolve_short(parts)
        invalid(
            "TikTokの動画の「共有」→「リンクをコピー」を使ってください。ホームやプロフィールのURLは追加できません。"
        )
    invalid()


class PostText(HTMLParser):
    """Keep the first paragraph as plain text, never use platform HTML as markup."""

    def __init__(self):
        super().__init__()
        self.active = False
        self.done = False
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "p" and not self.done:
            self.active = True
        if tag == "br" and self.active:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "p" and self.active:
            self.active = False
            self.done = True

    def handle_data(self, value):
        if self.active and not self.hidden:
            self.parts.append(value)


def clean(value, maximum):
    return " ".join(value.split())[:maximum] if isinstance(value, str) else ""


def fetch_metadata(ref):
    metadata = {"start_ms": ref.start_ms, "metadata_available": False}
    if ref.provider == "instagram":
        # Meta oEmbed requires an app token. No credentials are requested or scraped.
        return metadata
    endpoints = {
        "youtube": ("https://www.youtube.com/oembed", {"url": ref.url, "format": "json"}),
        "x": (
            "https://publish.x.com/oembed",
            {
                "url": ref.url.replace("https://x.com/", "https://twitter.com/"),
                "omit_script": "true",
                "dnt": "true",
                "hide_thread": "true",
            },
        ),
        "tiktok": ("https://www.tiktok.com/oembed", {"url": ref.url}),
    }
    endpoint, params = endpoints[ref.provider]
    try:
        data = network.json_metadata(endpoint + "?" + urlencode(params))
        title = clean(data.get("title"), 200)
        if ref.provider == "x":
            parser = PostText()
            parser.feed(clean(data.get("html"), 20000))
            title = clean("".join(parser.parts), 200)
        metadata.update(
            title=title, author=clean(data.get("author_name"), 100), metadata_available=bool(title)
        )
        thumbnail = data.get("thumbnail_url")
        if ref.provider == "tiktok" and isinstance(thumbnail, str) and network.valid_image_url(thumbnail):
            metadata["thumbnail_url"] = thumbnail
    except (network.FetchError, ValueError):
        pass
    return metadata


def describe_source(source):
    reference = source.kind != "local_upload"
    return {
        "provider": source.kind,
        "label": LABELS.get(source.kind, "リンク"),
        "url": source.external_url,
        "external_id": source.external_id,
        "author": source.metadata_json.get("author", ""),
        "start_ms": source.metadata_json.get("start_ms", 0),
        "thumbnail_url": f"https://i.ytimg.com/vi/{source.external_id}/hqdefault.jpg"
        if source.kind == "youtube" and not source.metadata_json.get("shared_import")
        else None,
        "capabilities": {
            "embed": reference,
            "download": not reference,
            "analyze": not reference,
            "cells": not reference,
        },
    }
