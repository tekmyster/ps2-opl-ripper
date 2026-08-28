# Optical engine

Optical drives are enumerated with SetupAPI using
`GUID_DEVINTERFACE_CDROM`. Device handles are opened with `CreateFileW` and
commands use `IOCTL_SCSI_PASS_THROUGH_DIRECT` with the verified x64 structure
layout (56-byte SPTD, aligned data pointer, 32-byte sense buffer).

Commands implemented are TEST UNIT READY, INQUIRY, GET CONFIGURATION, READ
CAPACITY(10), READ TOC, READ(12), and READ CD. DVD layer information comes from
`IOCTL_DVD_READ_STRUCTURE`; capacity is also used when a drive does not return a
layer descriptor. DVD9 is always one ISO across the full logical address space.

Read failures reduce the request from the configured chunk size to smaller
blocks and finally one sector. An unrecoverable LBA aborts and removes the
partial image by default. No zero-filled image is reported as successful.

CD TOC control bits distinguish audio/data tracks. The first raw data sector
distinguishes Mode 1 and Mode 2. Mode 1 payload starts at byte 16; Mode 2 XA
Form 1 validates duplicated subheaders and starts at byte 24. Form 2 is rejected
for OPL ISO conversion. Mixed-mode audio remains in the archival BIN/CUE.

