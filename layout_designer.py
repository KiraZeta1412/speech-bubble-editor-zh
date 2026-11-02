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
SNAP_TOLERANCE = 0.012  # 吸附容差（占页面比例）
HANDLE_SIZE = 10        # 缩放手柄的屏幕半径


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
                painter.setBrush(QColor("#ff7a45"))
                painter.setPen(Qt.PenStyle.NoPen)
                for corner in self._corner_points(box).values():
                    painter.drawEllipse(corner, HANDLE_SIZE / 2, HANDLE_SIZE / 2)

        if not self._rects:
            painter.setPen(QColor("#7f8fa3"))
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(page, int(Qt.AlignmentFlag.AlignCenter),
                             i18n.tr("在页面上拖动画出照片框"))

    def _corner_points(self, box: QRectF) -> dict[str, QPointF]:
        return {
            "TL": QPointF(box.left(), box.top()),
            "TR": QPointF(box.right(), box.top()),
            "BL": QPointF(box.left(), box.bottom()),
            "BR": QPointF(box.right(), box.bottom()),
        }

    # ---- 吸附 / 合法性 -------------------------------------------------

    def _snap(self, rect: QRectF, skip: int) -> QRectF:
        """把矩形边缘吸附到页面边界和其他矩形的边缘。"""
        edges_x = [0.0, 1.0]
        edges_y = [0.0, 1.0]
        for i, other in enumerate(self._rects):
            if i == skip:
                continue
            edges_x += [other.left(), other.right()]
            edges_y += [other.top(), other.bottom()]
        rect = QRectF(rect)
        for candidate in (rect.left(), rect.right()):
            for edge in edges_x:
                if abs(candidate - edge) < SNAP_TOLERANCE:
                    dx = edge - candidate
                    rect.moveLeft(rect.left() + dx)
                    break
        for candidate in (rect.top(), rect.bottom()):
            for edge in edges_y:
                if abs(candidate - edge) < SNAP_TOLERANCE:
                    dy = edge - candidate
                    rect.moveTop(rect.top() + dy)
                    break
        return rect

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

    def _hit(self, pos: QPointF) -> tuple[int, str]:
        """返回 (矩形下标, 手柄名)。手柄名空串表示点在矩形内部。"""
        for index in range(len(self._rects) - 1, -1, -1):
            box = self._to_widget(self._rects[index])
            if index == self._selected:
                for name, point in self._corner_points(box).items():
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
                cursors = {"TL": Qt.CursorShape.SizeFDiagCursor,
                           "BR": Qt.CursorShape.SizeFDiagCursor,
                           "TR": Qt.CursorShape.SizeBDiagCursor,
                           "BL": Qt.CursorShape.SizeBDiagCursor}
                self.setCursor(cursors.get(handle, Qt.CursorShape.CrossCursor))
            elif index >= 0:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        now = self._to_norm(pos)
        if self._mode == "new":
            candidate = QRectF(self._origin.topLeft(), now).normalized()
            candidate = self._snap(candidate, skip=-1)
            self._origin = candidate
            self._preview = candidate
            self.update()
            return

        if self._mode == "move":
            dx = now.x() - self._anchor.x()
            dy = now.y() - self._anchor.y()
            candidate = QRectF(self._origin)
            candidate.translate(dx, dy)
            # 夹在页面内
            if candidate.left() < 0:
                candidate.moveLeft(0)
            if candidate.top() < 0:
                candidate.moveTop(0)
            if candidate.right() > 1:
                candidate.moveRight(1)
            if candidate.bottom() > 1:
                candidate.moveBottom(1)
            candidate = self._snap(candidate, skip=self._selected)
            if self._is_valid(candidate, skip=self._selected):
                self._rects[self._selected] = candidate
                self.update()
            return

        if self._mode == "resize":
            rect = QRectF(self._origin)
            corner = self._grab_corner
            if "L" in corner:
                rect.setLeft(min(now.x(), rect.right() - MIN_SIZE))
            if "R" in corner:
                rect.setRight(max(now.x(), rect.left() + MIN_SIZE))
            if "T" in corner:
                rect.setTop(min(now.y(), rect.bottom() - MIN_SIZE))
            if "B" in corner:
                rect.setBottom(max(now.y(), rect.top() + MIN_SIZE))
            rect = self._snap(rect, skip=self._selected)
            if self._is_valid(rect, skip=self._selected):
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
            "在页面上拖动画出照片框；拖动框可以移动，拖四角可以缩放，"
            "按 Delete 删除。框不能重叠或超出页面。"))
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
