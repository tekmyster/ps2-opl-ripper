# PS2 OPL Ripper 0.1.2 Beta

Version 0.1.2 makes existing PS2-ready USB drives the normal, non-destructive
path.

## Changes

- Detects writable USB drives that already use one MBR partition and exFAT.
- Marks ready drives in the destination dropdown.
- Displays **PS2 READY DRIVE DETECTED** immediately below the dropdown.
- Uses **Use Existing PS2 Drive** to preserve installed games and files while
  creating only missing OPL folders.
- Adds a clearly labeled reformat checkbox that is off by default and resets
  whenever the selected physical drive changes.
- Retains the full device-details warning, system-disk protections, second
  warning, hardware identity revalidation, and typed `ERASE PHYSICALDRIVE N`
  confirmation for every requested reformat.
- Clears a previously prepared destination when the dropdown changes so a rip
  cannot silently continue to the earlier drive.

## Download and safety

Download `PS2OPLRipper.exe` for the single-file Windows x64 application. The
ZIP contains the same executable and its complete license/checksum documents.

The executable is not code-signed, so Windows SmartScreen may display a warning.
Administrator elevation is required. Use the application only for discs you
own. Selecting reformat permanently erases the chosen physical USB device.
