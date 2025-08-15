from __future__ import annotations

import dataclasses
import pathlib
import os
import sys
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG_PATH = pathlib.Path(__file__).resolve().parents[1] / "config.yaml"


@dataclasses.dataclass
class SerialConfig:
    port: Optional[str] = None
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 1.0


@dataclasses.dataclass
class ProtocolConfig:
    type: str = "mitutoyo6200"
    line_ending: str = "\r\n"


@dataclasses.dataclass
class ThresholdRule:
    operator: str = "between"  # lt, le, gt, ge, eq, between
    low: float = 0.0
    high: float = 10.0


@dataclasses.dataclass
class ClassificationConfig:
    mode: str = "threshold"  # threshold | window | none
    units: str = "mm"
    threshold: ThresholdRule = dataclasses.field(default_factory=ThresholdRule)


@dataclasses.dataclass
class LoggingConfig:
    csv_path: str = "logs/readings.csv"
    append: bool = True
    timestamp_tz: str = "local"  # local | utc


@dataclasses.dataclass
class AppConfig:
    serial: SerialConfig = dataclasses.field(default_factory=SerialConfig)
    protocol: ProtocolConfig = dataclasses.field(default_factory=ProtocolConfig)
    classification: ClassificationConfig = dataclasses.field(default_factory=ClassificationConfig)
    logging: LoggingConfig = dataclasses.field(default_factory=LoggingConfig)


def load_config(path: Optional[pathlib.Path] = None) -> AppConfig:
    cfg_path = path or _resolve_config_path()
    if cfg_path and cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}
        cfg = _from_dict(data)
    else:
        cfg = AppConfig()

    # On Windows, if logging path looks relative or defaults to logs/..., redirect to %ProgramData%
    if os.name == "nt":
        cfg.logging.csv_path = str(_resolve_windows_logs_path(cfg.logging.csv_path))
    return cfg


def _resolve_config_path() -> pathlib.Path:
    """Return the best config.yaml path based on platform and packaging.

    Priority:
    1) Windows: %ProgramData%/Laser_Scan_Micrometer/config.yaml
    2) Windows: %AppData%/Laser_Scan_Micrometer/config.yaml
    3) Frozen exe dir (PyInstaller): <exe_dir>/config.yaml
    4) Project root (source checkout): repo/config.yaml
    """
    candidates = []

    if os.name == "nt":
        programdata = os.environ.get("PROGRAMDATA", r"C:\\ProgramData")
        candidates.append(pathlib.Path(programdata) / "Laser_Scan_Micrometer" / "config.yaml")
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(pathlib.Path(appdata) / "Laser_Scan_Micrometer" / "config.yaml")

    # PyInstaller frozen executable directory
    exe_dir: Optional[pathlib.Path] = None
    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
    else:
        # When running from source, also consider cwd/exe dir for completeness
        try:
            exe_dir = pathlib.Path(__file__).resolve().parents[1]
        except Exception:
            exe_dir = None
    if exe_dir:
        candidates.append(exe_dir / "config.yaml")

    # Project root fallback
    candidates.append(DEFAULT_CONFIG_PATH)

    for p in candidates:
        if p and p.exists():
            return p
    # default to first candidate (even if not exists) so callers know where to write if needed
    return candidates[0]


def _resolve_windows_logs_path(current: str) -> pathlib.Path:
    """Ensure logs path is under %ProgramData% for write permission stability on Windows.

    If current is absolute, keep it. If it's relative (e.g., "logs/readings.csv"),
    place it under %ProgramData%/Laser_Scan_Micrometer/logs/...
    """
    p = pathlib.Path(current) if current else pathlib.Path("logs/readings.csv")
    if p.is_absolute():
        return p
    programdata = pathlib.Path(os.environ.get("PROGRAMDATA", r"C:\\ProgramData"))
    base = programdata / "Laser_Scan_Micrometer"
    # create logs dir if possible
    try:
        (base / "logs").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base / p


def _from_dict(d: Dict[str, Any]) -> AppConfig:
    def get(section: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        return {**defaults, **(d.get(section) or {})}

    serial = SerialConfig(**get("serial", dataclasses.asdict(SerialConfig())))
    protocol = ProtocolConfig(**get("protocol", dataclasses.asdict(ProtocolConfig())))

    thr_defaults = dataclasses.asdict(ThresholdRule())
    thr = ThresholdRule(**get("threshold", thr_defaults))

    cls_defaults = dataclasses.asdict(ClassificationConfig())
    # remove nested default threshold dict before constructing
    cls_defaults.pop("threshold", None)
    classification_kwargs = get("classification", cls_defaults)
    # Ensure we don't pass two values for 'threshold'
    classification_kwargs.pop("threshold", None)
    classification = ClassificationConfig(**classification_kwargs, threshold=thr)

    logging_cfg = LoggingConfig(**get("logging", dataclasses.asdict(LoggingConfig())))

    return AppConfig(
        serial=serial,
        protocol=protocol,
        classification=classification,
        logging=logging_cfg,
    )
