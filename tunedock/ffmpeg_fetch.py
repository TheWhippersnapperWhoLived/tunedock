"""Download a static ffmpeg build (Windows) into Tunedock's own folder. Only used when conversion needs ffmpeg.

Run directly (`python -m tunedock.ffmpeg_fetch --check|--download`) it prints progress for the setup script.
Set TUNEDOCK_FFMPEG_URL to use a different archive (a mirror, or for testing).
"""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from .winutil import hidden_kwargs

SOURCES = [
    {"name": "gyan.dev", "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
     "sha256_url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"},
    {"name": "BtbN (GitHub)", "url": "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
     "sha256_url": None},
]


class FetchError(Exception):
    pass


def target_path() -> Path:
    from .config import data_dir
    return data_dir() / "ffmpeg" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")


def sources():
    env = os.environ.get("TUNEDOCK_FFMPEG_URL")
    if env:
        return [{"name": "custom", "url": env, "sha256_url": env + ".sha256"}]
    return SOURCES


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Tunedock/1.0 (+ffmpeg fetch)"})
    return urllib.request.urlopen(req, timeout=timeout)


def _expected_hash(url):
    if not url:
        return None
    try:
        with _get(url, 15) as r:
            m = re.search(r"\b([0-9a-fA-F]{64})\b", r.read(4096).decode("ascii", "ignore"))
            return m.group(1).lower() if m else None
    except Exception:
        return None


def _download(url, out: Path, progress, cancel):
    h = hashlib.sha256()
    with _get(url) as r, open(out, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise FetchError("Cancelled")
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            progress("download", done, total)
    return h.hexdigest()


def _extract_binary(archive: Path, out: Path):
    """Pull just bin/ffmpeg(.exe) out of the archive."""
    names = ("ffmpeg.exe", "ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".new")
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as z:
                for i in z.infolist():
                    parts = i.filename.replace("\\", "/").split("/")
                    if not i.is_dir() and parts[-1].lower() in names and (len(parts) == 1 or parts[-2].lower() == "bin"):
                        with z.open(i) as src, open(tmp, "wb") as dst:
                            shutil.copyfileobj(src, dst, 1 << 20)
                        break
                else:
                    raise FetchError("ffmpeg wasn't inside the download")
        else:
            with tarfile.open(archive, "r:*") as t:
                for m in t:
                    parts = m.name.split("/")
                    if m.isfile() and parts[-1].lower() in names and (len(parts) == 1 or parts[-2].lower() == "bin"):
                        with t.extractfile(m) as src, open(tmp, "wb") as dst:
                            shutil.copyfileobj(src, dst, 1 << 20)
                        break
                else:
                    raise FetchError("ffmpeg wasn't inside the download")
        if os.name != "nt":
            tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, out)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _verify(path: Path, need=("libopus",)):
    try:
        v = subprocess.run([str(path), "-version"], capture_output=True, timeout=30, stdin=subprocess.DEVNULL, **hidden_kwargs())
        if v.returncode != 0:
            raise FetchError("The downloaded ffmpeg doesn't run on this PC")
        enc = subprocess.run([str(path), "-hide_banner", "-encoders"], capture_output=True, timeout=30,
                             stdin=subprocess.DEVNULL, **hidden_kwargs()).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as e:
        raise FetchError(f"The downloaded ffmpeg doesn't run ({e.__class__.__name__})")
    for n in need:
        if n not in enc:
            raise FetchError(f"This ffmpeg build can't encode {n.replace('lib', '')}")


def download(progress=None, cancel: threading.Event = None) -> Path:
    """-> path of the installed ffmpeg. progress(stage, done, total): stage is download | unpack | check."""
    progress = progress or (lambda *a: None)
    out = target_path()
    errors = []
    for src in sources():
        tmpdir = Path(tempfile.mkdtemp(prefix="tunedock_ff_"))
        try:
            archive = tmpdir / "ffmpeg.archive"
            got = _download(src["url"], archive, progress, cancel)
            want = _expected_hash(src.get("sha256_url"))
            if want and want != got:
                raise FetchError("The download was corrupted (checksum didn't match)")
            progress("unpack", 0, 0)
            _extract_binary(archive, out)
            progress("check", 0, 0)
            _verify(out)
            return out
        except FetchError as e:
            if str(e) == "Cancelled":
                raise
            errors.append(f"{src['name']}: {e}")
        except Exception as e:
            errors.append(f"{src['name']}: {e.__class__.__name__}: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    try:
        out.unlink()
    except OSError:
        pass
    raise FetchError("Couldn't download ffmpeg. " + "; ".join(errors) + ". Check your internet connection, or install it yourself (winget install Gyan.FFmpeg).")


def _cli():
    from . import media
    if "--check" in sys.argv:
        p = media.find_ffmpeg("", need="libopus")
        print(p if p else "")
        return 0 if p else 1
    last = [-1]

    def prog(stage, done, total):
        if stage == "download" and total:
            pct = int(done * 100 / total)
            if pct != last[0]:
                last[0] = pct
                filled = pct // 4
                print("\r    [%s%s] %3d%%  %.0f / %.0f MB" % ("#" * filled, "." * (25 - filled), pct, done / 1e6, total / 1e6), end="", flush=True)
        elif stage != "download":
            print("\r    %-60s" % {"unpack": "Unpacking...", "check": "Checking it works..."}[stage], end="", flush=True)
    try:
        path = download(prog)
    except FetchError as e:
        print("\n    " + str(e))
        return 1
    print("\r    Installed: %s%s" % (path, " " * 20))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
