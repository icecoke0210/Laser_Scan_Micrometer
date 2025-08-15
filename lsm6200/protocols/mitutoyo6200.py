from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


@dataclass
class Measurement:
    raw: str
    value: Optional[float]
    unit: Optional[str] = None


class Mitutoyo6200Parser:
    """
    Minimal, tolerant parser for Mitutoyo 6200 text output.
    Assumes line-oriented ASCII, attempts to extract first floating number.
    Adjust if your device emits prefixed frames or checksums.
    """

    def __init__(self, expected_unit: Optional[str] = None):
        self.expected_unit = expected_unit

    def parse_line(self, line: bytes | str) -> Optional[Measurement]:
        if isinstance(line, bytes):
            try:
                text = line.decode("utf-8", errors="replace").strip()
            except Exception:
                return None
        else:
            text = line.strip()
        if not text:
            return None

        m = NUMBER_RE.search(text)
        if not m:
            return Measurement(raw=text, value=None, unit=None)
        try:
            value = float(m.group(0))
        except ValueError:
            value = None

        # Try to guess unit: take trailing letters
        unit_match = re.search(r"([a-zA-Zμ]+)\s*$", text)
        unit = unit_match.group(1) if unit_match else self.expected_unit

        return Measurement(raw=text, value=value, unit=unit)
