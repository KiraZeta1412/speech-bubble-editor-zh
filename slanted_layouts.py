"""slanted_layouts.py —— 斜切拼贴预设。

和 collage_maker 的区别只有一个：分格不再是矩形，而是**多边形**
（梯形 / 平行四边形 / 三角形），所以能做斜向分割。

坐标一律是**归一化页面坐标**（0..1，y 向下），与实际页面尺寸无关 ——
同一套预设在任何比例（竖向 4:5 / 横向 16:9 / 方形 1:1）下都能用。

每个预设的块数是**固定的**（不像规整布局那样自适应照片数），
因为斜切形状一旦自适应很容易算错、出现空隙或重叠。
所以这里的做法是：预设决定块数，用户挑预设。
"""

from __future__ import annotations

# 斜切布局在 layout_type 里用这个前缀标记，例如 "斜切:diag2"
SLANT_PREFIX = "斜切:"

# 每个预设: id, 名称, 块数, cells（每块是一串 (x, y)，按顺序围成多边形）
PRESETS: tuple[dict, ...] = ()


def _add(pid: str, label: str, cells: list[list[tuple[float, float]]]):
    PRESETS_LIST.append({
        "id": pid,
        "label": label,
        "cells": [[[round(x, 6), round(y, 6)] for x, y in cell] for cell in cells],
    })


PRESETS_LIST: list[dict] = []


# ---------------------------------------------------------------------------
# 构造工具：斜向分割线
# ---------------------------------------------------------------------------

def _slant_seams(count: int, slant: float) -> list[tuple[float, float, float, float]]:
    """把页面竖着切成 count 条斜带，返回每条分割线 (x_top, x_bottom)。

    slant 是上下端点的水平偏移量：正值向右倾，负值向左倾。
    """
    seams = []
    for i in range(1, count):
        base = i / count
        seams.append((base - slant / 2, base + slant / 2))
    return seams


def _vertical_bands(count: int, slant: float) -> list[list[tuple[float, float]]]:
    """竖条斜切：每条是一个平行四边形（首尾两条被页面边界裁成直角梯形）。"""
    seams = _slant_seams(count, slant)
    cells = []
    top_prev, bottom_prev = 0.0, 0.0
    for x_top, x_bottom in seams:
        cells.append([(top_prev, 0.0), (x_top, 0.0),
                      (x_bottom, 1.0), (bottom_prev, 1.0)])
        top_prev, bottom_prev = x_top, x_bottom
    cells.append([(top_prev, 0.0), (1.0, 0.0), (1.0, 1.0), (bottom_prev, 1.0)])
    return cells


def _horizontal_bands(count: int, slant: float) -> list[list[tuple[float, float]]]:
    """横带斜切：每条是一个梯形。

    关键：一条分割线是**一根斜线**，从上边左侧 (left_y) 连到上边右侧 (right_y)。
    相邻两块必须共用同一根线 —— 上边用前一刀的线、下边用后一刀的线，
    否则两条线不重合，会出现重叠和多余面积。
    """
    def seam(k: int) -> tuple[float, float]:
        base = k / count
        return (base - slant / 2, base + slant / 2)

    cells = []
    prev_left, prev_right = 0.0, 0.0          # 页面顶边是水平的
    for k in range(1, count):
        next_left, next_right = seam(k)
        cells.append([
            (0.0, prev_left), (1.0, prev_right),
            (1.0, next_right), (0.0, next_left),
        ])
        prev_left, prev_right = next_left, next_right
    cells.append([
        (0.0, prev_left), (1.0, prev_right), (1.0, 1.0), (0.0, 1.0),
    ])
    return cells


# ---------------------------------------------------------------------------
# 预设清单
# ---------------------------------------------------------------------------

