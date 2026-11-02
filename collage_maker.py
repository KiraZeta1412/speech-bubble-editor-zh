"""Clean, reusable photo-collage page布局s."""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QRectF


COLLAGE_COUNTS = tuple(range(2, 10))
ASPECT_RATIOS = {
    "方形 · 1:1": 1.0,
    "竖版 · 4:5": 4 / 5,
    "故事 · 9:16": 9 / 16,
    "横版 · 16:9": 16 / 9,
    "照片 · 3:2": 3 / 2,
}
LAYOUT_TYPES = ("自动", "网格", "马赛克", "主图", "胶片条")
PAGE_BASE = 1600.0


def page_size(aspect_name: str) -> tuple[float, float]:
    ratio = ASPECT_RATIOS.get(aspect_name, 1.0)
    if ratio >= 1.0:
        return PAGE_BASE, PAGE_BASE / ratio
    return PAGE_BASE, PAGE_BASE / ratio


def _grid_layout(count: int, bounds: QRectF, gap: float) -> list[QRectF]:
    page_ratio = bounds.width() / max(1.0, bounds.height())
    columns = max(1, min(count, round(math.sqrt(count * page_ratio))))
    rows = math.ceil(count / columns)
    rects: list[QRectF] = []
    remaining = count
    y = bounds.top()
    row_h = (bounds.height() - gap * (rows - 1)) / rows
    for row in range(rows):
        row_count = min(columns, remaining)
        # Spread incomplete final rows across the full width; no dead corner.
        cell_w = (bounds.width() - gap * (row_count - 1)) / row_count
        x = bounds.left()
        for _ in range(row_count):
            rects.append(QRectF(x, y, cell_w, row_h))
            x += cell_w + gap
        y += row_h + gap
        remaining -= row_count
    return rects


def _mosaic_layout(count: int, bounds: QRectF, gap: float,
                   rng: random.Random) -> list[QRectF]:
    rects = [QRectF(bounds)]
    while len(rects) < count:
        index = max(range(len(rects)),
                    key=lambda i: rects[i].width() * rects[i].height())
        rect = rects.pop(index)
        split_vertical = rect.width() / max(1.0, rect.height()) > rng.uniform(0.82, 1.18)
        ratio = rng.uniform(0.42, 0.62)
        if split_vertical:
            available = rect.width() - gap
            first = available * ratio
            rects.extend((
                QRectF(rect.left(), rect.top(), first, rect.height()),
                QRectF(rect.left() + first + gap, rect.top(),
                       available - first, rect.height()),
            ))
        else:
            available = rect.height() - gap
            first = available * ratio
            rects.extend((
                QRectF(rect.left(), rect.top(), rect.width(), first),
                QRectF(rect.left(), rect.top() + first + gap,
                       rect.width(), available - first),
            ))
    return sorted(rects, key=lambda rect: (rect.top(), rect.left()))


def _hero_layout(count: int, bounds: QRectF, gap: float) -> list[QRectF]:
    if count <= 2:
        return _grid_layout(count, bounds, gap)
    portrait = bounds.height() >= bounds.width()
    if portrait:
        hero_h = (bounds.height() - gap) * 0.52
        hero = QRectF(bounds.left(), bounds.top(), bounds.width(), hero_h)
        rest = QRectF(bounds.left(), hero.bottom() + gap, bounds.width(),
                      bounds.bottom() - hero.bottom() - gap)
    else:
        hero_w = (bounds.width() - gap) * 0.56
        hero = QRectF(bounds.left(), bounds.top(), hero_w, bounds.height())
        rest = QRectF(hero.right() + gap, bounds.top(),
                      bounds.right() - hero.right() - gap, bounds.height())
    return [hero, *_grid_layout(count - 1, rest, gap)]


def _filmstrip_layout(count: int, bounds: QRectF, gap: float) -> list[QRectF]:
    portrait = bounds.height() >= bounds.width()
    rects: list[QRectF] = []
    if portrait:
        cell_h = (bounds.height() - gap * (count - 1)) / count
        for index in range(count):
            rects.append(QRectF(bounds.left(), bounds.top() + index * (cell_h + gap),
                                bounds.width(), cell_h))
    else:
        cell_w = (bounds.width() - gap * (count - 1)) / count
        for index in range(count):
            rects.append(QRectF(bounds.left() + index * (cell_w + gap), bounds.top(),
                                cell_w, bounds.height()))
    return rects


def generate_collage_layout(count: int, layout_type: str = "自动",
                            options: dict | None = None,
                            rng: random.Random | None = None):
    options = options or {}
    rng = rng or random.SystemRandom()
    count = max(min(int(count), max(COLLAGE_COUNTS)), min(COLLAGE_COUNTS))
    aspect_name = str(options.get("aspect_ratio", "方形 · 1:1"))
    width, height = page_size(aspect_name)
    margin = max(0.0, float(options.get("margin", 28)))
    gap = max(0.0, float(options.get("gap", 18)))
    bounds = QRectF(margin, margin, max(80.0, width - 2 * margin),
                    max(80.0, height - 2 * margin))

    chosen = layout_type if layout_type in LAYOUT_TYPES else "自动"
    if chosen == "自动":
        chosen = rng.choice(("网格", "马赛克", "主图", "胶片条"))
    if chosen == "马赛克":
        rects = _mosaic_layout(count, bounds, gap, rng)
    elif chosen == "主图":
        rects = _hero_layout(count, bounds, gap)
    elif chosen == "胶片条":
        rects = _filmstrip_layout(count, bounds, gap)
    else:
        rects = _grid_layout(count, bounds, gap)
    return rects, f"{count} 张照片  ·  {chosen.lower()}  ·  {aspect_name}", (width, height)
