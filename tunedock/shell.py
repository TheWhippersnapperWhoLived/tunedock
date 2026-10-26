"""Explorer right-click integration (per-user, no admin rights, nothing outside HKCU\\Software\\Classes)."""
import hashlib
import os
import sys
from pathlib import Path

from .archives import REGISTER_EXTS
from .media import AUDIO_EXTS

VERB = "Tunedock"
MENU_KEY = r"Tunedock\Menu"
LABEL = "Add to music library"
EXTS = sorted(AUDIO_EXTS) + list(REGISTER_EXTS)
ROOT = Path(__file__).resolve().parent.parent
SEP_BEFORE = 0x20


def launcher_parts():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = Path(sys.executable)
    if os.name == "nt" and exe.with_name("pythonw.exe").exists():
        exe = exe.with_name("pythonw.exe")
    return [str(exe), str(ROOT / "launch_tunedock.pyw")]


def command(to: str = "") -> str:
    base = " ".join('"%s"' % p for p in launcher_parts())
    return base + ' --add "%1"' + (' --to "%s"' % to if to else "")


def icon_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable + ",0"
    ico = ROOT / "assets" / "tunedock.ico"
    return str(ico) if ico.exists() else ""


def bases():
    return ["Directory"] + [r"SystemFileAssociations\%s" % e for e in EXTS]


def plan(cfg: dict, library_root: str, folders: list):
    """The complete set of registry values we want: [(key under HKCU\\Software\\Classes, name, value)]."""
    ops, submenu = [], cfg.get("menu_mode") == "submenu"
    icon = icon_path()
    for b in bases():
        k = r"%s\shell\%s" % (b, VERB)
        ops += [(k, "MUIVerb", LABEL), (k, "MultiSelectModel", "Player")]
        if icon:
            ops.append((k, "Icon", icon))
        if submenu:
            ops.append((k, "ExtendedSubCommandsKey", MENU_KEY))
        else:
            ops.append((k + r"\command", "", command()))
    if submenu:
        s = MENU_KEY + r"\shell"
        ops += [(s + r"\00_choose", "MUIVerb", "Choose folder\u2026"), (s + r"\00_choose\command", "", command())]
        chosen = cfg.get("menu_folders") or []
        names = [f for f in folders if not chosen or f in chosen][:30]
        for i, name in enumerate(names):
            k = s + r"\10_%03d" % i
            ops.append((k, "MUIVerb", name.replace("&", "&&")))
            if i == 0:
                ops.append((k, "CommandFlags", SEP_BEFORE))
            ops.append((k + r"\command", "", command(str(Path(library_root) / name))))
    return ops


