"""
redaction.py — RedactionItem：框住一块区域并打码。用来遮脸、车牌、名字等。

支持三种打码样式：

  mosaic  马赛克   按块大小降采样再放大（块越大越糊）
  blur    高斯模糊  真正的 Gaussian 模糊，不是缩放近似
  fill    纯色填充  硬打码；可自动取区域内平均色，融进背景不突兀

三种样式共用「羽化」参数：边缘做软过渡，避免生硬的矩形轮廓。

实现说明：效果在**源分辨率**下计算（框下面那片照片的真实像素），再缩放绘制到
框里；参数会按「源图 / 屏幕框」的比例换算，所以无论照片多大、画布缩放多少，
界面上看到的颗粒和模糊程度都和设定值一致。

ResizeHandle 复用 bubble.py 的实现，本类继续暴露它需要的鸭子类型接口
（body_rect / set_body_rect / get_style / get_font / _undo_stack / _handles）。
"""

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneContextMenuEvent, QMenu, QApplication,
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QPixmap, QImage
from PyQt6.QtCore import Qt, QRectF, QPointF

from bubble import ResizeHandle, ANCHORS, HANDLE_SIZE

DEFAULT_W = 220
DEFAULT_H = 150

# 样式标识（对外可用的字符串）
STYLE_MOSAIC = "mosaic"
STYLE_BLUR = "blur"
STYLE_FILL = "fill"
STYLES = (STYLE_MOSAIC, STYLE_BLUR, STYLE_FILL)

# 老版本用的是 "pixelate"，读旧文件/旧代码时映射到 mosaic
_LEGACY_MODES = {"pixelate": STYLE_MOSAIC}


def normalise_style(mode: str) -> str:
    mode = str(mode or "").strip().lower()
    mode = _LEGACY_MODES.get(mode, mode)
    return mode if mode in STYLES else STYLE_MOSAIC


# ---------------------------------------------------------------------------
# QImage <-> PIL 转换（Pillow 是项目既有依赖）
# ---------------------------------------------------------------------------

def _qimage_to_pil(image: QImage):
    from PIL import Image
    if image.format() != QImage.Format.Format_RGBA8888:
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = image.width(), image.height()
    ptr = image.constBits()
    ptr.setsize(h * image.bytesPerLine())
    raw = bytes(ptr)
    stride = image.bytesPerLine()
    if stride != w * 4:      # 行末有 padding，逐行裁掉
        raw = b"".join(raw[y * stride:y * stride + w * 4] for y in range(h))
    return Image.frombytes("RGBA", (w, h), raw)


def _pil_to_qimage(pil_image) -> QImage:
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes()
    image = QImage(data, pil_image.width, pil_image.height,
                   QImage.Format.Format_RGBA8888)
    return image.copy()      # copy() 让 QImage 拥有内存，脱离 Python 缓冲区


