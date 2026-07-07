from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.config import ExcelSettings

logger = logging.getLogger(__name__)


@dataclass
class StudentResult:
    full_name: str
    percent: Decimal
    source_row: int
    individual_number: str = ""
    login: str = ""
    test_started: str = ""


@dataclass(frozen=True)
class MoodleParseResult:
    students: list[StudentResult]
    header_row: int
    data_start_row: int
    percent_column: int
    individual_number_column: int | None = None
    individual_numbers: list[str] | None = None


class ExcelParseError(Exception):
    pass


class ExcelParser:
    FIRST_NAME_ALIASES = {
        "имя",
        "name",
        "firstname",
        "first name",
        "given name",
    }
    LAST_NAME_ALIASES = {
        "фамилия",
        "surname",
        "lastname",
        "last name",
        "family name",
    }
    MIDDLE_NAME_ALIASES = {
        "отчество",
        "middle name",
        "middlename",
    }
    PERCENT_ALIASES = {
        "процент",
        "итоговый процент",
        "общий процент",
        "%",
        "percentage",
        "percent",
        "процентная оценка",
        "итоговая оценка (%)",
    }
    INDIVIDUAL_NUMBER_ALIASES = {
        "индивидуальный номер",
        "инд номер",
        "инд. номер",
        "individual number",
        "id number",
        "group code",
    }
    LOGIN_ALIASES = {
        "логин",
        "login",
        "username",
        "user name",
    }
    TEST_STARTED_ALIASES = {
        "тест начат",
        "начало теста",
        "started",
        "test started",
        "started on",
    }

    def __init__(self, settings: ExcelSettings):
        self.settings = settings

    def parse(self, file_path: str | Path) -> MoodleParseResult:
        path = Path(file_path)
        if not path.exists():
            raise ExcelParseError(f"Excel-файл не найден: {path}")
        if path.suffix.lower() != ".xlsx":
            raise ExcelParseError("Поддерживаются только файлы .xlsx")

        try:
            workbook = load_workbook(path, data_only=True, read_only=True)
        except Exception as exc:
            raise ExcelParseError(f"Не удалось открыть Excel-файл: {exc}") from exc

        try:
            sheet = workbook.active
            header_row, columns = self._detect_columns(sheet)
            data_start_row = max(self.settings.data_start_row, header_row + 1)
            students = self._read_students(sheet, columns, data_start_row)
            if not students:
                raise ExcelParseError("В Excel-файле не найдены строки студентов")

            logger.info("Найдено студентов: %s", len(students))
            return MoodleParseResult(
                students=students,
                header_row=header_row,
                data_start_row=data_start_row,
                percent_column=columns["percent"],
                individual_number_column=columns.get("individual_number"),
                individual_numbers=self._unique_individual_numbers(students),
            )
        finally:
            workbook.close()

    def _detect_columns(self, sheet: Any) -> tuple[int, dict[str, int]]:
        max_row = self._sheet_max_row(sheet)
        max_column = self._sheet_max_column(sheet)
        max_search_row = min(self.settings.header_search_rows, max_row)
        best: tuple[int, dict[str, int], int] | None = None

        for row_idx in range(1, max_search_row + 1):
            row_values = self._row_values(sheet, row_idx, max_column)
            normalized = [self._normalize_header(value) for value in row_values]
            found: dict[str, int] = {}

            for idx, text in enumerate(normalized, start=1):
                if not text:
                    continue
                if "first_name" not in found and self._header_matches(text, self.FIRST_NAME_ALIASES):
                    found["first_name"] = idx
                if "last_name" not in found and self._header_matches(text, self.LAST_NAME_ALIASES):
                    found["last_name"] = idx
                if "middle_name" not in found and self._header_matches(text, self.MIDDLE_NAME_ALIASES):
                    found["middle_name"] = idx
                if "percent" not in found and self._looks_like_percent_header(text):
                    found["percent"] = idx
                if "individual_number" not in found and self._header_matches(text, self.INDIVIDUAL_NUMBER_ALIASES):
                    found["individual_number"] = idx
                if "login" not in found and self._header_matches(text, self.LOGIN_ALIASES):
                    found["login"] = idx
                if "test_started" not in found and self._header_matches(text, self.TEST_STARTED_ALIASES):
                    found["test_started"] = idx

            score = sum(1 for key in ("first_name", "last_name", "percent") if key in found)
            if best is None or score > best[2]:
                best = (row_idx, found, score)

            if {"first_name", "last_name", "percent"}.issubset(found.keys()):
                return row_idx, found

        if best and best[2] >= 2:
            row_idx, found, _ = best
            self._fill_missing_columns_by_position(sheet, row_idx, found)
            if {"first_name", "last_name", "percent"}.issubset(found.keys()):
                return row_idx, found

        raise ExcelParseError(
            "Не удалось найти обязательные столбцы. Нужны столбцы с именем, фамилией и процентом."
        )

    def _fill_missing_columns_by_position(self, sheet: Any, row_idx: int, found: dict[str, int]) -> None:
        # Резервная логика для нестандартных выгрузок: если имя/фамилия не найдены,
        # берем первые текстовые колонки, а процент ищем по числовым значениям ниже.
        if "percent" not in found:
            max_row = self._sheet_max_row(sheet)
            max_column = self._sheet_max_column(sheet)
            for col_idx in range(1, max_column + 1):
                values = [self._cell_value(sheet, r, col_idx) for r in range(row_idx + 1, min(max_row, row_idx + 8) + 1)]
                parsed = [self._parse_percent(v) for v in values]
                if sum(1 for value in parsed if value is not None) >= 2:
                    found["percent"] = col_idx
                    break

    def _read_students(self, sheet: Any, columns: dict[str, int], data_start_row: int) -> list[StudentResult]:
        students: list[StudentResult] = []
        max_row = self._sheet_max_row(sheet)

        for row_idx in range(data_start_row, max_row + 1):
            first_raw = self._cell_text(self._cell_value(sheet, row_idx, columns["first_name"]))
            last_raw = self._cell_text(self._cell_value(sheet, row_idx, columns["last_name"]))
            middle_raw = ""
            if "middle_name" in columns:
                middle_raw = self._cell_text(self._cell_value(sheet, row_idx, columns["middle_name"]))

            percent_raw = self._cell_value(sheet, row_idx, columns["percent"])
            percent_value = self._parse_percent(percent_raw)
            full_name = self._build_full_name(first_raw, last_raw, middle_raw)
            individual_number = ""
            if "individual_number" in columns:
                individual_number = self._cell_text(self._cell_value(sheet, row_idx, columns["individual_number"]))
            login = ""
            if "login" in columns:
                login = self._cell_text(self._cell_value(sheet, row_idx, columns["login"]))
            test_started = ""
            if "test_started" in columns:
                test_started = self._cell_text(self._cell_value(sheet, row_idx, columns["test_started"]))

            # Пропускаем строки с итоговой статистикой
            if self._is_summary_row(full_name, first_raw, last_raw):
                logger.debug("Пропущена строка итоговой статистики: %s", full_name)
                continue

            if not full_name and percent_value is None:
                continue
            if not full_name:
                logger.warning("Строка %s пропущена: отсутствует ФИО", row_idx)
                continue
            if percent_value is None:
                logger.warning(
                    "Строка %s пропущена: невозможно прочитать процент из значения '%s'",
                    row_idx,
                    percent_raw,
                )
                continue

            students.append(
                StudentResult(
                    full_name=full_name,
                    percent=percent_value,
                    source_row=row_idx,
                    individual_number=individual_number,
                    login=login,
                    test_started=test_started,
                )
            )

        return students

    @staticmethod
    def _unique_individual_numbers(students: list[StudentResult]) -> list[str]:
        values = {student.individual_number for student in students if student.individual_number}
        return sorted(values, key=lambda value: value.lower())

    @staticmethod
    def _is_summary_row(full_name: str, first_raw: str, last_raw: str) -> bool:
        """Проверяет, является ли строка итоговой статистикой (например, 'Общее среднее')."""
        summary_keywords = {"общее", "итог", "среднее", "средний", "total", "average", "summary"}
        name_lower = (full_name or "").lower()
        first_lower = (first_raw or "").lower()
        last_lower = (last_raw or "").lower()
        
        return any(keyword in name_lower for keyword in summary_keywords) or \
               any(keyword in first_lower for keyword in summary_keywords) or \
               any(keyword in last_lower for keyword in summary_keywords)

    def _build_full_name(self, first_raw: str, last_raw: str, middle_raw: str) -> str:
        first_parts = self._split_name(first_raw)
        last_parts = self._split_name(last_raw)
        middle_parts = self._split_name(middle_raw)

        if self.settings.swap_first_last_names:
            surname_parts = last_parts
            name_parts = first_parts
        else:
            surname_parts = last_parts
            name_parts = first_parts

        parts: list[str] = []
        parts.extend(surname_parts)
        parts.extend(name_parts)
        parts.extend(middle_parts)
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _split_name(value: str) -> list[str]:
        value = re.sub(r"\s+", " ", value.strip())
        return [part for part in value.split(" ") if part]

    @staticmethod
    def _cell_text(value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _sheet_max_row(sheet: Any) -> int:
        max_row = getattr(sheet, "max_row", None)
        if isinstance(max_row, int) and max_row > 0:
            return max_row
        try:
            rows = list(sheet.iter_rows(values_only=True))
        except Exception:
            return 0
        return len(rows)

    @staticmethod
    def _sheet_max_column(sheet: Any) -> int:
        max_column = getattr(sheet, "max_column", None)
        if isinstance(max_column, int) and max_column > 0:
            return max_column
        try:
            rows = list(sheet.iter_rows(values_only=True))
        except Exception:
            return 0
        if not rows:
            return 0
        return max(len(row) for row in rows)

    @staticmethod
    def _row_values(sheet: Any, row_idx: int, max_column: int) -> list[Any]:
        try:
            row = sheet[row_idx]
        except Exception:
            return []
        if max_column <= 0:
            return []
        values = [cell.value for cell in row]
        if len(values) >= max_column:
            return values
        return values + [None] * (max_column - len(values))

    @staticmethod
    def _cell_value(sheet: Any, row_idx: int, column_idx: int) -> Any:
        try:
            return sheet.cell(row=row_idx, column=column_idx).value
        except Exception:
            return None

    @staticmethod
    def _normalize_header(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip().lower().replace("ё", "е")
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _header_matches(cls, text: str, aliases: set[str]) -> bool:
        clean = re.sub(r"[^a-zа-я0-9% ]", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean in aliases or any(alias in clean for alias in aliases if len(alias) > 2)

    @classmethod
    def _looks_like_percent_header(cls, text: str) -> bool:
        if cls._header_matches(text, cls.PERCENT_ALIASES):
            return True
        return "%" in text or "процент" in text or "percent" in text

    @staticmethod
    def _parse_percent(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, (int, float, Decimal)):
            number = Decimal(str(value))
            # Иногда Moodle может выгрузить долю 0.95 вместо 95.
            if Decimal("0") <= number <= Decimal("1"):
                number *= Decimal("100")
            # Отбрасываем явно неправильные значения
            if not (Decimal("0") <= number <= Decimal("100")):
                return None
            return number.quantize(Decimal("0.01"))

        text = str(value).strip().replace("\xa0", " ")
        if not text:
            return None
        
        # Если текст содержит странные символы (не цифры, точки, запятые, %, /, пробелы, минус),
        # это явно ошибка в формате
        if re.search(r"[^0-9.,/%\s\-]", text):
            return None
        
        # Нормализуем разделители: заменяем запятые на точки, но только если это разумно
        # (e.g., "95,5" -> "95.5", но не "2581,011" где первая часть>100)
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        
        fraction_match = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", text)
        if fraction_match:
            try:
                num_str = fraction_match.group(1).replace(",", ".")
                denom_str = fraction_match.group(2).replace(",", ".")
                numerator = Decimal(num_str)
                denominator = Decimal(denom_str)
                if denominator != 0:
                    result = ((numerator / denominator) * Decimal("100")).quantize(Decimal("0.01"))
                    if Decimal("0") <= result <= Decimal("100"):
                        return result
            except InvalidOperation:
                return None

        # Пытаемся извлечь число — берём первое найденное
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        
        try:
            number = Decimal(match.group(0))
            # Если это явно число > 100 и нет знака %, то это ошибка
            if number > Decimal("100") and "%" not in text:
                return None
            if Decimal("0") <= number <= Decimal("1") and "%" not in text:
                number *= Decimal("100")
            if not (Decimal("0") <= number <= Decimal("100")):
                return None
            return number.quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
