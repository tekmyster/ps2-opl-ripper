# PS2 OPL Ripper

PS2 OPL Ripper is a native-looking Windows desktop application that prepares a USB
HDD/SSD for Open PS2 Loader (OPL), creates personal backup images from owned
PlayStation 2 discs, validates them, copies them into the correct `DVD` or `CD`
folder, and verifies the destination with SHA-256.

Current release: **0.1.2 Beta**. The packaged runtime is one file:
`PS2OPLRipper.exe`. It does not invoke
PowerShell, WMIC, diskpart, format.com, ImgBurn, 7-Zip, Java, WSL, or a separate
Python installation. Windows APIs are called directly with `ctypes`.

Project home: <https://github.com/tekmyster/ps2-opl-ripper>

Download releases: <https://github.com/tekmyster/ps2-opl-ripper/releases>

## Safety warning

**Initializing a USB drive erases every partition and file on that physical
drive.** PS2 OPL Ripper never chooses or formats a disk automatically. It identifies
the selected `PhysicalDrive`, displays its hardware and partition details,
blocks Windows/system/pagefile/EFI/recovery/active-boot disks, locks all volumes,
revalidates hardware identity, and requires the user to type a confirmation such
as `ERASE PHYSICALDRIVE 3`.

## Supported platform and media

- Windows 10 or Windows 11, x86-64
- Administrator access (declared in the executable manifest)
- USB HDD/SSD destination using one MBR primary exFAT partition
- OPL versions with exFAT USB support
- PS2 DVD5 and DVD9 as one 2048-byte-sector ISO
- Single-session PS2 data CDs using MODE1/2352 or MODE2 Form 1/2352 sectors
- Mixed-mode CD main-channel BIN/CUE archival; an OPL data ISO is created only
  when sector conversion and structural validation succeed

Mode 2 Form 2 sectors cannot be represented by the supported OPL 2048-byte ISO
conversion and cause a conservative failure. Standard TOC-based BIN/CUE output
preserves main-channel track data and INDEX 01 positions; it is not a forensic
subchannel image. Multi-session CDs and 4Kn destination drives are rejected in
this release rather than guessed.

## Run

Download or copy `PS2OPLRipper.exe`, launch it, approve the Administrator prompt,
and follow the three numbered sections. No internet connection is used.

Logs are written to:

`%LOCALAPPDATA%\PS2OPLRipper\Logs\PS2OPLRipper.log`

Full storage serial numbers are used in memory for identity verification but
are stored in logs only as a short SHA-256 fingerprint.

When an existing writable MBR/exFAT USB drive is detected, the destination
section displays **PS2 READY DRIVE DETECTED**. Select **Use Existing PS2 Drive**
to preserve its games and create only missing OPL folders. Reformatting is an
optional checkbox that is off by default, clears whenever drive selection
changes, and still requires the physical-drive typed confirmation.

## Build from source

Install CPython 3.13.14 x86-64 on Windows, then run from an ordinary PowerShell
prompt:

```powershell
.\build.ps1 -Clean
```

The script creates/reuses `.venv-build`, installs the exact versions in
`requirements-lock.txt`, runs the tests, and builds:

`dist\PS2OPLRipper.exe`

To rebuild using an already populated environment:

```powershell
.\build.ps1 -Clean -SkipInstall
```

The executable is intentionally unsigned until a project code-signing
certificate is supplied. Windows SmartScreen may therefore warn on first run.

## Testing

Normal test run:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv-build\Scripts\python.exe -m pytest -q
```

Elevated disposable-VHD mount test:

```powershell
$env:PS2RIPPER_RUN_VHD_TESTS = '1'
.\.venv-build\Scripts\python.exe -m pytest tests\integration\test_vhd_mount.py -q
```

The VHD test never touches physical USB hardware. Disposable-hardware and real
disc qualification still require the hardware matrix in `docs/testing.md`.

## Reporting a failed disc

Do not repeatedly stress a damaged disc. Preserve the log, record the optical
drive model, disc type, reported LBA and sense data, and whether another drive
can read the same owned disc. Do not post full storage serial numbers.

## Licensing

PS2 OPL Ripper is GPL-3.0-or-later because it vendors FATtools. See
`THIRD_PARTY_NOTICES.md`. Source for the exact bundled FATtools version and the
two reviewed patches is present under `src/FATtools`. In the application, open
**Help > Licenses and third-party notices** to read the complete runtime
component inventory, attributions, and full license texts.
