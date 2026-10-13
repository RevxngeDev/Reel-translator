"""Burns bilingual subtitles into the video with ffmpeg + libass (D-002, D-016).

Original on top (white, bold), translation below (yellow). Sizes scale with the
video width so 42 characters fit on a vertical frame. The original audio is kept
untouched (D-003).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.errors import RenderError
from core.render.layout import Cue

FONT = "Arial"  # ships with Windows; covers Latin and Cyrillic


def probe_size(video: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(video)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RenderError(f"ffprobe failed: {result.stderr.strip()}")
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def _ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(cues: list[Cue], width: int, height: int) -> str:
    orig_size = round(width * 0.040)
    trans_size = round(width * 0.036)
    outline = max(2, round(width * 0.004))
    margin_h = round(width * 0.05)
    margin_v = round(height * 0.12)
    # Colours are &HAABBGGRR.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Orig,{FONT},{orig_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,{margin_h},{margin_h},{margin_v},1
Style: Trans,{FONT},{trans_size},&H0000E6FF,&H0000E6FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{outline},0,2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in cues:
        text = "\\N".join(_escape(line) for line in cue.original)
        if cue.translation:
            text += "\\N{\\rTrans}" + "\\N".join(_escape(line) for line in cue.translation)
        events.append(f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Orig,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"


def render(cues: list[Cue], video: Path, out_path: Path, work_dir: Path) -> Path:
    width, height = probe_size(video)
    ass = work_dir / "subs.ass"
    ass.write_text(build_ass(cues, width, height), encoding="utf-8")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video.resolve()),
        # Relative path: avoids escaping the drive colon inside the filter graph.
        "-vf", f"subtitles={ass.name}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path.resolve()),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    except FileNotFoundError as exc:
        raise RenderError("ffmpeg is not installed or not on PATH") from exc
    if result.returncode != 0:
        raise RenderError(f"ffmpeg burn-in failed: {result.stderr.strip()}")
    return out_path
