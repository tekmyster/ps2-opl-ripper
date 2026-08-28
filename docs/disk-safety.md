# Disk safety invariants

1. No disk is selected automatically.
2. A drive letter is presentation metadata, never physical identity.
3. Destructive identity includes instance ID, serial, model, capacity, logical
   sector size, USB status, and current PhysicalDrive number.
4. The running Windows volume, active pagefiles, boot/active partitions, EFI,
   Microsoft reserved, recovery, spanned/ambiguous volumes, 4Kn disks, non-USB
   disks, and over-2-TiB 512-sector MBR targets are blocked.
5. Confirmation contains the actual physical disk number.
6. Every volume is locked before any is dismounted. Locks remain open throughout
   raw writes. Failure to lock stops the operation.
7. Identity and safety are re-enumerated after locks are acquired and immediately
   before the partition writer runs.
8. FATtools never opens a Windows raw device itself. It receives the already
   verified exclusive Win32 handle adapter.
9. Writes are flushed, disk properties are refreshed, Windows remount is awaited,
   and the mounted result is re-inspected.

FATtools 1.1.23 is pinned and vendored. The exFAT `PartitionOffset` bug is
patched from a byte offset to a sector offset, and the data partition is not
marked active. Both facts have direct image tests and a Windows VHD mount test.

