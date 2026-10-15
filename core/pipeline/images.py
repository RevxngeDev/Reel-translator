"""Image-post path: OCR every image, translate all text blocks in one batch (D-025)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.errors import NoTextError
from core.ocr.base import ImageTextReader
from core.pipeline.common import TextPair, check_languages, main_language, translate_texts
from core.translate.base import Translator


@dataclass
class ImagePostReport:
    images: list[Path]
    slides: list[list[TextPair]]  # one list of bilingual blocks per image, same order
    source_lang: str
    target_lang: str
    llm_tokens: int = 0
    result_path: Path | None = field(default=None)


def process_images(
    images: list[Path],
    target_lang: str,
    *,
    name: str,
    out_dir: Path,
    ocr: ImageTextReader,
    translator: Translator,
) -> ImagePostReport:
    texts = ocr.read(images)
    blocks = [(i, block) for i, text in enumerate(texts) for block in text.blocks]
    if not blocks:
        raise NoTextError("No readable text in the post's images")
    source_lang = main_language([t.language for t in texts])
    check_languages(source_lang, target_lang)

    pairs, tokens = translate_texts([b for _, b in blocks], source_lang, target_lang, translator)
    slides: list[list[TextPair]] = [[] for _ in images]
    for (i, _), pair in zip(blocks, pairs):
        slides[i].append(pair)

    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"{name}.images.json"
    result_path.write_text(json.dumps(
        {"source_lang": source_lang, "target_lang": target_lang,
         "slides": [[asdict(p) for p in slide] for slide in slides]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return ImagePostReport(images=images, slides=slides, source_lang=source_lang,
                           target_lang=target_lang, llm_tokens=tokens, result_path=result_path)
