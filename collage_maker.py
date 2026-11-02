"""Clean, reusable photo-collage page layouts.

布局引擎的两种玩法：

1. **分段引擎**（``_sections_layout``）—— 给一串「每段放几张」和段厚权重，
   就能生成几十种排布：``[1, n-1]`` 是「一上多下」，``[n-1, 1]`` 是「多上一小」，
   ``[1, n-2, 1]`` 是「上中下三段」。段内沿另一轴均分。
2. **主图引擎**（``_hero_layout``）—— 一块大图 + 剩余区域走网格，
   大图可以在上/下/左/右任一边。

所有布局都**随照片数量自适应**：用户先选几张，再选布局，
所以同一个布局在 2 张和 9 张时都能给出合理的排布。
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QRectF

import custom_layouts


COLLAGE_COUNTS = tuple(range(2, 10))
ASPECT_RATIOS = {
    "方形 · 1:1": 1.0,
    "竖版 · 4:5": 4 / 5,
    "故事 · 9:16": 9 / 16,
    "横版 · 16:9": 16 / 9,
    "照片 · 3:2": 3 / 2,
}

# 布局清单（顺序即界面上的排列顺序）
LAYOUT_TYPES = (
    "自动",
    "网格",
    "马赛克",
    "主图",
    "胶片条",
    "一上多下",
    "一左多右",
    "多上一小",
    "上中下",
    "左中右",
    "大图左",
    "大图右",
    "黄金比",
)

# 按钮上的短标签（比布局全名更适合小方块）
LAYOUT_LABELS = {
    "网格": "网格",
    "马赛克": "马赛克",
    "主图": "主图",
    "胶片条": "条带",
    "一上多下": "上大",
    "一左多右": "左大",
    "多上一小": "下大",
    "上中下": "三段",
    "左中右": "三竖",
    "大图左": "左图",
    "大图右": "右图",
    "黄金比": "黄金",
}

PAGE_BASE = 1600.0


def page_size(aspect_name: str) -> tuple[float, float]:
    ratio = ASPECT_RATIOS.get(aspect_name, 1.0)
    return PAGE_BASE, PAGE_BASE / ratio


# ---------------------------------------------------------------------------
# 基础排布
# ---------------------------------------------------------------------------

def _grid_layout(count: int, bounds: QRectF, gap: float) -> list[QRectF]:
    """按页面比例估算列数，逐行填满；末行不满也铺满整行，不留死角和空洞。"""
    page_ratio = bounds.width() / max(1.0, bounds.height())
    columns = max(1, min(count, round(math.sqrt(count * page_ratio))))
    rows = math.ceil(count / columns)
    rects: list[QRectF] = []
    remaining = count
    y = bounds.top()
    row_h = (bounds.height() - gap * (rows - 1)) / rows
    for _row in range(rows):
        row_count = min(columns, remaining)
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
    """递归劈开面积最大的一块，得到大小不一的马赛克感。"""
    rects = [QRectF(bounds)]
    while len(rects) < count:
        index = max(range(len(rects)),
                    key=lambda i: rects[i].width() * rects[i].height())
        rect = rects.pop(index)
        split_vertical = (rect.width() / max(1.0, rect.height())
                          > rng.uniform(0.82, 1.18))
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
    return sorted(rects, key=lambda r: (r.top(), r.left()))


def _filmstrip_layout(count: int, bounds: QRectF, gap: float) -> list[QRectF]:
    """等分条带：竖版页面上下切，横版左右切。"""
    rects: list[QRectF] = []
    if bounds.height() >= bounds.width():
        cell_h = (bounds.height() - gap * (count - 1)) / count
        for index in range(count):
            rects.append(QRectF(bounds.left(),
                                bounds.top() + index * (cell_h + gap),
                                bounds.width(), cell_h))
    else:
        cell_w = (bounds.width() - gap * (count - 1)) / count
        for index in range(count):
            rects.append(QRectF(bounds.left() + index * (cell_w + gap),
                                bounds.top(), cell_w, bounds.height()))
    return rects


# ---------------------------------------------------------------------------
# 分段引擎
# ---------------------------------------------------------------------------

def _sections_layout(sections: list[int], bounds: QRectF, gap: float,
                     weights: list[float] | None = None,
                     outer: str = "rows") -> list[QRectF]:
    """把页面切成若干「段」，每段内再沿另一轴均分。

    sections  每段放几张，例如 [1, 3] 表示一段 1 张、一段 3 张
    weights   各段厚度权重，None 或长度不符时等分
    outer     "rows" 段上下堆叠（段内左右分）；"cols" 段左右排列（段内上下分）
    """
    bands = len(sections)
    if bands == 0:
        return [QRectF(bounds)]
    if weights is None or len(weights) != bands:
        weights = [1.0] * bands
    total_weight = sum(weights) or 1.0

    rects: list[QRectF] = []
    if outer == "cols":
        available = bounds.width() - gap * (bands - 1)
        x = bounds.left()
        for cell_count, weight in zip(sections, weights):
            size = available * weight / total_weight
            cell_h = (bounds.height() - gap * (cell_count - 1)) / cell_count
            y = bounds.top()
            for _ in range(cell_count):
                rects.append(QRectF(x, y, size, cell_h))
                y += cell_h + gap
            x += size + gap
    else:
        available = bounds.height() - gap * (bands - 1)
        y = bounds.top()
        for cell_count, weight in zip(sections, weights):
            size = available * weight / total_weight
            cell_w = (bounds.width() - gap * (cell_count - 1)) / cell_count
            x = bounds.left()
            for _ in range(cell_count):
                rects.append(QRectF(x, y, cell_w, size))
                x += cell_w + gap
            y += size + gap
    return rects


# ---------------------------------------------------------------------------
# 主图引擎
# ---------------------------------------------------------------------------

HERO_SIDES = ("top", "bottom", "left", "right")


def _hero_layout(count: int, bounds: QRectF, gap: float,
                 side: str = "top", ratio: float = 0.58) -> list[QRectF]:
    """一块大图 + 剩余区域用网格填满。side 决定大图贴哪一边。"""
    if count <= 0:
        return []
    if count == 1:
        return [QRectF(bounds)]

    # 两格时退化成一次切分，按 side 决定切的方向
    if count == 2:
        vertical = side in ("top", "bottom")
        if side in ("bottom", "right"):
            ratio = 1.0 - ratio
        if vertical:
            available = bounds.height() - gap
            first_h = available * ratio
            return [
                QRectF(bounds.left(), bounds.top(), bounds.width(), first_h),
                QRectF(bounds.left(), bounds.top() + first_h + gap,
                       bounds.width(), available - first_h),
            ]
        available = bounds.width() - gap
        first_w = available * ratio
        return [
            QRectF(bounds.left(), bounds.top(), first_w, bounds.height()),
            QRectF(bounds.left() + first_w + gap, bounds.top(),
                   available - first_w, bounds.height()),
        ]

    if side in ("top", "bottom"):
        hero_h = (bounds.height() - gap) * ratio
        if side == "top":
            hero = QRectF(bounds.left(), bounds.top(), bounds.width(), hero_h)
            rest = QRectF(bounds.left(), hero.bottom() + gap, bounds.width(),
                          bounds.bottom() - hero.bottom() - gap)
        else:
            hero = QRectF(bounds.left(), bounds.bottom() - hero_h,
                          bounds.width(), hero_h)
            rest = QRectF(bounds.left(), bounds.top(), bounds.width(),
                          hero.top() - bounds.top() - gap)
    else:
        hero_w = (bounds.width() - gap) * ratio
        if side == "left":
            hero = QRectF(bounds.left(), bounds.top(), hero_w, bounds.height())
            rest = QRectF(hero.right() + gap, bounds.top(),
                          bounds.right() - hero.right() - gap, bounds.height())
        else:
            hero = QRectF(bounds.right() - hero_w, bounds.top(),
                          hero_w, bounds.height())
            rest = QRectF(bounds.left(), bounds.top(),
                          hero.left() - bounds.left() - gap, bounds.height())
    return [hero, *_grid_layout(count - 1, rest, gap)]


# ---------------------------------------------------------------------------
# 各布局的具体实现
# ---------------------------------------------------------------------------

def _layout_auto(count, bounds, gap, rng):
    picks = ("网格", "马赛克", "主图", "胶片条", "一上多下",
             "大图左", "上中下", "黄金比")
    return _build(rng.choice(picks), count, bounds, gap, rng)


def _layout_grid(count, bounds, gap, rng):
    return _grid_layout(count, bounds, gap)


def _layout_mosaic(count, bounds, gap, rng):
    return _mosaic_layout(count, bounds, gap, rng)


def _layout_hero(count, bounds, gap, rng):
    # 竖版页面大图放上，横版放左 —— 顺着页面比例来最顺眼
    side = "top" if bounds.height() >= bounds.width() else "left"
    return _hero_layout(count, bounds, gap, side=side)


def _layout_filmstrip(count, bounds, gap, rng):
    return _filmstrip_layout(count, bounds, gap)


def _layout_hero_top(count, bounds, gap, rng):
    return _hero_layout(count, bounds, gap, side="top", ratio=0.58)


def _layout_hero_left(count, bounds, gap, rng):
    return _hero_layout(count, bounds, gap, side="left", ratio=0.58)


def _layout_hero_bottom(count, bounds, gap, rng):
    """多上一小：上面一排小图，下面一张大图。"""
    return _hero_layout(count, bounds, gap, side="bottom", ratio=0.58)


def _layout_three_rows(count, bounds, gap, rng):
    """上中下三段：1 / 中间若干 / 1。"""
    if count < 3:
        return _hero_layout(count, bounds, gap, side="top")
    middle = count - 2
    return _sections_layout([1, middle, 1], bounds, gap,
                            weights=[0.26, 0.48, 0.26], outer="rows")


def _layout_three_cols(count, bounds, gap, rng):
    """左中右三竖：1 / 中间若干 / 1。"""
    if count < 3:
        return _hero_layout(count, bounds, gap, side="left")
    middle = count - 2
    return _sections_layout([1, middle, 1], bounds, gap,
                            weights=[0.27, 0.46, 0.27], outer="cols")


def _layout_hero_left_panel(count, bounds, gap, rng):
    """大图左：左侧一整条 + 右侧走网格。"""
    return _hero_layout(count, bounds, gap, side="left", ratio=0.56)


def _layout_hero_right_panel(count, bounds, gap, rng):
    """大图右：左侧走网格 + 右侧一整条。"""
    return _hero_layout(count, bounds, gap, side="right", ratio=0.56)


def _layout_golden(count, bounds, gap, rng):
    """黄金分割：大图按 0.618 切，看着比 0.58 更「不高不低」。"""
    side = "top" if bounds.height() >= bounds.width() else "left"
    return _hero_layout(count, bounds, gap, side=side, ratio=0.618)


_LAYOUT_BUILDERS = {
    "网格": _layout_grid,
    "马赛克": _layout_mosaic,
    "主图": _layout_hero,
    "胶片条": _layout_filmstrip,
    "一上多下": _layout_hero_top,
    "一左多右": _layout_hero_left,
    "多上一小": _layout_hero_bottom,
    "上中下": _layout_three_rows,
    "左中右": _layout_three_cols,
    "大图左": _layout_hero_left_panel,
    "大图右": _layout_hero_right_panel,
    "黄金比": _layout_golden,
}


def _build(name: str, count: int, bounds: QRectF, gap: float,
           rng: random.Random) -> list[QRectF]:
    builder = _LAYOUT_BUILDERS.get(name)
    if builder is None:
        if custom_layouts.is_custom(name):
            return _custom_layout_rects(name, bounds)
        return _grid_layout(count, bounds, gap)
    return builder(count, bounds, gap, rng)


def _custom_layout_rects(layout_type: str, bounds: QRectF) -> list[QRectF]:
    """把用户自定义布局的归一化矩形缩放进页面。

    矩形存的是 0..1 的页面相对坐标，所以同一套布局在任何页面比例下都能用。
    """
    stored = custom_layouts.get(custom_layouts.custom_name(layout_type))
    if not stored:
        return [QRectF(bounds)]
    rects: list[QRectF] = []
    for x, y, w, h in stored:
        rects.append(QRectF(bounds.left() + x * bounds.width(),
                            bounds.top() + y * bounds.height(),
                            w * bounds.width(),
                            h * bounds.height()))
    return rects


def is_known_layout(layout_type: str) -> bool:
    return (layout_type in LAYOUT_TYPES
            or custom_layouts.is_custom(layout_type))


def layout_rects(count: int, layout_type: str, aspect_name: str = "方形 · 1:1",
                 margin: float = 28, gap: float = 18,
                 rng: random.Random | None = None) -> list[QRectF]:
    """只要矩形、不要描述串时用这个（界面缩略图就走这条路）。"""
    rng = rng or random.Random(1234)
    count = max(min(int(count), max(COLLAGE_COUNTS)), min(COLLAGE_COUNTS))
    width, height = page_size(aspect_name)
    bounds = QRectF(margin, margin, max(80.0, width - 2 * margin),
                    max(80.0, height - 2 * margin))
    chosen = layout_type if is_known_layout(layout_type) else "自动"
    if chosen == "自动":
        chosen = rng.choice(tuple(n for n in LAYOUT_TYPES if n != "自动"))
    return _build(chosen, count, bounds, max(0.0, float(gap)), rng)


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

    chosen = layout_type if is_known_layout(layout_type) else "自动"
    if chosen == "自动":
        chosen = rng.choice(tuple(n for n in LAYOUT_TYPES if n != "自动"))
    rects = _build(chosen, count, bounds, gap, rng)
    if custom_layouts.is_custom(chosen):
        label = custom_layouts.custom_name(chosen)
        count_text = f"{len(rects)} 张照片  ·  {label}  ·  {aspect_name}"
    else:
        count_text = f"{count} 张照片  ·  {chosen.lower()}  ·  {aspect_name}"
    return rects, count_text, (width, height)
