"""Settings: one JSON file, validated on every change, written atomically."""
import copy
import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    """Bulky per-user data (downloaded ffmpeg). Kept out of the roaming settings folder."""
    if os.environ.get("TUNEDOCK_DATA"):
        p = Path(os.environ["TUNEDOCK_DATA"])
    elif os.environ.get("TUNEDOCK_HOME"):
        p = Path(os.environ["TUNEDOCK_HOME"]) / "data"
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME.lower()
    p.mkdir(parents=True, exist_ok=True)
    return p


def home() -> Path:
    env = os.environ.get("TUNEDOCK_HOME")
    if env:
        p = Path(env)
    elif os.name == "nt":
        p = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    else:
        p = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_NAME.lower()
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = {
    "library_root": "",
    "ffmpeg_path": "",
    # conversion
    "format": "opus",            # opus | mp3 | aac | vorbis | flac | keep
    "br_opus": 128, "br_mp3": 192, "br_aac": 192, "br_vorbis": 160,
    "opus_vbr": True,
    "mp3_vbr": False, "mp3_vq": 2,
    "channels": 0,               # 0 = keep, 1 = mono, 2 = stereo
    "sample_rate": 0,            # 0 = keep
    "copy_if_fit": True,         # already in target codec and not above target bitrate -> copy
    "lossy_policy": "convert",   # convert | keep  (what to do with lossy files in another codec)
    "replaygain": "off",         # off | track | album (track + album)
    "embed_art": True,
    "folder_art": True,
    "art_max_px": 0,             # 0 = original size
    # naming
    "file_template": "{artist} - {title}",
    "folder_rename": False,
    "folder_template": "{albumartist|artist} - {album}[ ({year})]",
    "copy_others": True,
    "on_conflict": "rename",     # rename | skip   (files are never overwritten)
    "threads": 0,                # 0 = auto
    # behaviour
    "auto_descend": True,
    "auto_delay_ms": 1600,
    "menu_mode": "single",       # single | submenu
    "menu_folders": [],          # empty = all top-level folders
    "notify": True,
    "keep_running": False,       # opt-in: stay running quietly (tray icon) so adding is instant
    "autostart": False,          # opt-in: start with Windows (needs keep_running)
    "ffmpeg_auto": True,         # download ffmpeg by itself, but only when conversion needs it
    "view_mode": "auto",         # auto = collage when it fits | list
    "onboarded": False,
    "after": "keep",             # keep | recycle
    # look
    "theme_mode": "system",      # system | light | dark
    "seed": "#6750A4",           # hex or "system"
    "reduce_motion": False,
}

_CHOICES = {
    "format": ("opus", "mp3", "aac", "vorbis", "flac", "keep"),
    "lossy_policy": ("convert", "keep"),
    "on_conflict": ("rename", "skip"),
    "replaygain": ("off", "track", "album"),
    "menu_mode": ("single", "submenu"),
    "after": ("keep", "recycle", "delete"),
    "view_mode": ("auto", "list"),
    "theme_mode": ("system", "light", "dark"),
    "channels": (0, 1, 2),
    "sample_rate": (0, 44100, 48000),
}
_RANGES = {
    "br_opus": (6, 510), "br_mp3": (32, 320), "br_aac": (32, 512), "br_vorbis": (32, 500),
    "mp3_vq": (0, 9), "art_max_px": (0, 4000), "threads": (0, 16), "auto_delay_ms": (0, 6000),
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def sanitize(data: dict) -> dict:
    """Return a complete, valid settings dict. Unknown keys are dropped."""
    out = copy.deepcopy(DEFAULTS)
    for k, default in DEFAULTS.items():
        if k not in data:
            continue
        v = data[k]
        try:
            if k in _CHOICES:
                v = int(v) if isinstance(default, int) and not isinstance(default, bool) else v
                if v in _CHOICES[k]:
                    out[k] = v
            elif k in _RANGES:
                lo, hi = _RANGES[k]
                out[k] = max(lo, min(hi, int(v)))
            elif k == "seed":
                if v == "system" or (isinstance(v, str) and _HEX.match(v)):
                    out[k] = v
            elif k == "menu_folders":
                out[k] = [str(x) for x in v][:200] if isinstance(v, (list, tuple)) else []
            elif isinstance(default, bool):
                out[k] = bool(v)
            elif isinstance(default, str):
                out[k] = str(v)
        except (TypeError, ValueError):
            pass
    return out


class Config:
    def __init__(self, path: Path = None):
        self.path = Path(path) if path else home() / "config.json"
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("not an object")
                self.data = sanitize(raw)
            except FileNotFoundError:
                self.data = copy.deepcopy(DEFAULTS)
            except (ValueError, OSError):
                try:  # keep the broken file so nothing is lost, then start clean
                    self.path.replace(self.path.with_name(f"config.json.bad-{int(time.time())}"))
                except OSError:
                    pass
                self.data = copy.deepcopy(DEFAULTS)

    def save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".cfg-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except OSError:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def get(self, key):
        with self._lock:
            return copy.deepcopy(self.data[key])

    def set(self, key, value) -> bool:
        """Validate + store one setting. Returns True when the stored value changed."""
        if key not in DEFAULTS:
            return False
        with self._lock:
            trial = dict(self.data)
            trial[key] = value
            clean = sanitize(trial)
            if clean[key] == self.data[key]:
                return False
            self.data = clean
            self.save()
            return True

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self.data)

    def bitrate(self, fmt=None) -> int:
        fmt = fmt or self.get("format")
        return int(self.data.get(f"br_{fmt}", 0) or 0)
