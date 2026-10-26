"""Material-You style dynamic colour from one seed colour.

Tonal palettes are built in OKLCH (perceptual, tiny, no dependencies) and mapped to the Material 3
colour roles. Not bit-identical to Google's HCT, but the same structure and tone contrast steps.
"""
import math
import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = max(0.0, c)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(h):
    m = _HEX.match(h)
    r, g, b = (_lin(int(m.group(1)[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    mm = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * mm - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * mm + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * mm - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _rgb(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def _in_gamut(rgb):
    return all(-0.0005 <= v <= 1.0005 for v in rgb)


def tone_L(t):
    y = ((t + 16) / 116) ** 3 if t > 8 else t / 903.3
    return y ** (1 / 3)


def color(hue, chroma, tone):
    """Hex colour at CIE-L*-style tone (0 black .. 100 white), chroma reduced until it fits sRGB."""
    L = tone_L(tone)
    if tone >= 99.5:
        chroma = 0
    lo, hi = 0.0, chroma
    if not _in_gamut(_rgb(L, hi, hue)):
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _in_gamut(_rgb(L, mid, hue)) else (lo, mid)
        hi = lo
    r, g, b = (max(0, min(1, _gam(v))) for v in _rgb(L, hi, hue))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def luminance(h):
    m = _HEX.match(h)
    r, g, b = (_lin(int(m.group(1)[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def scheme(seed="#6750A4", dark=False) -> dict:
    if not _HEX.match(seed or ""):
        seed = "#6750A4"
    _, c, h = hex_to_oklch(seed)
    pc = c if c < 0.02 else max(0.10, min(c, 0.19))
    P = lambda t: color(h, pc, t)
    S = lambda t: color(h, min(0.045, pc * 0.35), t)
    T = lambda t: color(h + 60, max(0.07, min(0.1, pc * 0.6)) if pc >= 0.02 else 0.02, t)
    N = lambda t: color(h, 0.011 if pc >= 0.02 else 0.0, t)
    NV = lambda t: color(h, 0.02 if pc >= 0.02 else 0.0, t)
    E = lambda t: color(29, 0.19, t)
    if not dark:
        s = dict(
            primary=P(40), onPrimary=P(100), primaryContainer=P(90), onPrimaryContainer=P(10),
            secondary=S(40), onSecondary=S(100), secondaryContainer=S(90), onSecondaryContainer=S(10),
            tertiary=T(40), onTertiary=T(100), tertiaryContainer=T(90), onTertiaryContainer=T(10),
            error=E(40), onError=E(100), errorContainer=E(90), onErrorContainer=E(10),
            background=N(98), onBackground=N(10), surface=N(98), onSurface=N(10),
            surfaceVariant=NV(90), onSurfaceVariant=NV(30), outline=NV(50), outlineVariant=NV(80),
            surfaceDim=N(87), surfaceBright=N(98), surfaceContainerLowest=N(100), surfaceContainerLow=N(96),
            surfaceContainer=N(94), surfaceContainerHigh=N(92), surfaceContainerHighest=N(90),
            inverseSurface=N(20), inverseOnSurface=N(95), inversePrimary=P(80))
    else:
        s = dict(
            primary=P(80), onPrimary=P(20), primaryContainer=P(30), onPrimaryContainer=P(90),
            secondary=S(80), onSecondary=S(20), secondaryContainer=S(30), onSecondaryContainer=S(90),
            tertiary=T(80), onTertiary=T(20), tertiaryContainer=T(30), onTertiaryContainer=T(90),
            error=E(80), onError=E(20), errorContainer=E(30), onErrorContainer=E(90),
            background=N(6), onBackground=N(90), surface=N(6), onSurface=N(90),
            surfaceVariant=NV(30), onSurfaceVariant=NV(80), outline=NV(60), outlineVariant=NV(30),
            surfaceDim=N(6), surfaceBright=N(24), surfaceContainerLowest=N(4), surfaceContainerLow=N(10),
            surfaceContainer=N(12), surfaceContainerHigh=N(17), surfaceContainerHighest=N(22),
            inverseSurface=N(90), inverseOnSurface=N(20), inversePrimary=P(40))
    s["scrim"] = "#000000"
    s["shadow"] = "#000000"
    return s


SWATCHES = ["#6750A4", "#0B6BCB", "#00796B", "#2E7D32", "#B26A00", "#C2185B", "#B3261E", "#5C6BC0"]
