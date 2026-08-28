# Architecture

The GUI depends on orchestration services, never directly on byte layouts.

`ui` → `core.workflow` → `windows`, `optical`, `imaging`, `storage`, `opl`, `ps2`

- `windows`: SetupAPI enumeration, Win32 handles, storage IOCTLs, volume locks,
  SPTI, optical ejection, virtual-disk integration.
- `storage`: FATtools-backed MBR/exFAT creation and independently checked boot
  fields.
- `optical`: profile/media classification and ISO9660/SYSTEM.CNF inspection.
- `imaging`: sequential DVD reads, raw CD archive, mode-aware CD conversion,
  retry logic, SHA-256, copy and structural verification.
- `ps2`: bounded SYSTEM.CNF parser and safe OPL filenames.
- `opl`: non-destructive folder and destination layout management.

All long operations use worker threads and cooperative cancellation. Partition
table/filesystem metadata creation runs inside a non-cancellable critical
section, after which a pending cancellation is acknowledged.

