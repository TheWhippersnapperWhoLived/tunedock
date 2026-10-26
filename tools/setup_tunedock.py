"""Steps 3-7 of setup.bat. Runs inside the private environment. Shows what it is doing, how long it has taken,
and never fails silently: everything is also written to setup.log."""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LOG = ROOT / "setup.log"
TOTAL = 7
IS_WIN = os.name == "nt"
EXE_NAME = "Tunedock.exe" if IS_WIN else "Tunedock"
# Not "Tunedock": Windows ignores letter case, so that would be the same folder as the tunedock\ source package.
APP_DIR = ROOT / "app"
T0 = time.time()


# ------------------------------------------------------------------ console look
def _enable_vt():
    if IS_WIN:
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                return bool(k.SetConsoleMode(h, mode.value | 0x0004))
        except Exception:
            return False
        return False
    return True


TTY = sys.stdout.isatty()
USE_COLOR = TTY and not os.environ.get("NO_COLOR") and _enable_vt()


def c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def head(n, text):
    print("\n" + c("1;36", f"[{n}/{TOTAL}]") + " " + c("1", text))


def ok(text):
    print("   " + c("32", "[ OK ]") + " " + text)


def warn(text):
    print("   " + c("33", "[ !! ]") + " " + text)


def bad(text):
    print("   " + c("31", "[ XX ]") + " " + text)


def info(text):
    print("          " + c("90", text))


def mmss(sec):
    return "%d:%02d" % divmod(int(sec), 60)


def log(text):
    with open(LOG, "a", encoding="utf-8", errors="replace") as f:
        f.write(text if text.endswith("\n") else text + "\n")


class Failed(Exception):
    pass


def run(cmd, label, cwd=ROOT, env=None, hint=""):
    """Run a command with a live 'still working' line (spinner, elapsed time, latest output). Returns (rc, lines)."""
    log("\n$ " + " ".join(str(x) for x in cmd))
    start = time.time()
    proc = subprocess.Popen([str(x) for x in cmd], cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    lines, last = [], [""]

    def reader():
        for line in proc.stdout:
            lines.append(line)
            log(line.rstrip("\n"))
            if line.strip():
                last[0] = line.strip()
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    spin, i, next_note = "|/-\\", 0, 20
    while proc.poll() is None:
        el = time.time() - start
        if TTY:
            width = max(40, shutil.get_terminal_size((100, 20)).columns - 1)
            line = "   %s %s  %s  %s" % (spin[i % 4], label, mmss(el), ("- " + last[0]) if last[0] else (hint or ""))
            print("\r" + line[:width].ljust(width), end="", flush=True)
        elif el > next_note:
            print("   ... still working (%s)" % mmss(el), flush=True)
            next_note += 20
        i += 1
        time.sleep(0.15)
    t.join(2)
    if TTY:
        print("\r" + " " * (shutil.get_terminal_size((100, 20)).columns - 1) + "\r", end="")
    return proc.returncode, lines


def fail(msg, lines=None):
    bad(msg)
    if lines:
        print()
        for l in [x.rstrip() for x in lines if x.strip()][-14:]:
            print("          " + l)
    print()
    print("   Full details: " + str(LOG))
    raise Failed(msg)


# ------------------------------------------------------------------ steps
def quit_running(exe):
    """A running copy keeps its files locked."""
    try:
        subprocess.run([str(exe), "--quit"], timeout=20, capture_output=True, stdin=subprocess.DEVNULL)
        time.sleep(1.5)
    except (OSError, subprocess.SubprocessError):
        pass


def check_source():
    """Older setups built the exe into Tunedock\\, which on Windows is the same folder as the tunedock\\ source package,
    and replaced the code with the exe. Undo that, or stop with clear instructions if the code is gone."""
    pkg = next((p for p in ROOT.iterdir() if p.is_dir() and p.name.lower() == "tunedock"), None)
    if pkg is None or not (pkg / "__init__.py").is_file():
        bad("Tunedock's code (the tunedock folder) is missing from %s." % ROOT)
        info("An older version of this setup removed it by mistake when it built the exe.")
        info("Extract the zip into this same folder again (choose to replace the files), then run setup.bat again.")
        raise Failed("source missing")
    old_exe = pkg / EXE_NAME
    leftovers = [p for p in (old_exe, pkg / "_internal") if p.exists()]
    if leftovers:
        quit_running(old_exe)
        try:
            for p in leftovers:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError as e:
            fail("Couldn't remove the old Tunedock.exe from the code folder (%s). Close Tunedock (tray icon, Quit) "
                 "and run setup.bat again." % e.__class__.__name__)
        ok("removed an old Tunedock.exe that an earlier setup put inside the code folder")
    if pkg.name != "tunedock":  # Python imports are case-sensitive even on Windows: "Tunedock" can't be imported as tunedock
        tmp = ROOT / "tunedock.renaming"
        pkg.rename(tmp)
        tmp.rename(ROOT / "tunedock")
    stale = ROOT / "tunedock.pyw"  # the old launcher name, which clashes with the package
    if stale.exists():
        stale.unlink()


def step_packages(skip):
    head(3, "Installing the components Tunedock is built from")
    if skip:
        ok("skipped")
        return
    info("First time this downloads about 300 MB, so it can take a few minutes.")
    py = sys.executable
    rc, lines = run([py, "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"], "Updating the installer")
    if rc != 0:
        warn("couldn't update pip, carrying on with the current one")
    core = ["PySide6-Essentials>=6.7", "mutagen>=1.47", "pyinstaller>=6.0"]
    rc, lines = run([py, "-m", "pip", "install", "--disable-pip-version-check", *core], "Installing interface, tag and build tools")
    if rc != 0:
        fail("Couldn't install the required components. Check your internet connection and run setup.bat again.", lines)
    ok("interface (PySide6), tag library (mutagen), exe builder (PyInstaller)")
    rc, lines = run([py, "-m", "pip", "install", "--disable-pip-version-check", "py7zr>=0.21"], "Installing optional .7z support")
    if rc == 0:
        ok(".7z archive support")
    else:
        warn(".7z support couldn't be installed (optional). Install 7-Zip if you need .7z or .rar files.")


def step_ffmpeg(skip):
    head(4, "Checking ffmpeg (needed to convert music)")
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8="1")
    rc = subprocess.run([sys.executable, "-m", "tunedock.ffmpeg_fetch", "--check"], cwd=ROOT, env=env,
                        capture_output=True, text=True)
    found = rc.stdout.strip()
    if rc.returncode == 0 and found:
        ok("ffmpeg found: " + found)
        return found
    bad("ffmpeg not found")
    if skip:
        warn("download skipped. Tunedock can fetch it later (Convert page) if you convert music.")
        return ""
    info("Converting music needs it, so it is being downloaded now (one time, about 80 MB).")
    print()
    code = subprocess.call([sys.executable, "-m", "tunedock.ffmpeg_fetch"], cwd=ROOT, env=env)
    print()
    if code == 0:
        ok("ffmpeg downloaded and checked")
        return "ok"
    warn("couldn't download ffmpeg. Setup continues; Tunedock will offer to download it when you convert.")
    return ""


