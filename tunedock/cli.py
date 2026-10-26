"""Command line, kept dependency-light so the 'forwarder' process starts in a blink."""
import argparse


def parse(argv):
    ap = argparse.ArgumentParser(prog="tunedock", add_help=True)
    ap.add_argument("--add", action="append", default=[], metavar="PATH")
    ap.add_argument("--to", default="", metavar="FOLDER", help="add straight to this folder, no window")
    ap.add_argument("--background", action="store_true", help="start quietly with no window")
    ap.add_argument("--quit", action="store_true", help="close a running Tunedock")
    ap.add_argument("paths", nargs="*")
    args, _unknown = ap.parse_known_args(argv)
    return args


def message(args) -> dict:
    paths = [p for p in args.add + args.paths if p]
    if args.quit:
        return {"cmd": "quit"}
    if paths:
        return {"cmd": "add", "paths": paths, "to": args.to or None}
    return {"cmd": "idle"} if args.background else {"cmd": "show"}
