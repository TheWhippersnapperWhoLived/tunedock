"""Browsing the music library and deciding when the folder picker can skip ahead."""
import os
import re
from pathlib import Path

from .media import AUDIO_EXTS
from .naming import safe_name

# folders that are part of an album rather than "more library"
IGNORED = {"$recycle.bin", "system volume information", "__macosx", "lost+found", "artwork", "scans", "scan",
           "covers", "cover", "booklet", "extras", "lyrics"}


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _hidden(entry) -> bool:
    if entry.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            return bool(entry.stat().st_file_attributes & 0x6)  # hidden | system
        except (OSError, AttributeError):
            return False
    return False


def _dirs(path):
    out = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False) and e.name.lower() not in IGNORED and not _hidden(e):
                        out.append(e)
                except OSError:
                    pass
    except OSError:
        return []
    out.sort(key=lambda e: _natural(e.name))
    return out


def _count(path):
    subs = audio = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() not in IGNORED and not _hidden(e):
                            subs += 1
                    elif os.path.splitext(e.name)[1].lower() in AUDIO_EXTS:
                        audio += 1
                except OSError:
                    pass
    except OSError:
        pass
    return subs, audio


def listing(path, limit=600):
    """Sub-folders of `path` with a hint of what is inside each."""
    items = []
    for i, e in enumerate(_dirs(path)):
        subs, audio = _count(e.path) if i < limit else (-1, -1)
        items.append({"name": e.name, "path": e.path, "subs": subs, "audio": audio})
    return items


def classify(path):
    """leaf = no sub-folders; albums = most sub-folders are leaves; branch = otherwise."""
    kids = _dirs(path)
    n = len(kids)
    if n == 0:
        return {"kind": "leaf", "subdirs": 0, "leaves": 0}
    leaves = sum(1 for k in kids[:300] if _count(k.path)[0] == 0)
    seen = min(n, 300)
    kind = "albums" if leaves / seen > 0.5 else "branch"
    return {"kind": kind, "subdirs": n, "leaves": leaves}


def can_auto(path, loose_files: bool) -> dict:
    """Should the picker save here without asking? Loose files need a leaf; folders also accept 'albums'."""
    c = classify(path)
    auto = c["kind"] == "leaf" or (c["kind"] == "albums" and not loose_files)
    return {"auto": auto, **c}


def make_folder(parent, name) -> str:
    name = safe_name(name)
    if not name:
        raise ValueError("Give the folder a name")
    p = Path(parent) / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def top_folders(root):
    return [e.name for e in _dirs(root)]