def signature(ops) -> str:
    return hashlib.sha1(repr(ops).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ registry backends
class WinReg:
    def __init__(self):
        import winreg
        self.w = winreg
        self.root = winreg.HKEY_CURRENT_USER

    def set(self, key, name, value):
        w = self.w
        with w.CreateKeyEx(self.root, r"Software\Classes\%s" % key, 0, w.KEY_WRITE) as h:
            if isinstance(value, int):
                w.SetValueEx(h, name, 0, w.REG_DWORD, value)
            else:
                w.SetValueEx(h, name, 0, w.REG_SZ, value)

    def get(self, key, name):
        w = self.w
        try:
            with w.OpenKey(self.root, r"Software\Classes\%s" % key) as h:
                return w.QueryValueEx(h, name)[0]
        except OSError:
            return None

    def set_raw(self, path, name, value):
        w = self.w
        with w.CreateKeyEx(self.root, path, 0, w.KEY_WRITE) as h:
            w.SetValueEx(h, name, 0, w.REG_SZ, value)

    def get_raw(self, path, name):
        w = self.w
        try:
            with w.OpenKey(self.root, path) as h:
                return w.QueryValueEx(h, name)[0]
        except OSError:
            return None

    def del_raw(self, path, name):
        w = self.w
        try:
            with w.OpenKey(self.root, path, 0, w.KEY_WRITE) as h:
                w.DeleteValue(h, name)
        except OSError:
            pass

    def delete_tree(self, key):
        w = self.w
        path = r"Software\Classes\%s" % key
        try:
            with w.OpenKey(self.root, path, 0, w.KEY_READ | w.KEY_WRITE) as h:
                while True:
                    try:
                        sub = w.EnumKey(h, 0)
                    except OSError:
                        break
                    self.delete_tree(r"%s\%s" % (key, sub))
            w.DeleteKey(self.root, path)
        except OSError:
            pass


class MemReg:
    """In-memory stand-in, used by the tests."""
    def __init__(self):
        self.d = {}

    def set(self, key, name, value):
        self.d[(key.lower(), name)] = value

    def get(self, key, name):
        return self.d.get((key.lower(), name))

    def set_raw(self, path, name, value):
        self.d[("raw:" + path.lower(), name)] = value

    def get_raw(self, path, name):
        return self.d.get(("raw:" + path.lower(), name))

    def del_raw(self, path, name):
        self.d.pop(("raw:" + path.lower(), name), None)

    def delete_tree(self, key):
        k = key.lower()
        for kk in [x for x in self.d if x[0] == k or x[0].startswith(k + "\\")]:
            del self.d[kk]


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    return " ".join('"%s"' % p for p in launcher_parts()) + " --background"


def set_autostart(on: bool, reg=None):
    reg = reg or WinReg()
    if on:
        reg.set_raw(RUN_KEY, "Tunedock", autostart_command())
    else:
        reg.del_raw(RUN_KEY, "Tunedock")


def autostart_enabled(reg=None) -> bool:
    try:
        reg = reg or WinReg()
    except ImportError:
        return False
    return reg.get_raw(RUN_KEY, "Tunedock") is not None


def create_shortcut(lnk, target, args="", workdir="", icon="", desc="Tunedock") -> str:
    """Create a .lnk without showing any window. Returns '' or an error message."""
    if os.name != "nt":
        return "Shortcuts are only available on Windows."
    import subprocess
    from .winutil import hidden_kwargs
    q = lambda t: str(t).replace("'", "''")
    lnk = Path(lnk)
    lnk.parent.mkdir(parents=True, exist_ok=True)
    cmd = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.Arguments='%s'; "
           "$s.WorkingDirectory='%s'; $s.IconLocation='%s'; $s.Description='%s'; $s.Save()") % (
        q(lnk), q(target), q(args), q(workdir), q(icon), q(desc))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                            "-Command", cmd], capture_output=True, stdin=subprocess.DEVNULL, timeout=30, **hidden_kwargs())
        return "" if r.returncode == 0 and lnk.exists() else "Couldn't create the shortcut."
    except (OSError, subprocess.SubprocessError) as e:
        return f"Couldn't create the shortcut ({e.__class__.__name__})."


def create_start_shortcut() -> str:
    """Start-menu shortcut that starts Tunedock without any console window."""
    parts = launcher_parts()
    lnk = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Tunedock.lnk"
    ico = ROOT / "assets" / "tunedock.ico"
    icon = parts[0] + ",0" if getattr(sys, "frozen", False) else str(ico)
    return create_shortcut(lnk, parts[0], " ".join('"%s"' % p for p in parts[1:]), str(ROOT), icon)


def _notify():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass


def uninstall(reg=None):
    reg = reg or WinReg()
    for b in bases():
        reg.delete_tree(r"%s\shell\%s" % (b, VERB))
    reg.delete_tree("Tunedock")
    _notify()


def install(cfg, library_root, folders, reg=None):
    reg = reg or WinReg()
    ops = plan(cfg, library_root, folders)
    for b in bases():  # start clean so switching modes can't leave stale entries
        reg.delete_tree(r"%s\shell\%s" % (b, VERB))
    reg.delete_tree("Tunedock")
    for key, name, value in ops:
        reg.set(key, name, value)
    reg.set("Tunedock", "Signature", signature(ops))
    _notify()


def is_installed(reg=None) -> bool:
    try:
        reg = reg or WinReg()
    except ImportError:
        return False
    return reg.get(r"Directory\shell\%s" % VERB, "MUIVerb") is not None


def needs_refresh(cfg, library_root, folders, reg=None) -> bool:
    try:
        reg = reg or WinReg()
    except ImportError:
        return False
    return is_installed(reg) and reg.get("Tunedock", "Signature") != signature(plan(cfg, library_root, folders))


# ------------------------------------------------------------------ .reg export (for people who want to see / hand-apply it)
def _esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def export_reg(ops, path):
    lines, last = ["Windows Registry Editor Version 5.00", ""], None
    for key, name, value in ops:
        if key != last:
            lines += ["", r"[HKEY_CURRENT_USER\Software\Classes\%s]" % key]
            last = key
        n = "@" if name == "" else '"%s"' % _esc(name)
        lines.append("%s=%s" % (n, "dword:%08x" % value if isinstance(value, int) else '"%s"' % _esc(value)))
    Path(path).write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-16"))


def export_uninstall_reg(path):
    lines = ["Windows Registry Editor Version 5.00", ""]
    for b in bases():
        lines.append(r"[-HKEY_CURRENT_USER\Software\Classes\%s\shell\%s]" % (b, VERB))
    lines.append(r"[-HKEY_CURRENT_USER\Software\Classes\Tunedock]")
    Path(path).write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-16"))
