from __future__ import annotations

import csv
import datetime as dt
import pathlib
from typing import Optional

from .config import LoggingConfig


def _now(tz: str) -> str:
    if tz == "utc":
        return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    # default local
    return dt.datetime.now().isoformat(timespec="seconds")


class CsvLogger:
    def __init__(self, cfg: LoggingConfig):
        self.cfg = cfg
        self.path = pathlib.Path(cfg.csv_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._writer = None
        self._index = 1

    def __enter__(self):
        mode = "a" if self.cfg.append else "w"
        self._file = self.path.open(mode, newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if not self.cfg.append or self._file.tell() == 0:
            # Header with index and six category columns
            self._writer.writerow([
                "No.",
                "timestamp",
                "Cat1_超過上限公差",
                "Cat2_0.115",
                "Cat3_0.110",
                "Cat4_0.105",
                "Cat5_0.100",
                "Cat6_超過下限公差",
                "unit",
                "reason",
                "raw",
            ])
            self._index = 1
        else:
            # Continue index based on existing rows (exclude header)
            try:
                with self.path.open("r", encoding="utf-8") as rf:
                    row_count = sum(1 for _ in rf)
                # row_count includes header; data rows = max(row_count - 1, 0)
                data_rows = max(row_count - 1, 0)
                self._index = data_rows + 1
            except Exception:
                self._index = 1
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None

    def log_categorized(
        self,
        value_3dp: Optional[float],
        category_code: int,
        unit: str,
        reason: str,
        raw: str,
    ) -> None:
        if not self._writer:
            raise RuntimeError("CsvLogger must be used as a context manager")
        # Prepare six category fields; put value into the matching one
        cats = ["", "", "", "", "", ""]
        if value_3dp is not None and 1 <= category_code <= 6:
            cats[category_code - 1] = f"{value_3dp:.3f}"
        self._writer.writerow([
            self._index,
            _now(self.cfg.timestamp_tz),
            *cats,
            unit,
            reason or "",
            raw,
        ])
        self._index += 1