def newest_source():
    newest = 0.0
    for base in (ROOT / "tunedock", ROOT / "assets"):
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                newest = max(newest, p.stat().st_mtime)
    return max(newest, (ROOT / "launch_tunedock.pyw").stat().st_mtime)


def step_build(force):
    head(5, "Building %s" % EXE_NAME)
    target_dir = APP_DIR
    exe = target_dir / EXE_NAME
    if exe.exists() and not force and exe.stat().st_mtime >= newest_source():
        ok("already built and up to date: " + str(exe))
        return exe
    if exe.exists():
        quit_running(exe)
    build = ROOT / "_build"
    shutil.rmtree(build, ignore_errors=True)
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "INFO",
           "--name", "Tunedock", "--distpath", build / "dist", "--workpath", build / "work", "--specpath", build,
           "--add-data", f"{ROOT / 'tunedock' / 'qml'}{sep}tunedock/qml", "--add-data", f"{ROOT / 'assets'}{sep}assets"]
    if IS_WIN:
        cmd += ["--windowed", "--icon", ROOT / "assets" / "tunedock.ico"]
    cmd.append(ROOT / "launch_tunedock.pyw")
    info("Packing Python, the interface and its libraries into one folder. Usually 1 to 4 minutes.")
    rc, lines = run(cmd, "Building", hint="starting")
    built = build / "dist" / "Tunedock" / EXE_NAME
    if rc != 0 or not built.exists():
        warn("the .exe couldn't be built (details in setup.log). Using a launcher shortcut instead.")
        for l in [x.rstrip() for x in lines if x.strip()][-6:]:
            info(l)
        shutil.rmtree(build, ignore_errors=True)
        return None
    if (target_dir / "__init__.py").exists():  # never replace source code with the build
        shutil.rmtree(build, ignore_errors=True)
        fail("%s looks like source code, not an old build, so it was left alone." % target_dir)
    try:
        shutil.rmtree(target_dir, ignore_errors=False) if target_dir.exists() else None
        shutil.copytree(build / "dist" / "Tunedock", target_dir)
    except OSError as e:
        shutil.rmtree(build, ignore_errors=True)
        fail("Couldn't replace the old Tunedock folder (%s). Close Tunedock (tray icon, Quit) and run setup.bat again." % e.__class__.__name__)
    shutil.rmtree(build, ignore_errors=True)
    size = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file()) / 1e6
    ok("created %s (%.0f MB, runs without Python)" % (exe, size))
    return exe


