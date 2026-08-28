import ctypes
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows ABI test")


def test_windows_structure_sizes():
    from ps2ripper.windows.native import (
        SCSI_PASS_THROUGH_DIRECT,
        SP_DEVICE_INTERFACE_DATA,
        SP_DEVINFO_DATA,
        SPTD_WITH_SENSE,
        STORAGE_DEVICE_NUMBER,
        STORAGE_PROPERTY_QUERY,
    )

    assert ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT) == 56
    assert SCSI_PASS_THROUGH_DIRECT.DataBuffer.offset == 24
    assert ctypes.sizeof(SPTD_WITH_SENSE) == 88
    assert ctypes.sizeof(SP_DEVICE_INTERFACE_DATA) == 32
    assert ctypes.sizeof(SP_DEVINFO_DATA) == 32
    assert ctypes.sizeof(STORAGE_PROPERTY_QUERY) == 12
    assert ctypes.sizeof(STORAGE_DEVICE_NUMBER) == 12
