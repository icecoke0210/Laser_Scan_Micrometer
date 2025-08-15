from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Optional, Tuple

getcontext().prec = 12


@dataclass
class ProcessedValue:
    raw_5dp: float
    cut_4dp: float
    rounded_3dp: float


def truncate_to_decimals(value: float, decimals: int) -> float:
    sign = 1 if value >= 0 else -1
    d = Decimal(str(abs(value)))
    factor = Decimal(10) ** decimals
    truncated = (d * factor).to_integral_value(rounding="ROUND_DOWN") / factor
    return float(truncated) * sign


def round_half_up(value: float, decimals: int) -> float:
    q = Decimal(10) ** -decimals
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def process_value(raw: float) -> ProcessedValue:
    # Ensure 5dp representation for display
    raw_5dp = float(f"{raw:.5f}")
    cut_4dp = truncate_to_decimals(raw_5dp, 4)
    # Round to 3dp using ten-thousandth (i.e., HALF_UP on the 4th digit)
    rounded_3dp = round_half_up(cut_4dp, 3)
    return ProcessedValue(raw_5dp=raw_5dp, cut_4dp=cut_4dp, rounded_3dp=rounded_3dp)


@dataclass
class Category:
    code: int
    name: str  # descriptive name (relative to standard)
    color: str


def categories_relative() -> list[Category]:
    return [
        Category(1, "超過上限公差", "#d32f2f"),
        Category(2, "標準+0.005", "#ef6c00"),
        Category(3, "標準±0.002", "#388e3c"),
        Category(4, "標準-0.005", "#1976d2"),
        Category(5, "標準-0.010", "#7b1fa2"),
        Category(6, "超過下限公差", "#5d4037"),
    ]


@dataclass
class CategoryResult:
    category: Category
    reason: str


def classify_six_bins(value_3dp: float, standard: float = 0.110) -> CategoryResult:
    cats = categories_relative()
    # Compute bands relative to standard per user's spec
    hi_limit = standard + 0.008
    bin2_lo, bin2_hi = standard + 0.003, standard + 0.007
    bin3_lo, bin3_hi = standard - 0.002, standard + 0.002
    bin4_lo, bin4_hi = standard - 0.007, standard - 0.003
    bin5_lo, bin5_hi = standard - 0.012, standard - 0.008
    lo_limit = standard - 0.013

    v = value_3dp
    if v >= hi_limit:
        return CategoryResult(cats[0], f"{v:.3f} >= {hi_limit:.3f}")
    if bin2_lo <= v <= bin2_hi:
        return CategoryResult(cats[1], f"{bin2_lo:.3f} <= {v:.3f} <= {bin2_hi:.3f}")
    if bin3_lo <= v <= bin3_hi:
        return CategoryResult(cats[2], f"{bin3_lo:.3f} <= {v:.3f} <= {bin3_hi:.3f}")
    if bin4_lo <= v <= bin4_hi:
        return CategoryResult(cats[3], f"{bin4_lo:.3f} <= {v:.3f} <= {bin4_hi:.3f}")
    if bin5_lo <= v <= bin5_hi:
        return CategoryResult(cats[4], f"{bin5_lo:.3f} <= {v:.3f} <= {bin5_hi:.3f}")
    if v <= lo_limit:
        return CategoryResult(cats[5], f"{v:.3f} <= {lo_limit:.3f}")

    # If in gaps, choose nearest band center
    centers = {
        cats[1]: standard + 0.005,
        cats[2]: standard,
        cats[3]: standard - 0.005,
        cats[4]: standard - 0.010,
    }
    closest = min(centers.items(), key=lambda kv: abs(v - kv[1]))
    return CategoryResult(closest[0], f"closest to {closest[1]:.3f}")
