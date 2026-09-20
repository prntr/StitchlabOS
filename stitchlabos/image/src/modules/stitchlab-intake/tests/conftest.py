"""Make the in-repo ``stitchlab_intake`` package importable for tests.

On the target Pi the package lives at /home/pi/stitchlab_intake/ and is
found via the CLI shim's PYTHONPATH. From the repo we need to point at
``filesystem/home/pi`` directly so pytest can import without installation.
"""

import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_PARENT = os.path.normpath(
    os.path.join(_HERE, "..", "filesystem", "home", "pi"),
)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
