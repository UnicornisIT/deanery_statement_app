from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GradeRule:
    min_percent: Decimal
    max_percent: Decimal
    grade_number: int
    grade_short: str
    grade_full: str

    def contains(self, percent: Decimal) -> bool:
        return self.min_percent <= percent <= self.max_percent
