"""Tags, artwork and ffmpeg encoding."""
import base64
import hashlib
import os
import re
import shutil
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import mutagen
from .winutil import hidden_kwargs
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (APIC, COMM, ID3, TALB, TCOM, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, TXXX, USLT,
                         ID3NoHeaderError)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a", ".m4b", ".aac", ".ogg", ".oga", ".opus", ".wma", ".ape", ".wv",
              ".aif", ".aiff", ".aifc", ".mka", ".mp2", ".tta", ".mp4"}
LOSSLESS = {"flac", "alac", "pcm", "ape", "wv", "tta"}
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

FORMATS = {
    # best overall first: Opus (most quality per bit), AAC (next best lossy, works on nearly every phone/Apple device),
    # MP3 (plays on anything), FLAC (lossless, large), Vorbis (older, mostly superseded by Opus), then "keep as is"
    "opus": dict(label="Opus", ext=".opus", enc="libopus", lossy=True, lo=6, hi=510, presets=[64, 96, 128, 160, 192, 256]),
    "aac": dict(label="AAC", ext=".m4a", enc="aac", lossy=True, lo=32, hi=512, presets=[128, 160, 192, 256, 320]),
    "mp3": dict(label="MP3", ext=".mp3", enc="libmp3lame", lossy=True, lo=32, hi=320, presets=[128, 192, 256, 320]),
    "flac": dict(label="FLAC", ext=".flac", enc="flac", lossy=False, lo=0, hi=0, presets=[]),
    "vorbis": dict(label="Vorbis", ext=".ogg", enc="libvorbis", lossy=True, lo=32, hi=500, presets=[96, 128, 160, 192, 256, 320]),
    "keep": dict(label="Keep", ext=None, enc=None, lossy=False, lo=0, hi=0, presets=[]),
}


class MediaError(Exception):
    pass


class Canceled(Exception):
    pass


