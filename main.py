"""
main.py — Entry point for Speech Bubble Editor v3.
"""

import faulthandler
import logging
import os
import sys

# ── Early crash log (macOS windowed builds suppress all stdout/stderr) ────────
# Configure the root logger to write to a file before any Qt imports.
_LOG_PATH = os.path.expanduser("~/speechbubble_debug.log")
_logger = logging.getLogger("sbe")

try:
    _fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(_fh)
    _logger.setLevel(logging.DEBUG)
    try:
        faulthandler.enable(_fh.stream)
    except Exception:
        pass
except Exception:
    # Unwritable log path — use a no-op logger; never let this crash the app.
    _logger.addHandler(logging.NullHandler())

_logger.info("=== Speech Bubble Editor starting ===")
_logger.info(f"Python {sys.version}  platform={sys.platform}")
_logger.info(f"executable={sys.executable}")


def _log_unhandled_exception(exc_type, exc, tb):
    _logger.exception("UNHANDLED EXCEPTION", exc_info=(exc_type, exc, tb))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _log_unhandled_exception

_singleton_server = None  # module-level — prevents GC of the QLocalServer


def _resource_path(relative: str) -> str:
    """Return absolute path to a bundled resource (PyInstaller-aware)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _load_qss(relative: str) -> str:
    """Read a QSS file from bundled resources. Returns empty string on error."""
    path = _resource_path(relative)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _apply_system_theme(app):
    """Apply the v4 dark UI theme consistently across packaged builds."""
    app.setStyle("Fusion")
    qss = _load_qss(os.path.join("theme", "dark.qss"))
    if qss:
        app.setStyleSheet(qss)
        _logger.info("dark.qss loaded")
    else:
        _logger.warning("theme/dark.qss not found; packaged UI will be unstyled")


def _check_duplicate_instance() -> bool:
    """Return True if another instance is already running (probe only, no server)."""
    try:
        from PyQt6.QtNetwork import QLocalSocket
    except ImportError:
        return False

    SERVER_NAME = "SpeechBubbleEditorV3"
    probe = QLocalSocket()
    probe.connectToServer(SERVER_NAME)
    if probe.waitForConnected(400):
        probe.write(b"raise")
        probe.flush()
        probe.waitForBytesWritten(1000)
        probe.disconnectFromServer()
        return True
    return False


def _start_single_instance_server(window) -> None:
    """Start the local server that lets a second launch raise the first window."""
    global _singleton_server
    try:
        from PyQt6.QtNetwork import QLocalServer
    except ImportError:
        return

    from PyQt6.QtCore import Qt

    SERVER_NAME = "SpeechBubbleEditorV3"
    _singleton_server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    _singleton_server.listen(SERVER_NAME)

    def _on_connection():
        conn = _singleton_server.nextPendingConnection()
        if conn:
            def _read():
                data = bytes(conn.readAll()).decode("utf-8", errors="ignore")
                if "raise" in data:
                    window.setWindowState(
                        window.windowState() & ~Qt.WindowState.WindowMinimized
                        | Qt.WindowState.WindowActive
                    )
                    window.raise_()
                    window.activateWindow()
            conn.readyRead.connect(_read)

    _singleton_server.newConnection.connect(_on_connection)


def _load_fonts():
    """Load bundled fonts — deferred so the window appears before font scanning."""
    from PyQt6.QtGui import QFontDatabase
    fonts_dir = _resource_path("fonts")
    if os.path.isdir(fonts_dir):
        for fname in os.listdir(fonts_dir):
            if fname.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(
                    os.path.join(fonts_dir, fname))
    # 汉化版：把随包分发的中文字体加入应用字体回退链。
    # 界面主字体 Inter 没有中文字形，没有这一层时，未装中文字体的 Windows
    # 会把中文渲染成方块。
    try:
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            f = QFont(app.font())
            fams = [x for x in (f.families() or [f.family()]) if x]
            if "Noto Sans SC" not in fams:
                fams.append("Noto Sans SC")
            f.setFamilies(fams)
            app.setFont(f)
    except Exception:
        pass
    _logger.info("fonts loaded (deferred)")


def main():
    try:
        smoke_test = len(sys.argv) == 3 and sys.argv[1] == "--smoke-test"
        startup_test = len(sys.argv) == 3 and sys.argv[1] == "--startup-test"
        diagnostic = smoke_test or startup_test
        if (
            sys.platform.startswith("linux")
            and os.environ.get("QT_QPA_PLATFORM") != "offscreen"
            and os.environ.get("DBUS_SESSION_BUS_ADDRESS")
            and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
        ):
            os.environ.setdefault("QT_QPA_PLATFORMTHEME", "xdgdesktopportal")

        _logger.info("importing QApplication…")
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QIcon, QFont
        from PyQt6.QtCore import QTimer
        _logger.info("QApplication imported OK")

        app = QApplication(sys.argv)
        app.setApplicationName("Speech Bubble Editor")
        app.setOrganizationName("Long Weekend Labs")
        _logger.info("QApplication created OK")

        # Fast-fail before building the window if another instance is running
        if not diagnostic and _check_duplicate_instance():
            _logger.info("duplicate instance detected — exiting")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(None, "已在运行",
                                    "Speech Bubble Editor 已在运行。")
            sys.exit(0)
        _logger.info("single-instance check passed")

        _apply_system_theme(app)
        _logger.info("theme applied")

        # App icon
        icon_path = _resource_path(os.path.join("icons", "icon.png"))
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        _logger.info("icon set")

        _logger.info("importing MainWindow…")
        from main_window import MainWindow
        _logger.info("MainWindow imported OK")

        _logger.info("creating MainWindow…")
        window = MainWindow()
        _logger.info("MainWindow created OK")

        if not diagnostic:
            _start_single_instance_server(window)

        # Defer font loading so the window appears before font-file scanning.
        QTimer.singleShot(0, _load_fonts)

        if startup_test:
            from startup_probe import StartupProbe
            window._startup_probe = StartupProbe(app, window, sys.argv[2])
        window.show()
        _logger.info("window.show() called — entering event loop")
        # Opt-in packaged-build check. Normal launches do no diagnostic work.
        if smoke_test:
            from smoke_check import run_smoke_check
            QTimer.singleShot(500, lambda: run_smoke_check(app, window, sys.argv[2]))
        sys.exit(app.exec())
    except Exception:
        _logger.exception("EXCEPTION in main()")
        raise


if __name__ == "__main__":
    main()
