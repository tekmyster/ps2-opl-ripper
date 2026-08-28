from __future__ import annotations

import ctypes
from ctypes import wintypes

from .native import WinHandle, kernel32, raise_last_error


class RawDiskStream:
    """Aligned file-like adapter over a caller-owned exclusive Win32 handle."""

    mode = "r+b"

    def __init__(self, handle: WinHandle, size: int, sector_size: int = 512) -> None:
        self.handle = handle
        self.size = size
        self.sector_size = sector_size
        self.position = 0
        self.closed = False

    def type(self) -> str:
        return "disk"

    def seek(self, offset: int, whence: int = 0) -> None:
        target = (
            offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        )
        if target < 0 or target > self.size:
            raise ValueError("Raw disk seek is out of range")
        new_position = ctypes.c_longlong()
        if not kernel32.SetFilePointerEx(
            self.handle.value, ctypes.c_longlong(target), ctypes.byref(new_position), 0
        ):
            raise_last_error("SetFilePointerEx(raw disk)")
        self.position = new_position.value

    def tell(self) -> int:
        return self.position

    def read(self, size: int) -> bytearray:
        if size < 0 or self.position + size > self.size:
            raise ValueError("Raw disk read is out of range")
        if self.position % self.sector_size or size % self.sector_size:
            raise ValueError("Raw disk reads must be sector aligned")
        buffer = ctypes.create_string_buffer(size)
        transferred = wintypes.DWORD()
        if not kernel32.ReadFile(self.handle.value, buffer, size, ctypes.byref(transferred), None):
            raise_last_error("ReadFile(raw disk)")
        self.position += transferred.value
        return bytearray(buffer.raw[: transferred.value])

    def write(self, data: bytes | bytearray | memoryview) -> None:
        payload = bytes(data)
        if self.position % self.sector_size or len(payload) % self.sector_size:
            raise ValueError("Raw disk writes must be sector aligned")
        if self.position + len(payload) > self.size:
            raise ValueError("Raw disk write is out of range")
        buffer = ctypes.create_string_buffer(payload)
        transferred = wintypes.DWORD()
        if not kernel32.WriteFile(
            self.handle.value, buffer, len(payload), ctypes.byref(transferred), None
        ):
            raise_last_error("WriteFile(raw disk)")
        if transferred.value != len(payload):
            raise OSError("Raw disk returned a short write")
        self.position += transferred.value

    def flush(self) -> None:
        if not kernel32.FlushFileBuffers(self.handle.value):
            raise_last_error("FlushFileBuffers(raw disk)")

    def close(self) -> None:
        # FATtools calls close while transitioning from the partition table to
        # filesystem creation. The owning context retains the exclusive handle.
        self.flush()