# 1) 对角二分：两个三角形
_add("diag2", "对角 2", [
    [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
    [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
])

# 2) 反斜对角二分
_add("diag2b", "反斜 2", [
    [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
    [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
])

# 3) 斜条三分：三条平行斜带
_add("bands3", "斜条 3", _vertical_bands(3, 0.18))

# 4) 斜条四分
_add("bands4", "斜条 4", _vertical_bands(4, 0.16))

# 5) 斜梯形二分：一条斜横线把页面切成两个梯形
_add("trap2", "斜梯形 2", _horizontal_bands(2, 0.16))

# 6) 斜梯形三分
_add("trap3", "斜梯形 3", _horizontal_bands(3, 0.14))

# 7) 斜梯形四分
_add("trap4", "斜梯形 4", _horizontal_bands(4, 0.12))

# 8) 放射四分：从中心点发散成四个三角形
_add("radial4", "放射 4", [
    [(0.0, 0.0), (1.0, 0.0), (0.52, 0.46)],
    [(1.0, 0.0), (1.0, 1.0), (0.52, 0.46)],
    [(1.0, 1.0), (0.0, 1.0), (0.52, 0.46)],
    [(0.0, 1.0), (0.0, 0.0), (0.52, 0.46)],
])

# 9) 斜格四分：中间一个斜十字，四块都是四边形
_add("cross4", "斜格 4", [
    [(0.0, 0.0), (0.55, 0.0), (0.45, 0.5), (0.0, 0.45)],
    [(0.55, 0.0), (1.0, 0.0), (1.0, 0.55), (0.45, 0.5)],
    [(0.45, 0.5), (1.0, 0.55), (1.0, 1.0), (0.5, 1.0)],
    [(0.0, 0.45), (0.45, 0.5), (0.5, 1.0), (0.0, 1.0)],
])

# 10) 斜格六分：三竖两横，竖缝是斜的
def _grid6() -> list[list[tuple[float, float]]]:
    slant = 0.10
    rows = [(0.0, 0.5), (0.5, 1.0)]
    seams = _slant_seams(3, slant)   # 两条竖缝
    cells: list[list[tuple[float, float]]] = []
    for top, bottom in rows:
        mid_top = (top + bottom) / 2
        top_prev, bottom_prev = 0.0, 0.0
        for x_top, x_bottom in seams:
            cells.append([
                (top_prev, top), (x_top, top),
                (x_bottom, bottom), (bottom_prev, bottom),
            ])
            top_prev, bottom_prev = x_top, x_bottom
        cells.append([
            (top_prev, top), (1.0, top), (1.0, bottom), (bottom_prev, bottom),
        ])
    return cells


_add("grid6", "斜格 6", _grid6())

# 11) 风车四分：中心一个菱形，外面四块梯形
_add("pinwheel4", "风车 4", [
    [(0.0, 0.0), (0.62, 0.0), (0.5, 0.5), (0.0, 0.38)],
    [(0.62, 0.0), (1.0, 0.0), (1.0, 0.62), (0.5, 0.5)],
    [(1.0, 0.62), (1.0, 1.0), (0.38, 1.0), (0.5, 0.5)],
    [(0.38, 1.0), (0.0, 1.0), (0.0, 0.38), (0.5, 0.5)],
])

# 12) 斜三分：上下各一条斜线，中间一块大平行四边形
_add("slant3", "斜三层", [
    [(0.0, 0.0), (1.0, 0.0), (1.0, 0.22), (0.0, 0.30)],
    [(0.0, 0.30), (1.0, 0.22), (1.0, 0.74), (0.0, 0.82)],
    [(0.0, 0.82), (1.0, 0.74), (1.0, 1.0), (0.0, 1.0)],
])

# ---------------------------------------------------------------------------
# 三块预设（补）
# ---------------------------------------------------------------------------

# 斜角三分：一个大三角 + 右下角切成两半
_add("corner3", "斜角 3", [
    [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
    [(1.0, 0.0), (1.0, 1.0), (0.5, 1.0)],
    [(1.0, 0.0), (0.5, 1.0), (0.0, 1.0)],
])

# 错层三分：两条斜线方向相反，形成 Z 字形错层
_add("zigzag3", "错层 3", [
    [(0.0, 0.0), (1.0, 0.0), (1.0, 0.24), (0.0, 0.30)],
    [(0.0, 0.30), (1.0, 0.24), (1.0, 0.76), (0.0, 0.70)],
    [(0.0, 0.70), (1.0, 0.76), (1.0, 1.0), (0.0, 1.0)],
])

# 斜一二：左边一大块 + 右边上下两块（两条缝都是斜的）
# 注意：分割点必须**落在竖缝上**，否则会留细缝 —— 竖缝是斜的，
# 在 y 处的 x 不等于顶端 x，必须按线性插值算。
def _vseam_x(y: float, top_x: float, bottom_x: float) -> float:
    return top_x + (bottom_x - top_x) * y


_add("slant1plus2", "斜一二", [
    [(0.0, 0.0), (0.42, 0.0), (0.38, 1.0), (0.0, 1.0)],
    [(0.42, 0.0), (1.0, 0.0), (1.0, 0.54),
     (_vseam_x(0.46, 0.42, 0.38), 0.46)],
    [(_vseam_x(0.46, 0.42, 0.38), 0.46), (1.0, 0.54), (1.0, 1.0), (0.38, 1.0)],
])

# 斜带三分：中间一条斜向大带 + 左上、右下两个三角
_add("paraband3", "斜带 3", [
    [(0.0, 0.0), (0.6, 0.0), (0.0, 0.6)],
    [(0.0, 0.6), (0.6, 0.0), (1.0, 0.0), (0.0, 1.0)],
    [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
])

# ---------------------------------------------------------------------------
# 四块预设（补）
# ---------------------------------------------------------------------------

# 斜一三：左边一大块 + 右边竖着三块
_add("slant1plus3", "斜一三", [
    [(0.0, 0.0), (0.46, 0.0), (0.42, 1.0), (0.0, 1.0)],
    [(0.46, 0.0), (1.0, 0.0), (1.0, 0.34),
     (_vseam_x(0.28, 0.46, 0.42), 0.28)],
    [(_vseam_x(0.28, 0.46, 0.42), 0.28), (1.0, 0.34), (1.0, 0.68),
     (_vseam_x(0.62, 0.46, 0.42), 0.62)],
    [(_vseam_x(0.62, 0.46, 0.42), 0.62), (1.0, 0.68), (1.0, 1.0), (0.42, 1.0)],
])

# 斜三一：上面横着三块（缝是斜的）+ 下面一大块
# 竖缝必须正好落在横缝上：横缝 y(x) = 0.58 + 0.08x
_H1 = (0.58, 0.66)


def _hseam_y(x: float) -> float:
    return _H1[0] + (_H1[1] - _H1[0]) * x


_add("slant3plus1", "斜三一", [
    [(0.0, 0.0), (0.30, 0.0), (0.30, _hseam_y(0.30)), (0.0, _H1[0])],
    [(0.30, 0.0), (0.66, 0.0), (0.66, _hseam_y(0.66)), (0.30, _hseam_y(0.30))],
    [(0.66, 0.0), (1.0, 0.0), (1.0, _H1[1]), (0.66, _hseam_y(0.66))],
    [(0.0, _H1[0]), (1.0, _H1[1]), (1.0, 1.0), (0.0, 1.0)],
])

# 斜角四分：一个大三角 + 右下角再切成三份
_add("corner4", "斜角 4", [
    [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
    [(1.0, 0.0), (1.0, 1.0), (0.667, 1.0)],
    [(1.0, 0.0), (0.667, 1.0), (0.333, 1.0)],
    [(1.0, 0.0), (0.333, 1.0), (0.0, 1.0)],
])

# 斜对角四分：两条对角把页面切成四个块，上下两半各再斜切一刀
_add("diag4split", "斜对角 4", [
    [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5)],
    [(0.5, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.5)],
    [(1.0, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 1.0)],
    [(1.0, 0.5), (1.0, 1.0), (0.5, 1.0)],
])

# 按块数排序，让 2 块 / 3 块 / 4 块 / 6 块各自聚在一起，方便挑
PRESETS = tuple(sorted(PRESETS_LIST, key=lambda p: (len(p["cells"]), p["id"])))


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------

def preset_ids() -> list[str]:
    return [p["id"] for p in PRESETS]


def get(preset_id: str) -> dict | None:
    for preset in PRESETS:
        if preset["id"] == preset_id:
            return preset
    return None


def label(preset_id: str) -> str:
    preset = get(preset_id)
    return preset["label"] if preset else preset_id


def cell_count(preset_id: str) -> int:
    preset = get(preset_id)
    return len(preset["cells"]) if preset else 0


def default_id() -> str:
    return PRESETS[0]["id"] if PRESETS else ""


def polygon_rects(preset_id: str, width: float, height: float):
    """把预设换算成页面像素坐标，返回 [(QRectF 包围盒, [QPointF...]), ...]。

    分格 item 需要一个包围盒来定位，多边形点则用于裁剪路径。
    """
    from PyQt6.QtCore import QPointF, QRectF

    preset = get(preset_id)
    if preset is None:
        return []
    out = []
    for cell in preset["cells"]:
        points = [QPointF(x * width, y * height) for x, y in cell]
        if not points:
            continue
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        box = QRectF(min(xs), min(ys),
                     max(1.0, max(xs) - min(xs)), max(1.0, max(ys) - min(ys)))
        out.append((box, points))
    return out
