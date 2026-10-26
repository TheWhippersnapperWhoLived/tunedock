"""Scan what the user passed in, then convert / copy / tag it into the library."""
import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import archives, media, naming, replaygain, winutil
from .media import AUDIO_EXTS, FORMATS, Canceled, MediaError

SKIP_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}
SKIP_EXTS = {".m3u", ".m3u8", ".pls", ".tmp", ".part", ".db"}
SKIP_DIRS = {"__macosx", "$recycle.bin", "system volume information"}
V_KBPS = [245, 225, 190, 175, 165, 130, 115, 100, 85, 65]
TMP_PREFIX = ".tdpart-"


# ------------------------------------------------------------------ scanning
@dataclass
class ItemScan:
    src: Path
    kind: str                     # file | dir | archive
    root: Path                    # folder whose contents are mirrored (parent folder for a loose file)
    folder_name: str = ""         # name of the album folder created in the library ('' for loose files)
    audio: list = field(default_factory=list)
    others: list = field(default_factory=list)
    error: str = ""


@dataclass
class Scan:
    items: list = field(default_factory=list)
    temp: list = field(default_factory=list)

    @property
    def track_count(self):
        return sum(len(i.audio) for i in self.items)

    @property
    def loose(self):
        return any(i.kind == "file" and i.audio for i in self.items)

    def summary(self) -> dict:
        folders = set()
        for i in self.items:
            if i.kind != "file":
                folders.update(p.parent for p in i.audio)
        return {
            "items": len(self.items), "tracks": self.track_count, "albums": len(folders),
            "loose": sum(1 for i in self.items if i.kind == "file" and i.audio),
            "errors": [f"{i.src.name}: {i.error}" for i in self.items if i.error],
            "labels": [i.src.name for i in self.items][:12],
        }

    def cleanup(self):
        for t in self.temp:
            shutil.rmtree(t, ignore_errors=True)
        self.temp = []


def sweep_old_temp(max_age=86400):
    """Remove unpack folders left behind by a crashed run."""
    base = Path(tempfile.gettempdir())
    try:
        for p in base.glob("tunedock_*"):
            if p.is_dir() and time.time() - p.stat().st_mtime > max_age:
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def _walk(root: Path):
    audio, others = [], []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if not d.startswith(".") and d.lower() not in SKIP_DIRS)
        for fn in sorted(fns):
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            if fn.startswith(".") or low in SKIP_FILES:
                continue
            p = Path(dp) / fn
            if ext in AUDIO_EXTS:
                audio.append(p)
            elif ext not in SKIP_EXTS:
                others.append(p)
    return audio, others


def _unwrap(extract_dir: Path, stem: str):
    """An archive that holds one top folder (Artist - Album/...) shouldn't create folder-in-folder."""
    entries = [e for e in extract_dir.iterdir() if not e.name.startswith(".") and e.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0], entries[0].name
    return extract_dir, stem


def _expand_nested(root: Path, depth=0):
    if depth >= 2:
        return
    n = 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = Path(dp) / fn
            if archives.is_archive(p) and n < 20:
                n += 1
                out = p.parent / archives.archive_stem(p.name)
                try:
                    archives.extract(p, out)
                    p.unlink()
                    _expand_nested(out, depth + 1)
                except (archives.ArchiveError, OSError):
                    pass


def scan_inputs(paths, cancel: threading.Event = None) -> Scan:
    scan, seen = Scan(), set()
    for raw in paths:
        if cancel is not None and cancel.is_set():
            break
        p = Path(raw)
        try:
            key = str(p.resolve()).lower()
        except OSError:
            key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not p.exists():
                scan.items.append(ItemScan(p, "file", p.parent, error="Not found"))
            elif p.is_dir():
                it = ItemScan(p, "dir", p, folder_name=p.name)
                it.audio, it.others = _walk(p)
                if not it.audio:
                    it.error = "No audio files inside"
                scan.items.append(it)
            elif archives.is_archive(p):
                tmp = Path(tempfile.mkdtemp(prefix="tunedock_"))
                scan.temp.append(tmp)
                stem = archives.archive_stem(p.name)
                try:
                    archives.extract(p, tmp)
                    _expand_nested(tmp)
                    root, name = _unwrap(tmp, stem)
                    it = ItemScan(p, "archive", root, folder_name=name)
                    it.audio, it.others = _walk(root)
                    if not it.audio:
                        it.error = "No audio files inside"
                except archives.ArchiveError as e:
                    it = ItemScan(p, "archive", tmp, error=str(e))
                scan.items.append(it)
            elif p.suffix.lower() in AUDIO_EXTS:
                scan.items.append(ItemScan(p, "file", p.parent, audio=[p]))
            else:
                scan.items.append(ItemScan(p, "file", p.parent, error="Not an audio file or archive"))
        except OSError as e:
            scan.items.append(ItemScan(p, "file", p.parent, error=f"Can't read ({e.strerror or e})"))
    return scan


