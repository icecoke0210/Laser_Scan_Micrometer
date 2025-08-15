from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulatorConfig:
    standard: float = 0.110
    spread: float = 0.012  # +/- around standard for random demo values


class MicrometerSimulator:
    """Generate demo measurements around a standard value with high precision (5 dp)."""

    def __init__(self, cfg: Optional[SimulatorConfig] = None):
        self.cfg = cfg or SimulatorConfig()

    def next_value(self) -> float:
        # Generate a value around standard within +/- spread, with 5 decimal places
        raw = self.cfg.standard + random.uniform(-self.cfg.spread, self.cfg.spread)
        # Quantize to 5 decimals like device might output
        return float(f"{raw:.5f}")