class RedactionItem(QGraphicsItem):
    """一块打码区域：马赛克 / 高斯模糊 / 纯色填充。"""

    def __init__(self, scene_x: float, scene_y: float, mode: str = STYLE_MOSAIC):
        super().__init__()
        hw, hh = DEFAULT_W / 2, DEFAULT_H / 2
        self._rect = QRectF(-hw, -hh, DEFAULT_W, DEFAULT_H)
        self._mode = normalise_style(mode)

        # 各样式自己的参数
        self._block_size = 14        # 马赛克块边长（屏幕像素，2..64）
        self._blur_radius = 12       # 高斯模糊半径（屏幕像素，1..64）
        self._feather = 0            # 边缘羽化（屏幕像素，0..40）
        self._fill_color = QColor("#101010")
        self._fill_auto = False      # True = 取区域内平均色

        self._drag_start_pos: QPointF | None = None
        self._page_panel_index: int | None = None
        self._page_frame = QRectF()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,            True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,         True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        # 在照片/叠加层之上，气泡之下（气泡 z=100）
        self.setZValue(90)
        self.setPos(scene_x, scene_y)

        self._handles: dict[str, ResizeHandle] = {}
        for anchor in ANCHORS:
            h = ResizeHandle(anchor, self)
            h.setVisible(False)
            self._handles[anchor] = h
        self._update_handle_positions()

    # ------------------------------------------------------------------
    # ResizeHandle / ResizeBubbleCommand 需要的接口
    # ------------------------------------------------------------------

    @property
    def body_rect(self) -> QRectF:
        return self._rect

    def set_body_rect(self, rect: QRectF):
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self._update_handle_positions()
        self.update()

    def get_style(self) -> str:
        return self._mode          # 不是 "text"，所以手柄不会按字号缩放

    def get_font(self) -> QFont:
        return QFont()             # 手柄按下时会读 pointSize()

    def _undo_stack(self):
        scene = self.scene()
        return getattr(scene, "undo_stack", None) if scene else None

    def _update_handle_positions(self):
        r = self._rect
        cx, cy = r.center().x(), r.center().y()
        l, t, ri, b = r.left(), r.top(), r.right(), r.bottom()
        for anchor, (x, y) in {
            "TL": (l, t), "TC": (cx, t), "TR": (ri, t),
            "ML": (l, cy),               "MR": (ri, cy),
            "BL": (l, b), "BC": (cx, b), "BR": (ri, b),
        }.items():
            self._handles[anchor].setPos(x, y)

    # ------------------------------------------------------------------
    # 对外参数接口
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        """当前样式（mosaic / blur / fill）。"""
        return self._mode

    def set_mode(self, mode: str):
        mode = normalise_style(mode)
        if mode != self._mode:
            self._mode = mode
            self.update()

    def get_block_size(self) -> int:
        return self._block_size

    def set_block_size(self, value: int):
        self._block_size = max(2, min(64, int(value)))
        if self._mode == STYLE_MOSAIC:
            self.update()

    def get_blur_radius(self) -> int:
        return self._blur_radius

    def set_blur_radius(self, value: int):
        self._blur_radius = max(1, min(64, int(value)))
        if self._mode == STYLE_BLUR:
            self.update()

    def get_feather(self) -> int:
        return self._feather

    def set_feather(self, value: int):
        self._feather = max(0, min(40, int(value)))
        self.update()

    def get_fill_color(self) -> QColor:
        return QColor(self._fill_color)

    def set_fill_color(self, color: QColor):
        self._fill_color = QColor(color)
        if self._mode == STYLE_FILL:
            self.update()

    def is_fill_auto(self) -> bool:
        return self._fill_auto

    def set_fill_auto(self, auto: bool):
        self._fill_auto = bool(auto)
        if self._mode == STYLE_FILL:
            self.update()

    # 旧接口兼容：老代码把 0..100 的 intensity 当强度用
    def get_intensity(self) -> int:
        if self._mode == STYLE_MOSAIC:
            return int(round(self._block_size / 64 * 100))
        return int(round(self._blur_radius / 64 * 100))

    def set_intensity(self, value: int):
        value = max(1, min(100, int(value)))
        if self._mode == STYLE_MOSAIC:
            self._block_size = max(2, min(64, int(round(value / 100 * 64))))
        else:
            self._blur_radius = max(1, min(64, int(round(value / 100 * 64))))
        self.update()

    def attach_to_page_panel(self, index: int, frame: QRectF):
        """绑定到某个漫画分格 / 拼贴画框。"""
        self._page_panel_index = int(index)
        self._page_frame = QRectF(frame)
        width = max(50.0, min(220.0, frame.width() * 0.38))
        height = max(40.0, min(150.0, frame.height() * 0.28))
        self.set_body_rect(QRectF(-width / 2, -height / 2, width, height))
        self.setPos(frame.center())
        self.update()

    def set_frame(self, frame: QRectF):
        """页面重新排版时跟随，保持相对位置和相对大小。"""
        frame = QRectF(frame)
        old = QRectF(self._page_frame)
        if old.width() > 0 and old.height() > 0:
            nx = (self.pos().x() - old.left()) / old.width()
            ny = (self.pos().y() - old.top()) / old.height()
            sx = frame.width() / old.width()
            sy = frame.height() / old.height()
            r = self._rect
            self.set_body_rect(QRectF(
                -r.width() * sx / 2, -r.height() * sy / 2,
                r.width() * sx, r.height() * sy))
            self._page_frame = frame
            self.setPos(frame.left() + nx * frame.width(),
                        frame.top() + ny * frame.height())
        else:
            self._page_frame = frame
        self.update()

    # ------------------------------------------------------------------
    # 几何 / 绘制
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        pad = HANDLE_SIZE + 2
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self._rect
        src = self._sample_source()
        if src is not None and not src.isNull():
            painter.drawPixmap(r, self._render_effect(src), QRectF(src.rect()))
        else:
            # 还没载入照片：显示中性占位块
            painter.fillRect(r, QColor(28, 33, 42, 200))

        # 只在选中时描虚线框，否则打码区不该有常驻边框
        if self.isSelected():
            painter.setPen(QPen(QColor("#ff8a3d"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

    def _sample_source(self) -> QPixmap | None:
        """取出框下面那片照片区域（源分辨率）。"""
        scene = self.scene()

        # 情况一：绑定在漫画分格 / 拼贴画框上
        if scene is not None and self._page_panel_index is not None:
            panels = getattr(scene, "_manga_panels", ())
            panel = next((p for p in panels
                          if p.index == self._page_panel_index), None)
            if panel is None or not panel.has_image():
                return None
            pm = panel.pixmap()
            target = panel._draw_geometry()
            if pm.isNull() or target.width() <= 0 or target.height() <= 0:
                return None
            local = panel.mapFromScene(
                self.mapToScene(self._rect)).boundingRect()
            src = QRectF(
                (local.x() - target.x()) * pm.width() / target.width(),
                (local.y() - target.y()) * pm.height() / target.height(),
                local.width() * pm.width() / target.width(),
                local.height() * pm.height() / target.height(),
            ).intersected(QRectF(pm.rect()))
            return pm.copy(src.toRect()) if src.width() >= 1 and src.height() >= 1 else None

        # 情况二：普通照片
        photo = getattr(scene, "_photo_item", None) if scene else None
        if photo is None:
            return None
        pm = photo.pixmap()
        if pm is None or pm.isNull():
            return None
        dw, dh = float(photo.display_w), float(photo.display_h)
        if dw <= 0 or dh <= 0:
            return None
        nw, nh = pm.width(), pm.height()
        srect = self.mapToScene(self._rect).boundingRect()
        sx, sy = nw / dw, nh / dh
        src = QRectF((srect.x() - photo.pos().x()) * sx,
                     (srect.y() - photo.pos().y()) * sy,
                     srect.width() * sx, srect.height() * sy)
        src = src.intersected(QRectF(0, 0, nw, nh))
        if src.width() < 1 or src.height() < 1:
            return None
        return pm.copy(src.toRect())

    # ---- 效果处理 -----------------------------------------------------

    def _source_ratio(self, src: QPixmap) -> float:
        """源图相对屏幕框的缩放比例，用于把「屏幕像素」参数换算到源分辨率。"""
        box_w = max(1.0, float(self._rect.width()))
        return max(0.05, src.width() / box_w)

    def _render_effect(self, src: QPixmap) -> QPixmap:
        base = src.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ratio = self._source_ratio(src)

        if self._mode == STYLE_MOSAIC:
            effect = self._mosaic(base, max(2, int(round(self._block_size * ratio))))
        elif self._mode == STYLE_FILL:
            effect = self._fill(base)
        else:
            effect = self._blur(base, max(1.0, self._blur_radius * ratio))

        if self._feather > 0:
            effect = self._feathered(base, effect,
                                     max(1.0, self._feather * ratio))
        return QPixmap.fromImage(effect)

    def _mosaic(self, image: QImage, block: int) -> QImage:
        """按块降采样再放大（最近邻），得到经典马赛克。"""
        w, h = image.width(), image.height()
        if w < 2 or h < 2:
            return image
        sw = max(1, w // block)
        sh = max(1, h // block)
        small = image.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.FastTransformation)

    def _blur(self, image: QImage, radius: float) -> QImage:
        """真正的 Gaussian 模糊（Pillow），比缩放近似干净得多。"""
        try:
            from PIL import ImageFilter
            pil = _qimage_to_pil(image)
            out = pil.filter(ImageFilter.GaussianBlur(radius=float(radius)))
            return _pil_to_qimage(out)
        except Exception:
            # Pillow 不可用时退回缩放近似，保证功能不中断
            w, h = image.width(), image.height()
            factor = max(1.0, radius)
            sw, sh = max(1, int(w / factor)), max(1, int(h / factor))
            small = image.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)

    def _fill(self, image: QImage) -> QImage:
        """纯色填充；auto 模式取区域平均色，融进背景。"""
        color = QColor(self._fill_color)
        if self._fill_auto:
            color = self._average_color(image)
        out = QImage(image.size(), QImage.Format.Format_RGBA8888)
        out.fill(color)
        return out

    @staticmethod
    def _average_color(image: QImage) -> QColor:
        """区域平均色（缩到 1x1 取，比逐像素求和快得多）。"""
        try:
            one = image.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            return QColor(one.pixelColor(0, 0))
        except Exception:
            return QColor("#101010")

    def _feathered(self, base: QImage, effect: QImage, feather: float) -> QImage:
        """用羽化蒙版混合原图与效果图，边缘自然过渡。"""
        try:
            from PIL import Image, ImageDraw, ImageFilter
            w, h = base.width(), base.height()
            inset = max(0, int(round(feather)))
            mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(mask)
            draw.rectangle([inset, inset, max(inset, w - 1 - inset),
                            max(inset, h - 1 - inset)], fill=255)
            if inset > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(max(0.5, feather / 2.0)))
            base_pil = _qimage_to_pil(base).convert("RGB")
            eff_pil = _qimage_to_pil(effect).convert("RGB")
            blended = Image.composite(eff_pil, base_pil, mask)
            return _pil_to_qimage(blended)
        except Exception:
            return effect

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene:
                sr = (self._page_frame if self._page_panel_index is not None
                      and not self._page_frame.isNull() else scene.sceneRect())
                r = self._rect
                x = max(sr.left() - r.left(),
                        min(value.x(), sr.right() - r.right()))
                y = max(sr.top() - r.top(),
                        min(value.y(), sr.bottom() - r.bottom()))
                return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            for h in self._handles.values():
                h.setVisible(bool(value))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.update()   # 重新采样新位置下面的照片
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            old, new = self._drag_start_pos, self.pos()
            if old is not None and (old - new).manhattanLength() > 1:
                stack = self._undo_stack()
                if stack:
                    from undo_commands import MoveBubbleCommand
                    stack.push(MoveBubbleCommand(self, old, new))
            self._drag_start_pos = None

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        menu = QMenu()
        act_mosaic = menu.addAction("马赛克")
        act_blur   = menu.addAction("高斯模糊")
        act_fill   = menu.addAction("纯色填充")
        for act, style in ((act_mosaic, STYLE_MOSAIC),
                           (act_blur,   STYLE_BLUR),
                           (act_fill,   STYLE_FILL)):
            act.setCheckable(True)
            act.setChecked(self._mode == style)
        menu.addSeparator()
        act_dup = menu.addAction("创建副本")
        act_del = menu.addAction("删除")
        chosen = menu.exec(event.screenPos())
        if chosen == act_mosaic:
            self.set_mode(STYLE_MOSAIC)
        elif chosen == act_blur:
            self.set_mode(STYLE_BLUR)
        elif chosen == act_fill:
            self.set_mode(STYLE_FILL)
        elif chosen == act_dup:
            self._duplicate()
        elif chosen == act_del:
            self._delete()

    def _delete(self):
        scene = self.scene()
        if not scene:
            return
        stack = self._undo_stack()
        if stack:
            from undo_commands import DeleteBubbleCommand
            stack.push(DeleteBubbleCommand(scene, self))
        else:
            scene.removeItem(self)

    def _duplicate(self):
        scene = self.scene()
        if not scene:
            return
        nb = RedactionItem(self.scenePos().x() + 25,
                           self.scenePos().y() + 25, mode=self._mode)
        nb.set_body_rect(QRectF(self._rect))
        nb.set_block_size(self._block_size)
        nb.set_blur_radius(self._blur_radius)
        nb.set_feather(self._feather)
        nb.set_fill_color(self._fill_color)
        nb.set_fill_auto(self._fill_auto)
        if self._page_panel_index is not None:
            nb._page_panel_index = self._page_panel_index
            nb._page_frame = QRectF(self._page_frame)
        stack = self._undo_stack()
        if stack:
            from undo_commands import AddBubbleCommand
            stack.push(AddBubbleCommand(scene, nb))
        else:
            scene.addItem(nb)
