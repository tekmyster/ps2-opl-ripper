# Testing and qualification

Automated layers:

- parsers, naming, cancellation, CUE times, sector conversion, retries and hashes
- ctypes structure sizes and constants on x64 Windows
- 256 MiB disposable raw-image MBR/exFAT creation and reopen
- elevated dynamic-VHD attach, native Windows exFAT mount, OPL directory check,
  persisted file, detach and reconnect
- mocked optical sector readers and injected unreadable LBAs
- offscreen Qt construction and one-file packaging smoke test

Physical release qualification must use expendable hardware and owned discs:

| Case | Required evidence |
| --- | --- |
| Disposable USB | identity survives refresh, locks work, MBR/exFAT mounts after reconnect, >4 GiB file |
| DVD5 | full ISO, SYSTEM.CNF/game ID, matching copy hash |
| DVD9 | actual dual-layer descriptor/capacity, layer transition, one >4 GiB ISO |
| Data CD | TOC, raw BIN/CUE, converted ISO, game ID and hash |
| Mixed CD | audio tracks retained, explicit choice, validated data ISO when supported |
| Damaged disc | adaptive retries, exact LBA, no false success |
| Non-PS2/empty/audio | conservative classification and no install |
| Clean VMs | Windows 10 and 11, one EXE, no external runtime/tool |

Hardware cases must not be marked passed merely because mocked or VHD tests pass.

