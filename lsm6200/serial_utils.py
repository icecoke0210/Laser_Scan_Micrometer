from __future__ import annotations

import contextlib
from typing import List, Optional

import serial  # type: ignore
from serial import Serial
from serial.tools import list_ports


PARITY_MAP = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK,
    "S": serial.PARITY_SPACE,
}

STOPBITS_MAP = {
    1: serial.STOPBITS_ONE,
    1.5: serial.STOPBITS_ONE_POINT_FIVE,
    2: serial.STOPBITS_TWO,
}


def available_ports() -> List[str]:
    return [p.device for p in list_ports.comports()]


def open_serial(
    port: str,
    baudrate: int = 9600,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1,
    timeout: float = 1.0,
) -> Serial:
    parity_val = PARITY_MAP.get(parity.upper(), serial.PARITY_NONE)
    stopbits_val = STOPBITS_MAP.get(stopbits, serial.STOPBITS_ONE)
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity_val,
        stopbits=stopbits_val,
        timeout=timeout,
    )


@contextlib.contextmanager
def managed_serial(*args, **kwargs):
    ser: Optional[Serial] = None
    try:
        ser = open_serial(*args, **kwargs)
        yield ser
    finally:
        with contextlib.suppress(Exception):
            if ser and ser.is_open:
                ser.close()
