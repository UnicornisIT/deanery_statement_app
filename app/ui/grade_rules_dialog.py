from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.db.models import GradeRule
from app.db.repositories import GradeRuleRepository


class GradeRulesDialog(QDialog):
    rules_changed = Signal()
    HEADERS = ["Мин. %", "Макс. %", "Оценка", "Кратко", "Полностью"]

    def __init__(self, repository: GradeRuleRepository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Правила оценивания")
        self.resize(760, 420)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        add_button = QPushButton("Добавить строку", self)
        delete_button = QPushButton("Удалить строку", self)
        save_button = QPushButton("Сохранить", self)
        close_button = QPushButton("Закрыть", self)

        add_button.clicked.connect(self._add_row)
        delete_button.clicked.connect(self._delete_row)
        save_button.clicked.connect(self._save)
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(buttons)

        self.reload()

    def reload(self) -> None:
        try:
            rules = self.repository.get_rules()
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить правила: {exc}")
            return

        self.table.setRowCount(len(rules))
        for row_index, rule in enumerate(rules):
            values = [
                str(rule.min_percent),
                str(rule.max_percent),
                str(rule.grade_number),
                rule.grade_short,
                rule.grade_full,
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def _add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        defaults = ["0", "100", "5", "отл", "отлично"]
        for col_index, value in enumerate(defaults):
            self.table.setItem(row, col_index, QTableWidgetItem(value))
        self.table.setCurrentCell(row, 0)

    def _delete_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _save(self) -> None:
        try:
            rules = self._read_rules()
            self.repository.replace_rules(rules)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить правила: {exc}")
            return

        self.rules_changed.emit()
        QMessageBox.information(self, "Правила оценивания", "Правила сохранены")
        self.reload()

    def _read_rules(self) -> list[GradeRule]:
        rules: list[GradeRule] = []
        for row in range(self.table.rowCount()):
            values = [
                self.table.item(row, col).text().strip() if self.table.item(row, col) else ""
                for col in range(self.table.columnCount())
            ]
            if not any(values):
                continue
            min_percent = Decimal(values[0])
            max_percent = Decimal(values[1])
            grade_number = int(values[2])
            if min_percent > max_percent:
                raise ValueError(f"В строке {row + 1} минимум больше максимума")
            if not values[3] or not values[4]:
                raise ValueError(f"В строке {row + 1} заполните названия оценки")
            rules.append(
                GradeRule(
                    min_percent=min_percent,
                    max_percent=max_percent,
                    grade_number=grade_number,
                    grade_short=values[3],
                    grade_full=values[4],
                )
            )
        if not rules:
            raise ValueError("Добавьте хотя бы одно правило")
        return rules
