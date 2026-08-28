"""Prefer the exact Qt/Shiboken DLLs bundled by PyInstaller on Windows.

Some desktop software adds a different Qt build to PATH. In one-file mode the
executable directory is not the extraction directory, so an incompatible
Qt6Core.dll could otherwise win Windows' dependency search.
"""

import os
import sys

_dll_handles = []

if sys.platform == "win32" and hasattr(sys, "_MEIPASS"):
    bundle_root = sys._MEIPASS
    dll_directories = [
        os.path.join(bundle_root, "PySide6"),
        os.path.join(bundle_root, "shiboken6"),
        bundle_root,
    ]
    os.environ["PATH"] = os.pathsep.join(dll_directories + [os.environ.get("PATH", "")])
    for directory in dll_directories:
        if os.path.isdir(directory):
            _dll_handles.append(os.add_dll_directory(directory))
