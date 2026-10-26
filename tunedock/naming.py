"""Filename templates.

Syntax
  {artist}              a field
  {track:02}            zero-padded number          (also :upper :lower :title)
  {albumartist|artist}  first non-empty field wins   ('literal' allowed: {artist|'Unknown'})
  [ ({year})]           optional group - vanishes when any field inside is empty
  \\{ \\} \\[ \\]          literal brackets
"""
import re
import unicodedata
from functools import lru_cache

FIELDS = {
    "artist": "Artist", "title": "Title", "album": "Album", "albumartist": "Album artist",
    "track": "Track no.", "tracktotal": "Track total", "disc": "Disc no.", "disctotal": "Disc total",
    "year": "Year", "genre": "Genre", "composer": "Composer", "filename": "Original name",
}
PRESETS = [
    ("Artist - Title", "{artist} - {title}"),
    ("01 Title", "{track:02} {title}"),
    ("01 - Artist - Title", "{track:02} - {artist} - {title}"),
    ("Title only", "{title}"),
    ("Full detail", "{artist} - {album} - {track:02} - {title}"),
    ("Multi-disc", "[{disc}-]{track:02} {title}"),
]
FOLDER_PRESETS = [
    ("Artist - Album (Year)", "{albumartist|artist} - {album}[ ({year})]"),
    ("Album (Year)", "{album}[ ({year})]"),
    ("Year - Album", "[{year} - ]{album}"),
]
SAMPLE = {
    "artist": "Nova Lark", "title": "Glass Harbor", "album": "Slow Tides", "albumartist": "Nova Lark",
    "track": "3", "tracktotal": "11", "disc": "1", "disctotal": "2", "year": "2024",
    "genre": "Indie", "composer": "M. Reyes", "filename": "03 glass harbor final",
}


class TemplateError(ValueError):
    pass


def _field(body, pos):
    chain_part, _, spec = body.partition(":")
    chain = []
    for part in chain_part.split("|"):
        part = part.strip()
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "'\"":
            chain.append(("lit", part[1:-1]))
        elif part in FIELDS:
            chain.append(("fld", part))
        elif not part:
            raise TemplateError("Empty field {} at position %d" % pos)
        else:
            raise TemplateError("Unknown field {%s}. Try: %s" % (part, ", ".join(FIELDS)))
    specs = []
    for s in filter(None, (x.strip() for x in spec.split(","))):
        if s.isdigit() or s in ("upper", "lower", "title"):
            specs.append(s)
        else:
            raise TemplateError("Unknown format ':%s' - use a number like :02, or upper / lower / title" % s)
    return ("f", chain, specs)


@lru_cache(maxsize=256)
def parse(template: str):
    stack, i, n = [[]], 0, len(template)
    while i < n:
        c = template[i]
        if c == "\\" and i + 1 < n:
            stack[-1].append(("t", template[i + 1])); i += 2
        elif c == "{":
            j = template.find("}", i)
            if j < 0:
                raise TemplateError("Missing } to close the { at position %d" % (i + 1))
            stack[-1].append(_field(template[i + 1:j], i + 1)); i = j + 1
        elif c == "[":
            if len(stack) > 1:
                raise TemplateError("Optional [ ] groups can't be nested")
            stack.append([]); i += 1
        elif c == "]":
            if len(stack) == 1:
                raise TemplateError("Unexpected ] at position %d" % (i + 1))
            g = stack.pop(); stack[-1].append(("g", g)); i += 1
        elif c == "}":
            raise TemplateError("Unexpected } at position %d" % (i + 1))
        else:
            stack[-1].append(("t", c)); i += 1
    if len(stack) > 1:
        raise TemplateError("Missing ] to close an optional group")
    return stack[0]


def _apply(value, specs):
    for s in specs:
        if s.isdigit():
            if value.isdigit():
                value = value.zfill(int(s))
        elif s == "upper":
            value = value.upper()
        elif s == "lower":
            value = value.lower()
        elif s == "title":
            value = value.title()
    return value


def _walk(nodes, ctx):
    out, ok = [], True
    for node in nodes:
        if node[0] == "t":
            out.append(node[1])
        elif node[0] == "f":
            val = ""
            for kind, v in node[1]:
                val = v if kind == "lit" else (ctx.get(v) or "")
                if val:
                    break
            if not val:
                ok = False
            out.append(_apply(val, node[2]))
        else:
            text, gok = _walk(node[1], ctx)
            if gok:
                out.append(text)
    return "".join(out), ok


def validate(template: str):
    """-> (ok, message)"""
    try:
        parse(template)
        return True, ""
    except TemplateError as e:
        return False, str(e)


_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str, limit: int = 150) -> str:
    name = unicodedata.normalize("NFC", name)
    name = name.replace(": ", " - ").replace("/", "-").replace("\\", "-").replace('"', "'")
    name = re.sub(r'[<>:?*|\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[:limit].rstrip(" .")
    if name.split(".")[0].upper() in _WIN_RESERVED:
        name += "_"
    return name


_EDGE = re.compile(r"^[\s\-\u2013\u2014_.,;:]+|[\s\-\u2013\u2014_,;:]+$")


def render(template: str, ctx: dict, limit: int = 150) -> str:
    """Render and clean. Invalid templates raise TemplateError."""
    text, _ = _walk(parse(template), ctx)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    text = re.sub(r"(\s[-\u2013\u2014]\s*){2,}", " - ", text)
    text = _EDGE.sub("", text)
    return safe_name(text, limit)


def preview(template: str, ctx: dict = None):
    """-> (ok, text_or_error)"""
    try:
        return True, render(template, ctx or SAMPLE)
    except TemplateError as e:
        return False, str(e)


_PUNCT_NUM = re.compile(r"^\s*(\d{1,3})(?:[-.]\d{1,3})?\s*[-._)]+\s*(.+)$")
_SPACE_NUM = re.compile(r"^\s*(\d{2})\s+(.+)$")


def clean_stem(stem: str, track=None) -> str:
    m = _PUNCT_NUM.match(stem)
    if m:
        return m.group(2).strip()
    m = _SPACE_NUM.match(stem)
    if m and (m.group(1).startswith("0") or (track and int(m.group(1)) == track)):
        return m.group(2).strip()
    return stem.strip()


def build_context(meta, src) -> dict:
    """Turn tags (+ the file name when tags are missing) into template values."""
    artists = [a for a in meta.artist if a]
    artist = ", ".join(artists)
    if len(artist) > 80:
        artist = meta.albumartist or artists[0]
    albumartist = meta.albumartist
    title = (meta.title or "").strip()
    stem = src.stem
    if not title:
        title = clean_stem(stem, meta.track)
    first = artists[0] if artists else ""
    for a in (artist, first):
        if a and title.lower().startswith(a.lower() + " - ") and len(title) > len(a) + 3:
            title = title[len(a) + 3:].strip()
            break
    date = meta.date or ""
    m = re.match(r"\s*(\d{4})", date)
    return {
        "artist": artist, "title": title, "album": (meta.album or "").strip(), "albumartist": albumartist,
        "track": str(meta.track) if meta.track else "", "tracktotal": str(meta.tracktotal) if meta.tracktotal else "",
        "disc": str(meta.disc) if meta.disc else "", "disctotal": str(meta.disctotal) if meta.disctotal else "",
        "year": m.group(1) if m else "", "genre": ", ".join(meta.genre), "composer": meta.composer or "",
        "filename": stem,
    }