def make_lnk(lnk, target, args, workdir, icon):
    """Create a .lnk with PowerShell, hidden. Returns '' or an error text."""
    q = lambda t: str(t).replace("'", "''")
    Path(lnk).parent.mkdir(parents=True, exist_ok=True)
    cmd = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.Arguments='%s'; "
           "$s.WorkingDirectory='%s'; $s.IconLocation='%s'; $s.Description='Tunedock'; $s.Save()") % (
        q(lnk), q(target), q(args), q(workdir), q(icon))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return e.__class__.__name__
    return "" if r.returncode == 0 and Path(lnk).exists() else ((r.stderr or r.stdout).strip().splitlines() or ["failed"])[-1]


def step_shortcuts(exe):
    head(6, "Creating shortcuts")
    if not IS_WIN:
        warn("shortcuts are only made on Windows")
        return
    ico = ROOT / "assets" / "tunedock.ico"
    if exe:
        target, args, icon, wd = str(exe), "", str(exe) + ",0", str(exe.parent)
    else:  # fallback: a shortcut that starts the app with no console window
        pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
        target, args, icon, wd = str(pyw), '"%s"' % (ROOT / "launch_tunedock.pyw"), str(ico), str(ROOT)
    start = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Tunedock.lnk"
    for lnk, label in ((start, "the Start menu"), (ROOT / "Tunedock.lnk", "this folder")):
        err = make_lnk(lnk, target, args, wd, icon)
        (ok if not err else warn)(("Tunedock in %s" % label) if not err else "%s: %s" % (label, err))
    info("Right-click the Tunedock icon in the taskbar later to pin it.")


def step_finish(exe, ff, launch):
    head(7, "Finishing")
    print()
    print("  " + c("1;32", "=" * 58))
    print("    " + c("1;32", "Tunedock is ready") + "  (setup took %s)" % mmss(time.time() - T0))
    print("  " + c("1;32", "=" * 58))
    if exe:
        print("    Program     " + str(exe))
    else:
        print("    Program     Tunedock.lnk (launcher shortcut)")
    print("    ffmpeg      " + ("ready" if ff else "not installed yet (Tunedock will offer to download it)"))
    print("    Log         " + str(LOG))
    print()
    if launch:
        print("    Next: Tunedock opens now. The first time, it asks for your music")
        print("    folder, then offers to add \"Add to music library\" to the right-click menu.")
    print("    (If a Windows SmartScreen box appears: More info > Run anyway.")
    print("     The program is unsigned because it was just built on your PC.)")
    print()
    if launch:
        try:
            if exe and IS_WIN:
                os.startfile(str(exe))  # noqa
            elif IS_WIN:
                os.startfile(str(ROOT / "Tunedock.lnk"))  # noqa
        except OSError:
            warn("couldn't open it automatically. Use the Tunedock shortcut.")
    elif exe and IS_WIN:
        # A quiet start points the right-click menu and start-with-Windows entries at this exe, then exits by itself
        # (or stays in the notification area if "Stay ready in the background" is on).
        try:
            subprocess.Popen([str(exe), "--background"], cwd=str(exe.parent), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-packages", action="store_true")
    ap.add_argument("--skip-ffmpeg", action="store_true")
    ap.add_argument("--force-build", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--build-only", action="store_true", help="install packages and build app/Tunedock.exe, nothing else (used by the release workflow)")
    a = ap.parse_args()
    LOG.write_text("Tunedock setup %s\nPython %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0], sys.executable), encoding="utf-8")
    try:
        check_source()
        if a.build_only:
            step_packages(a.skip_packages)
            return 0 if step_build(True) else 1
        step_packages(a.skip_packages)
        ff = step_ffmpeg(a.skip_ffmpeg)
        exe = step_build(a.force_build)
        step_shortcuts(exe)
        step_finish(exe, ff, not a.no_launch)
        return 0
    except Failed:
        return 1
    except KeyboardInterrupt:
        print("\n   Setup was cancelled. Run setup.bat again to continue.")
        return 1
    except Exception as e:  # never leave the user with a bare traceback
        bad("Unexpected problem: %s: %s" % (e.__class__.__name__, e))
        import traceback
        log(traceback.format_exc())
        print("   Full details: " + str(LOG))
        return 1


if __name__ == "__main__":
    sys.exit(main())
