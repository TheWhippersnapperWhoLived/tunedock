"""Safe archive extraction (zip, tar family built in; 7z via py7zr or 7-Zip; rar via 7-Zip/unrar)."""
import os
import shutil
import subprocess
import tarfile
from .winutil import hidden_kwargs
import zipfile
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz")
REGISTER_EXTS = (".zip", ".7z", ".rar", ".tar", ".tgz", ".tbz2", ".txz", ".gz", ".bz2", ".xz")


class ArchiveError(Exception):
    pass


def is_archive(path) -> bool:
    n = Path(path).name.lower()
    return any(n.endswith(s) for s in SUFFIXES)


def archive_stem(name: str) -> str:
    low = name.lower()
    for s in SUFFIXES:
        if low.endswith(s) and len(name) > len(s):
            return name[:-len(s)]
    return Path(name).stem


def _target(dest: Path, member: str):
    m = member.replace("\\", "/").lstrip("/")
    if not m or m.endswith("/") or m.startswith("__MACOSX/") or "/__MACOSX/" in m:
        return None
    parts = [p for p in m.split("/") if p not in ("", ".")]
    if any(p == ".." or ":" in p[:2] for p in parts) or not parts:
        return None
    t = dest.joinpath(*parts)
    try:
        t.resolve().relative_to(dest.resolve())
    except ValueError:
        return None
    return t


def _check_space(dest: Path, need: int):
    free = shutil.disk_usage(dest).free
    if need > free * 0.95:
        raise ArchiveError("Not enough free disk space in the temp folder to unpack this archive")


def _fix_zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            return name.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name


def _unzip(path, dest):
    try:
        with zipfile.ZipFile(path) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            _check_space(dest, sum(i.file_size for i in infos))
            for i in infos:
                t = _target(dest, _fix_zip_name(i))
                if t is None:
                    continue
                t.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zf.open(i) as src, open(t, "wb") as out:
                        shutil.copyfileobj(src, out, 1 << 20)
                except RuntimeError:
                    raise ArchiveError("This zip is password-protected")
    except zipfile.BadZipFile:
        raise ArchiveError("This zip file is damaged or not a zip")


def _untar(path, dest):
    try:
        with tarfile.open(path, "r:*") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            _check_space(dest, sum(m.size for m in members))
            for m in members:
                t = _target(dest, m.name)
                if t is None:
                    continue
                t.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with src, open(t, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
    except (tarfile.TarError, EOFError, OSError) as e:
        if isinstance(e, ArchiveError):
            raise
        raise ArchiveError("Can't read this archive (%s)" % (e.__class__.__name__,))


def find_7z():
    for n in ("7z", "7za", "7zz", "7zr"):
        p = shutil.which(n)
        if p:
            return p
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            p = Path(base) / "7-Zip" / "7z.exe"
            if p.is_file():
                return str(p)
    return ""


def _external(path, dest, label):
    exe = find_7z()
    if exe:
        cmd = [exe, "x", "-y", "-aoa", "-bd", "-o" + str(dest), str(path)]
    else:
        un = shutil.which("unrar")
        bs = shutil.which("bsdtar")
        if un and label == "rar":
            cmd = [un, "x", "-y", "-idq", str(path), str(dest) + os.sep]
        elif bs:
            cmd = [bs, "-xf", str(path), "-C", str(dest)]
        else:
            raise ArchiveError("Opening .%s files needs 7-Zip (free, 7-zip.org). Install it and try again." % label)
    p = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=3600, **hidden_kwargs())
    if p.returncode not in (0, 1):  # 7z returns 1 for warnings
        msg = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()
        raise ArchiveError("Couldn't unpack: " + (msg[-1] if msg else "unknown error"))


def _un7z(path, dest):
    try:
        import py7zr
    except ImportError:
        return _external(path, dest, "7z")
    try:
        with py7zr.SevenZipFile(path) as z:
            names = z.getnames()
            if any(_target(dest, n) is None and not n.endswith("/") and n for n in names if "__MACOSX" not in n):
                raise ArchiveError("Archive contains unsafe paths")
            z.extractall(dest)
    except ArchiveError:
        raise
    except Exception as e:
        if "assword" in str(e):
            raise ArchiveError("This 7z is password-protected")
        # py7zr can't do every codec; 7-Zip can
        if find_7z():
            return _external(path, dest, "7z")
        raise ArchiveError("Couldn't unpack this 7z (%s)" % e.__class__.__name__)


def extract(path, dest) -> None:
    path, dest = Path(path), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    n = path.name.lower()
    if n.endswith(".zip"):
        _unzip(path, dest)
    elif n.endswith(".7z"):
        _un7z(path, dest)
    elif n.endswith(".rar"):
        _external(path, dest, "rar")
    else:
        _untar(path, dest)
