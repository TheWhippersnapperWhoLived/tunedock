"""Build a small, realistic test library with ffmpeg + mutagen (no real music needed)."""
import subprocess
from pathlib import Path

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4, MP4Cover


def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


def tone(path, freq=440, dur=2.0, vol=0.5, codec=None, extra=()):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}", "-af", f"volume={vol}"]
    if codec:
        cmd += ["-c:a", codec]
    ff(*cmd, *extra, str(path))
    return path


def cover(path, color="red", size=600, ext="jpg"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    ff("-f", "lavfi", "-i", f"color=c={color}:s={size}x{size}", "-frames:v", "1", str(path))
    return Path(path)


def make_library(root: Path):
    root = Path(root)
    jpg = cover(root.parent / "cov.jpg", "red", 800)
    png = cover(root.parent / "cov.png", "blue", 300)
    a = tone(root / "Artist A/Album 1/01 - Song One.flac", 440, 3, 0.6)
    f = FLAC(a)
    f["title"], f["artist"], f["album"], f["albumartist"] = "Song One", "Artist A", "Album 1", "Artist A"
    f["tracknumber"], f["tracktotal"], f["date"], f["genre"], f["comment"] = "1", "2", "2021-05-01", "Rock", "hello"
    p = Picture(); p.type = 3; p.mime = "image/png"; p.data = png.read_bytes(); p.width = p.height = 300; p.depth = 24
    f.add_picture(p); f.save()
    b = tone(root / "Artist A/Album 1/02 Song Two.flac", 523, 3, 0.2)
    f = FLAC(b)
    f["title"], f["artist"], f["album"], f["albumartist"], f["tracknumber"] = "Song Two: The Sequel", "Artist A", "Album 1", "Artist A", "2"
    f.save()
    m = tone(root / "Artist B/Single.m4a", 330, 2, 0.4, "aac")
    mp = MP4(m); mp["\xa9nam"], mp["\xa9ART"], mp["\xa9alb"] = ["Single Track"], ["Artist B"], ["The Singles"]
    mp["covr"] = [MP4Cover(jpg.read_bytes(), imageformat=MP4Cover.FORMAT_JPEG)]; mp.save()
    mp3 = tone(root / "Artist C/untagged track 07.mp3", 600, 2, 0.5)
    mp3b = tone(root / "Artist D/noart.mp3", 700, 2, 0.5)
    t = ID3(); t.save(mp3b)
    (root / "Artist D").mkdir(exist_ok=True)
    (root / "Artist D/cover.jpg").write_bytes(jpg.read_bytes())
    (root / "Artist D/noart.lrc").write_text("[00:00.00]la la\n", encoding="utf-8")
    tone(root / "Artist D/opus_src.opus", 800, 2, 0.5, "libopus", ("-b:a", "64k"))
    (root / "Notes.txt").write_text("hi")
    return root
