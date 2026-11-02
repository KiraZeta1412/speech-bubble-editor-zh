"""
version.py — Single source of truth for the application version and branding.

History:
  v2.0.0 — Video support (MP4, AVI, WebM, MOV, MKV), video scrubber,
            trim / cut / reverse editing, dual video mode, audio-preserving
            export via FFmpeg, app icon, Long Weekend Labs branding.
  v2.1.0 — LRU frame cache for responsive scrubbing; playback respects
            trim markers; export pre-renders bubble overlay once (fast);
            export dialog is modal; player stops before export; welcome
            screen with click-to-open; + Bubble toolbar button (Ctrl+B);
            Instagram-style slim semi-transparent scrim/caption bar;
            scrim bubble compact height; shape preserved on style switch;
            bubbles clamped to canvas; meme bar resize fix; lock aspect
            ratio on by default.
  v2.1.10 — Production release: Caption bubble style (stroke text overlay,
             Anton font, 8-direction outline, optional fill background);
             step frame / first / last frame controls; time label shows
             trim selection range; reverse playback live in GUI (not just
             export); meme bar position fixed after resize; dual mode right
             pane布局 fixed (placeholder tracked through all moves).
  v3.0.0 — Single instance enforcement; macOS support; overlay layers
            (add photo/video as freely-positioned layer, z-order controls,
            undo/redo); dual mode seam settings (gap, border, feather) in
            Properties Panel; theme-aware welcome screen; GitHub link in
            About dialog; zoom bar and video controls hidden until media
            is loaded.
  v3.1.0 — Dropped macOS support. Native ARM64 builds for Windows 11 ARM
            and Linux aarch64 (RPM, DEB, AppImage, portable tar.gz).
            All dependencies bundled — no system Python or Qt required.
  v4.0.0 — Modern side-inspector UI (TopBar, ToolSidebar, InspectorDock);
            undo coverage for all properties (style, color, font, etc.);
            lazy-import cv2/numpy (2s cold startup); native-resolution
            export fix; background-thread frame decoding with LRU cache;
            single-instance fail-fast; Python logging module; dark theme
            via theme/dark.qss.
  v4.0.2 — Bundles theme/dark.qss in packaged builds and applies the v4
            dark UI consistently for Windows/Linux artifacts.
  v4.0.3 — v4 UI redesign pass: ContextToolbar (selection-sensitive action
            strip with align/z-order/delete); 7 bubble styles in Inspector
            (adds Scrim + Caption); Justify text-alignment button; refactored
            AccordionSection with teal/muted chevron button; TopBar height
            fixed to 52px with zoom dropdown menu; ToolSidebar width fixed
            to 80px; Caption and Text tools wired to add bubbles with correct
            default style; Delete key bound to delete selected item; complete
            dark.qss rewrite using exact v4 design tokens (accent #ff8a3d).
  v4.0.4 — Top-bar icon render fix; font dropdown uses QFontDatabase; video
            slowdown control with magnetic 10/25/35/50/75/100% stops.
  v4.0.6 — Local test build: safer bubble text fitting, rectangle tail handle,
            text copy/paste menus, and stronger crash logging.
  v4.1.0 — Font size is now a slider. Resizing a speech bubble fits the text to
            fill it in BOTH axes — the text wraps and grows to use the height,
            not just the width, so a tall bubble no longer leaves the text tiny
            at the top. Instagram default text style + bundled Inter font,
            blur/pixelate redaction layers, Camtasia-style block text fit, and a
            full-resolution dual-export布局 fix.
  v4.5.0 — Comic and Photo Collage page editors, visual布局 generation,
            magnetic photo reordering, frame-aware effects, named collage
            presets, bidirectional image scaling, and unified page inspectors.
  v4.5.1 — Responsive editor polish, stable selection layout and low-resolution
            bubble sizing, unified inspector structure, and the blue-and-orange
            Night Desk interface theme.
"""

__version__  = "4.5.2"
__app_name__ = "漫画气泡编辑器"
__org_name__ = "Long Weekend Labs"
__copyright__ = "© 2026 Long Weekend Labs"
