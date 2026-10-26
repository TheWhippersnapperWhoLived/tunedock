"""The object QML talks to. All state lives here; the UI only displays it and sends intents."""
import logging
import os
import threading
import time
import traceback
from collections import deque
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPalette

from . import colors, config, ffmpeg_fetch, ingest, library, media, naming, shell, winutil

log = logging.getLogger("tunedock")
KEY_MENU = {"menu_mode", "menu_folders", "library_root"}


def _local(p) -> str:
    s = str(p)
    if s.startswith("file:"):
        s = QUrl(s).toLocalFile()
    return s


def _mb(n):
    return round(n / 1048576, 1)


def describe(rep: dict) -> dict:
    ok = rep["converted"] + rep["copied"]
    if rep.get("fatal"):
        title, sub, kind = "Couldn't add that", rep["fatal"], "error"
    elif rep["cancelled"]:
        title, sub, kind = "Stopped", f"{ok} track{'s' * (ok != 1)} were added before you cancelled", "warn"
    elif rep["failed"] and not ok:
        title, sub, kind = "Nothing was added", f"{rep['failed']} failed", "error"
    elif rep["failed"]:
        title, sub, kind = f"Added {ok} track{'s' * (ok != 1)}", f"{rep['failed']} couldn't be converted", "warn"
    elif ok == 0 and rep["skipped"]:
        title, sub, kind = "Already in your library", f"{rep['skipped']} skipped", "ok"
    else:
        title, sub, kind = f"Added {ok} track{'s' * (ok != 1)}", "", "ok"
    n_rep = rep.get("replaced", 0)
    if n_rep and rep["failed"] == 0 and not rep["cancelled"] and not rep.get("fatal") and n_rep == ok:
        title = f"Reprocessed {ok} track{'s' * (ok != 1)}"
    elif n_rep and not sub and not rep.get("fatal"):
        sub = f"{n_rep} replaced in place"
    out = dict(rep)
    out.update(title=title, sub=sub, kind=kind, inMB=_mb(rep["bytes_in"]), outMB=_mb(rep["bytes_out"]),
               destName=Path(rep["dest"]).name or rep["dest"], added=ok)
    return out


