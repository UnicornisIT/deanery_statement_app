from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QHeaderView,
    QItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

from app.services.docx_generator import StatementStudent


class DateDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QDateEdit(parent)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd.MM.yyyy")
        editor.setDate(QDate.currentDate())
        editor.setMinimumDate(QDate(1900, 1, 1))
        editor.setMaximumDate(QDate(2100, 12, 31))
        editor.setStyleSheet(
            "QDateEdit { border: 1px solid #4f5b93; border-radius: 6px; padding: 2px 6px; }"
            "QDateEdit::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 18px; }"
        )
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or ""
        date = QDate.currentDate()
        parsed = PreviewTable._parse_date_text(str(value))
        if parsed is not None:
            date = parsed
        editor.setDate(date)

    def setModelData(self, editor, model, index):
        date = editor.date()
        model.setData(index, date.toString("dd.MM.yyyy"), Qt.EditRole)


class PreviewTable(QTableWidget):
    HEADERS = ["№", "ФИО студента", "Инд. номер", "Тест начат", "Процент", "Оценка", "Примечание"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.AllEditTriggers)
        self.setItemDelegateForColumn(3, DateDelegate(self))
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
                display_value = self._format_display_value(col_idx, value)
                item = QTableWidgetItem(display_value)
                if col_idx in (0, 2, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 3:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, student)
                self.setItem(row_idx, col_idx, item)

    @staticmethod
    def _format_display_value(column: int, value: str) -> str:
        if column != 3 or not value:
            return value
        parsed = PreviewTable._parse_date_text(value)
        return parsed.toString("dd.MM.yyyy") if parsed else value

    @staticmethod
    def _parse_date_text(value: str) -> QDate | None:
        if not value:
            return None
        text = value.strip()
        if text.isdigit():
            if len(text) == 8:
                day, month, year = text[:2], text[2:4], text[4:]
                qdate = QDate.fromString(f"{day}.{month}.{year}", "dd.MM.yyyy")
                return qdate if qdate.isValid() else None
            if len(text) == 4:
                day, month = text[:2], text[2:]
                today = QDate.currentDate()
                qdate = QDate(today.year(), int(month), int(day))
                return qdate if qdate.isValid() else None
        qdate = QDate.fromString(text, "dd.MM.yyyy")
        if qdate.isValid():
            return qdate
        qdate = QDate.fromString(text, "yyyy-MM-dd")
        if qdate.isValid():
            return qdate
        return None
