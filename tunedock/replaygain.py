"""ReplayGain / loudness tagging.

Loudness is measured with ffmpeg's EBU R128 meter on the *final* audio.
  * MP3 / FLAC / Vorbis / AAC(M4A): REPLAYGAIN_* tags, ReplayGain 2.0 reference of -18 LUFS
  * Opus: R128_TRACK_GAIN / R128_ALBUM_GAIN (RFC 7845, Q7.8 dB relative to -23 LUFS) - what Opus players read
Album gain is the duration-weighted energy mean of the track loudness values (close to, but not
bit-identical with, a single measurement over the whole album).
"""
import math
import re
from dataclasses import dataclass
from pathlib import Path

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from .media import MediaError, run_proc, _last_line

RG_REF = -18.0
R128_REF = -23.0


@dataclass
class Loud:
    lufs: float
    peak: float      # linear, 1.0 = full scale
    dur: float


_I = re.compile(r"Integrated loudness:\s+I:\s+(-?\d+(?:\.\d+)?|-inf)\s+LUFS")
_P = re.compile(r"True peak:\s+Peak:\s+(-?\d+(?:\.\d+)?|-inf)\s+dBFS")


def measure(ffmpeg, path, dur=0.0, cancel=None, procs=None):
    """-> Loud, or None for silence / unreadable audio."""
    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-nostats", "-v", "info", "-i", str(path), "-map", "0:a:0",
           "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"]
    rc, _, err = run_proc(cmd, cancel, procs, limit=1800)
    if rc != 0:
        raise MediaError("loudness scan failed: " + _last_line(err))
    i, p = _I.findall(err), _P.findall(err)
    if not i or i[-1] == "-inf":
        return None
    peak_db = float(p[-1]) if p and p[-1] != "-inf" else -60.0
    if not dur:
        try:
            dur = float(mutagen.File(str(path)).info.length)
        except Exception:
            dur = 1.0
    return Loud(float(i[-1]), 10 ** (peak_db / 20.0), max(dur, 0.001))


def album_loud(items):
    items = [x for x in items if x]
    if not items:
        return None
    tot = sum(x.dur for x in items)
    energy = sum(x.dur * 10 ** (x.lufs / 10.0) for x in items) / tot
    return Loud(10 * math.log10(energy), max(x.peak for x in items), tot)


def _gain(ld, ref):
    return ref - ld.lufs


def _fmt_gain(db):
    return "%+.2f dB" % db


def _q78(db):
    return str(max(-32768, min(32767, int(round(db * 256)))))


def write_tags(path, track=None, album=None) -> bool:
    """Write whatever of track/album loudness is given. Returns False for unsupported containers."""
    path = Path(path)
    f = mutagen.File(str(path))
    if isinstance(f, OggOpus):
        t = f.tags if f.tags is not None else (f.add_tags() or f.tags)
        for k in list(t.keys()):
            if k.lower().startswith("replaygain_"):
                del t[k]
        if track:
            t["R128_TRACK_GAIN"] = [_q78(_gain(track, R128_REF))]
        if album:
            t["R128_ALBUM_GAIN"] = [_q78(_gain(album, R128_REF))]
        f.save()
        return True
    if isinstance(f, (OggVorbis, FLAC)):
        t = f.tags if f.tags is not None else (f.add_tags() or f.tags)
        if track:
            t["REPLAYGAIN_TRACK_GAIN"] = [_fmt_gain(_gain(track, RG_REF))]
            t["REPLAYGAIN_TRACK_PEAK"] = ["%.6f" % track.peak]
        if album:
            t["REPLAYGAIN_ALBUM_GAIN"] = [_fmt_gain(_gain(album, RG_REF))]
            t["REPLAYGAIN_ALBUM_PEAK"] = ["%.6f" % album.peak]
        t["REPLAYGAIN_REFERENCE_LOUDNESS"] = ["%.2f LUFS" % RG_REF]
        f.save()
        return True
    if isinstance(f, MP3):
        try:
            t = ID3(str(path))
        except ID3NoHeaderError:
            t = ID3()
        def put(desc, val):
            t.delall("TXXX:" + desc)
            t.add(TXXX(encoding=1, desc=desc, text=[val]))
        if track:
            put("REPLAYGAIN_TRACK_GAIN", _fmt_gain(_gain(track, RG_REF)))
            put("REPLAYGAIN_TRACK_PEAK", "%.6f" % track.peak)
        if album:
            put("REPLAYGAIN_ALBUM_GAIN", _fmt_gain(_gain(album, RG_REF)))
            put("REPLAYGAIN_ALBUM_PEAK", "%.6f" % album.peak)
        put("REPLAYGAIN_REFERENCE_LOUDNESS", "%.2f LUFS" % RG_REF)
        t.save(str(path), v1=0, v2_version=3)
        return True
    if isinstance(f, MP4):
        if f.tags is None:
            f.add_tags()
        base = "----:com.apple.iTunes:"
        def put(name, val):
            f.tags[base + name] = [val.encode("utf-8")]
        if track:
            put("replaygain_track_gain", _fmt_gain(_gain(track, RG_REF)))
            put("replaygain_track_peak", "%.6f" % track.peak)
        if album:
            put("replaygain_album_gain", _fmt_gain(_gain(album, RG_REF)))
            put("replaygain_album_peak", "%.6f" % album.peak)
        put("replaygain_reference_loudness", "%.2f LUFS" % RG_REF)
        f.save()
        return True
    return False
