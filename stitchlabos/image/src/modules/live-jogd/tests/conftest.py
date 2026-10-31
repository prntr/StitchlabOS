"""Make the in-repo live_jogd modules importable for tests.

On the Pi the daemon runs from /home/pi/live_jogd with that directory as
its working directory; from the repo we point at filesystem/home/pi/live_jogd.
"""

import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "filesystem", "home", "pi", "live_jogd"),
)
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)
