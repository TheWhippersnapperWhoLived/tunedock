"""Small Windows-only helpers (all no-ops elsewhere): hidden child processes, window focus, taskbar identity."""
import os

IS_WIN = os.name == "nt"
APP_ID = "Tunedock.MusicLibrary"


def hidden_kwargs() -> dict:
    """subprocess kwargs that never show a console window, not even for a flash."""
    if not IS_WIN:
        return {}
    import subprocess
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return {"creationflags": 0x08000000, "startupinfo": si}  # CREATE_NO_WINDOW


def set_app_id():
    """Own taskbar identity, so the taskbar shows Tunedock's icon instead of Python's."""
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def allow_foreground():
    """Called by the short-lived process Explorer started: lets the already-running Tunedock take the focus."""
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_uint(-1).value)  # ASFW_ANY
        except Exception:
            pass


def force_foreground(hwnd: int) -> bool:
    """Bring a window to the front and give it keyboard focus, past Windows' focus-stealing prevention."""
    if not IS_WIN or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.IsIconic.argtypes = [wintypes.HWND]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.BringWindowToTop.argtypes = [wintypes.HWND]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
        u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        h = wintypes.HWND(hwnd)
        if u.IsIconic(h):
            u.ShowWindow(h, 9)  # SW_RESTORE
        fg = u.GetForegroundWindow()
        cur = k.GetCurrentThreadId()
        fg_tid = u.GetWindowThreadProcessId(fg, None) if fg else 0
        attached = bool(fg_tid and fg_tid != cur and u.AttachThreadInput(cur, fg_tid, True))
        try:
            u.BringWindowToTop(h)
            u.SetForegroundWindow(h)
        finally:
            if attached:
                u.AttachThreadInput(cur, fg_tid, False)
        if u.GetForegroundWindow() != h.value:   # last resort: a synthetic Alt press unlocks SetForegroundWindow
            u.keybd_event(0x12, 0, 0, 0)
            u.keybd_event(0x12, 0, 2, 0)
            u.SetForegroundWindow(h)
        return True
    except Exception:
        return False


def recycle(path: str):
    """Move a file or folder to the Recycle Bin. Raises OSError on failure."""
    if not IS_WIN:
        try:
            from send2trash import send2trash
        except ImportError:
            raise OSError("no Recycle Bin available here")
        send2trash(path)
        return
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    op = SHFILEOPSTRUCTW()
    op.wFunc = 3                      # FO_DELETE
    op.pFrom = os.path.abspath(path) + "\0"   # the API wants a double-null-terminated list
    op.fFlags = 0x40 | 0x10 | 0x400 | 0x4      # ALLOWUNDO | NOCONFIRMATION | NOERRORUI | SILENT
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise OSError(f"Recycle Bin refused it (code {rc})")


def recycle_available() -> bool:
    if IS_WIN:
        return True
    try:
        import send2trash  # noqa: F401
        return True
    except ImportError:
        return False
