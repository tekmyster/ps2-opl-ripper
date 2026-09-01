# PS2 OPL Ripper license and third-party notices

This inventory covers code and runtime components shipped inside
`PS2OPLRipper.exe`. Test-only packages such as pytest, Hypothesis, coverage, and
Ruff are not shipped in the application and are therefore not included in the
runtime notice list.

| Component | Version | License used by this distribution |
| --- | --- | --- |
| PS2 OPL Ripper | 0.1.2 Beta | GPL-3.0-or-later |
| FATtools | 1.1.23 | GPL-3.0 |
| Qt for Python: PySide6, Essentials, Addons, shiboken6, and Qt | 6.11.2 | LGPL-3.0-only option |
| pycdlib | 1.20.0 | LGPL-2.1-only |
| hexdump | 3.3 | Public Domain |
| CPython | 3.13.14 | Python Software Foundation License Version 2 and bundled notices |
| PyInstaller bootloader and run-time hooks | 6.22.2 | GPL-2.0-or-later with Bootloader Exception; run-time hooks under Apache-2.0 |

## FATtools modifications

PS2 OPL Ripper vendors the complete FATtools 1.1.23 Python source in `src/FATtools`.
Two reviewed changes are applied: exFAT `PartitionOffset` is written in sectors,
and the OPL data partition is not marked active.

## Complete terms

The Help > Licenses and third-party notices dialog in the application displays
this inventory, the component-specific attribution, and the complete applicable
license texts. The source distribution also contains:

- `LICENSE.txt` — GNU GPL version 3
- `licenses/LGPL-3.0-only.txt` — GNU LGPL version 3
- `licenses/pycdlib-LGPL-2.1.txt` — GNU LGPL version 2.1
- `licenses/hexdump-3.3-PUBLIC-DOMAIN.txt` — hexdump public-domain statement
- CPython's complete `LICENSE.txt`, collected from the pinned Python 3.13.14
  build during packaging
- PyInstaller's complete `COPYING.txt`, collected from PyInstaller 6.22.2
  during packaging

PySide6 package metadata offers LGPL-3.0-only, GPL-2.0-only, GPL-3.0-only, and
commercial licensing alternatives. This open-source build uses the LGPL 3.0
option. Qt and the Qt logo are trademarks of The Qt Company Ltd.

Microsoft Visual C++ redistributable DLLs supplied with the Qt for Python wheel
are Microsoft components and are redistributed under Microsoft's applicable
Visual Studio license terms; they are not covered by the open-source licenses
listed above.
