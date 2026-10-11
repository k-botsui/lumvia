import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.analysis.processing import ffmpeg, run_command


@dataclass
class Event:
    start_ms: int
    end_ms: int
    label: str
    event_type: str = "scene"
    confidence: float | None = None
    details: dict | None = None


class Analyzer(Protocol):
    name: str
    version: str
    configuration: dict

    def analyze(self, path: Path, duration_ms: int, cancelled) -> list[Event]: ...


class SceneAnalyzer:
    name = "scenes"
    version = "ffmpeg-scene-v1"
    configuration = {"threshold": 0.32, "minimum_scene_ms": 500, "analysis_width": 320, "max_events": 300}

    def analyze(self, path, duration_ms, cancelled):
        args = ffmpeg(
            path,
            "-an",
            "-vf",
            "scale=320:-2,select='gt(scene,0.32)',showinfo",
            "-vsync",
            "vfr",
            "-f",
            "null",
            "-",
        )
        args[args.index("-loglevel") + 1] = "info"
        _, stderr = run_command(args, cancelled)
        candidates = sorted({round(float(t) * 1000) for t in re.findall(r"pts_time:([0-9.]+)", stderr)})
        boundaries = [0]
        for position in candidates:
            if position - boundaries[-1] >= 500 and duration_ms - position >= 500:
                boundaries.append(position)
                if len(boundaries) >= 300:
                    break
        boundaries.append(duration_ms)
        return [
            Event(a, b, f"シーン {i + 1:02d}") for i, (a, b) in enumerate(zip(boundaries, boundaries[1:]))
        ]


def capabilities():
    return [
        {
            "id": "scenes",
            "name": "シーンを見つける",
            "description": "映像の切り替わりから、Cellの候補を見つけます。",
            "available": True,
        }
    ]