# ------------------------------------------------------------------ ffmpeg discovery
def ffmpeg_candidates(configured: str = "") -> list:
    from .config import data_dir
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    cands = []
    if configured:
        c = Path(configured)
        cands.append(c / exe if c.is_dir() else c)
    try:
        cands.append(data_dir() / "ffmpeg" / exe)      # the copy Tunedock downloaded itself
    except OSError:
        pass
    here = Path(__file__).resolve().parent.parent
    cands += [here / exe, here / "bin" / exe, Path(os.sys.executable).parent / exe]
    found = shutil.which("ffmpeg")
    if found:
        cands.append(Path(found))
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        up = os.environ.get("USERPROFILE", "")
        cands += [Path(la) / "Microsoft/WinGet/Links/ffmpeg.exe", Path("C:/ffmpeg/bin/ffmpeg.exe"),
                  Path(up) / "scoop/shims/ffmpeg.exe", Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
                  Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe")]
    out = []
    for c in cands:
        try:
            if c.is_file() and str(c) not in out:
                out.append(str(c))
        except OSError:
            pass
    return out


def find_ffmpeg(configured: str = "", need: str = "") -> str:
    """First ffmpeg found. With `need` (an encoder name) a build that actually has it wins over one that lacks it."""
    cands = ffmpeg_candidates(configured)
    if need:
        for c in cands:
            if need in available_encoders(c):
                return c
    return cands[0] if cands else ""


_enc_cache = {}


def available_encoders(ffmpeg: str) -> set:
    if ffmpeg in _enc_cache:
        return _enc_cache[ffmpeg]
    names = set()
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, timeout=20, stdin=subprocess.DEVNULL,
                             **hidden_kwargs()).stdout.decode("utf-8", "replace")
        for line in out.splitlines():
            m = re.match(r"^\s[A-Z.]{6}\s(\S+)", line)
            if m:
                names.add(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    _enc_cache[ffmpeg] = names
    return names


def run_proc(cmd, cancel: threading.Event = None, procs: set = None, limit=3600):
    """Run a subprocess that can be cancelled. -> (returncode, stdout bytes, stderr text)"""
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         **hidden_kwargs())
    if procs is not None:
        procs.add(p)  # set.add is atomic under the GIL
    t0 = time.time()
    try:
        while True:
            try:
                out, err = p.communicate(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if cancel is not None and cancel.is_set():
                    p.kill(); p.communicate()
                    raise Canceled()
                if time.time() - t0 > limit:
                    p.kill(); p.communicate()
                    raise MediaError("ffmpeg took too long and was stopped")
    finally:
        if procs is not None:
            procs.discard(p)
    return p.returncode, out, err.decode("utf-8", "replace")


def _last_line(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else "unknown ffmpeg error"


# ------------------------------------------------------------------ tag model
@dataclass
class Meta:
    title: str = ""
    artist: list = field(default_factory=list)
    album: str = ""
    albumartist: str = ""
    track: int = 0
    tracktotal: int = 0
    disc: int = 0
    disctotal: int = 0
    date: str = ""
    genre: list = field(default_factory=list)
    composer: str = ""
    comment: str = ""
    lyrics: str = ""


@dataclass
class Art:
    data: bytes
    mime: str
    w: int = 0
    h: int = 0


@dataclass
class Probe:
    path: Path
    meta: Meta
    codec: str
    length: float
    kbps: float
    f: object = None
    marker: str = ""      # "opus;128": written by Tunedock itself, so a later pass can tell the file is already done


def _num(s):
    m = re.match(r"\s*(\d+)(?:\s*/\s*(\d+))?", str(s or ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


def _dict(tags):
    d = {}
    try:
        for k, v in tags.items():
            vals = v if isinstance(v, (list, tuple)) else [v]
            for x in vals:
                s = str(x).strip()
                if s:
                    d.setdefault(str(k).lower(), []).append(s)
    except Exception:
        pass
    return d


def _first(d, *keys):
    for k in keys:
        if d.get(k):
            return d[k]
    return []


def _meta_from_dict(d) -> Meta:
    m = Meta()
    m.title = (_first(d, "title") or [""])[0]
    m.artist = list(_first(d, "artist", "author"))
    m.album = (_first(d, "album", "wm/albumtitle") or [""])[0]
    m.albumartist = (_first(d, "albumartist", "album_artist", "album artist", "wm/albumartist") or [""])[0]
    m.track, tt = _num((_first(d, "tracknumber", "track", "wm/tracknumber") or [""])[0])
    m.tracktotal = tt or _num((_first(d, "tracktotal", "totaltracks", "tracks") or [""])[0])[0]
    m.disc, dt = _num((_first(d, "discnumber", "disc", "part", "wm/partofset") or [""])[0])
    m.disctotal = dt or _num((_first(d, "disctotal", "totaldiscs", "discs") or [""])[0])[0]
    m.date = (_first(d, "date", "year", "originaldate", "wm/year") or [""])[0]
    m.genre = list(_first(d, "genre", "wm/genre"))
    m.composer = (_first(d, "composer", "wm/composer") or [""])[0]
    m.comment = (_first(d, "comment", "description", "comments") or [""])[0]
    m.lyrics = (_first(d, "lyrics", "unsyncedlyrics") or [""])[0]
    return m


def _meta_from_id3(t) -> Meta:
    def txt(fid):
        fr = t.get(fid)
        return [str(x).strip() for x in fr.text if str(x).strip()] if fr is not None else []
    m = Meta()
    m.title = (txt("TIT2") or [""])[0]
    m.artist = txt("TPE1")
    m.album = (txt("TALB") or [""])[0]
    m.albumartist = (txt("TPE2") or [""])[0]
    m.track, m.tracktotal = _num((txt("TRCK") or [""])[0])
    m.disc, m.disctotal = _num((txt("TPOS") or [""])[0])
    m.date = (txt("TDRC") or txt("TYER") or [""])[0]
    m.genre = txt("TCON")
    m.composer = (txt("TCOM") or [""])[0]
    for c in t.getall("COMM"):
        if c.text and str(c.text[0]).strip() and not c.desc.lower().startswith(("itunnorm", "iTunSMPB".lower())):
            m.comment = str(c.text[0]).strip(); break
    for u in t.getall("USLT"):
        if u.text.strip():
            m.lyrics = u.text.strip(); break
    for x in t.getall("TXXX"):  # a few common extras written by other taggers
        d = x.desc.lower()
        if d == "album artist" and not m.albumartist and x.text:
            m.albumartist = str(x.text[0])
        if d == "totaltracks" and not m.tracktotal and x.text:
            m.tracktotal = _num(x.text[0])[0]
    return m


def _meta_from_mp4(t) -> Meta:
    def s(k):
        v = t.get(k)
        return [str(x).strip() for x in v if str(x).strip()] if v else []
    m = Meta()
    m.title = (s("\xa9nam") or [""])[0]
    m.artist = s("\xa9ART")
    m.album = (s("\xa9alb") or [""])[0]
    m.albumartist = (s("aART") or [""])[0]
    if t.get("trkn"):
        m.track, m.tracktotal = t["trkn"][0][0] or 0, (t["trkn"][0][1] if len(t["trkn"][0]) > 1 else 0) or 0
    if t.get("disk"):
        m.disc, m.disctotal = t["disk"][0][0] or 0, (t["disk"][0][1] if len(t["disk"][0]) > 1 else 0) or 0
    m.date = (s("\xa9day") or [""])[0]
    m.genre = s("\xa9gen")
    m.composer = (s("\xa9wrt") or [""])[0]
    m.comment = (s("\xa9cmt") or [""])[0]
    m.lyrics = (s("\xa9lyr") or [""])[0]
    return m


_NAME_CODEC = {"WAVE": "pcm", "AIFF": "pcm", "ASF": "wma", "MonkeysAudio": "ape", "WavPack": "wv",
               "TrueAudio": "tta", "AAC": "aac", "MP2": "mp2", "MP4": "aac"}
_EXT_CODEC = {".mp3": "mp3", ".flac": "flac", ".opus": "opus", ".wav": "pcm", ".aif": "pcm", ".aiff": "pcm",
              ".m4a": "aac", ".aac": "aac", ".ogg": "vorbis", ".oga": "vorbis", ".wma": "wma", ".ape": "ape",
              ".wv": "wv", ".tta": "tta"}


def probe(path: Path) -> Probe:
    try:
        f = mutagen.File(str(path))
    except Exception:
        f = None
    meta, codec, length, kbps = Meta(), _EXT_CODEC.get(path.suffix.lower(), "unknown"), 0.0, 0.0
    if f is not None:
        try:
            tags = f.tags
            if isinstance(tags, ID3):
                meta = _meta_from_id3(tags)
            elif isinstance(f, MP4):
                meta = _meta_from_mp4(tags) if tags else Meta()
            elif tags is not None:
                meta = _meta_from_dict(_dict(tags))
        except Exception:
            meta = Meta()
        if isinstance(f, MP3):
            codec = "mp3"
        elif isinstance(f, OggOpus):
            codec = "opus"
        elif isinstance(f, OggVorbis):
            codec = "vorbis"
        elif isinstance(f, FLAC):
            codec = "flac"
        elif isinstance(f, MP4):
            c = str(getattr(f.info, "codec", "") or "")
            codec = "alac" if c.startswith("alac") else "aac"
        else:
            codec = _NAME_CODEC.get(type(f).__name__, codec)
        length = float(getattr(f.info, "length", 0) or 0)
        kbps = float(getattr(f.info, "bitrate", 0) or 0) / 1000.0
    marker = ""
    try:
        tags = getattr(f, "tags", None)
        if isinstance(tags, ID3):
            fr = tags.get("TXXX:TUNEDOCK")
            marker = str(fr.text[0]) if fr is not None and fr.text else ""
        elif isinstance(f, MP4):
            v = (tags or {}).get("----:com.apple.iTunes:TUNEDOCK")
            marker = bytes(v[0]).decode("utf-8", "ignore") if v else ""
        elif tags is not None:
            v = tags.get("tunedock")
            marker = str(v[0]) if v else ""
    except Exception:
        marker = ""
    return Probe(path, meta, codec, length, kbps, f, marker)


# ------------------------------------------------------------------ artwork
def image_info(d: bytes):
    if d[:8] == b"\x89PNG\r\n\x1a\n" and len(d) >= 24:
        w, h = struct.unpack(">II", d[16:24]); return "image/png", w, h
    if d[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(d):
            if d[i] != 0xFF:
                i += 1; continue
            m = d[i + 1]
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2; continue
            if m == 0xFF:
                i += 1; continue
            ln = struct.unpack(">H", d[i + 2:i + 4])[0]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", d[i + 5:i + 9]); return "image/jpeg", w, h
            i += 2 + ln
        return "image/jpeg", 0, 0
    if d[:4] == b"RIFF" and d[8:12] == b"WEBP":
        return "image/webp", 0, 0
    if d[:3] == b"GIF":
        return "image/gif", 0, 0
    return None


def _art(data: bytes) -> Optional[Art]:
    info = image_info(bytes(data)[:600000] if len(data) > 600000 else bytes(data))
    return Art(bytes(data), info[0], info[1], info[2]) if info else None


def extract_art(p: Probe, ffmpeg: str = "") -> Optional[Art]:
    f = p.f
    try:
        if f is not None and isinstance(getattr(f, "tags", None), ID3):
            frames = f.tags.getall("APIC")
            frames.sort(key=lambda x: 0 if x.type == 3 else 1)
            return _art(frames[0].data) if frames else None
        if isinstance(f, FLAC):
            pics = sorted(f.pictures, key=lambda x: 0 if x.type == 3 else 1)
            return _art(pics[0].data) if pics else None
        if isinstance(f, MP4):
            c = (f.tags or {}).get("covr")
            return _art(c[0]) if c else None
        if isinstance(f, (OggOpus, OggVorbis)):
            pics = []
            for b in (f.tags or {}).get("metadata_block_picture", []):
                try:
                    pics.append(Picture(base64.b64decode(b)))
                except Exception:
                    pass
            pics.sort(key=lambda x: 0 if x.type == 3 else 1)
            return _art(pics[0].data) if pics else None
    except Exception:
        return None
    if ffmpeg:  # other containers: let ffmpeg pull the first attached picture
        try:
            rc, out, _ = run_proc([ffmpeg, "-nostdin", "-v", "error", "-i", str(p.path), "-map", "0:v:0", "-frames:v", "1",
                                   "-c:v", "mjpeg", "-f", "image2pipe", "-"], limit=60)
            return _art(out) if rc == 0 and out else None
        except (MediaError, OSError):
            return None
    return None


COVER_NAMES = ("cover", "folder", "front", "album", "albumart", "albumartsmall")


def find_folder_art(folder: Path) -> Optional[Art]:
    try:
        names = {e.name.lower(): e for e in os.scandir(folder) if e.is_file()}
    except OSError:
        return None
    for base in COVER_NAMES:
        for ext in (".jpg", ".jpeg", ".png"):
            e = names.get(base + ext)
            if e:
                try:
                    return _art(Path(e.path).read_bytes())
                except OSError:
                    return None
    return None


_art_cache = {}
_art_lock = threading.Lock()


def normalize_art(art: Art, max_px: int, ffmpeg: str) -> Optional[Art]:
    """MP4/ID3 want jpeg or png; optionally shrink. Falls back to the original on any failure."""
    need_convert = art.mime not in ("image/jpeg", "image/png")
    need_shrink = bool(max_px) and (art.w == 0 or art.w > max_px or art.h > max_px)
    if not (need_convert or need_shrink):
        return art
    if not ffmpeg:
        return None if need_convert else art
    key = (hashlib.sha1(art.data).hexdigest(), max_px)
    with _art_lock:
        if key in _art_cache:
            return _art_cache[key]
    result = None if need_convert else art
    try:
        vf = ("scale=w='min(%d,iw)':h='min(%d,ih)':force_original_aspect_ratio=decrease" % (max_px, max_px)) if max_px else "null"
        proc = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", "pipe:0", "-vf", vf, "-frames:v", "1",
                               "-c:v", "mjpeg", "-q:v", "2", "-f", "image2pipe", "pipe:1"],
                              input=art.data, capture_output=True, timeout=60, **hidden_kwargs())
        if proc.returncode == 0 and proc.stdout:
            result = _art(proc.stdout) or result
    except (OSError, subprocess.SubprocessError):
        pass
    with _art_lock:
        _art_cache[key] = result
    return result


# ------------------------------------------------------------------ encoding
def target_ext(fmt: str) -> str:
    return FORMATS[fmt]["ext"]


def build_cmd(ffmpeg, src, dst, fmt, cfg) -> list:
    spec = FORMATS[fmt]
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y", "-i", str(src),
           "-map", "0:a:0", "-vn", "-map_chapters", "-1", "-map_metadata", "0", "-c:a", spec["enc"]]
    kb = int(cfg.get(f"br_{fmt}", 0) or 0)
    if fmt == "opus":
        cmd += ["-b:a", f"{kb}k", "-vbr", "on" if cfg.get("opus_vbr", True) else "off"]
    elif fmt == "mp3":
        cmd += ["-q:a", str(int(cfg.get("mp3_vq", 2)))] if cfg.get("mp3_vbr") else ["-b:a", f"{kb}k"]
        cmd += ["-id3v2_version", "3", "-write_id3v1", "0"]
    elif fmt in ("aac", "vorbis"):
        cmd += ["-b:a", f"{kb}k"]
        if fmt == "aac":
            cmd += ["-movflags", "+faststart"]
    elif fmt == "flac":
        cmd += ["-compression_level", "8"]
    if cfg.get("channels"):
        cmd += ["-ac", str(int(cfg["channels"]))]
    if cfg.get("sample_rate") and fmt != "opus":
        cmd += ["-ar", str(int(cfg["sample_rate"]))]
    cmd.append(str(dst))
    return cmd


def encode(ffmpeg, src, dst, fmt, cfg, cancel=None, procs=None):
    rc, _, err = run_proc(build_cmd(ffmpeg, src, dst, fmt, cfg), cancel, procs)
    if rc != 0:
        raise MediaError(_last_line(err))
    if not Path(dst).is_file() or Path(dst).stat().st_size == 0:
        raise MediaError("ffmpeg produced an empty file")


# ------------------------------------------------------------------ tag finishing
_JUNK = {"encoder", "major_brand", "minor_version", "compatible_brands", "creation_time", "handler_name",
         "vendor_id", "encoded_by", "encoding", "language"}
_RENAMED = ("album_artist", "track", "disc", "description", "totaltracks", "tracktotal", "totaldiscs", "disctotal",
            "tracks", "discs", "year", "unsyncedlyrics")


def make_picture(art: Art) -> Picture:
    p = Picture()
    p.type, p.mime, p.desc, p.width, p.height, p.depth, p.data = 3, art.mime, "", art.w, art.h, 24, art.data
    return p


def _vc_set(t, key, vals):
    if key in t:
        del t[key]
    vals = [str(v) for v in vals if v not in (None, "", 0)]
    if vals:
        t[key] = vals


def _finalize_vorbis(f, meta, art, marker=""):
    if f.tags is None:
        f.add_tags()
    t = f.tags
    if meta is not None:
        for k in list(t.keys()):
            if k.lower() in _JUNK or k.lower() in _RENAMED:
                del t[k]
        _vc_set(t, "TITLE", [meta.title]); _vc_set(t, "ARTIST", meta.artist); _vc_set(t, "ALBUM", [meta.album])
        _vc_set(t, "ALBUMARTIST", [meta.albumartist]); _vc_set(t, "TRACKNUMBER", [meta.track])
        _vc_set(t, "TRACKTOTAL", [meta.tracktotal]); _vc_set(t, "DISCNUMBER", [meta.disc])
        _vc_set(t, "DISCTOTAL", [meta.disctotal]); _vc_set(t, "DATE", [meta.date]); _vc_set(t, "GENRE", meta.genre)
        _vc_set(t, "COMPOSER", [meta.composer]); _vc_set(t, "COMMENT", [meta.comment]); _vc_set(t, "LYRICS", [meta.lyrics])
        if marker:
            _vc_set(t, "TUNEDOCK", [marker])
    if art is not None:
        pic = make_picture(art)
        if isinstance(f, FLAC):
            f.clear_pictures(); f.add_picture(pic)
        else:
            if "metadata_block_picture" in t:
                del t["metadata_block_picture"]
            t["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]
    f.save()


def _finalize_mp3(path, meta, art, marker=""):
    try:
        t = ID3(str(path))
    except ID3NoHeaderError:
        t = ID3()
    if meta is not None:
        for x in list(t.getall("TXXX")):
            if x.desc.lower() in _JUNK | {"comment", "lyrics", "uslt", "description", "totaltracks", "totaldiscs", "tracktotal"}:
                t.delall("TXXX:" + x.desc)
        t.delall("TSSE")
        for fid in ("TIT2", "TPE1", "TALB", "TPE2", "TRCK", "TPOS", "TDRC", "TYER", "TCON", "TCOM", "COMM", "USLT"):
            t.delall(fid)

        def add(cls, vals):
            vals = [v for v in vals if v]
            if vals:
                t.add(cls(encoding=1, text=vals))
        add(TIT2, [meta.title]); add(TPE1, meta.artist); add(TALB, [meta.album]); add(TPE2, [meta.albumartist])
        if meta.track:
            add(TRCK, ["%d/%d" % (meta.track, meta.tracktotal) if meta.tracktotal else str(meta.track)])
        if meta.disc:
            add(TPOS, ["%d/%d" % (meta.disc, meta.disctotal) if meta.disctotal else str(meta.disc)])
        add(TDRC, [meta.date]); add(TCON, meta.genre); add(TCOM, [meta.composer])
        if meta.comment:
            t.add(COMM(encoding=1, lang="eng", desc="", text=[meta.comment]))
        if meta.lyrics:
            t.add(USLT(encoding=1, lang="eng", desc="", text=meta.lyrics))
        if marker:
            t.delall("TXXX:TUNEDOCK")
            t.add(TXXX(encoding=1, desc="TUNEDOCK", text=[marker]))
    if art is not None:
        t.delall("APIC")
        t.add(APIC(encoding=1, mime=art.mime, type=3, desc="Cover", data=art.data))
    t.save(str(path), v1=0, v2_version=3)


def _finalize_mp4(f, meta, art, marker=""):
    if f.tags is None:
        f.add_tags()
    t = f.tags
    if meta is not None:
        t.pop("\xa9too", None)
        for k, vals in (("\xa9nam", [meta.title]), ("\xa9ART", meta.artist), ("\xa9alb", [meta.album]),
                        ("aART", [meta.albumartist]), ("\xa9day", [meta.date]), ("\xa9gen", meta.genre),
                        ("\xa9wrt", [meta.composer]), ("\xa9cmt", [meta.comment]), ("\xa9lyr", [meta.lyrics])):
            vals = [v for v in vals if v]
            t.pop(k, None)
            if vals:
                t[k] = vals
        if meta.track:
            t["trkn"] = [(meta.track, meta.tracktotal)]
        if meta.disc:
            t["disk"] = [(meta.disc, meta.disctotal)]
        if marker:
            t["----:com.apple.iTunes:TUNEDOCK"] = [marker.encode("utf-8")]
    if art is not None:
        fmt = MP4Cover.FORMAT_PNG if art.mime == "image/png" else MP4Cover.FORMAT_JPEG
        t["covr"] = [MP4Cover(art.data, imageformat=fmt)]
    f.save()


def finalize(path, meta: Optional[Meta], art: Optional[Art], marker: str = "") -> bool:
    """Write clean, standard tags (meta) and/or artwork. Unsupported containers are left alone."""
    path = Path(path)
    f = mutagen.File(str(path))
    if f is None:
        return False
    if isinstance(f, MP3):
        _finalize_mp3(path, meta, art, marker)
    elif isinstance(f, (OggOpus, OggVorbis, FLAC)):
        _finalize_vorbis(f, meta, art, marker)
    elif isinstance(f, MP4):
        _finalize_mp4(f, meta, art, marker)
    else:
        return False
    return True


def has_art(path) -> bool:
    try:
        f = mutagen.File(str(path))
        if f is None:
            return True
        return extract_art(Probe(Path(path), Meta(), "", 0, 0, f)) is not None
    except Exception:
        return True
