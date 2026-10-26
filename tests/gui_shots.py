"""Headless GUI check: loads the real QML, drives the Backend, saves screenshots to /tmp/shots."""
import os, sys, shutil, tempfile, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
tmp = Path(tempfile.mkdtemp(prefix="tdgui_"))
os.environ["TUNEDOCK_HOME"] = str(tmp / "home")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures
from PySide6.QtCore import QEventLoop, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuickControls2 import QQuickStyle

msgs = []
qInstallMessageHandler(lambda m, c, t: msgs.append(t))
QQuickStyle.setStyle("Basic")
app = QGuiApplication(sys.argv[:1])
from tunedock import config
from tunedock.bridge import Backend

lib = tmp / "Music"
for d in ("Rock/Artist X/Album One", "Rock/Artist X/Album Two", "Rock/Artist Y/First", "Jazz/Miles/Kind", "Jazz/Trane/Giant", "Classical", "Podcasts"):
    (lib / d).mkdir(parents=True)
src = fixtures.make_library(tmp / "src" / "Music")
import random
random.seed(3)
for n in ("Alt Rock","Ambient","Blues","Country","Electronic","Folk","Hip Hop","Indie","Jazz Standards","Metal","Pop","Soul"):
    for a in range(random.choice([0,1,2,3,5,9,14])): (lib / "Genres" / n / f"Artist {a}").mkdir(parents=True)
for i in range(110): (lib / "Huge" / f"Artist {i:03d}").mkdir(parents=True)
cfgp = config.Config(); cfgp.set("library_root", str(lib)); cfgp.set("auto_descend", True); cfgp.set("onboarded", True)
backend = Backend(cfgp)
qmlRegisterSingletonInstance(Backend, "Td", 1, 0, "Backend", backend)
engine = QQmlApplicationEngine()
engine.load(str(Path(__file__).resolve().parent.parent / "tunedock/qml/main.qml"))
roots = engine.rootObjects()
if not roots:
    print("QML FAILED TO LOAD"); print("\n".join(msgs)); sys.exit(1)
win = roots[0]

def pump(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

out = Path("/tmp/shots"); shutil.rmtree(out, ignore_errors=True); out.mkdir()
def shot(name, wait=500):
    pump(wait); win.grabWindow().save(str(out / f"{name}.png")); print("shot", name)

backend.showWindow(); pump(300)
shot("1_idle")
which = sys.argv[1] if len(sys.argv) > 1 else "all"
backend.addPaths([str(src / "Artist A"), str(src / "Artist B")]); shot("2_pick_root", 1800)
backend.navTo(str(lib / "Rock")); shot("3_pick_rock", 900)
backend.setCfg("auto_descend", False)
backend.navTo(str(lib / "Genres")); shot("3b_collage", 1600)
backend.navTo(str(lib / "Huge")); shot("3c_list_fallback", 1200)
backend.setCfg("auto_descend", True)
backend.navTo(str(lib / "Rock")); pump(300)
backend.navTo(str(lib / "Rock/Artist X")); shot("4_pick_artist_auto_countdown", 900)
win.setProperty("page", 2); shot("6_convert", 700)
win.setProperty("page", 1); shot("7_library", 700)
win.setProperty("page", 3); shot("8_names", 700)
win.setProperty("page", 4); shot("9a_system", 700)
win.setProperty("page", 5); shot("9_style", 700)
win.setProperty("page", 0)
backend.setCfg("theme_mode", "dark"); shot("10_dark_style_pick", 900)
backend.setCfg("theme_mode", "light")
backend.navTo(str(lib / "Rock/Artist X/Album One")); 
pump(2500)  # countdown -> auto save
shot("11_running_or_done", 300)
pump(6000); shot("12_done", 600)
backend.setCfg("onboarded", False); shot("13_onboarding", 900)
backend._on_nav  # noqa
print("stage:", backend.stage, backend.report.get("title"), backend.report.get("converted"), backend.report.get("failed"))
print("files in lib:", sorted(str(p.relative_to(lib)) for p in lib.rglob("*.opus")))
print("QT MESSAGES:"); print("\n".join(sorted(set(msgs))[:40]))
shutil.rmtree(tmp, ignore_errors=True)
