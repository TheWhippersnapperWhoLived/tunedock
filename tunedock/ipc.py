"""Single-instance plumbing, standard library only so the 'forwarder' process stays tiny and fast.

Explorer starts one process per selected file. The first process becomes the server; every later
one just hands its paths to it and exits.
"""
import getpass
import hashlib
import os
import tempfile
import threading
import time
from multiprocessing.connection import AuthenticationError, Client, Listener


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return "user"


def _scope():
    """One running copy per user and settings folder, so a test or second profile never talks to the everyday copy."""
    home = os.environ.get("TUNEDOCK_HOME", "")
    return _user() + ("|" + os.path.normcase(os.path.abspath(home)) if home else "")


def _address():
    h = hashlib.sha1(_scope().encode()).hexdigest()[:10]
    if os.name == "nt":
        return r"\\.\pipe\tunedock-" + h, "AF_PIPE"
    return os.path.join(tempfile.gettempdir(), f"tunedock-{h}.sock"), "AF_UNIX"


def _key():
    return hashlib.sha256(("tunedock:" + _scope()).encode()).digest()


def _send_once(msg) -> bool:
    addr, fam = _address()
    try:
        c = Client(addr, family=fam, authkey=_key())
    except (OSError, EOFError, AuthenticationError):
        return False
    try:
        if os.name == "nt":  # this process was just started by Explorer, so it may hand the foreground to the running instance
            from .winutil import allow_foreground
            allow_foreground()
        c.send(msg)
        return True
    except (OSError, EOFError):
        return False
    finally:
        try:
            c.close()
        except OSError:
            pass


def send(msg, timeout=10.0) -> bool:
    """Hand a message to the running instance. Never blocks longer than `timeout` (a wedged server can't hang a right-click)."""
    result = [False]
    t = threading.Thread(target=lambda: result.__setitem__(0, _send_once(msg)), daemon=True)
    t.start()
    t.join(timeout)
    return result[0]


def acquire():
    """Become the server if nobody else is. -> Listener or None."""
    addr, fam = _address()
    for _ in range(2):
        try:
            return Listener(addr, family=fam, authkey=_key())
        except PermissionError:
            return None  # Windows: first pipe instance is taken
        except OSError:
            if fam == "AF_UNIX" and os.path.exists(addr):
                if send({"cmd": "ping"}):
                    return None
                try:
                    os.unlink(addr)  # stale socket from a crash
                except OSError:
                    return None
            else:
                return None
    return None


def forward_or_serve(msg, attempts=60):
    """-> ('sent', None) | ('server', Listener) | ('alone', None)"""
    for _ in range(attempts):
        if send(msg):
            return "sent", None
        lis = acquire()
        if lis is not None:
            return "server", lis
        time.sleep(0.05)
    return "alone", None


class Server(threading.Thread):
    def __init__(self, listener, on_message):
        super().__init__(daemon=True)
        self.listener, self.on_message = listener, on_message

    def run(self):
        while True:
            try:
                conn = self.listener.accept()
            except (OSError, EOFError, AuthenticationError):
                if getattr(self, "stopping", False):
                    return
                time.sleep(0.05)
                continue
            try:
                msg = conn.recv()
                if isinstance(msg, dict):
                    self.on_message(msg)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def stop(self):
        self.stopping = True
        try:
            self.listener.close()
        except OSError:
            pass
