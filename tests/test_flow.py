"""Regression tests for the add flow: not getting stuck on the finished screen, held adds, instant auto-save."""
import os, sys, shutil, tempfile
from pathlib import Path
os.environ.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Basic")
tmp = Path(tempfile.mkdtemp(prefix="tdflow_")); os.environ["TUNEDOCK_HOME"] = str(tmp / "home")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuickControls2 import QQuickStyle
QQuickStyle.setStyle("Basic"); app = QGuiApplication(sys.argv[:1])
from tunedock import config
from tunedock.bridge import Backend

ok = fail = 0
def check(n, c, x=""):
    global ok, fail
    ok += bool(c); fail += (not c); print("  ok  " if c else "  FAIL", n, "" if c else x)
def pump(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()
def wait_for(pred, ms=15000):
    t = 0
    while t < ms and not pred(): pump(100); t += 100
    return pred()

lib = tmp / "Music"
for d in ("Rock/Artist X/Album One", "Classical", "Empty Leaf"): (lib / d).mkdir(parents=True)
src = fixtures.make_library(tmp / "src" / "Music")
c = config.Config(); c.set("library_root", str(lib)); c.set("auto_descend", False)
b = Backend(c); qmlRegisterSingletonInstance(Backend, "Td", 1, 0, "Backend", b)
e = QQmlApplicationEngine(); e.load(str(Path(__file__).resolve().parent.parent / "tunedock/qml/main.qml"))
b.showWindow(); pump(400)

print("1) a finished add must not trap the next one")
b.addPaths([str(src / "Artist B")]); check("scanned", wait_for(lambda: b.stage == "pick"))
b.navTo(str(lib / "Classical")); wait_for(lambda: not b.nav["loading"] and b.nav["path"].endswith("Classical"))
b.chooseHere(); check("first job reaches the done screen", wait_for(lambda: b.stage == "done"), b.stage)
b.addPaths([str(src / "Artist A")])
check("new items leave the done screen", wait_for(lambda: b.stage in ("scanning", "pick")), b.stage)
check("old result cleared", not b.report)
check("new scan shows the new items", wait_for(lambda: b.scan["tracks"] == 2), b.scan)

print("2) closing the window on a finished screen resets it")
b.navTo(str(lib / "Classical")); wait_for(lambda: not b.nav["loading"]); b.chooseHere(); wait_for(lambda: b.stage == "done")
b.windowClosed(); check("reset after close", b.stage == "idle" and not b.report)
b.showWindow(); b.addPaths([str(src / "Artist B")]); check("fresh add after reopen", wait_for(lambda: b.stage == "pick"))
b.clearQueue()

print("3) adds that arrive during a running job start right after it")
b._stage = "running"; b.stageChanged.emit()
b.addPaths([str(src / "Artist B")]); check("held while running", b._held != [] and b.stage == "running")
rep = {"converted": 1, "copied": 0, "skipped": 0, "failed": 0, "errors": [], "notes": [], "bytes_in": 1, "bytes_out": 1,
       "dest": str(lib), "cancelled": False, "seconds": 1, "total": 1, "fatal": ""}
b._on_event({"type": "job_done", "quick": False, "job": 1, "report": rep})
check("held items started a new add (no stuck done screen)", wait_for(lambda: b.stage in ("scanning", "pick")) and not b._held, b.stage)
check("previous result reported in the corner card", b.toast["visible"] and "Added" in b.toast["title"], b.toast)
b.clearQueue()

print("4) instant auto-save (delay 0)")
c.set("auto_descend", True); b.setCfg("auto_delay_ms", 0); check("0 is accepted", c.get("auto_delay_ms") == 0)
b.addPaths([str(src / "Artist B")]); wait_for(lambda: b.stage == "pick")
b.navTo(str(lib / "Empty Leaf"))
check("saves by itself, no click", wait_for(lambda: b.stage in ("running", "done"), 6000), b.stage)
wait_for(lambda: b.stage == "done")
check("file landed in the leaf folder", any((lib / "Empty Leaf").rglob("*.opus")), list((lib / "Empty Leaf").rglob("*")))
b.finish()

print("5) a normal delay still waits")
b.setCfg("auto_delay_ms", 1500)
b.addPaths([str(src / "Artist B")]); wait_for(lambda: b.stage == "pick"); pump(300)
b.navTo(str(lib / "Classical" / "..")); b.navTo(str(lib / "Rock" / "Artist X" / "Album One"))
wait_for(lambda: not b.nav["loading"]); pump(400)
check("still on the picker before the delay is up", b.stage == "pick", b.stage)
check("then saves", wait_for(lambda: b.stage in ("running", "done"), 6000))
wait_for(lambda: b.stage == "done")

print("6) music already in the folder it is added to is reprocessed in place")
shutil.copytree(src / "Artist A", lib / "Rock" / "Artist A")
c.set("auto_descend", False); b.finish(); b.clearQueue()
b.addPaths([str(lib / "Rock" / "Artist A")]); wait_for(lambda: b.stage == "pick")
b.navTo(str(lib / "Rock")); wait_for(lambda: not b.nav["loading"] and b.nav["path"].endswith("Rock"))
check("picker knows everything is already there", b.nav["allInplace"] is True and b.nav["inplace"] == 1, b.nav)
b.navTo(str(lib / "Classical")); wait_for(lambda: not b.nav["loading"] and b.nav["path"].endswith("Classical"))
check("elsewhere it is a normal add", b.nav["allInplace"] is False)
b.navTo(str(lib / "Rock")); wait_for(lambda: not b.nav["loading"] and b.nav["path"].endswith("Rock"))
b.chooseHere(); wait_for(lambda: b.stage == "done")
check("reported as reprocessed", b.report["title"].startswith("Reprocessed") and b.report["replaced"] == 2, b.report)
names = sorted(p.name for p in (lib / "Rock" / "Artist A").rglob("*.opus"))
check("same folder, files replaced (no second copy)", len(names) == 2 and not (lib / "Rock" / "Artist A (2)").exists() and not list((lib / "Rock" / "Artist A").rglob("*.flac")), names)
b.finish()

print("7) branched (no-window) adds show progress, phases and the result")
e.load(str(Path(__file__).resolve().parent.parent / "tunedock/qml/components/Toast.qml"))
b.windowClosed(); pump(200)
qdest = lib / "Jazz"; qdest.mkdir(exist_ok=True)
qsrc = tmp / "quick_src"; shutil.copytree(src / "Artist B", qsrc)
c.set("after", "delete"); seen = []
b.toastChanged.connect(lambda: seen.append((b.toast["state"], b.toast["title"], b.toast["sub"], b.toast["visible"])))
b.receive({"cmd": "add", "paths": [str(qsrc)], "to": str(qdest)})
check("indicator appears instantly, before any work", wait_for(lambda: len(seen) > 0, 1000) and seen[0][0] == "working" and "Jazz" in seen[0][1], seen[:1])
check("finishes with a result card", wait_for(lambda: seen and seen[-1][0] == "done", 20000), seen[-1:])
subs = " | ".join(x[2] for x in seen)
check("shows converting progress", "1 of 1" in subs, subs)
check("shows the moving/cleanup phase", "Deleting the originals" in subs, subs)
check("result names the destination", "Added 1 track to Jazz" in seen[-1][1], seen[-1])
check("original really gone and file in place", not qsrc.exists() and any(qdest.rglob("*.opus")))
tw = [w for w in app.allWindows() if w.width() == 400 and w.height() == 124]
check("corner card is its own window, shown while the main window is closed", bool(tw) and tw[0].isVisible() and not b.windowVisible, (len(tw), b.windowVisible))
c.set("notify", False); seen.clear()
b._show_toast("x", "y", "working", 0.5, ""); check("notifications off: progress stays quiet", seen and seen[-1][3] is False)
b._show_toast("x", "boom", "error", 1.0, ""); check("notifications off: errors still show", seen[-1][3] is True)
c.set("notify", True); c.set("after", "keep")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
