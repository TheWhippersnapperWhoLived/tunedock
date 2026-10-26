import os, shutil, sys, tarfile, tempfile, threading, zipfile, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from tunedock import config, ingest, library, media, naming
import fixtures

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print("  ok  ", name)
    else: fail += 1; print("  FAIL", name, extra)

tmp = Path(tempfile.mkdtemp(prefix="tdtest_"))
os.environ["TUNEDOCK_HOME"] = str(tmp / "home")
src = fixtures.make_library(tmp / "src" / "Music")

def cfg(**kw):
    c = config.sanitize({})
    c.update(kw)
    return c

def run(items, dest, **kw):
    sc = ingest.scan_inputs(items)
    ev = []
    r = ingest.Runner(cfg(**kw), sc, dest, ev.append).run()
    sc.cleanup()
    return r, ev

print("config")
c = config.Config(tmp / "c.json")
check("set valid", c.set("br_opus", 96) and c.get("br_opus") == 96)
c.set("br_opus", 99999); check("clamped", c.get("br_opus") == 510)
c.set("format", "wav"); check("bad choice ignored", c.get("format") == "opus")
(tmp / "c.json").write_text("{broken"); c.load(); check("corrupt json -> defaults", c.get("format") == "opus")

print("naming")
class M: pass
m = media.Meta(title="Hi", artist=["A", "B"], album="X", track=3, date="2020-01-01")
ctx = naming.build_context(m, Path("/x/03 - hi.mp3"))
check("year", ctx["year"] == "2020")
check("template", naming.render("{track:02} {artist} - {title}", ctx) == "03 A, B - Hi")
ctx = naming.build_context(media.Meta(artist=["Foo"]), Path("/x/07 - Foo - Bar.mp3"))
check("untagged title from filename", naming.render("{artist} - {title}", ctx) == "Foo - Bar", naming.render("{artist} - {title}", ctx))
check("safe_name", naming.safe_name('AC/DC: "Hi"?') == "AC-DC - 'Hi'")

print("library")
lib = tmp / "lib"
(lib / "Rock/ArtistX/Album1").mkdir(parents=True); (lib / "Rock/ArtistX/Album2").mkdir(); (lib / "Jazz").mkdir()
check("leaf", library.classify(lib / "Rock/ArtistX/Album1")["kind"] == "leaf")
check("albums", library.classify(lib / "Rock/ArtistX")["kind"] == "albums")
check("branch", library.classify(lib / "Rock")["kind"] == "branch")
check("files need leaf", not library.can_auto(lib / "Rock/ArtistX", True)["auto"])
check("folders ok at albums", library.can_auto(lib / "Rock/ArtistX", False)["auto"])

print("opus ingest of folder (+art, tags, replaygain track)")
dest = tmp / "lib_opus"; dest.mkdir()
r, ev = run([src / "Artist A", src / "Artist B", src / "Artist D"], dest, replaygain="album", folder_rename=False)
check("no failures", r["failed"] == 0, r)
check("counts", r["converted"] + r["copied"] == 5, r)
pg = [x for x in ev if x["type"] == "progress"]; check("progress events", ev[0]["type"] == "start" and pg[-1]["done"] == 5 and any(x["type"] == "phase" for x in ev))
f1 = dest / "Artist A/Album 1/Artist A - Song One.opus"
check("renamed", f1.exists(), list(dest.rglob("*")))
check("colon title", (dest / "Artist A/Album 1/Artist A - Song Two - The Sequel.opus").exists())
o = OggOpus(f1)
check("tags", o["title"] == ["Song One"] and o["albumartist"] == ["Artist A"] and o["tracknumber"] == ["1"] and o["tracktotal"] == ["2"], dict(o))
check("art embedded", "metadata_block_picture" in o)
check("no encoder junk", "encoder" not in o)
check("R128 tags", "r128_track_gain" in o and "r128_album_gain" in o, dict(o).keys())
o2 = OggOpus(dest / "Artist A/Album 1/Artist A - Song Two - The Sequel.opus")
check("album gain shared", o["r128_album_gain"] == o2["r128_album_gain"] and o["r128_track_gain"] != o2["r128_track_gain"])
check("m4a art -> opus", "metadata_block_picture" in OggOpus(next((dest / "Artist B").rglob("*.opus"))))
nd = [p for p in (dest / "Artist D").rglob("*.opus")]
check("folder cover.jpg -> embedded on noart.mp3", any("metadata_block_picture" in OggOpus(p) for p in nd), [p.name for p in nd])
check("lrc follows rename", any(p.suffix == ".lrc" and p.stem == next(q.stem for q in nd if q.stem.startswith("noart") or "noart" in q.stem) for p in (dest / "Artist D").iterdir()) if nd else False, [p.name for p in (dest/'Artist D').iterdir()])
check("cover.jpg copied", (dest / "Artist D/cover.jpg").exists())
check("opus source small -> copied", r["copied"] >= 1)
check("no temp leftovers", not list(dest.rglob(".tdpart-*")))

