from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class GeneratedStatement:
    id: int
    subject_name: str
    group_name: str
    specialty_name: str
    teacher_name: str
    source_excel_file: str
    output_docx_file: str
    created_at: datetime | None