# ------------------------------------------------------------------ helpers
def move_noclobber(tmp: Path, final: Path) -> Path:
    """Move tmp to final without ever replacing an existing file; picks 'name (2)' if it has to."""
    n = 0
    while True:
        target = final if n == 0 else final.with_name(f"{final.stem} ({n + 1}){final.suffix}")
        try:
            os.link(tmp, target)
        except FileExistsError:
            n += 1
            continue
        except OSError:
            pass  # filesystem without hard links
        else:
            os.unlink(tmp)
            return target
        if target.exists():
            n += 1
            continue
        try:
            os.rename(tmp, target)
            return target
        except FileExistsError:
            n += 1


@dataclass
class Task:
    item: int
    src: Path
    out_dir: Path
    album_key: tuple = None
    inplace: bool = False         # the file already lives in the destination: replace it with the reprocessed one


def same_path(a, b) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return str(a).lower() == str(b).lower()


@dataclass
class Result:
    state: str                     # converted | copied | skipped | failed
    name: str
    src_bytes: int = 0
    dst_bytes: int = 0
    msg: str = ""
    final: Path = None
    loud: object = None
    album_key: tuple = None
    item: int = 0
    replaced: bool = False


class Runner:
    def __init__(self, cfg: dict, scan: Scan, dest, emit=None, cancel: threading.Event = None):
        self.cfg, self.scan, self.dest = cfg, scan, Path(dest)
        self.emit = emit or (lambda e: None)
        self.cancel = cancel or threading.Event()
        need = media.FORMATS[cfg["format"]]["enc"] if cfg.get("format") in media.FORMATS else ""
        self.ffmpeg = media.find_ffmpeg(cfg.get("ffmpeg_path", ""), need=need or "")
        self.lock = threading.Lock()
        self.claims, self.procs = set(), set()
        self.lrc = {}
        self._folder_art = {}
        self.notes = []
        self._tops = {}
        self._inplace = set()

    def cancel_now(self):
        self.cancel.set()
        for p in list(self.procs):
            try:
                p.kill()
            except OSError:
                pass

    # ---------------------------------------------------------- planning
    def _folder_name(self, it: ItemScan) -> str:
        name = it.folder_name
        if not (self.cfg["folder_rename"] and self.cfg["folder_template"].strip()):
            return naming.safe_name(name) or "Music"
        direct = sorted(p for p in it.audio if p.parent == it.root)
        if direct and len(direct) == len(it.audio):  # album-like: audio only at the top
            try:
                pr = media.probe(direct[0])
                ctx = naming.build_context(pr.meta, direct[0])
                if ctx["album"]:
                    new = naming.render(self.cfg["folder_template"], ctx)
                    if new:
                        return new
            except (naming.TemplateError, OSError):
                pass
        return naming.safe_name(name) or "Music"

    def _is_inplace(self, it: ItemScan) -> bool:
        """Already sitting directly in the folder it's being added to -> reprocess and replace instead of duplicating."""
        if it.kind not in ("file", "dir"):
            return False
        try:
            return it.src.resolve().parent == self.dest.resolve()
        except OSError:
            return False

    def _tasks(self):
        tasks, others = [], []
        for idx, it in enumerate(self.scan.items):
            if it.error and not it.audio:
                continue
            inplace = self._is_inplace(it)
            if inplace:
                self._inplace.add(idx)
            if it.kind == "file":
                tasks.append(Task(idx, it.audio[0], self.dest, inplace=inplace))
                continue
            top = self.dest / self._folder_name(it)
            self._tops[idx] = top
            for p in it.audio:
                rel = p.parent.relative_to(it.root)
                out = top.joinpath(*[naming.safe_name(x) or "_" for x in rel.parts])
                tasks.append(Task(idx, p, out, ("d", str(out).lower()), inplace=inplace))
            for p in it.others:
                rel = p.parent.relative_to(it.root)
                out = top.joinpath(*[naming.safe_name(x) or "_" for x in rel.parts])
                others.append(Task(idx, p, out, inplace=inplace))
        return tasks, others

    def _decide(self, pr: media.Probe, fmt: str) -> str:
        cfg = self.cfg
        if fmt == "keep":
            return "copy"
        if pr.codec == fmt or (fmt == "vorbis" and pr.codec == "vorbis"):
            if fmt == "flac":
                return "copy"
            if cfg["copy_if_fit"]:
                target = V_KBPS[cfg["mp3_vq"]] if (fmt == "mp3" and cfg["mp3_vbr"]) else cfg[f"br_{fmt}"]
                try:   # our own earlier work: trust the note we left instead of guessing from the file size
                    mf, mk = pr.marker.split(";")
                    if mf == fmt and float(mk) <= target:
                        return "copy"
                except ValueError:
                    pass
                kb = pr.kbps
                if pr.codec == "opus" and pr.length:
                    art = media.extract_art(pr)
                    kb = max(0.0, (pr.path.stat().st_size - (len(art.data) if art else 0)) * 8 / pr.length / 1000)
                vbr = fmt in ("opus", "vorbis") or (fmt == "mp3" and cfg["mp3_vbr"])
                if kb and kb <= target * (1.15 if vbr else 1.05):
                    return "copy"
            return "encode"
        if pr.codec not in media.LOSSLESS and cfg["lossy_policy"] == "keep":
            return "copy"
        return "encode"

    def _fit(self, out_dir: Path, base: str, ext: str) -> str:
        room = max(24, 245 - len(str(out_dir)) - len(ext) - 8)
        return base[:room].rstrip(" .") or "Track"

    def _claim(self, out_dir: Path, base: str, ext: str, album="", same_size=None, own: Path = None):
        base = self._fit(out_dir, base, ext)
        alb = naming.safe_name(album, 60) if album else ""
        cands = [base] + ([f"{base} ({alb})"] if alb else []) + [f"{base} ({i})" for i in range(2, 500)]
        with self.lock:
            for i, name in enumerate(cands):
                p = out_dir / (name + ext)
                key = str(p).lower()
                if key in self.claims:
                    continue
                if p.exists() and not (own is not None and same_path(p, own)):
                    if i == 0 and same_size is not None and p.stat().st_size == same_size:
                        return None
                    if i == 0 and self.cfg["on_conflict"] == "skip" and same_size is None:
                        return None
                    continue
                self.claims.add(key)
                return p
        raise MediaError("Couldn't find a free file name")

    def _art_for(self, pr: media.Probe, src_dir: Path):
        cfg = self.cfg
        if not cfg["embed_art"]:
            return None
        art = media.extract_art(pr, self.ffmpeg)
        if art is None and cfg["folder_art"]:
            with self.lock:
                if src_dir not in self._folder_art:
                    self._folder_art[src_dir] = media.find_folder_art(src_dir)
                art = self._folder_art[src_dir]
        return media.normalize_art(art, cfg["art_max_px"], self.ffmpeg) if art else None

    # ---------------------------------------------------------- one track
    def _track(self, t: Task) -> Result:
        cfg, src = self.cfg, t.src
        if self.cancel.is_set():
            raise Canceled()
        size = src.stat().st_size
        pr = media.probe(src)
        ctx = naming.build_context(pr.meta, src)
        tpl = cfg["file_template"].strip()
        try:
            base = naming.render(tpl, ctx) if tpl else naming.safe_name(src.stem)
        except naming.TemplateError:
            base = naming.render("{artist} - {title}", ctx)
        base = base or naming.safe_name(src.stem) or "Track"
        fmt = cfg["format"]
        action = self._decide(pr, fmt)
        ext = media.target_ext(fmt) if action == "encode" else src.suffix.lower()
        t.out_dir.mkdir(parents=True, exist_ok=True)
        final = self._claim(t.out_dir, base, ext, pr.meta.album, own=src if t.inplace else None)
        if final is None:
            return Result("skipped", final_name(base, ext), size, 0, "already in the library", item=t.item)
        tmp = t.out_dir / f"{TMP_PREFIX}{uuid.uuid4().hex[:10]}{ext}"
        warn = []
        try:
            art = None
            if action == "encode":
                art = self._art_for(pr, src.parent)
                media.encode(self.ffmpeg, src, tmp, fmt, cfg, self.cancel, self.procs)
                try:
                    media.finalize(tmp, pr.meta, art, marker=f"{fmt};{V_KBPS[cfg['mp3_vq']] if (fmt == 'mp3' and cfg['mp3_vbr']) else cfg.get('br_' + fmt, 0)}")
                except Exception as e:
                    warn.append(f"tags: {e.__class__.__name__}")
            else:
                shutil.copyfile(src, tmp)
                if fmt != "keep" and cfg["embed_art"] and cfg["folder_art"]:
                    try:
                        if not media.has_art(tmp):
                            fa = self._art_for(pr, src.parent)
                            if fa:
                                media.finalize(tmp, None, fa)
                    except Exception as e:
                        warn.append(f"art: {e.__class__.__name__}")
            loud = None
            if cfg["replaygain"] != "off" and fmt != "keep":
                try:
                    loud = replaygain.measure(self.ffmpeg, tmp, pr.length, self.cancel, self.procs)
                    if loud and not replaygain.write_tags(tmp, track=loud):
                        warn.append("replaygain: format not supported")
                except Canceled:
                    raise
                except Exception as e:
                    warn.append(f"replaygain: {e}")
            if self.cancel.is_set():
                raise Canceled()
            replaced = False
            if t.inplace and same_path(final, src):
                os.replace(tmp, final)       # same name: swap the new file in atomically
                final2, replaced = final, True
            else:
                final2 = move_noclobber(tmp, final)
                if t.inplace:                # new name or format: the old file goes once the new one is safely in place
                    try:
                        src.unlink()
                        replaced = True
                    except OSError:
                        warn.append("the old file couldn't be removed")
            tmp = None
            if final2 != final:
                with self.lock:
                    self.claims.add(str(final2).lower())
        finally:
            if tmp is not None:
                try:
                    tmp.unlink()
                except OSError:
                    pass
        with self.lock:
            self.lrc[(str(src.parent).lower(), src.stem.lower())] = final2.stem
        key = None
        if loud is not None:
            alb = (pr.meta.album or "").strip().lower()
            if alb:
                key = ("a", str(t.out_dir).lower(), alb)
            elif t.album_key:
                key = t.album_key
        return Result("converted" if action == "encode" else "copied", final2.name, size, final2.stat().st_size,
                      "; ".join(warn), final2, loud, key, t.item, replaced)

    def _other(self, t: Task):
        src = t.src
        if self.cancel.is_set():
            raise Canceled()
        name, ext = src.stem, src.suffix
        if ext.lower() == ".lrc":
            new = self.lrc.get((str(src.parent).lower(), src.stem.lower()))
            if new:
                name = new
        size = src.stat().st_size
        t.out_dir.mkdir(parents=True, exist_ok=True)
        if t.inplace:
            final = self._claim(t.out_dir, name, ext, "", own=src)
            if final is None or same_path(final, src):
                return                        # already where it belongs
            move_noclobber(src, final)        # e.g. a .lrc following its renamed track
            return
        final = self._claim(t.out_dir, name, ext, "", same_size=size)
        if final is None:
            return
        tmp = t.out_dir / f"{TMP_PREFIX}{uuid.uuid4().hex[:10]}{ext}"
        try:
            shutil.copyfile(src, tmp)
            move_noclobber(tmp, final)
            tmp = None
        finally:
            if tmp is not None:
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # ---------------------------------------------------------- the job
    def run(self) -> dict:
        t0 = time.time()
        cfg = self.cfg
        rep = {"converted": 0, "copied": 0, "skipped": 0, "failed": 0, "errors": [], "notes": [], "bytes_in": 0,
               "bytes_out": 0, "dest": str(self.dest), "cancelled": False, "seconds": 0.0, "total": 0, "fatal": "", "replaced": 0}
        try:
            self.dest.mkdir(parents=True, exist_ok=True)
            probe_file = self.dest / f"{TMP_PREFIX}{uuid.uuid4().hex[:6]}.w"
            probe_file.write_bytes(b"x")
            probe_file.unlink()
            if shutil.disk_usage(self.dest).free < 50 * 1024 * 1024:
                raise OSError("less than 50 MB free")
        except OSError as e:
            rep["fatal"] = f"Can't write to that folder ({e.strerror or e})"
            return rep
        if cfg["format"] != "keep" and not self.ffmpeg:
            rep["fatal"] = "ffmpeg wasn't found. Set its location on the Convert page."
            return rep
        if cfg["format"] != "keep":
            if FORMATS[cfg["format"]]["enc"] not in media.available_encoders(self.ffmpeg):
                rep["fatal"] = f"This ffmpeg can't encode {FORMATS[cfg['format']]['label']}. Pick another format or use a full ffmpeg build."
                return rep

        tasks, others = self._tasks()
        rep["total"] = len(tasks)
        self.emit({"type": "start", "total": len(tasks)})
        workers = cfg["threads"] or max(1, min(8, os.cpu_count() or 2))
        results, done, bad_items = [], 0, set()
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(self._track, t): t for t in tasks}
                for fut in as_completed(futs):
                    t = futs[fut]
                    try:
                        r = fut.result()
                    except Canceled:
                        rep["cancelled"] = True
                        continue
                    except Exception as e:
                        msg = ("in use by another program (close it and try again)" if isinstance(e, PermissionError)
                               else (str(e) or e.__class__.__name__))
                        r = Result("failed", t.src.name, msg=msg, item=t.item)
                        rep["errors"].append(f"{t.src.name}: {msg}")
                        bad_items.add(t.item)
                    results.append(r)
                    rep[r.state] += 1
                    rep["bytes_in"] += r.src_bytes
                    rep["bytes_out"] += r.dst_bytes
                    rep["replaced"] += 1 if r.replaced else 0
                    if r.msg and r.state != "failed" and r.state != "skipped":
                        rep["notes"].append(f"{r.name}: {r.msg}")
                    done += 1
                    self.emit({"type": "progress", "done": done, "total": len(tasks), "name": r.name,
                               "state": r.state, "msg": r.msg})
            if cfg["replaygain"] == "album" and not self.cancel.is_set():
                self.emit({"type": "phase", "text": "Adding album loudness tags\u2026"})
                self._album_gain(results, rep)
            if not self.cancel.is_set():
                if others:
                    self.emit({"type": "phase", "text": "Copying covers and lyrics\u2026"})
                for o in others:
                    try:
                        self._other(o)
                    except Canceled:
                        rep["cancelled"] = True
                        break
                    except Exception as e:
                        rep["notes"].append(f"{o.src.name}: {e}")
        finally:
            self._sweep()
        if self.cancel.is_set():
            rep["cancelled"] = True
        if not rep["cancelled"]:
            self._tidy_inplace(bad_items)
            if cfg["after"] in ("recycle", "delete"):
                self.emit({"type": "phase", "text": "Moving the originals to the Recycle Bin\u2026" if cfg["after"] == "recycle" else "Deleting the originals\u2026"})
                self._originals(bad_items, rep)
        rep["seconds"] = round(time.time() - t0, 1)
        rep["errors"] = rep["errors"][:50]
        rep["notes"] = rep["notes"][:30]
        return rep

    def _album_gain(self, results, rep):
        groups = {}
        for r in results:
            if r.loud is not None and r.album_key and r.final:
                groups.setdefault(r.album_key, []).append(r)
        for rs in groups.values():
            al = replaygain.album_loud([r.loud for r in rs])
            for r in rs:
                try:
                    replaygain.write_tags(r.final, album=al) if r.final.suffix.lower() == ".opus" else \
                        replaygain.write_tags(r.final, track=r.loud, album=al)
                except Exception as e:
                    rep["notes"].append(f"{r.name}: album gain: {e.__class__.__name__}")

    def _sweep(self):
        for root in {self.dest} | {p for p in self._touched()}:
            try:
                for f in root.glob(TMP_PREFIX + "*"):
                    f.unlink()
            except OSError:
                pass

    def _touched(self):
        with self.lock:
            return {Path(k).parent for k in self.claims}

    def _tidy_inplace(self, bad_items):
        """A reprocessed folder that got a new name leaves the old, now empty, folders behind: remove those (empty only)."""
        for idx in self._inplace:
            it, top = self.scan.items[idx], self._tops.get(idx)
            if idx in bad_items or it.kind != "dir" or top is None:
                continue
            if top.exists() and same_path(top, it.root):
                continue                              # same folder name, nothing moved away
            for dp, _dns, _fns in os.walk(it.root, topdown=False):
                try:
                    os.rmdir(dp)                      # only succeeds for empty folders
                except OSError:
                    pass

    def _originals(self, bad_items, rep):
        """'Move' semantics: once an item went in completely, recycle or delete what the user gave us."""
        mode = self.cfg["after"]
        lib = self.cfg.get("library_root") or ""
        try:
            dest = self.dest.resolve()
            lr = Path(lib).resolve() if lib else None
        except OSError:
            return
        for idx, it in enumerate(self.scan.items):
            if idx in bad_items or it.error or idx in self._inplace:   # in-place items were already replaced
                continue
            try:
                src = it.src.resolve()
                if dest == src or src in dest.parents:
                    continue                       # never remove a folder that contains the destination
                if lr is not None and (src == lr or src in lr.parents):
                    continue                       # never the library itself, or anything that contains it
                if mode == "recycle":
                    winutil.recycle(str(src))
                elif src.is_dir():
                    shutil.rmtree(src)
                else:
                    src.unlink()
            except Exception as e:
                rep["notes"].append(f"{it.src.name}: couldn't remove the original ({e.__class__.__name__})")


def final_name(base, ext):
    return base + ext
