# Changelog

All notable changes to PS2 OPL Ripper are documented here.

## 0.1.1 Beta — 2026-08-28

- Added a Help menu with About and Licenses and third-party notices dialogs.
- Added an in-application inventory of every runtime package shipped in the
  executable, with pinned versions, attribution, and complete license terms.
- Adopted the PS2 OPL Ripper product name and `PS2OPLRipper.exe` filename.
- Published the first public beta source and Windows x64 binary release.

## 0.1.0 — 2026-08-28

- Implemented native Windows USB disk enumeration and safety validation.
- Added guarded MBR/exFAT initialization using vendored FATtools.
- Added native Windows optical access, PS2 DVD and supported CD imaging,
  structural validation, SHA-256 copy verification, cancellation, and GUI flow.
- Added unit, image, mocked-device, UI, and disposable VHD tests.
