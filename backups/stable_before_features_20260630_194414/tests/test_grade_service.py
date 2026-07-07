from decimal import Decimal

from app.db.models import GradeRule
from app.services.grade_service import GradeService


class FakeRepo:
    def get_rules(self):
        return [
            GradeRule(Decimal("91"), Decimal("100"), 5, "отл", "отлично"),
            GradeRule(Decimal("81"), Decimal("90"), 4, "хор", "хорошо"),
            GradeRule(Decimal("71"), Decimal("80"), 3, "удовл", "удовлетворительно"),
            GradeRule(Decimal("0"), Decimal("70"), 2, "неуд", "неудовлетворительно"),
        ]


def test_grade_70_is_two():
    service = GradeService(FakeRepo())
    assert service.calculate(70).formatted_grade == "2 (неуд) - 70%"


def test_grade_95_is_five():
    service = GradeService(FakeRepo())
    assert service.calculate(95).formatted_grade == "5 (отл) - 95%"
