from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .config import ClassificationConfig


@dataclass
class ClassificationResult:
    verdict: str  # PASS, FAIL, UNKNOWN, NONE
    reason: Optional[str] = None


def classify_value(value: Optional[float], cfg: ClassificationConfig) -> ClassificationResult:
    if cfg.mode == "none":
        return ClassificationResult("NONE", "Classification disabled")

    if value is None:
        return ClassificationResult("UNKNOWN", "No numeric value parsed")

    if cfg.mode == "threshold":
        rule = cfg.threshold
        op = rule.operator.lower()
        lo = rule.low
        hi = rule.high

        if op == "lt":
            ok = value < lo
            expr = f"{value} < {lo}"
        elif op == "le":
            ok = value <= lo
            expr = f"{value} <= {lo}"
        elif op == "gt":
            ok = value > hi
            expr = f"{value} > {hi}"
        elif op == "ge":
            ok = value >= hi
            expr = f"{value} >= {hi}"
        elif op == "eq":
            ok = value == lo
            expr = f"{value} == {lo}"
        elif op == "between":
            ok = lo <= value <= hi
            expr = f"{lo} <= {value} <= {hi}"
        else:
            return ClassificationResult("UNKNOWN", f"Unknown operator: {rule.operator}")

        return ClassificationResult("PASS" if ok else "FAIL", expr)

    # Placeholder for future modes (e.g., window, ML, etc.)
    return ClassificationResult("UNKNOWN", f"Unknown mode: {cfg.mode}")