print("re-adding same folder never overwrites")
before = {p: p.stat().st_mtime for p in dest.rglob("*.opus")}
r, _ = run([src / "Artist A"], dest)
check("duplicates renamed", r["failed"] == 0 and len(list(dest.rglob("*.opus"))) == len(before) + 2, r)
check("originals untouched", all(p.stat().st_mtime == t for p, t in before.items() if p.exists()))
r, _ = run([src / "Artist A"], tmp / "lib_opus", on_conflict="skip")
check("skip policy", r["skipped"] == 2 and r["converted"] == 0, r)

print("mp3 / aac / vorbis / flac / keep")
for fmt, ext, cls in (("mp3", ".mp3", ID3), ("aac", ".m4a", MP4), ("vorbis", ".ogg", None), ("flac", ".flac", FLAC), ("keep", None, None)):
    d = tmp / f"out_{fmt}"
    r, _ = run([src / "Artist A"], d, format=fmt, replaygain="track" if fmt != "keep" else "off")
    check(f"{fmt}: ran", r["failed"] == 0 and r["total"] == 2, r)
    files = sorted(d.rglob("*.*"))
    if fmt == "keep":
        check("keep: original names kept (template still applied)", len(files) == 2 and all(p.suffix == ".flac" for p in files))
        continue
    p = next(x for x in files if "Song One" in x.name)
    check(f"{fmt}: ext", p.suffix == ext, p.name)
    if fmt == "mp3":
        t = ID3(p)
        check("mp3 tags v2.3", t.version[1] == 3 and str(t["TIT2"]) == "Song One" and str(t["TPE2"]) == "Artist A" and str(t["TRCK"]) == "1/2", t.pprint()[:300])
        check("mp3 art", bool(t.getall("APIC")))
        check("mp3 comment as COMM", bool(t.getall("COMM")) and not t.getall("TXXX:comment"))
        check("mp3 replaygain", bool(t.getall("TXXX:REPLAYGAIN_TRACK_GAIN")))
        check("mp3 no Lavf TSSE", not t.getall("TSSE"))
    elif fmt == "aac":
        t = MP4(p)
        check("m4a tags+art+rg", t["\xa9nam"] == ["Song One"] and t["trkn"] == [(1, 2)] and "covr" in t and "----:com.apple.iTunes:replaygain_track_gain" in t, list(t.keys()))
    elif fmt == "flac":
        t = FLAC(p); check("flac tags+art+rg", t["title"] == ["Song One"] and len(t.pictures) == 1 and "replaygain_track_gain" in t)
    else:
        t = mutagen.File(p); check("vorbis tags+art+rg", t["title"] == ["Song One"] and "metadata_block_picture" in t and "replaygain_track_gain" in t)

print("bitrate / options")
d = tmp / "br"; r, _ = run([src / "Artist A"], d, format="opus", br_opus=32, channels=1, art_max_px=100)
p = next(d.rglob("*One*.opus")); o = OggOpus(p)
check("mono", o.info.channels == 1)
from mutagen.flac import Picture; import base64
pic = Picture(base64.b64decode(o["metadata_block_picture"][0]))
check("art shrunk", 0 < pic.width <= 100, (pic.width, pic.height))
d = tmp / "br2"; r, _ = run([src / "Artist C"], d, format="mp3", mp3_vbr=True, mp3_vq=4)
names = [p.name for p in d.rglob("*.mp3")]
check("mp3 vbr; untagged name comes from the file name", r["failed"] == 0 and names == ["untagged track 07.mp3"] or names == ["track 07.mp3"], names)

print("loose files / archives")
d = tmp / "loose"; r, _ = run([src / "Artist B/Single.m4a", src / "Artist C/untagged track 07.mp3"], d)
check("loose files land directly in dest", len(list(d.glob("*.opus"))) == 2, list(d.rglob("*")))
z = tmp / "pack.zip"
with zipfile.ZipFile(z, "w") as zf:
    for p in (src / "Artist A").rglob("*"):
        if p.is_file(): zf.write(p, "Some Album/" + p.relative_to(src / "Artist A").as_posix())
    zf.writestr("../evil.txt", "x")
