"""Runtime license inventory and bundled-notice loading."""

from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import dataclass
from pathlib import Path

from ps2ripper import __version__


@dataclass(frozen=True, slots=True)
class LicenseDocument:
    """One user-visible application or third-party license document."""

    identifier: str
    title: str
    component: str
    version: str
    license_name: str
    homepage: str
    notice: str
    license_path: str

    def display_text(self) -> str:
        heading = [
            self.component,
            "=" * len(self.component),
            f"Version: {self.version}",
            f"License: {self.license_name}",
        ]
        if self.homepage:
            heading.append(f"Project: {self.homepage}")
        if self.notice:
            heading.extend(("", self.notice.strip()))
        heading.extend(("", "Full license text", "-----------------", _read_resource(self.license_path)))
        return "\n".join(heading).strip() + "\n"


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


def _distribution_license(distribution_name: str, suffix: str) -> Path | None:
    """Locate a development-environment license when running from source."""

    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    normalized_suffix = suffix.replace("\\", "/").lower()
    for item in distribution.files or ():
        if str(item).replace("\\", "/").lower().endswith(normalized_suffix):
            path = Path(distribution.locate_file(item))
            if path.is_file():
                return path
    return None


def _fallback_path(relative_path: str) -> Path | None:
    if relative_path == "licenses/python/LICENSE.txt":
        candidate = Path(sys.base_prefix) / "LICENSE.txt"
        return candidate if candidate.is_file() else None
    if relative_path == "licenses/pyinstaller/COPYING.txt":
        return _distribution_license("pyinstaller", "licenses/COPYING.txt")
    return None


def _read_resource(relative_path: str) -> str:
    path = _resource_root() / Path(relative_path)
    if not path.is_file():
        path = _fallback_path(relative_path) or path
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return f"License text could not be loaded from {relative_path}: {exc}"


_DOCUMENTS = (
    LicenseDocument(
        identifier="ps2ripper",
        title="PS2 OPL Ripper — GPL 3.0 or later",
        component="PS2 OPL Ripper",
        version=__version__,
        license_name="GNU General Public License 3.0 or later",
        homepage="",
        notice=(
            "PS2 OPL Ripper is free software. It is provided without warranty. The source tree "
            "contains the complete application source and reproducible build instructions."
        ),
        license_path="LICENSE.txt",
    ),
    LicenseDocument(
        identifier="fattools",
        title="FATtools — GPL 3.0",
        component="FATtools",
        version="1.1.23",
        license_name="GNU General Public License 3.0",
        homepage="https://github.com/maxpat78/FATtools",
        notice=(
            "Copyright (C) 2012–2025 maxpat78. PS2 OPL Ripper vendors the FATtools source. "
            "The vendored copy contains two documented patches: exFAT PartitionOffset is "
            "written in sectors, and the OPL data partition is not marked active."
        ),
        license_path="LICENSE.txt",
    ),
    LicenseDocument(
        identifier="qt-for-python",
        title="Qt for Python / PySide6 — LGPL 3.0",
        component="Qt for Python (PySide6, PySide6 Essentials/Addons, shiboken6, Qt 6)",
        version="6.11.2",
        license_name="LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only (LGPL option used)",
        homepage="https://pyside.org",
        notice=(
            "Copyright The Qt Company Ltd and Qt contributors. The Qt libraries are loaded "
            "as separate DLLs extracted by the single-file launcher. Qt and the Qt logo are "
            "trademarks of The Qt Company Ltd."
        ),
        license_path="licenses/LGPL-3.0-only.txt",
    ),
    LicenseDocument(
        identifier="pycdlib",
        title="pycdlib — LGPL 2.1",
        component="pycdlib",
        version="1.20.0",
        license_name="GNU Lesser General Public License 2.1 only",
        homepage="https://github.com/clalancette/pycdlib",
        notice="Copyright Chris Lalancette and pycdlib contributors.",
        license_path="licenses/pycdlib-LGPL-2.1.txt",
    ),
    LicenseDocument(
        identifier="hexdump",
        title="hexdump — Public Domain",
        component="hexdump",
        version="3.3",
        license_name="Public Domain",
        homepage="https://bitbucket.org/techtonik/hexdump/",
        notice=(
            "The package metadata and upstream README designate this work as Public Domain. "
            "Credits: anatoly techtonik, George Schizas, and Ian Land."
        ),
        license_path="licenses/hexdump-3.3-PUBLIC-DOMAIN.txt",
    ),
    LicenseDocument(
        identifier="cpython",
        title="CPython — PSF License",
        component="CPython",
        version="3.13.14",
        license_name="Python Software Foundation License Version 2 and bundled notices",
        homepage="https://www.python.org/",
        notice=(
            "Copyright Python Software Foundation and contributors. The complete CPython "
            "license file below also contains notices for software incorporated by CPython."
        ),
        license_path="licenses/python/LICENSE.txt",
    ),
    LicenseDocument(
        identifier="pyinstaller",
        title="PyInstaller bootloader — GPL exception",
        component="PyInstaller bootloader and run-time hooks",
        version="6.22.2",
        license_name="GPL-2.0-or-later WITH Bootloader-exception; run-time hooks Apache-2.0",
        homepage="https://pyinstaller.org/",
        notice=(
            "Copyright PyInstaller Development Team and earlier contributors. PyInstaller is "
            "a build dependency; its compiled bootloader and run-time hooks are present in the "
            "single executable under the terms reproduced below."
        ),
        license_path="licenses/pyinstaller/COPYING.txt",
    ),
)


def load_license_documents() -> tuple[LicenseDocument, ...]:
    """Return the pinned inventory of components shipped in the executable."""

    return _DOCUMENTS


def third_party_overview() -> str:
    """Return the human-readable distribution notice included with the executable."""

    return _read_resource("THIRD_PARTY_NOTICES.md")
