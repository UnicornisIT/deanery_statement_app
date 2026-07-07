from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from app.services.docx_generator import StatementStudent


class PreviewTable(QTableWidget):
    HEADERS = ["№", "ФИО студента", "Инд. номер", "Тест начат", "Процент", "Оценка", "Примечание"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)

    def set_students(self, students: list[StatementStudent]) -> None:
        self.setRowCount(len(students))
        for row_idx, student in enumerate(students):
            values = [
                str(student.number) if student.number else "",
                student.full_name,
                student.individual_number,
                student.test_started,
                f"{student.percent}%",
                student.grade.formatted_grade,
                student.note,
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_idx in (0, 2, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row_idx, col_idx, item)
