import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import settings


class ProcessingError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class Cancelled(Exception):
    pass


def video_encoding(quality=24):
    if settings.video_encoder == "h264_videotoolbox":
        # Apple's encoder permits an LGPL-only FFmpeg build, including older Intel Macs.
        return ["-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", "3000k"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(quality)]


def run_command(arguments, cancelled=lambda: False, timeout=None):
    """Bound CPU time, output size, memory (Linux), elapsed time, and process descendants."""
    timeout = timeout or settings.processing_timeout_seconds
    limiter = Path(__file__).with_name("resource_limiter.py")
    with TemporaryDirectory(prefix="lumvia-process-") as directory:
        out, err = Path(directory) / "stdout", Path(directory) / "stderr"
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(
                [sys.executable, str(limiter), str(timeout), *map(str, arguments)],
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                cwd=directory,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if k
                    in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE"}
                },
            )
            start = time.monotonic()
            try:
                while process.poll() is None:
                    if cancelled():
                        raise Cancelled()
                    if time.monotonic() - start > timeout:
                        raise ProcessingError(
                            "TIMED_OUT", "処理時間の上限に達しました。短い動画でお試しください。"
                        )
                    if out.stat().st_size + err.stat().st_size > 8 * 1024 * 1024:
                        raise ProcessingError("OUTPUT_LIMIT", "この動画は処理上限を超えています。")
                    time.sleep(0.2)
                if process.returncode:
                    raise ProcessingError(
                        "INVALID_MEDIA", "動画を処理できませんでした。別の形式で保存してお試しください。"
                    )
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        return out.read_text(errors="replace"), err.read_text(errors="replace")


def probe(path, cancelled):
    output, _ = run_command(
        [
            settings.ffprobe_bin,
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
            path,
        ],
        cancelled,
        30,
    )
    try:
        info = json.loads(output)
        video = next(
            s
            for s in info["streams"]
            if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
        )
        duration = round(float(info["format"]["duration"]) * 1000)
        width, height = int(video["width"]), int(video["height"])
        if (
            not 0 < duration <= settings.max_duration_ms
            or not 0 < width <= 4096
            or not 0 < height <= 4096
            or len(info["streams"]) > 16
        ):
            raise ValueError()
        return {"duration_ms": duration, "width": width, "height": height}
    except (KeyError, ValueError, StopIteration, OverflowError):
        raise ProcessingError("MEDIA_LIMIT", "対応する動画は60分以内、縦横4096ピクセル以内です。") from None


def ffmpeg(input_path, *arguments):
    return [
        settings.ffmpeg_bin,
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
        str(input_path),
        *map(str, arguments),
    ]


def can_remux(path, cancelled):
    output, _ = run_command(
        [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,matroska,webm,avi",
            "-show_entries",
            "stream=codec_type,codec_name,pix_fmt,width,height",
            "-of",
            "json",
            path,
        ],
        cancelled,
        30,
    )
    streams = json.loads(output).get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    return bool(
        len(video) == 1
        and video[0].get("codec_name") == "h264"
        and video[0].get("pix_fmt") == "yuv420p"
        and video[0].get("width", 99999) <= 1280
        and video[0].get("height", 99999) <= 1920
        and all(s.get("codec_name") == "aac" for s in audio)
    )
