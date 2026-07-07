from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from typing import Protocol

from app.db.models import GradeRule


class GradeRuleProvider(Protocol):
    def get_rules(self) -> list[GradeRule]:
        ...


@dataclass(frozen=True)
class GradeResult:
    percent: Decimal
    grade_number: int
    grade_short: str
    grade_full: str

    @property
    def formatted_percent(self) -> str:
        value = self.percent.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return f"{int(value)}%"

    @property
    def formatted_grade(self) -> str:
        return f"{self.grade_number} ({self.grade_short}) - {self.formatted_percent}"


class GradeService:
    def __init__(self, repository: GradeRuleProvider):
        self.repository = repository
        self._rules: list[GradeRule] | None = None

    def reload_rules(self) -> None:
        self._rules = self.repository.get_rules()
        if not self._rules:
            raise ValueError("В базе данных не найдены правила оценивания grade_rules")

    @property
    def rules(self) -> list[GradeRule]:
        if self._rules is None:
            self.reload_rules()
        return self._rules or []

    def calculate(self, percent: Decimal | int | float | str) -> GradeResult:
        raw_value = Decimal(str(percent)).quantize(Decimal("0.01"))
        matched = self._match_rule(raw_value)
        result_percent = raw_value

        # В Moodle процент может прийти с десятичной частью, а начальная шкала
        # часто задается целыми диапазонами. Если точного попадания нет,
        # пробуем процент, округленный так же, как он будет показан в ведомости.
        if matched is None:
            rounded_value = raw_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            matched = self._match_rule(rounded_value)
            result_percent = rounded_value

        if matched is None:
            raise ValueError(f"Для процента {raw_value} не найдено правило оценивания")

        return GradeResult(
            percent=result_percent,
            grade_number=matched.grade_number,
            grade_short=matched.grade_short,
            grade_full=matched.grade_full,
        )

    def _match_rule(self, value: Decimal) -> GradeRule | None:
        for rule in self.rules:
            if rule.contains(value):
                return rule
        return None
