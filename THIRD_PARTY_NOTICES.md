# Third-party software

Tunedock's own code is MIT licensed (see `LICENSE`). The downloadable `Tunedock.exe` also contains the libraries
below, each under its own license. Their source code is available from the links given.

| Component | License | Source |
| --- | --- | --- |
| mutagen (audio tags) | GPL-2.0-or-later | https://github.com/quodlibet/mutagen |
| PySide6 / Qt for Python and shiboken6 (interface) | LGPL-3.0, GPL-2.0 or GPL-3.0 | https://code.qt.io/cgit/pyside/pyside-setup.git |
| py7zr (.7z support) and its dependencies | LGPL-2.1-or-later (dependencies vary) | https://github.com/miurahr/py7zr |
| PyInstaller (builds the exe) | GPL-2.0-or-later with a special exception for the programs it builds | https://github.com/pyinstaller/pyinstaller |
| Python | PSF License | https://www.python.org |

**What this means for the exe.** Because mutagen is GPL-2.0-or-later, the combined `Tunedock.exe` is distributed under
the GPL as a whole. The complete source for every build is this repository (each release is tagged to its commit).
If you only use the source code on its own, the MIT license in `LICENSE` applies to Tunedock's code.

**ffmpeg is not included.** Tunedock finds an ffmpeg you already have, or downloads one the first time you convert
music (from gyan.dev or the BtbN GitHub builds). ffmpeg is LGPL/GPL software with its own terms: https://ffmpeg.org/legal.html
