# Changelog

All notable changes to PS2 OPL Ripper are documented here.

## 0.1.2 Beta — 2026-09-01

- Added automatic recognition and labeling of existing writable MBR/exFAT PS2
  drives.
- Added the bold `PS2 READY DRIVE DETECTED` destination status banner.
- Added a default-off reformat checkbox that resets whenever drive selection
  changes and retains the existing warning plus typed-confirmation safeguards.
- Existing PS2 drives now use an explicit preservation path that reuses games,
  creates only missing OPL folders, and never formats the drive.
- Changing destination drives now invalidates the previously prepared target,
  preventing a rip from continuing to an earlier hidden selection.

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