class Backend(QObject):
    schemeChanged = Signal()
    cfgChanged = Signal()
    stageChanged = Signal()
    queueChanged = Signal()
    scanChanged = Signal()
    navChanged = Signal()
    progressChanged = Signal()
    reportChanged = Signal()
    toastChanged = Signal()
    statusChanged = Signal()
    windowChanged = Signal()
    raiseWindow = Signal()
    goto = Signal(int)
    _scanDone = Signal(object)
    _navDone = Signal(object)
    _event = Signal(object)
    _msg = Signal(object)
    _detected = Signal(object)
    _dlEvent = Signal(object)
    dlChanged = Signal()

    def __init__(self, cfg: config.Config, parent=None):
        super().__init__(parent)
        self.config = cfg
        self._stage, self._inputs, self._scan = "idle", [], None
        self._scan_summary = {"items": 0, "tracks": 0, "albums": 0, "loose": 0, "errors": [], "labels": []}
        self._nav = {"path": "", "parts": [], "entries": [], "decision": {"auto": False, "kind": "branch"},
                     "loading": False, "root": "", "ok": False}
        self._progress = {"done": 0, "total": 0, "name": "", "state": "", "recent": [], "quick": False, "active": False}
        self._report = {}
        self._toast = {"visible": False, "title": "", "sub": "", "value": -1.0, "state": "working", "dest": ""}
        self._status = {"ffmpeg": "", "ffmpegOk": False, "fmtOk": {}, "menuInstalled": False, "windows": os.name == "nt",
                        "sevenZip": False, "recycle": False, "libraryOk": False, "libraryFolders": []}
        self._window = False
        self._held = []
        self._pending = []
        self._jobs, self._lock, self._alive, self._runner, self._job_id = deque(), threading.Lock(), False, None, 0
        self._nav_token = 0
        self._scheme, self._dark = {}, False
        self._cancelled_gui = False
        self._qwindow = None
        self._dl = {"state": "idle", "pct": -1.0, "msg": ""}
        self._dl_thread, self._dl_cancel, self._dl_lock, self._waiting_dl = None, None, threading.Lock(), False

        self._debounce = QTimer(self, singleShot=True, interval=450)
        self._debounce.timeout.connect(self._flush)
        self._scan_timer = QTimer(self, singleShot=True, interval=120)
        self._scan_timer.timeout.connect(self._start_scan)
        self._menu_timer = QTimer(self, singleShot=True, interval=900)
        self._menu_timer.timeout.connect(self._sync_menu)
        self._toast_timer = QTimer(self, singleShot=True, interval=6000)
        self._toast_timer.timeout.connect(self._hide_toast)

        self._scanDone.connect(self._on_scan)
        self._navDone.connect(self._on_nav)
        self._event.connect(self._on_event)
        self._msg.connect(self._on_msg)
        self._detected.connect(self._on_detected)
        self._dlEvent.connect(self._on_dl)
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._rebuild_scheme())
        self._rebuild_scheme()
        self._refresh_library()
        threading.Thread(target=self._detect, daemon=True).start()
        self._menu_timer.start()   # on start-up: repair the Explorer menu / autostart entries if they point somewhere old

    # ------------------------------------------------------------ properties
    @Property("QVariantMap", notify=schemeChanged)
    def scheme(self):
        return self._scheme

    @Property(bool, notify=schemeChanged)
    def dark(self):
        return self._dark

    @Property("QVariantMap", notify=cfgChanged)
    def cfg(self):
        return self.config.snapshot()

    @Property(str, notify=stageChanged)
    def stage(self):
        return self._stage

    @Property("QVariantMap", notify=scanChanged)
    def scan(self):
        return self._scan_summary

    @Property("QVariantMap", notify=navChanged)
    def nav(self):
        return self._nav

    @Property("QVariantMap", notify=progressChanged)
    def progress(self):
        return self._progress

    @Property("QVariantMap", notify=reportChanged)
    def report(self):
        return self._report

    @Property("QVariantMap", notify=toastChanged)
    def toast(self):
        return self._toast

    @Property("QVariantMap", notify=dlChanged)
    def ffmpegDl(self):
        return self._dl

    @Property("QVariantMap", notify=statusChanged)
    def status(self):
        return self._status

    @Property(bool, notify=windowChanged)
    def windowVisible(self):
        return self._window

    @Property(str, constant=True)
    def iconUrl(self):
        p = Path(__file__).resolve().parent.parent / "assets" / "tunedock.png"
        return QUrl.fromLocalFile(str(p)).toString() if p.exists() else ""

    @Property("QVariantList", constant=True)
    def formats(self):
        return [{"key": k, "label": v["label"], "lo": v["lo"], "hi": v["hi"], "presets": v["presets"], "lossy": v["lossy"]}
                for k, v in media.FORMATS.items()]

    @Property("QVariantList", constant=True)
    def namePresets(self):
        return [{"label": a, "tpl": b} for a, b in naming.PRESETS]

    @Property("QVariantList", constant=True)
    def folderPresets(self):
        return [{"label": a, "tpl": b} for a, b in naming.FOLDER_PRESETS]

    @Property("QVariantList", constant=True)
    def fields(self):
        return [{"key": k, "label": v} for k, v in naming.FIELDS.items()]

    @Property("QVariantList", constant=True)
    def swatches(self):
        return colors.SWATCHES

    # ------------------------------------------------------------ settings
    @Slot(str, "QVariant")
    def setCfg(self, key, value):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        if key in ("library_root", "ffmpeg_path") and isinstance(value, str) and value.startswith("file:"):
            value = _local(value)
        if not self.config.set(key, value):
            return
        self.cfgChanged.emit()
        if key in ("theme_mode", "seed"):
            self._rebuild_scheme()
        if key == "library_root":
            self._refresh_library()
        if key in KEY_MENU or key == "library_root":
            self._menu_timer.start()
        if key in ("autostart", "keep_running"):
            self._apply_autostart()
        if key in ("ffmpeg_path", "format"):
            threading.Thread(target=self._detect, daemon=True).start()

    def _apply_autostart(self):
        if os.name != "nt":
            return
        try:
            shell.set_autostart(bool(self.config.get("autostart") and self.config.get("keep_running")))
        except Exception:
            log.exception("autostart")

    def _accent(self):
        try:
            return QGuiApplication.palette().color(QPalette.ColorRole.Accent).name()
        except Exception:
            return QGuiApplication.palette().color(QPalette.ColorRole.Highlight).name()

    def _rebuild_scheme(self):
        mode, seed = self.config.get("theme_mode"), self.config.get("seed")
        dark = mode == "dark" or (mode == "system" and QGuiApplication.styleHints().colorScheme().name == "Dark")
        self._scheme = colors.scheme(self._accent() if seed == "system" else seed, dark)
        self._dark = dark
        self.schemeChanged.emit()

    @Slot(result=str)
    def systemAccent(self):
        return self._accent()

    # ------------------------------------------------------------ environment
    @staticmethod
    def _can_download():
        return os.name == "nt" or bool(os.environ.get("TUNEDOCK_FFMPEG_URL"))

    def _detect(self):
        cfg = self.config.snapshot()
        fmt = cfg["format"]
        need = media.FORMATS[fmt]["enc"] or ""
        ff = media.find_ffmpeg(cfg["ffmpeg_path"], need=need)
        enc = media.available_encoders(ff) if ff else set()
        fmt_ok = {k: (v["enc"] is None or v["enc"] in enc) for k, v in media.FORMATS.items()}
        needed = fmt != "keep"
        ready = (not needed) or (bool(ff) and need in enc)
        note = ""
        if needed and not ff:
            note = "ffmpeg wasn't found"
        elif needed and ff and need not in enc:
            note = f"This ffmpeg can't encode {media.FORMATS[fmt]['label']}"
        from . import archives
        self._detected.emit(dict(ffmpeg=ff, ffmpegOk=bool(ff), ffmpegNeeded=needed, ffmpegReady=ready, ffmpegNote=note,
                                 canDownload=self._can_download(), fmtOk=fmt_ok, sevenZip=bool(archives.find_7z()),
                                 recycle=winutil.recycle_available(), menuInstalled=shell.is_installed()))

    def _on_detected(self, info):
        self._status = dict(self._status, **info)
        self.statusChanged.emit()
        self._refresh_library()
        # only when the main job (converting) can't work without it, and only if the user hasn't turned this off
        if (not info["ffmpegReady"] and info["canDownload"] and self.config.get("ffmpeg_auto")
                and self._dl["state"] not in ("downloading", "error")):
            self._start_download()

    # ------------------------------------------------------------ ffmpeg download
    @Slot()
    def downloadFfmpeg(self):
        if self._dl["state"] == "error":
            self._dl = {"state": "idle", "pct": -1.0, "msg": ""}
        self._start_download()

    @Slot()
    def cancelDownload(self):
        if self._dl_cancel:
            self._dl_cancel.set()

    def _start_download(self):
        with self._dl_lock:
            if self._dl_thread is not None and self._dl_thread.is_alive():
                return
            self._dl_cancel = threading.Event()
            self._dl_thread = threading.Thread(target=self._dl_work, daemon=True)
            self._dl_thread.start()

    def _dl_work(self):
        last = [-2]
        self._dlEvent.emit({"state": "downloading", "pct": -1.0, "msg": "Starting\u2026"})

        def prog(stage, done, total):
            if stage == "download":
                pct = done / total if total else -1.0
                key = int(pct * 100) if total else -1
                if key != last[0]:
                    last[0] = key
                    self._dlEvent.emit({"state": "downloading", "pct": pct, "msg": f"{done / 1e6:.0f} of {total / 1e6:.0f} MB" if total else f"{done / 1e6:.0f} MB"})
            else:
                self._dlEvent.emit({"state": "downloading", "pct": -1.0, "msg": "Unpacking\u2026" if stage == "unpack" else "Checking it works\u2026"})
        try:
            ffmpeg_fetch.download(prog, self._dl_cancel)
            self._dlEvent.emit({"state": "done", "pct": 1.0, "msg": ""})
        except ffmpeg_fetch.FetchError as e:
            self._dlEvent.emit({"state": "idle" if str(e) == "Cancelled" else "error", "pct": -1.0, "msg": "" if str(e) == "Cancelled" else str(e)})
        except Exception as e:
            log.exception("ffmpeg download")
            self._dlEvent.emit({"state": "error", "pct": -1.0, "msg": f"Couldn't download ffmpeg ({e.__class__.__name__})."})

    def _on_dl(self, info):
        self._dl = info
        self.dlChanged.emit()
        if self._waiting_dl and info["state"] == "downloading":
            pct = info["pct"]
            self._show_toast("Getting ffmpeg ready", info["msg"], "working", pct, "")
        if info["state"] == "done":
            threading.Thread(target=self._detect, daemon=True).start()

    @Slot()
    def _refresh_library(self):
        root = self.config.get("library_root")
        ok = bool(root) and Path(root).is_dir()
        self._status = dict(self._status, libraryOk=ok, libraryFolders=library.top_folders(root) if ok else [])
        self.statusChanged.emit()

    # ------------------------------------------------------------ explorer menu
    def _sync_menu(self):
        if os.name != "nt":
            return
        self._apply_autostart()   # also removes a stale start-with-Windows entry when the opt-in is off
        if not shell.is_installed():
            return
        root = self.config.get("library_root")
        folders = library.top_folders(root) if root and Path(root).is_dir() else []
        try:
            if shell.needs_refresh(self.config.snapshot(), root, folders):
                shell.install(self.config.snapshot(), root, folders)
        except Exception:
            log.exception("menu refresh failed")

    @Slot(result=str)
    def installMenu(self):
        if os.name != "nt":
            return "The right-click menu is only available on Windows."
        root = self.config.get("library_root")
        if self.config.get("menu_mode") == "submenu" and not (root and Path(root).is_dir()):
            return "Choose your library folder first."
        try:
            folders = library.top_folders(root) if root and Path(root).is_dir() else []
            shell.install(self.config.snapshot(), root, folders)
        except Exception as e:
            log.exception("install menu")
            return f"Couldn't update the menu: {e}"
        self._status = dict(self._status, menuInstalled=True)
        self.statusChanged.emit()
        return ""

    @Slot(result=str)
    def removeMenu(self):
        try:
            shell.uninstall()
        except Exception as e:
            return f"Couldn't remove the menu: {e}"
        self._status = dict(self._status, menuInstalled=False)
        self.statusChanged.emit()
        return ""

    @Slot(str, result=str)
    def exportReg(self, folder):
        try:
            d = Path(_local(folder))
            root = self.config.get("library_root")
            ops = shell.plan(self.config.snapshot(), root, library.top_folders(root) if root else [])
            shell.export_reg(ops, d / "tunedock-add-menu.reg")
            shell.export_uninstall_reg(d / "tunedock-remove-menu.reg")
            return str(d)
        except Exception as e:
            return ""

    # ------------------------------------------------------------ naming preview
    @Slot(str, result="QVariantMap")
    def preview(self, tpl):
        ok, text = naming.preview(tpl)
        out = {"ok": ok, "text": text if ok else "", "error": "" if ok else text, "untagged": ""}
        if ok:
            bare = dict(naming.SAMPLE, artist="", album="", albumartist="", track="", year="", title="", disc="", genre="", composer="")
            bare["title"] = "glass harbor final"
            out["untagged"] = naming.render(tpl, bare) or bare["filename"]
        return out

    # ------------------------------------------------------------ window / ipc
    def receive(self, msg: dict):
        """Called from the IPC thread."""
        self._msg.emit(msg)

    def _on_msg(self, msg):
        cmd = msg.get("cmd")
        if cmd == "show":
            self.showWindow()
        elif cmd == "quit":
            QGuiApplication.quit()
        elif cmd == "add":
            paths = [p for p in msg.get("paths", []) if p]
            if msg.get("to"):
                # show something right away, before the short grouping window and the real work begin
                n = len(paths)
                self._show_toast("Adding to " + (Path(msg["to"]).name or msg["to"]),
                                 "Getting started\u2026" if n <= 1 else f"Getting {n} items ready\u2026", "working", -1.0, msg["to"])
                self._pending.append(msg)      # quick adds are grouped over a short window
                self._debounce.start()
            elif paths:
                self.showWindow()              # open at once; the scan batches itself
                self.goto.emit(0)
                self.addPaths(paths)

    def attach_window(self, win):
        self._qwindow = win

    def showWindow(self):
        self._window = True
        self.windowChanged.emit()
        self.raiseWindow.emit()
        for ms in (30, 180, 500):  # Windows can refuse the first attempt; later ones catch up
            QTimer.singleShot(ms, self._focus)

    def _focus(self):
        if self._qwindow is not None and self._window:
            try:
                winutil.force_foreground(int(self._qwindow.winId()))
            except Exception:
                pass

    @Slot()
    def quitApp(self):
        QGuiApplication.quit()

    @Slot(result=str)
    def createShortcut(self):
        return shell.create_start_shortcut()

    @Slot()
    def windowClosed(self):
        self._window = False
        self.windowChanged.emit()
        if self._stage in ("pick", "scanning", "idle"):
            self.clearQueue()
        elif self._stage == "done":    # next time the window opens it should be fresh, not the old result
            self._report = {}
            self.reportChanged.emit()
            self._set_stage("idle")

    def _flush(self):
        pend, self._pending = self._pending, []
        quick = {}
        for m in pend:
            quick.setdefault(m["to"], []).extend(p for p in m.get("paths", []) if p)
        for to, paths in quick.items():
            self._quick(paths, to)

    def _quick(self, paths, to):
        if not Path(to).is_dir():
            self._show_toast("Folder not found", f"{Path(to).name} is gone - refresh the right-click menu on the System page.", "error", 1.0, "")
            return
        self._submit({"quick": True, "paths": paths, "dest": to})

    # ------------------------------------------------------------ add flow (GUI)
    @Slot("QVariantList")
    def addPaths(self, paths):
        paths = [_local(p) for p in paths if p]
        if not paths:
            return
        if self._stage == "done":      # finished screen: start over with the new items
            self._report = {}
            self.reportChanged.emit()
            self._set_stage("idle")
        if self._stage == "running":   # can't interrupt a job; they start the moment it finishes
            self._held.extend(paths)
            return
        for p in paths:
            if p not in self._inputs:
                self._inputs.append(p)
        self._set_stage("scanning")
        self._emit_queue()
        self._scan_timer.start()

    def _emit_queue(self):
        self.queueChanged.emit()

    @Slot()
    def clearQueue(self):
        self._inputs = []
        if self._scan:
            self._scan.cleanup()
        self._scan = None
        self._scan_summary = {"items": 0, "tracks": 0, "albums": 0, "loose": 0, "errors": [], "labels": []}
        self.scanChanged.emit()
        self._set_stage("idle")

    def _set_stage(self, s):
        if s != self._stage:
            self._stage = s
            self.stageChanged.emit()

    def _start_scan(self):
        paths = list(self._inputs)
        old = self._scan

        def work():
            try:
                sc = ingest.scan_inputs(paths)
            except Exception:
                log.exception("scan failed")
                sc = ingest.Scan()
            self._scanDone.emit((paths, sc, old))
        threading.Thread(target=work, daemon=True).start()

    def _on_scan(self, payload):
        paths, sc, old = payload
        if old:
            old.cleanup()
        if paths != self._inputs:  # more files were dropped meanwhile; a newer scan is coming
            sc.cleanup()
            return
        self._scan = sc
        self._scan_summary = sc.summary()
        self.scanChanged.emit()
        self._set_stage("pick")
        self._nav_home()

    # ------------------------------------------------------------ navigation
    def _root(self):
        r = self.config.get("library_root")
        return r if r and Path(r).is_dir() else ""

    @Slot()
    def navHome(self):
        self._nav_home()

    def _nav_home(self):
        root = self._root()
        if not root:
            self._nav = dict(self._nav, ok=False, path="", entries=[], parts=[], loading=False, root="")
            self.navChanged.emit()
            return
        self._nav_to(root)

    @Slot(str)
    def navTo(self, path):
        root = self._root()
        if not root:
            return
        try:
            p = Path(_local(path)).resolve()
            r = Path(root).resolve()
            if p != r and r not in p.parents:
                return
        except OSError:
            return
        self._nav_to(str(p))

    @Slot()
    def navUp(self):
        root = self._root()
        cur = self._nav.get("path")
        if root and cur and Path(cur).resolve() != Path(root).resolve():
            self._nav_to(str(Path(cur).parent))

    def _nav_to(self, path):
        self._nav_token += 1
        token = self._nav_token
        loose = bool(self._scan and self._scan.loose) or not self._scan
        self._nav = dict(self._nav, loading=True, path=path, ok=True, root=self._root())
        self.navChanged.emit()

        def work():
            try:
                entries = library.listing(path)
                decision = library.can_auto(path, loose)
            except Exception:
                log.exception("listing failed")
                entries, decision = [], {"auto": False, "kind": "branch"}
            self._navDone.emit((token, path, entries, decision))
        threading.Thread(target=work, daemon=True).start()

    def _on_nav(self, payload):
        token, path, entries, decision = payload
        if token != self._nav_token:
            return
        root = Path(self._root() or path)
        parts = [{"name": root.name or str(root), "path": str(root)}]
        try:
            for part in Path(path).resolve().relative_to(root.resolve()).parts:
                parts.append({"name": part, "path": str(Path(parts[-1]["path"]) / part)})
        except ValueError:
            pass
        inplace = 0
        if self._scan:
            try:
                here = Path(path).resolve()
                inplace = sum(1 for i in self._scan.items if i.kind in ("file", "dir") and not i.error and i.src.resolve().parent == here)
            except OSError:
                pass
        self._nav = {"path": path, "parts": parts, "entries": entries, "decision": decision, "loading": False,
                     "root": str(root), "ok": True, "name": parts[-1]["name"], "atRoot": len(parts) == 1,
                     "inplace": inplace, "allInplace": bool(self._scan) and inplace == len([i for i in self._scan.items if not i.error]) and inplace > 0}
        self.navChanged.emit()

    @Slot(str, result=str)
    def newFolder(self, name):
        try:
            p = library.make_folder(self._nav["path"], name)
        except (ValueError, OSError) as e:
            return str(e) if isinstance(e, ValueError) else f"Couldn't create it ({e.strerror})"
        self._nav_to(p)
        return ""

    @Slot()
    def chooseHere(self):
        if self._stage == "pick" and self._scan and self._nav.get("path") and self._scan.track_count:
            self._job_id += 1
            self._progress = {"done": 0, "total": self._scan.track_count, "name": "", "state": "", "recent": [],
                              "quick": False, "active": True}
            self.progressChanged.emit()
            self._set_stage("running")
            sc, self._scan = self._scan, None
            self._inputs = []
            self._submit({"quick": False, "scan": sc, "dest": self._nav["path"]})

    # ------------------------------------------------------------ jobs
    def _submit(self, job):
        self._job_id += 1
        job["id"] = self._job_id
        with self._lock:
            self._jobs.append(job)
            if self._alive:
                return
            self._alive = True
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        while True:
            with self._lock:
                if not self._jobs:
                    self._alive = False
                    return
                job = self._jobs.popleft()
            self._run_job(job)

    def _run_job(self, job):
        jid, quick = job["id"], job["quick"]
        emit = lambda e: self._event.emit(dict(e, job=jid, quick=quick))
        emit({"type": "job_start", "dest": job["dest"]})
        scan = job.get("scan")
        rep = None
        try:
            self._await_ffmpeg(emit)
            if scan is None:
                scan = ingest.scan_inputs(job["paths"])
            if scan.track_count == 0:
                errs = [f"{i.src.name}: {i.error}" for i in scan.items if i.error]
                rep = {"converted": 0, "copied": 0, "skipped": 0, "failed": 0, "errors": errs, "notes": [], "bytes_in": 0,
                       "bytes_out": 0, "dest": job["dest"], "cancelled": False, "seconds": 0, "total": 0,
                       "fatal": errs[0] if errs else "No audio files found"}
            else:
                self._cancel = threading.Event()
                self._runner = ingest.Runner(self.config.snapshot(), scan, job["dest"], emit, self._cancel)
                rep = self._runner.run()
        except Exception as e:
            log.error("job crashed\n%s", traceback.format_exc())
            rep = {"converted": 0, "copied": 0, "skipped": 0, "failed": 0, "errors": [], "notes": [], "bytes_in": 0,
                   "bytes_out": 0, "dest": job["dest"], "cancelled": False, "seconds": 0, "total": 0,
                   "fatal": f"Something went wrong ({e.__class__.__name__}). Details are in the log file."}
        finally:
            self._runner = None
            if scan is not None:
                scan.cleanup()
        emit({"type": "job_done", "report": rep})

    def _await_ffmpeg(self, emit):
        """Conversion without ffmpeg can't work: fetch it first (once), if allowed. Runs on the job thread."""
        cfg = self.config.snapshot()
        if cfg["format"] == "keep":
            return
        need = media.FORMATS[cfg["format"]]["enc"]
        ff = media.find_ffmpeg(cfg["ffmpeg_path"], need=need)
        if ff and need in media.available_encoders(ff):
            return
        if not (cfg["ffmpeg_auto"] and self._can_download()):
            return
        self._waiting_dl = True
        emit({"type": "waiting_ffmpeg"})
        self._start_download()
        t = self._dl_thread
        while t is not None and t.is_alive():
            t.join(0.2)
        self._waiting_dl = False

    @Slot()
    def cancel(self):
        r = self._runner
        if r:
            r.cancel_now()

    def _on_event(self, e):
        t, quick = e["type"], e["quick"]
        if t == "job_start":
            if quick:
                self._show_toast(f"Adding to {Path(e['dest']).name}", "Reading files\u2026", "working", -1.0, e["dest"])
            return
        if t == "phase":
            if quick:
                self._show_toast(self._toast["title"], e["text"], "working", -1.0, self._toast["dest"])
            else:
                self._progress = dict(self._progress, name=e["text"])
                self.progressChanged.emit()
            return
        if t == "waiting_ffmpeg":
            if not quick:
                self._progress = dict(self._progress, name="Downloading ffmpeg (one time only)\u2026")
                self.progressChanged.emit()
            return
        if t == "progress":
            pr = dict(self._progress)
            pr.update(done=e["done"], total=e["total"], name=e["name"], state=e["state"], quick=quick, active=True)
            if not quick:
                pr["recent"] = ([{"name": e["name"], "state": e["state"], "msg": e.get("msg", "")}] + pr["recent"])[:6]
                self._progress = pr
                self.progressChanged.emit()
            else:
                self._show_toast(self._toast["title"], f"{e['done']} of {e['total']} \u00b7 {e['name']}", "working",
                                 e["done"] / max(1, e["total"]), self._toast["dest"])
            return
        if t == "job_done":
            rep = describe(e["report"])
            if quick:
                self._toast_timer.stop()
                self._show_toast(rep["title"] + (f" to {rep['destName']}" if rep["kind"] == "ok" and rep["added"] else ""),
                                 rep["sub"] or f"{rep['converted']} converted \u00b7 {rep['copied']} copied" + (f" \u00b7 {rep['skipped']} skipped" if rep["skipped"] else ""),
                                 "done" if rep["kind"] == "ok" else ("error" if rep["kind"] == "error" else "warn"), 1.0, rep["dest"])
                if not self._jobs:
                    self._toast_timer.start(7000 if rep["kind"] != "ok" else 5000)
            else:
                self._progress = dict(self._progress, active=False)
                self.progressChanged.emit()
                if self._held:
                    # more was added while this ran: report this one in the corner card and go straight on
                    held, self._held = self._held, []
                    self._show_toast(rep["title"], rep["sub"] or f"{rep['converted']} converted \u00b7 {rep['copied']} copied",
                                     "done" if rep["kind"] == "ok" else ("error" if rep["kind"] == "error" else "warn"), 1.0, rep["dest"])
                    self._toast_timer.start(6000)
                    self._report = {}
                    self.reportChanged.emit()
                    self._set_stage("idle")
                    self.addPaths(held)
                else:
                    self._report = rep
                    self.reportChanged.emit()
                    self._set_stage("done")

    @Slot()
    def finish(self):
        """Back to the start screen (Add more / Done)."""
        self._report = {}
        self.reportChanged.emit()
        self._set_stage("idle")
        if self._held:
            held, self._held = self._held, []
            self.addPaths(held)

    # ------------------------------------------------------------ toast
    def _show_toast(self, title, sub, state, value, dest):
        # "Notifications" off silences progress and success; warnings and errors always show
        visible = bool(self.config.get("notify")) or state in ("warn", "error")
        self._toast = {"visible": visible, "title": title, "sub": sub, "value": value, "state": state, "dest": dest}
        self.toastChanged.emit()

    def _hide_toast(self):
        if self._jobs or self._runner:
            self._toast_timer.start(2000)
            return
        self._toast = dict(self._toast, visible=False)
        self.toastChanged.emit()

    @Slot()
    def dismissToast(self):
        self._toast_timer.stop()
        self._hide_toast()

    # ------------------------------------------------------------ misc
    @Slot(str)
    def openPath(self, path):
        path = _local(path)
        if not path:
            return
        if os.name == "nt":
            try:
                os.startfile(path)  # noqa
                return
            except OSError:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot(result=bool)
    def busy(self):
        if self.config.get("keep_running"):
            return True   # stay resident: the next right-click opens instantly
        return bool(self._runner or self._jobs or self._pending or self._debounce.isActive() or self._toast["visible"]
                    or self._window or self._stage in ("running", "scanning"))
