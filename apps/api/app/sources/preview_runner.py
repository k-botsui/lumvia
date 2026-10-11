"""Runs in a resource-limited process; never imports browser cookies or credentials."""

import io
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from yt_dlp import YoutubeDL
from yt_dlp.networking import Request, Response
from yt_dlp.networking.exceptions import HTTPError, RequestError

from app.sources.network import FetchError
from app.sources.public_video import MAX_VIDEO, PublicVideoHTTPS, approved_url


class QuietLogger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class AnonymousDL(YoutubeDL):
    def __init__(self, transport):
        self.transport = transport
        super().__init__(
            {
                "quiet": True,
                "no_warnings": True,
                "logger": QuietLogger(),
                "cachedir": False,
                "skip_download": True,
                "noplaylist": True,
                "retries": 0,
                "extractor_retries": 0,
                "socket_timeout": 4,
                "proxy": "",
                "js_runtimes": {},
                "remote_components": [],
            }
        )

    def urlopen(self, req):
        if isinstance(req, str):
            req = Request(req)
        if not isinstance(req, Request):
            raise RequestError("Unsupported request")
        try:
            status, headers, body, url = self.transport.fetch(
                req.url,
                headers=req.headers,
                method=req.method,
                data=req.data,
            )
        except FetchError as exc:
            raise RequestError("Public video unavailable") from exc
        response = Response(io.BytesIO(body), url, headers, status=status)
        if status >= 400:
            raise HTTPError(response)
        return response


def choose_format(info):
    duration = float(info.get("duration") or 0)
    if not math.isfinite(duration) or not 0 < duration <= 600 or info.get("is_live") or info.get("has_drm"):
        raise FetchError("Unsupported duration")
    formats = []
    for item in info.get("formats") or [info]:
        if (
            item.get("ext") == "mp4"
            and (item.get("protocol") or "https") in {"https", "http"}
            and item.get("vcodec") != "none"
            and not item.get("has_drm")
            and not item.get("manifest_url")
            and approved_url(item.get("url", ""))
            and (item.get("filesize") or item.get("filesize_approx") or 0) <= MAX_VIDEO
        ):
            formats.append(item)
    if not formats:
        raise FetchError("No public MP4")
    # Prefer combined audio/video, then a small picture suitable for scene selection.
    return min(
        formats,
        key=lambda f: (
            f.get("acodec") == "none",
            not f.get("height"),
            abs((f.get("height") or 480) - 480),
            f.get("tbr") or 10000,
        ),
    )


def local_probe(path, binary):
    # Child processes stay in the runner's process group so its wall timeout kills them too.
    with path.with_suffix(".probe").open("w+b") as output:
        subprocess.run(
            [
                binary,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm,avi",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            stdout=output,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=True,
        )
        output.seek(0)
        info = json.loads(output.read(65536))
    path.with_suffix(".probe").unlink()
    streams = info["streams"]
    video = next(
        s for s in streams if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
    )
    duration = round(float(info["format"]["duration"]) * 1000)
    width, height = int(video["width"]), int(video["height"])
    if not 0 < duration <= 600000 or not 0 < width <= 4096 or not 0 < height <= 4096 or len(streams) > 16:
        raise FetchError("Media limit")
    return {"duration_ms": duration, "width": width, "height": height}


def main(url, directory, ffmpeg_binary="ffmpeg", ffprobe_binary="ffprobe"):
    directory = Path(directory)
    transport = PublicVideoHTTPS()
    with AnonymousDL(transport) as extractor:
        info = extractor.extract_info(url, download=False, process=False)
        if not isinstance(info, dict) or info.get("_type", "video") != "video":
            raise FetchError("Single public video required")
        candidate = choose_format(info)
        original = directory / "input.mp4"
        with original.open("wb") as output:
            transport.fetch(
                candidate["url"],
                headers=dict(extractor.params.get("http_headers") or {})
                | (info.get("http_headers") or {})
                | (candidate.get("http_headers") or {}),
                output=output,
            )
    metadata = local_probe(original, ffprobe_binary)
    if metadata["duration_ms"] > 600000:
        raise FetchError("Duration limit")
    preview = directory / "preview.mp4"
    subprocess.run(
        [
            ffmpeg_binary,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-threads",
            "2",
            "-filter_threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,matroska,webm,avi",
            "-i",
            str(original),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            "scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            "-fs",
            str(MAX_VIDEO + 1),
            str(preview),
        ],
        timeout=45,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    final = local_probe(preview, ffprobe_binary)
    if preview.stat().st_size > MAX_VIDEO or abs(final["duration_ms"] - metadata["duration_ms"]) > 100:
        raise FetchError("Incomplete preview")
    original.unlink()
    print(json.dumps(final))


if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except Exception:
        # Do not log upstream URLs, authentication tokens, or extractor response bodies.
        print("Public preview unavailable", file=sys.stderr)
        sys.exit(1)
