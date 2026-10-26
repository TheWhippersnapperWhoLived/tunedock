# Starts Tunedock (no console window). Named differently from the "tunedock" package on purpose: on Windows a .pyw file counts as an
# importable module, and a launcher called tunedock.pyw clashes with the package.
# Fast path: if Tunedock is already running, hand it the request and leave in a few milliseconds.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tunedock import cli, ipc

_msg = cli.message(cli.parse(sys.argv[1:]))
if ipc.send(_msg) or _msg["cmd"] == "quit":
    sys.exit(0)

from tunedock.app import main

sys.exit(main())
