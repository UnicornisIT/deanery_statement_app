from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from app.db.connection import DatabaseConnection
from app.db.models import GeneratedStatement, GradeRule


class DirectoryRepository:
    TABLES = {
        "subjects": ("subjects", "name"),
        "groups": ("student_groups", "name"),
        "specialties": ("specialties", "name"),
        "teachers": ("teachers", "full_name"),
    }

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def list_values(self, directory: str) -> list[str]:
        table, column = self._resolve(directory)
        with self.db.cursor(dictionary=True) as cursor:
            cursor.execute(f"SELECT {column} AS value FROM {table} ORDER BY {column}")
            return [str(row["value"]) for row in cursor.fetchall()]

    def add_value(self, directory: str, value: str) -> None:
        value = value.strip()
        if not value:
            return
        table, column = self._resolve(directory)
        with self.db.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table} ({column}) VALUES (%s) ON CONFLICT ({column}) DO NOTHING",
                (value,),
            )

    def add_many(self, directory: str, values: Iterable[str]) -> None:
        for value in values:
            self.add_value(directory, value)

    def update_value(self, directory: str, old_value: str, new_value: str) -> None:
        old_value = old_value.strip()
        new_value = new_value.strip()
        if not old_value or not new_value or old_value == new_value:
            return

        table, column = self._resolve(directory)
        with self.db.cursor(dictionary=True) as cursor:
            cursor.execute(f"SELECT 1 FROM {table} WHERE {column} = %s", (new_value,))
            if cursor.fetchone():
                raise ValueError("Такое значение уже есть в справочнике")

            cursor.execute(
                f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
                (new_value, old_value),
            )

    def delete_value(self, directory: str, value: str) -> None:
        value = value.strip()
        if not value:
            return

        table, column = self._resolve(directory)
        with self.db.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE {column} = %s", (value,))

    def _resolve(self, directory: str) -> tuple[str, str]:
        if directory not in self.TABLES:
            raise ValueError(f"Неизвестный справочник: {directory}")
        return self.TABLES[directory]


class GradeRuleRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_rules(self) -> list[GradeRule]:
        with self.db.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT min_percent, max_percent, grade_number, grade_short, grade_full
                FROM grade_rules
                ORDER BY grade_number DESC, min_percent DESC
                """
            )
            rules = []
            for row in cursor.fetchall():
                rules.append(
                    GradeRule(
                        min_percent=Decimal(str(row["min_percent"])),
                        max_percent=Decimal(str(row["max_percent"])),
                        grade_number=int(row["grade_number"]),
                        grade_short=str(row["grade_short"]),
                        grade_full=str(row["grade_full"]),
                    )
                )
            return rules

    def replace_rules(self, rules: list[GradeRule]) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM grade_rules")
            for rule in rules:
                cursor.execute(
                    """
                    INSERT INTO grade_rules
                    (min_percent, max_percent, grade_number, grade_short, grade_full)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        rule.min_percent,
                        rule.max_percent,
                        rule.grade_number,
                        rule.grade_short,
                        rule.grade_full,
                    ),
                )


class GeneratedStatementRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    def save(
        self,
        subject_name: str,
        group_name: str,
        specialty_name: str,
        teacher_name: str,
        source_excel_file: str,
        output_docx_file: str,
    ) -> None:
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO generated_statements
                (subject_name, group_name, specialty_name, teacher_name, source_excel_file, output_docx_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    subject_name,
                    group_name,
                    specialty_name,
                    teacher_name,
                    source_excel_file,
                    output_docx_file,
                ),
            )

    def list_recent(self, limit: int = 100) -> list[GeneratedStatement]:
        with self.db.cursor(dictionary=True) as cursor:
            cursor.execute(
                """
                SELECT id, subject_name, group_name, specialty_name, teacher_name,
                       source_excel_file, output_docx_file, created_at
                FROM generated_statements
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [
                GeneratedStatement(
                    id=int(row["id"]),
                    subject_name=str(row.get("subject_name") or ""),
                    group_name=str(row.get("group_name") or ""),
                    specialty_name=str(row.get("specialty_name") or ""),
                    teacher_name=str(row.get("teacher_name") or ""),
                    source_excel_file=str(row.get("source_excel_file") or ""),
                    output_docx_file=str(row.get("output_docx_file") or ""),
                    created_at=row.get("created_at"),
                )
                for row in cursor.fetchall()
            ]
