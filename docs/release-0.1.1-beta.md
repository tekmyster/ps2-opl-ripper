# PS2 OPL Ripper 0.1.1 Beta

This is the first public beta of PS2 OPL Ripper, a self-contained Windows 10/11
x64 application for preparing an MBR/exFAT Open PS2 Loader USB drive and making
verified personal backups of owned PlayStation 2 discs.

## Highlights

- Native Windows USB physical-disk enumeration and conservative system-disk
  protection
- Typed destructive confirmation and physical-device identity revalidation
- MBR plus one primary exFAT partition using vendored FATtools
- Native Windows optical access without ImgBurn, PowerShell, WMIC, or diskpart
- PS2 DVD5/DVD9 ISO ripping and supported CD BIN/CUE plus OPL ISO conversion
- SHA-256 source/destination verification and structural ISO validation
- Help menu with About and complete in-application runtime license notices

## Download

Download `PS2OPLRipper.exe` for the single-file application. The Windows x64
ZIP contains the same executable plus the license and checksum documents.

The executable is not code-signed, so Windows SmartScreen may display a warning.
Administrator elevation is required for raw disk and optical operations.

## Beta qualification note

The automated suite passes 33 tests, and the disposable native VHD integration
test has passed on Windows. Real optical drives and disposable USB hardware vary
by controller and firmware; please report failures with the application log and
device model. Do not include full storage serial numbers in public reports.

Use this application only to back up discs you own. Initializing a selected USB
drive erases all partitions and files on that physical device.
