from __future__ import annotations

import ctypes
import uuid
from ctypes import wintypes
from dataclasses import dataclass

from .native import (
    DIGCF_DEVICEINTERFACE,
    DIGCF_PRESENT,
    ERROR_INSUFFICIENT_BUFFER,
    ERROR_NO_MORE_ITEMS,
    GUID,
    INVALID_HANDLE_VALUE,
    SP_DEVICE_INTERFACE_DATA,
    SP_DEVINFO_DATA,
    raise_last_error,
    setupapi,
)


@dataclass(frozen=True)
class DeviceInterface:
    path: str
    instance_id: str
    properties: dict[int, str]


def _device_property(info_set: int, devinfo: SP_DEVINFO_DATA, prop: int) -> str:
    required = wintypes.DWORD()
    prop_type = wintypes.DWORD()
    setupapi.SetupDiGetDeviceRegistryPropertyW(
        info_set,
        ctypes.byref(devinfo),
        prop,
        ctypes.byref(prop_type),
        None,
        0,
        ctypes.byref(required),
    )
    if not required.value:
        return ""
    buffer = ctypes.create_string_buffer(required.value)
    if not setupapi.SetupDiGetDeviceRegistryPropertyW(
        info_set,
        ctypes.byref(devinfo),
        prop,
        ctypes.byref(prop_type),
        buffer,
        required.value,
        ctypes.byref(required),
    ):
        return ""
    return ctypes.wstring_at(ctypes.addressof(buffer)).rstrip("\x00")


def _instance_id(info_set: int, devinfo: SP_DEVINFO_DATA) -> str:
    required = wintypes.DWORD()
    setupapi.SetupDiGetDeviceInstanceIdW(
        info_set, ctypes.byref(devinfo), None, 0, ctypes.byref(required)
    )
    if not required.value:
        return ""
    buffer = ctypes.create_unicode_buffer(required.value)
    if not setupapi.SetupDiGetDeviceInstanceIdW(
        info_set, ctypes.byref(devinfo), buffer, required.value, ctypes.byref(required)
    ):
        raise_last_error("SetupDiGetDeviceInstanceIdW")
    return buffer.value


def enumerate_device_interfaces(
    class_uuid: uuid.UUID, properties: tuple[int, ...]
) -> list[DeviceInterface]:
    guid = GUID.from_uuid(class_uuid)
    info_set = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if info_set in (None, 0, INVALID_HANDLE_VALUE):
        raise_last_error("SetupDiGetClassDevsW")
    devices: list[DeviceInterface] = []
    try:
        index = 0
        while True:
            interface = SP_DEVICE_INTERFACE_DATA()
            interface.cbSize = ctypes.sizeof(interface)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                info_set, None, ctypes.byref(guid), index, ctypes.byref(interface)
            ):
                code = ctypes.get_last_error()
                if code == ERROR_NO_MORE_ITEMS:
                    break
                raise_last_error("SetupDiEnumDeviceInterfaces")

            required = wintypes.DWORD()
            devinfo = SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(devinfo)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set,
                ctypes.byref(interface),
                None,
                0,
                ctypes.byref(required),
                ctypes.byref(devinfo),
            )
            if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or required.value < 8:
                raise_last_error("SetupDiGetDeviceInterfaceDetailW(size)")
            detail = ctypes.create_string_buffer(required.value)
            ctypes.cast(detail, ctypes.POINTER(wintypes.DWORD))[0] = 8
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set,
                ctypes.byref(interface),
                detail,
                required.value,
                ctypes.byref(required),
                ctypes.byref(devinfo),
            ):
                raise_last_error("SetupDiGetDeviceInterfaceDetailW")
            path = ctypes.wstring_at(ctypes.addressof(detail) + 4)
            devices.append(
                DeviceInterface(
                    path=path,
                    instance_id=_instance_id(info_set, devinfo),
                    properties={
                        prop: _device_property(info_set, devinfo, prop) for prop in properties
                    },
                )
            )
            index += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info_set)
    return devices
