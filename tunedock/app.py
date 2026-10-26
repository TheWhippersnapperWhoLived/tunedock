"""Entry point: argument handling, single-instance forwarding, Qt start-up."""
import logging
import os
import sys
import time
from pathlib import Path


def setup_log():
    import logging.handlers
    from .config import home
    h = logging.handlers.RotatingFileHandler(home() / "tunedock.log", maxBytes=400_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log = logging.getLogger("tunedock")
    log.setLevel(logging.INFO)
    log.addHandler(h)
    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        log.addHandler(logging.StreamHandler())
    sys.excepthook = lambda *a: log.error("unhandled", exc_info=a)
    return log


def main(argv=None):
    from . import cli, ipc
    args = cli.parse(sys.argv[1:] if argv is None else argv)
    msg = cli.message(args)
    if msg["cmd"] == "quit":
        ipc.send(msg)
        return 0
    state, listener = ipc.forward_or_serve(msg)
    if state == "sent":
        return 0  # an existing instance took over

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from . import winutil
    winutil.set_app_id()   # before any window exists, so the taskbar uses our icon
    import threading
    from PySide6.QtCore import QTimer, QtMsgType, qInstallMessageHandler
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
    from PySide6.QtQuickControls2 import QQuickStyle

    log = setup_log()
    qInstallMessageHandler(lambda mode, ctx, text: log.log(
        logging.WARNING if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg) else logging.INFO,
        "qt: %s", text))
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Tunedock")
    app.setOrganizationName("Tunedock")
    app.setQuitOnLastWindowClosed(False)
    f = QFont()
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Roboto", "Noto Sans", "Helvetica Neue", "Arial"])
    f.setPixelSize(15)
    app.setFont(f)
    here = Path(__file__).resolve().parent
    assets = here.parent / "assets"
    icon = QIcon()
    for name in ("tunedock.png", "tunedock.ico"):
        if (assets / name).exists():
            icon.addFile(str(assets / name))
    app.setWindowIcon(icon)

    from .bridge import Backend
    from .config import Config
    from . import ingest
    threading.Thread(target=ingest.sweep_old_temp, daemon=True).start()
    backend = Backend(Config())
    qmlRegisterSingletonInstance(Backend, "Td", 1, 0, "Backend", backend)
    engine = QQmlApplicationEngine()
    engine.load(str(here / "qml" / "main.qml"))
    if not engine.rootObjects():
        log.error("The interface failed to load")
        return 1
    backend.attach_window(engine.rootObjects()[0])
    engine.load(str(here / "qml" / "components" / "Toast.qml"))   # the corner progress card: a separate top-level window
    from .tray import Tray
    tray = Tray(backend, icon)  # noqa: F841 (kept alive for the process lifetime)

    server = None
    if listener is not None:
        server = ipc.Server(listener, backend.receive)
        server.start()
    backend.receive(msg)

    idle = {"n": 0}

    def tick():
        idle["n"] = 0 if backend.busy() else idle["n"] + 1
        if idle["n"] >= 3:
            app.quit()
    t = QTimer()
    t.timeout.connect(tick)
    t.start(1000)
    code = app.exec()
    if server:
        server.stop()
    return code
