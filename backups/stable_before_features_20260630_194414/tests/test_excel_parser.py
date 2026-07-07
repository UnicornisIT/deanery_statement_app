from decimal import Decimal

from app.config import ExcelSettings
from app.services.excel_parser import ExcelParser


class FakeCell:
    def __init__(self, value):
        self.value = value


class FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows
        self.max_row = None
        self.max_column = None

    def __getitem__(self, row_idx):
        return [FakeCell(value) for value in self._rows[row_idx - 1]]

    def iter_rows(self, values_only=False):
        if values_only:
            return [tuple(row) for row in self._rows]
        return [[FakeCell(value) for value in row] for row in self._rows]

    def cell(self, row, column):
        return FakeCell(self._rows[row - 1][column - 1])


class FakeWorkbook:
    def __init__(self, sheet):
        self._sheet = sheet

    @property
    def active(self):
        return self._sheet

    def close(self):
        return None


def test_parse_accepts_sheet_without_precomputed_dimensions(tmp_path, monkeypatch):
    path = tmp_path / "students.xlsx"
    path.write_bytes(b"dummy")

    rows = [
        ["Фамилия", "Имя", "Процент"],
        ["Иванов", "Иван", 95],
    ]
    sheet = FakeWorksheet(rows)

    monkeypatch.setattr(
        "app.services.excel_parser.load_workbook",
        lambda *args, **kwargs: FakeWorkbook(sheet),
    )

    parser = ExcelParser(ExcelSettings(header_search_rows=5, data_start_row=2, swap_first_last_names=True))
    result = parser.parse(path)

    assert result.header_row == 1
    assert result.data_start_row == 2
    assert len(result.students) == 1
    assert result.students[0].full_name == "Иванов Иван"
    assert result.students[0].percent == Decimal("95")


def test_parse_reads_individual_number_column(tmp_path, monkeypatch):
    path = tmp_path / "students.xlsx"
    path.write_bytes(b"dummy")

    rows = [
        ["Фамилия", "Имя", "Индивидуальный номер", "Процент"],
        ["Иванов", "Иван", "25sd9", 95],
        ["Петров", "Петр", "25ld9", 88],
        ["Сидоров", "Сидор", "25sd9", 77],
    ]
    sheet = FakeWorksheet(rows)

    monkeypatch.setattr(
        "app.services.excel_parser.load_workbook",
        lambda *args, **kwargs: FakeWorkbook(sheet),
    )

    parser = ExcelParser(ExcelSettings(header_search_rows=5, data_start_row=2, swap_first_last_names=False))
    result = parser.parse(path)

    assert result.individual_number_column == 3
    assert result.individual_numbers == ["25ld9", "25sd9"]
    assert [student.individual_number for student in result.students] == ["25sd9", "25ld9", "25sd9"]


def test_parse_reads_attempt_metadata(tmp_path, monkeypatch):
    path = tmp_path / "students.xlsx"
    path.write_bytes(b"dummy")

    rows = [
        ["Фамилия", "Имя", "Логин", "Тест начат", "Процент"],
        ["Иванов", "Иван", "12345", "24 июня 2026  12:21", 95],
    ]
    sheet = FakeWorksheet(rows)

    monkeypatch.setattr(
        "app.services.excel_parser.load_workbook",
        lambda *args, **kwargs: FakeWorkbook(sheet),
    )

    parser = ExcelParser(ExcelSettings(header_search_rows=5, data_start_row=2, swap_first_last_names=False))
    result = parser.parse(path)

    assert result.students[0].login == "12345"
    assert result.students[0].test_started == "24 июня 2026 12:21"