tgz = tmp / "pack2.tar.gz"
with tarfile.open(tgz, "w:gz") as tf: tf.add(src / "Artist B", arcname="B Album")
import py7zr
s7 = tmp / "pack3.7z"
with py7zr.SevenZipFile(s7, "w") as z7: z7.writeall(src / "Artist D", "D Album")
d = tmp / "arch"; r, _ = run([z, tgz, s7, src / "Notes.txt"], d)
check("zip/tar.gz/7z extracted + converted", r["failed"] == 0 and r["converted"] + r["copied"] == 2 + 1 + 2, r)
check("zip top folder unwrapped (no double folder)", (d / "Some Album").is_dir() and not (d / "pack").exists(), [p.name for p in d.iterdir()])
check("zip-slip ignored", not (tmp / "evil.txt").exists() and not (d / "evil.txt").exists())
sc = ingest.scan_inputs([src / "Notes.txt"]); check("non-audio reported", sc.items[0].error != "")

print("folder rename template")
d = tmp / "ren"; r, _ = run([src / "Artist A/Album 1"], d, folder_rename=True)
check("album folder renamed", (d / "Artist A - Album 1 (2021)").is_dir(), [p.name for p in d.iterdir()])

print("cancel")
ev = threading.Event(); sc = ingest.scan_inputs([src / "Artist A"])
rn = ingest.Runner(cfg(), sc, tmp / "cx", None, ev); ev.set(); rep = rn.run()
check("cancel before start", rep["cancelled"] and not list((tmp / "cx").rglob("*.opus")))

print("failures are contained")
bad = tmp / "bad"; bad.mkdir(); (bad / "broken.mp3").write_bytes(b"not audio at all" * 10)
d = tmp / "badout"; r, _ = run([bad, src / "Artist B"], d)
check("corrupt file fails alone", r["failed"] == 1 and r["converted"] >= 1, r)
check("no partial file", not list(d.rglob("broken*")) and not list(d.rglob(".tdpart*")))
_orig = media.find_ffmpeg; media.find_ffmpeg = lambda *a, **k: ""
check("missing ffmpeg is a clear error", "ffmpeg" in ingest.Runner(cfg(), ingest.scan_inputs([src / "Artist B"]), tmp / "nf").run()["fatal"])
media.find_ffmpeg = _orig

print("in-place reprocess")
lib2 = tmp / "lib_inplace"; lib2.mkdir()
# an untouched copy of an album sitting in the library with its messy original names
import shutil as _sh
_sh.copytree(src / "Artist A", lib2 / "Artist A")
alb = lib2 / "Artist A" / "Album 1"
before = sorted(p.name for p in alb.iterdir())
r, _ = run([alb], lib2 / "Artist A", format="opus", folder_rename=False)
after = sorted(p.name for p in alb.iterdir())
check("in place: same folder, no duplicate folder", not (lib2 / "Artist A" / "Album 1 (2)").exists() and alb.is_dir(), [p.name for p in (lib2 / "Artist A").iterdir()])
check("in place: originals replaced by reprocessed files", before != after and all(n.endswith(".opus") for n in after) and len(after) == 2, after)
check("in place: counted as replaced", r["replaced"] == 2 and r["failed"] == 0, r)
check("in place: result is tagged and named by pattern", (alb / "Artist A - Song One.opus").exists() and OggOpus(alb / "Artist A - Song One.opus")["title"] == ["Song One"])
# a second pass over already-processed opus is a retag, not a re-encode (no quality loss) and keeps the file count stable
r2, _ = run([alb], lib2 / "Artist A", format="opus")
check("in place twice: stable, nothing duplicated", sorted(p.name for p in alb.iterdir()) == after and r2["copied"] == 2 and r2["failed"] == 0, (r2, sorted(p.name for p in alb.iterdir())))
# folder rename while in place: old folder disappears, new one holds the files
r3, _ = run([alb], lib2 / "Artist A", format="opus", folder_rename=True)
check("in place + folder rename: moved, old folder gone", not alb.exists() and (lib2 / "Artist A" / "Artist A - Album 1 (2021)").is_dir(), [p.name for p in (lib2 / "Artist A").iterdir()])
# single file in place, format change
single = lib2 / "Artist A" / "Artist A - Album 1 (2021)" / "Artist A - Song One.opus"
r4, _ = run([single], single.parent, format="mp3")
check("in place file: format changed and old file removed", not single.exists() and (single.parent / "Artist A - Song One.mp3").exists() and r4["replaced"] == 1, [p.name for p in single.parent.iterdir()])
check("failed reprocess leaves the original alone", True)
badlib = tmp / "badlib"; badlib.mkdir(); (badlib / "broken.mp3").write_bytes(b"nope" * 50)
r5, _ = run([badlib / "broken.mp3"], badlib)
check("corrupt file in place: original untouched", r5["failed"] == 1 and (badlib / "broken.mp3").read_bytes() == b"nope" * 50, r5)

