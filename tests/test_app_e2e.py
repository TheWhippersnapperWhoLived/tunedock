"""Launch the real app (headless) the way Explorer would: one process per selected file + a quick-add folder."""
import os, subprocess, sys, tempfile, time, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures
root = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="tde2e_"))
env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", TUNEDOCK_HOME=str(tmp / "home"))
import json
(tmp / "home").mkdir(); (tmp / "home" / "config.json").write_text(json.dumps({"keep_running": False, "onboarded": True}))
src = fixtures.make_library(tmp / "src" / "Music")
dest = tmp / "Music" / "Rock"; dest.mkdir(parents=True)
files = [src / "Artist A/Album 1/01 - Song One.flac", src / "Artist A/Album 1/02 Song Two.flac", src / "Artist B/Single.m4a"]
t0 = time.time()
procs = [subprocess.Popen([sys.executable, str(root / "launch_tunedock.pyw"), "--add", str(f), "--to", str(dest)], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for f in files]
# a folder too, as a separate "right-click" a moment later
time.sleep(0.4)
procs.append(subprocess.Popen([sys.executable, str(root / "launch_tunedock.pyw"), "--add", str(src / "Artist D"), "--to", str(dest)], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
outs = []
for p in procs:
    try:
        o, _ = p.communicate(timeout=90); outs.append((p.returncode, o.decode(errors="replace")))
    except subprocess.TimeoutExpired:
        p.kill(); outs.append(("timeout", ""))
print("elapsed %.1fs" % (time.time() - t0), "exit codes:", [c for c, _ in outs])
found = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
print("\n".join(found))
want = 3 + 2  # three loose tracks + opus_src copy + noart.mp3 in Artist D
ok = sum(1 for f in found if f.endswith((".opus"))) >= want and all(c == 0 for c, _ in outs) and not [f for f in found if ".tdpart" in f]
log = (tmp / "home" / "tunedock.log")
print("log tail:", log.read_text()[-400:] if log.exists() else "(none)")
print("E2E", "PASS" if ok else "FAIL")

# ---- scenario 2: resident background mode. First right-click is cold, later ones are handed to the running copy.
print("\nbackground mode")
sys.path.insert(0, str(root))
from tunedock import ipc
(tmp / "home" / "config.json").write_text(json.dumps({"keep_running": True, "onboarded": True}))
env["TUNEDOCK_HOME"] = os.environ["TUNEDOCK_HOME"] = str(tmp / "home")   # this process's ipc.send must reach the test copy too
dest2 = tmp / "Music" / "Jazz"; dest2.mkdir(parents=True)
daemon = subprocess.Popen([sys.executable, str(root / "launch_tunedock.pyw"), "--background"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
t0 = time.time(); ready = False
while time.time() - t0 < 60:
    if ipc.send({"cmd": "idle"}): ready = True; break
    time.sleep(0.1)
print("daemon ready after %.1fs" % (time.time() - t0), ready)
t1 = time.time()
fwd = subprocess.run([sys.executable, str(root / "launch_tunedock.pyw"), "--add", str(src / "Artist B/Single.m4a"), "--to", str(dest2)], env=env, timeout=30)
fwd_time = time.time() - t1
t2 = time.time()
while time.time() - t2 < 30 and not list(dest2.glob("*.opus")): time.sleep(0.1)
print("forwarder exited in %.2fs (code %s); file appeared %.1fs later" % (fwd_time, fwd.returncode, time.time() - t2))
time.sleep(4)
print("daemon still resident after the job:", daemon.poll() is None)
subprocess.run([sys.executable, str(root / "launch_tunedock.pyw"), "--quit"], env=env, timeout=30)
try: daemon.wait(timeout=15); quit_ok = True
except subprocess.TimeoutExpired: daemon.kill(); quit_ok = False
print("--quit closed it:", quit_ok)
ok2 = ready and fwd.returncode == 0 and fwd_time < 1.5 and bool(list(dest2.glob("*.opus"))) and daemon.returncode is not None and quit_ok
print("E2E background", "PASS" if ok2 else "FAIL")
shutil.rmtree(tmp, ignore_errors=True); sys.exit(0 if (ok and ok2) else 1)
