"""Packs up to 4 images into one grid image. Groq bills vision input per image, so
one 2x2 grid costs about the same as one slide and read better in our test (D-024).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_PER_GRID = 4
CELL_MAX_WIDTH = 1080
GUTTER = 24  # white gap that keeps slides visually separate


def layout(n: int) -> tuple[int, int]:
    """(columns, rows) for n images: 1 -> 1x1, 2 -> 2x1, 3-4 -> 2x2."""
    if not 1 <= n <= MAX_PER_GRID:
        raise ValueError(f"grid holds 1..{MAX_PER_GRID} images, got {n}")
    return (1, 1) if n == 1 else (2, 1) if n == 2 else (2, 2)


def describe(n: int) -> str:
    cols, rows = layout(n)
    if n == 1:
        return ""
    order = "left to right" if rows == 1 else "left to right, then top to bottom"
    return (f" The image is a grid of {n} separate slides ({cols} columns x {rows} rows), "
            f"numbered 1 to {n} {order}. Prefix every block with its slide number, like \"[2] \".")


def pack(paths: list[Path]) -> Image.Image:
    images = [Image.open(p).convert("RGB") for p in paths]
    try:
        if len(images) == 1:
            img = images[0]
            if img.width > CELL_MAX_WIDTH * 2:
                img = img.resize((CELL_MAX_WIDTH * 2, round(img.height * CELL_MAX_WIDTH * 2 / img.width)))
            return img.copy()
        cols, rows = layout(len(images))
        cell_w = min(CELL_MAX_WIDTH, max(i.width for i in images))
        cell_h = max(round(i.height * cell_w / i.width) for i in images)
        grid = Image.new("RGB", (cols * cell_w + (cols - 1) * GUTTER, rows * cell_h + (rows - 1) * GUTTER), "white")
        for n, img in enumerate(images):
            scale = min(cell_w / img.width, cell_h / img.height)
            fitted = img.resize((round(img.width * scale), round(img.height * scale)))
            col, row = n % cols, n // cols
            x = col * (cell_w + GUTTER) + (cell_w - fitted.width) // 2
            y = row * (cell_h + GUTTER) + (cell_h - fitted.height) // 2
            grid.paste(fitted, (x, y))
        return grid
    finally:
        for img in images:
            img.close()
