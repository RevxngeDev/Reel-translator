"""CLI: python -m core translate <url> --to <lang>"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from core import SUPPORTED_LANGS, providers
from core.errors import PipelineError
from core.pipeline import run_job


def _translate(args: argparse.Namespace) -> int:
    name = args.name or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out)

    started = time.monotonic()
    # Media lives only inside this temporary directory and is deleted on exit.
    with tempfile.TemporaryDirectory(prefix="reel-") as tmp:
        try:
            report = run_job(
                args.url,
                args.to,
                name=name,
                work_dir=Path(tmp),
                out_dir=out_dir,
                source=providers.video_source(),
                stt=providers.speech_to_text(),
                translator=providers.translator(),
                render_video=not args.no_video,
            )
        except PipelineError as exc:
            print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
            return 1

    meta = {k: str(v) if isinstance(v, Path) else v for k, v in asdict(report).items()}
    meta["url"] = args.url
    meta["elapsed_s"] = round(time.monotonic() - started, 1)
    (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m core")
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("translate", help="Translate a reel into bilingual subtitles")
    t.add_argument("url", help="Reel URL")
    t.add_argument("--to", required=True, choices=SUPPORTED_LANGS, help="Target language")
    t.add_argument("--out", default="out", help="Output directory (default: out)")
    t.add_argument("--no-video", action="store_true", help="Skip the subtitled video")
    t.add_argument("--name", help="Base name for output files (default: timestamp)")
    t.set_defaults(func=_translate)

    args = parser.parse_args(argv)
    return args.func(args)
