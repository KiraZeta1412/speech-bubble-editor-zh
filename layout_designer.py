"""layout_designer.py —— 让用户自己画拼贴布局。

用法：在页面上拖动画出矩形，每个矩形就是一个照片框。
可以移动、缩放、删除，不允许重叠或超出页面。

保存后布局以「自定义 · 名字」的形式存进 QSettings，
画廊里会多出一个带正确预览图的按钮。
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

import i18n

MIN_SIZE = 0.02        # 最小边长（占页面比例）
SNAP_TOLERANCE = 0.022  # 吸附容差（占页面比例）；给宽一点，靠近边缘就能吸上
HANDLE_SIZE = 10        # 缩放手柄的命中半径 / 显示尺寸


class LayoutDesignCanvas(QWidget):
    """画布：页面按当前比例显示，矩形用 0..1 归一化坐标存。"""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list[QRectF] = []      # 归一化 0..1
        self._selected = -1
        self._mode = None                   # "new" / "move" / "resize"
        self._anchor = QPointF()
        self._origin = QRectF()
        self._aspect = 1.0
        self._grab_corner = ""
        self._snap_x: list[float] = [0.0, 1.0]   # 按下时缓存的吸附候选
        self._snap_y: list[float] = [0.0, 1.0]
        self._grid_size = 0                 # 底纹参考线数量
        self.setMinimumSize(320, 320)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ---- 数据 ----------------------------------------------------------

    def set_aspect(self, ratio: float):
        """页面宽高比（w/h），只影响显示，不影响存的值。"""
        self._aspect = max(0.1, float(ratio))
        self.update()

    def rects(self) -> list[list[float]]:
        return [[round(r.x(), 5), round(r.y(), 5),
                 round(r.width(), 5), round(r.height(), 5)] for r in self._rects]

    def set_rects(self, values):
        self._rects = []
        for item in values or []:
            if len(item) != 4:
                continue
            x, y, w, h = (float(v) for v in item)
            rect = QRectF(x, y, w, h).intersected(QRectF(0, 0, 1, 1))
            if rect.width() > 0 and rect.height() > 0:
                self._rects.append(rect)
        self._selected = -1
        self.update()
        self.changed.emit()

    def clear_all(self):
        self._rects.clear()
        self._selected = -1
        self.update()
        self.changed.emit()

    def delete_selected(self):
        if 0 <= self._selected < len(self._rects):
            self._rects.pop(self._selected)
            self._selected = -1
            self.update()
            self.changed.emit()

    def start_with_grid(self, rows: int, cols: int):
        """给一个等分网格当起点，用户再改。"""
        self._rects = []
        for r in range(rows):
            for c in range(cols):
                self._rects.append(QRectF(c / cols, r / rows, 1 / cols, 1 / rows))
        self._selected = -1
        self.update()
        self.changed.emit()

    # ---- 坐标换算 ------------------------------------------------------

    def _page_rect(self) -> QRectF:
        """页面在控件里的显示矩形（留边距给句柄用）。"""
        pad = HANDLE_SIZE + 4
        avail_w = max(20.0, self.width() - pad * 2)
        avail_h = max(20.0, self.height() - pad * 2)
        if avail_w / avail_h >= self._aspect:
            h = avail_h
            w = h * self._aspect
        else:
            w = avail_w
            h = w / self._aspect
        return QRectF(pad + (avail_w - w) / 2, pad + (avail_h - h) / 2, w, h)

    def _to_norm(self, pos: QPointF) -> QPointF:
        page = self._page_rect()
        if page.width() <= 0 or page.height() <= 0:
            return QPointF(0, 0)
        return QPointF((pos.x() - page.x()) / page.width(),
                       (pos.y() - page.y()) / page.height())

    def _to_widget(self, rect: QRectF) -> QRectF:
        page = self._page_rect()
        return QRectF(page.x() + rect.x() * page.width(),
                      page.y() + rect.y() * page.height(),
                      rect.width() * page.width(),
                      rect.height() * page.height())

    # ---- 绘制 ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#141a22"))

        page = self._page_rect()
        painter.setPen(QPen(QColor("#65758b"), 1))
        painter.setBrush(QColor("#0b1119"))
        painter.drawRect(page)

        # 三分参考线，方便对着画
        painter.setPen(QPen(QColor(101, 117, 139, 60), 1, Qt.PenStyle.DotLine))
        for k in (1, 2):
            x = page.x() + page.width() * k / 3
            y = page.y() + page.height() * k / 3
            painter.drawLine(QPointF(x, page.top()), QPointF(x, page.bottom()))
            painter.drawLine(QPointF(page.left(), y), QPointF(page.right(), y))

        for index, rect in enumerate(self._rects):
            box = self._to_widget(rect)
            selected = index == self._selected
            painter.setPen(QPen(QColor("#ff7a45" if selected else "#5d7898"),
                                1.6 if selected else 1.0))
            painter.setBrush(QColor(255, 122, 69, 45) if selected
                             else QColor(129, 144, 164, 60))
            painter.drawRect(box)
            if selected:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#ff7a45"))
                points = self._handle_points(box)
                for name in ("TL", "TR", "BL", "BR"):
                    painter.drawEllipse(points[name],
                                        HANDLE_SIZE / 2, HANDLE_SIZE / 2)
                # 边中点画成小长条：暗示只能沿一个方向拉伸
                for name, w, h in (("L", 4, 14), ("R", 4, 14),
                                   ("T", 14, 4), ("B", 14, 4)):
                    point = points[name]
                    painter.drawRect(QRectF(point.x() - w / 2, point.y() - h / 2,
                                            w, h))

        if not self._rects:
            painter.setPen(QColor("#7f8fa3"))
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(page, int(Qt.AlignmentFlag.AlignCenter),
                             i18n.tr("在页面上拖动画出照片框"))

    def _handle_points(self, box: QRectF) -> dict[str, QPointF]:
        """8 个手柄：4 个角 + 4 条边的中点（边中点只沿一个方向拉伸）。"""
        cx = (box.left() + box.right()) / 2
        cy = (box.top() + box.bottom()) / 2
        return {
            "TL": QPointF(box.left(), box.top()),
            "TR": QPointF(box.right(), box.top()),
            "BL": QPointF(box.left(), box.bottom()),
            "BR": QPointF(box.right(), box.bottom()),
            "L": QPointF(box.left(), cy),
            "R": QPointF(box.right(), cy),
            "T": QPointF(cx, box.top()),
            "B": QPointF(cx, box.bottom()),
        }

    LEFT_HANDLES = frozenset(("TL", "BL", "L"))
    RIGHT_HANDLES = frozenset(("TR", "BR", "R"))
    TOP_HANDLES = frozenset(("TL", "TR", "T"))
    BOTTOM_HANDLES = frozenset(("BL", "BR", "B"))
    HANDLE_CURSORS = {
        "TL": Qt.CursorShape.SizeFDiagCursor,
        "BR": Qt.CursorShape.SizeFDiagCursor,
        "TR": Qt.CursorShape.SizeBDiagCursor,
        "BL": Qt.CursorShape.SizeBDiagCursor,
        "L": Qt.CursorShape.SizeHorCursor,
        "R": Qt.CursorShape.SizeHorCursor,
        "T": Qt.CursorShape.SizeVerCursor,
        "B": Qt.CursorShape.SizeVerCursor,
    }

    # ---- 吸附 ----------------------------------------------------------

    def _snap_targets(self, skip: int) -> tuple[list[float], list[float]]:
        """吸附候选：页面边界 + 其他矩形的边缘。按下时算一次就够。"""
        xs = [0.0, 1.0]
        ys = [0.0, 1.0]
        for index, other in enumerate(self._rects):
            if index == skip:
                continue
            xs += [other.left(), other.right()]
            ys += [other.top(), other.bottom()]
        return xs, ys

    @staticmethod
    def _snap_value(value: float, targets: list[float]) -> float:
        """单条边吸附：取容差内最近的候选。"""
        best = value
        best_delta = SNAP_TOLERANCE
        for target in targets:
            delta = abs(value - target)
            if delta < best_delta:
                best = target
                best_delta = delta
        return best

    @staticmethod
    def _snap_delta(values, targets) -> float:
        """整块平移的吸附量：在若干条边里挑最近的一个偏移。"""
        best = 0.0
        best_delta = SNAP_TOLERANCE
        for value in values:
            for target in targets:
                delta = abs(value - target)
                if delta < best_delta:
                    best = target - value
                    best_delta = delta
        return best

    @staticmethod
    def _normalized(rect: QRectF) -> QRectF:
        return QRectF(rect.normalized())

    def _is_valid(self, rect: QRectF, skip: int) -> bool:
        rect = self._normalized(rect)
        if rect.width() < MIN_SIZE or rect.height() < MIN_SIZE:
            return False
        if (rect.left() < -1e-6 or rect.top() < -1e-6
                or rect.right() > 1 + 1e-6 or rect.bottom() > 1 + 1e-6):
            return False
        for i, other in enumerate(self._rects):
            if i == skip:
                continue
            inter = rect.intersected(other)
            if inter.width() > 1e-4 and inter.height() > 1e-4:
                return False
        return True

    def _clamp_edge(self, rect: QRectF, handle: str, skip: int) -> None:
        """把被拖的边顶到邻居外侧。

        不做「移动被拒绝」那套（那会表现为拖动时冻结、再突然跳过去），
        而是让边一路滑过去、顶住邻居停下 —— 手感连续，也不会留缝。
        """
        for index, other in enumerate(self._rects):
            if index == skip:
                continue
            x_overlap = (rect.left() < other.right() - 1e-6
                         and rect.right() > other.left() + 1e-6)
            y_overlap = (rect.top() < other.bottom() - 1e-6
                         and rect.bottom() > other.top() + 1e-6)
            if handle in self.RIGHT_HANDLES and y_overlap:
                if other.left() >= rect.left() and rect.right() > other.left():
                    rect.setRight(min(rect.right(), other.left()))
            if handle in self.LEFT_HANDLES and y_overlap:
                if other.right() <= rect.right() and rect.left() < other.right():
                    rect.setLeft(max(rect.left(), other.right()))
            if handle in self.BOTTOM_HANDLES and x_overlap:
                if other.top() >= rect.top() and rect.bottom() > other.top():
                    rect.setBottom(min(rect.bottom(), other.top()))
            if handle in self.TOP_HANDLES and x_overlap:
                if other.bottom() <= rect.bottom() and rect.top() < other.bottom():
                    rect.setTop(max(rect.top(), other.bottom()))

    def _hit(self, pos: QPointF) -> tuple[int, str]:
        """返回 (矩形下标, 手柄名)。手柄名空串表示点在矩形内部。"""
        for index in range(len(self._rects) - 1, -1, -1):
            box = self._to_widget(self._rects[index])
            if index == self._selected:
                for name, point in self._handle_points(box).items():
                    if (abs(pos.x() - point.x()) <= HANDLE_SIZE
                            and abs(pos.y() - point.y()) <= HANDLE_SIZE):
                        return index, name
            if box.contains(pos):
                return index, ""
        return -1, ""

    # ---- 鼠标交互 ------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        index, handle = self._hit(pos)
        self._anchor = self._to_norm(pos)
        self._snap_x, self._snap_y = self._snap_targets(index)
        if index >= 0:
            self._selected = index
            self._origin = QRectF(self._rects[index])
            self._grab_corner = handle
            self._mode = "resize" if handle else "move"
        else:
            self._selected = -1
            self._mode = "new"
            self._origin = QRectF(self._anchor, self._anchor)
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._mode is None:
            index, handle = self._hit(pos)
            if handle:
                self.setCursor(self.HANDLE_CURSORS.get(
                    handle, Qt.CursorShape.CrossCursor))
            elif index >= 0:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        now = self._to_norm(pos)

        if self._mode == "new":
            candidate = QRectF(self._origin.topLeft(), now).normalized()
            x1 = self._snap_value(candidate.left(), self._snap_x)
            x2 = self._snap_value(candidate.right(), self._snap_x)
            y1 = self._snap_value(candidate.top(), self._snap_y)
            y2 = self._snap_value(candidate.bottom(), self._snap_y)
            self._origin = QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized()
            self.update()
            return

        if self._mode == "move":
            dx = now.x() - self._anchor.x()
            dy = now.y() - self._anchor.y()
            candidate = QRectF(self._origin)
            candidate.translate(dx, dy)
            # 吸附：整块平移，所以用偏移量
            snap = QRectF(candidate)
            snap.translate(self._snap_delta(
                (candidate.left(), candidate.right()), self._snap_x),
                self._snap_delta(
                (candidate.top(), candidate.bottom()), self._snap_y))
            if self._is_valid(snap, self._selected):
                candidate = snap
            # 夹进页面
            if candidate.left() < 0:
                candidate.moveLeft(0)
            if candidate.top() < 0:
                candidate.moveTop(0)
            if candidate.right() > 1:
                candidate.moveRight(1)
            if candidate.bottom() > 1:
                candidate.moveBottom(1)
            # 与邻居冲突时，退化成单轴滑动（沿邻居边缘滑行），
            # 而不是整块不动 —— 这样拖起来是连续的。
            if not self._is_valid(candidate, self._selected):
                only_x = QRectF(self._origin)
                only_x.translate(candidate.left() - self._origin.left(), 0)
                only_y = QRectF(self._origin)
                only_y.translate(0, candidate.top() - self._origin.top())
                if self._is_valid(only_x, self._selected):
                    candidate = only_x
                elif self._is_valid(only_y, self._selected):
                    candidate = only_y
                else:
                    candidate = QRectF(self._origin)
            self._rects[self._selected] = candidate
            self.update()
            return

        if self._mode == "resize":
            rect = QRectF(self._origin)
            handle = self._grab_corner
            # 先夹到对边之前，避免拉过头翻转
            if handle in self.LEFT_HANDLES:
                x = min(self._snap_value(now.x(), self._snap_x),
                        self._origin.right() - MIN_SIZE)
                rect.setLeft(max(0.0, x))
            if handle in self.RIGHT_HANDLES:
                x = max(self._snap_value(now.x(), self._snap_x),
                        self._origin.left() + MIN_SIZE)
                rect.setRight(min(1.0, x))
            if handle in self.TOP_HANDLES:
                y = min(self._snap_value(now.y(), self._snap_y),
                        self._origin.bottom() - MIN_SIZE)
                rect.setTop(max(0.0, y))
            if handle in self.BOTTOM_HANDLES:
                y = max(self._snap_value(now.y(), self._snap_y),
                        self._origin.top() + MIN_SIZE)
                rect.setBottom(min(1.0, y))
            # 顶住邻居
            self._clamp_edge(rect, handle, self._selected)
            if rect.width() >= MIN_SIZE and rect.height() >= MIN_SIZE:
                if self._is_valid(rect, self._selected):
                    self._rects[self._selected] = rect
                    self.update()

    def mouseReleaseEvent(self, event):
        if self._mode == "new":
            candidate = self._normalized(self._origin)
            if self._is_valid(candidate, skip=-1):
                self._rects.append(candidate)
                self._selected = len(self._rects) - 1
                self.changed.emit()
        self._mode = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._selected = -1
            self.update()
            return
        super().keyPressEvent(event)


class LayoutDesignerDialog(QDialog):
    """自己设计拼贴布局。"""

    def __init__(self, parent=None, aspect: float = 1.0,
                 initial: list | None = None, name: str = ""):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("自定义拼贴布局"))
        self.setModal(True)
        self.resize(560, 620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hint = QLabel(i18n.tr(
            "在页面上拖动画出照片框；拖动框可以移动，拖四角等比缩放，"
            "拖边中点可单独水平或竖直拉伸。按 Delete 删除。"
            "框不能重叠或超出页面，靠近边缘会自动吸附。"))
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        lay.addWidget(hint)

        self.canvas = LayoutDesignCanvas(self)
        self.canvas.set_aspect(aspect)
        if initial:
            self.canvas.set_rects(initial)
        lay.addWidget(self.canvas, stretch=1)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        self.btn_clear = QPushButton(i18n.tr("清空"))
        self.btn_clear.clicked.connect(self.canvas.clear_all)
        tools.addWidget(self.btn_clear)
        for rows, cols, text in ((2, 2, "2 × 2"), (3, 3, "3 × 3"), (1, 2, "1 × 2")):
            btn = QPushButton(text)
            btn.clicked.connect(
                lambda _=False, r=rows, c=cols: self.canvas.start_with_grid(r, c))
            tools.addWidget(btn)
        self.btn_delete = QPushButton(i18n.tr("删除选中"))
        self.btn_delete.clicked.connect(self.canvas.delete_selected)
        tools.addWidget(self.btn_delete)
        tools.addStretch(1)
        lay.addLayout(tools)

        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(QLabel(i18n.tr("布局名称")))
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText(i18n.tr("例如：我的三格"))
        name_row.addWidget(self.name_edit, stretch=1)
        lay.addLayout(name_row)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        lay.addWidget(self._buttons)

        self.canvas.changed.connect(self._sync_ok)
        self._sync_ok()

    def _sync_ok(self):
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(len(self.canvas.rects()) > 0)

    def _on_accept(self):
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        if not self.canvas.rects():
            return
        self.accept()

    # ---- 给调用方读结果 ------------------------------------------------

    def result_name(self) -> str:
        return self.name_edit.text().strip()

    def result_rects(self) -> list[list[float]]:
        return self.canvas.rects()
