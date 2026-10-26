"""Notification-area icon. Always there when "stay ready in the background" is on; otherwise it only appears while a
right-click quick-add is running, shows progress in its tooltip, and pops a native notification with the result."""
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Tray:
    def __init__(self, backend, icon):
        self.backend = backend
        self.ok = QSystemTrayIcon.isSystemTrayAvailable()
        self.active = False
        self.last = None
        self.menu = QMenu()
        self.menu.addAction("Open Tunedock").triggered.connect(backend.showWindow)
        self.menu.addSeparator()
        self.menu.addAction("Quit").triggered.connect(backend.quitApp)
        self.icon = QSystemTrayIcon(icon)
        self.icon.setToolTip("Tunedock")
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        backend.cfgChanged.connect(self.sync)
        backend.toastChanged.connect(self._toast)
        self.sync()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.backend.showWindow()

    def _toast(self):
        t = self.backend.toast
        self.active = bool(t["visible"])
        if self.ok:
            self.icon.setToolTip(("%s\n%s" % (t["title"], t["sub"])).strip() if self.active else "Tunedock")
            if self.active and t["state"] in ("done", "warn", "error"):
                sig = (t["title"], t["sub"], t["state"])
                if sig != self.last:
                    self.last = sig
                    kind = {"done": QSystemTrayIcon.MessageIcon.Information, "warn": QSystemTrayIcon.MessageIcon.Warning,
                            "error": QSystemTrayIcon.MessageIcon.Critical}[t["state"]]
                    self.icon.setVisible(True)
                    self.icon.showMessage(t["title"], t["sub"], kind, 6000)
            elif t["state"] == "working":
                self.last = None
        self.sync()

    def sync(self):
        if self.ok:
            self.icon.setVisible(bool(self.backend.config.get("keep_running")) or self.active)
