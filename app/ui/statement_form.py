from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)


class StatementForm(QGroupBox):
    add_value_requested = Signal(str, str)
    moodle_filter_changed = Signal()
    ALL_MOODLE_FILTER_LABEL = "Все из файла"
    EMPTY_MOODLE_FILTER_LABEL = "Без инд. номера"
    SELECT_MOODLE_FILTER_LABEL = "Выберите инд. номер"

    def __init__(self, parent=None):
        super().__init__("Данные ведомости", parent)

        self.subject_combo = self._combo()
        self.group_combo = self._combo()
        self.specialty_combo = self._combo()
        self.teacher_combo = self._combo()
        self.moodle_filter_values: list[str] = []
        self.selected_moodle_filters: set[str] = set()
        self.moodle_filter_edit = QLineEdit()
        self.moodle_filter_edit.setReadOnly(True)
        self.moodle_filter_menu = QMenu(self)
        self.moodle_filter_button = QToolButton()
        self.moodle_filter_button.setObjectName("fieldDropdownButton")
        self.moodle_filter_button.setText("⌄")
        self.moodle_filter_button.setFixedSize(28, 36)
        self.moodle_filter_button.setToolTip("Выбрать инд. номера Moodle")
        self.moodle_filter_button.clicked.connect(self._show_moodle_filter_menu)
        self.include_percent_checkbox = QCheckBox("Добавлять проценты в итоговую ведомость")
        self.include_percent_checkbox.setChecked(False)

        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addRow("По предмету:", self._field_row("subjects", self.subject_combo))
        layout.addRow("Группа:", self._field_row("groups", self.group_combo))
        layout.addRow("Специальность:", self._field_row("specialties", self.specialty_combo))
        layout.addRow("Преподаватель:", self._field_row("teachers", self.teacher_combo))
        layout.addRow("Инд. номер Moodle:", self._moodle_filter_row())
        layout.addRow("", self.include_percent_checkbox)

        self.group_combo.currentTextChanged.connect(self.moodle_filter_changed.emit)

    @staticmethod
    def _combo() -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setMaxVisibleItems(12)

        completer = QCompleter(combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)
        return combo

    def _field_row(self, directory: str, combo: QComboBox) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        dropdown_button = QToolButton(row)
        dropdown_button.setObjectName("fieldDropdownButton")
        dropdown_button.setText("⌄")
        dropdown_button.setFixedSize(28, 36)
        dropdown_button.setToolTip("Открыть список")
        dropdown_button.clicked.connect(combo.showPopup)

        add_button = QPushButton("+", row)
        add_button.setObjectName("fieldAddButton")
        add_button.setFixedSize(36, 36)
        add_button.setToolTip("Добавить текущее значение в справочник")
        add_button.clicked.connect(partial(self._request_add_value, directory, combo))

        layout.addWidget(combo, stretch=1)
        layout.addWidget(dropdown_button)
        layout.addWidget(add_button)
        return row

    def _request_add_value(self, directory: str, combo: QComboBox) -> None:
        self.add_value_requested.emit(directory, combo.currentText().strip())

    def _moodle_filter_row(self) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.moodle_filter_edit, stretch=1)
        layout.addWidget(self.moodle_filter_button)
        return row

    def set_values(
        self,
        subjects: list[str],
        groups: list[str],
        specialties: list[str],
        teachers: list[str],
    ) -> None:
        self._fill(self.subject_combo, subjects)
        self._fill(self.group_combo, groups)
        self._fill(self.specialty_combo, specialties)
        self._fill(self.teacher_combo, teachers)

    @staticmethod
    def _fill(combo: QComboBox, values: list[str]) -> None:
        current = combo.currentText().strip()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        if combo.completer():
            combo.completer().setModel(combo.model())
        if current:
            index = combo.findText(current)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                combo.setEditText(current)
        combo.blockSignals(False)

    def set_subject(self, subject: str) -> None:
        if subject:
            self.subject_combo.setEditText(subject)

    def set_moodle_filter_values(self, values: list[str], include_empty: bool = False) -> None:
        previous = self.selected_moodle_filters
        self.moodle_filter_values = [self.EMPTY_MOODLE_FILTER_LABEL, *values] if include_empty else values
        self.selected_moodle_filters = {value for value in previous if value in self.moodle_filter_values}
        self._rebuild_moodle_filter_menu()
        self._update_moodle_filter_text()

    def get_moodle_filters(self) -> list[str]:
        return [value for value in self.moodle_filter_values if value in self.selected_moodle_filters]

    def _show_moodle_filter_menu(self) -> None:
        self.moodle_filter_menu.popup(self.moodle_filter_button.mapToGlobal(self.moodle_filter_button.rect().bottomLeft()))

    def _rebuild_moodle_filter_menu(self) -> None:
        self.moodle_filter_menu.clear()

        for value in self.moodle_filter_values:
            action = QAction(value, self.moodle_filter_menu)
            action.setCheckable(True)
            action.setChecked(value in self.selected_moodle_filters)
            action.triggered.connect(partial(self._toggle_moodle_filter, value))
            self.moodle_filter_menu.addAction(action)

    def _toggle_moodle_filter(self, value: str, *_args) -> None:
        if value in self.selected_moodle_filters:
            self.selected_moodle_filters.remove(value)
        else:
            self.selected_moodle_filters.add(value)
        self._rebuild_moodle_filter_menu()
        self._update_moodle_filter_text()
        self.moodle_filter_changed.emit()

    def _update_moodle_filter_text(self) -> None:
        selected = self.get_moodle_filters()
        if not self.moodle_filter_values:
            self.moodle_filter_edit.setText("")
        elif not selected:
            self.moodle_filter_edit.setText(self.ALL_MOODLE_FILTER_LABEL)
        elif len(selected) <= 2:
            self.moodle_filter_edit.setText(", ".join(selected))
        else:
            self.moodle_filter_edit.setText(f"Выбрано: {len(selected)}")

    def get_data(self) -> dict[str, str | bool]:
        return {
            "subject": self.subject_combo.currentText().strip(),
            "group": self.group_combo.currentText().strip(),
            "specialty": self.specialty_combo.currentText().strip(),
            "teacher": self.teacher_combo.currentText().strip(),
            "include_percent": self.include_percent_checkbox.isChecked(),
        }