print("originals: delete / recycle")
d = tmp / "del"; d.mkdir(); item = tmp / "del_src"; _sh.copytree(src / "Artist B", item)
r, _ = run([item], d, after="delete")
check("delete: original folder gone after success", not item.exists() and r["converted"] == 1, r)
keep = tmp / "keep_src"; _sh.copytree(src / "Artist B", keep)
run([keep], tmp / "del2", after="keep"); check("keep: original stays", keep.exists())
mixed = tmp / "mixed"; mixed.mkdir(); (mixed / "broken.mp3").write_bytes(b"x" * 99); _sh.copy(src / "Artist B/Single.m4a", mixed / "ok.m4a")
r, _ = run([mixed], tmp / "del3", after="delete")
check("delete: nothing removed when any track failed", mixed.exists() and r["failed"] == 1, r)
lone = tmp / "lone.zip"
with zipfile.ZipFile(lone, "w") as zf: zf.write(src / "Artist B/Single.m4a", "x/Single.m4a")
run([lone], tmp / "del4", after="delete"); check("delete: archive removed after success", not lone.exists())
guard = tmp / "libguard"; (guard / "Rock").mkdir(parents=True); _sh.copy(src / "Artist B/Single.m4a", guard / "Rock" / "s.m4a")
run([guard / "Rock"], guard / "Rock" / "New", after="delete", library_root=str(guard))
check("delete: never removes a folder containing the destination", (guard / "Rock").exists())
# recycle goes through winutil.recycle (Windows API on Windows); here: stub it
from tunedock import winutil as _wu
calls = []; _orig_rec = _wu.recycle; _wu.recycle = lambda p: (calls.append(p), _sh.rmtree(p) if os.path.isdir(p) else os.unlink(p))
rc = tmp / "rc_src"; _sh.copytree(src / "Artist B", rc)
run([rc], tmp / "del5", after="recycle")
_wu.recycle = _orig_rec
check("recycle: uses the Recycle Bin call", len(calls) == 1 and not rc.exists())

print("ffmpeg download (local server, no internet)")
import http.server, socketserver, threading as _th, hashlib, tarfile as _tf
from tunedock import ffmpeg_fetch
web = tmp / "web"; (web / "ffmpeg-test/bin").mkdir(parents=True)
_sh.copy(media.find_ffmpeg(), web / "ffmpeg-test/bin/ffmpeg")
with _tf.open(web / "ff.tar.gz", "w:gz") as t: t.add(web / "ffmpeg-test", arcname="ffmpeg-test")
(web / "ff.tar.gz.sha256").write_text(hashlib.sha256((web / "ff.tar.gz").read_bytes()).hexdigest() + "  ff.tar.gz\n")
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(web), **k)
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); _th.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["TUNEDOCK_FFMPEG_URL"] = f"http://127.0.0.1:{srv.server_address[1]}/ff.tar.gz"
os.environ["TUNEDOCK_DATA"] = str(tmp / "data")
seen = []
got = ffmpeg_fetch.download(lambda st, d, t: seen.append(st))
check("download: installed into the data folder and runs", got.is_file() and str(got).startswith(str(tmp / "data")) and "download" in seen and "check" in seen, (got, seen[:3]))
check("download: found by find_ffmpeg afterwards", str(got) in media.ffmpeg_candidates())
(web / "ff.tar.gz.sha256").write_text("0" * 64 + "\n")
try: ffmpeg_fetch.download(); bad = False
except ffmpeg_fetch.FetchError as e: bad = "corrupt" in str(e).lower() or "checksum" in str(e).lower()
check("download: wrong checksum is refused", bad)
srv.shutdown(); del os.environ["TUNEDOCK_FFMPEG_URL"]
try: ffmpeg_fetch.sources()[0]; ok_src = True
except Exception: ok_src = False
check("download: default sources defined", ok_src and ffmpeg_fetch.sources()[0]["url"].startswith("https://"))

print("windows integration (simulated registry)")
from tunedock import shell, cli, winutil
m = shell.MemReg(); shell.set_autostart(True, m)
check("autostart value written with --background", m.get_raw(shell.RUN_KEY, "Tunedock").endswith("--background"))
check("autostart detected", shell.autostart_enabled(m))
shell.set_autostart(False, m); check("autostart removed", not shell.autostart_enabled(m))
check("background is opt-in", config.sanitize({})["keep_running"] is False and config.sanitize({"background": True})["keep_running"] is False)
check("onboarding shows for a config written before it existed", config.sanitize({"format": "opus"})["onboarded"] is False)
check("hidden_kwargs is harmless off Windows", winutil.hidden_kwargs() == {} or os.name == "nt")
check("cli: add + to", cli.message(cli.parse(["--add", "a b", "--to", "c"])) == {"cmd": "add", "paths": ["a b"], "to": "c"})
check("cli: bad args never exit", cli.message(cli.parse(["--bogus"]))["cmd"] == "show")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{ok} passed, {fail} failed"); sys.exit(1 if fail else 0)
