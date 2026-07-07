from __future__ import annotations

from functools import partial

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)


class StatementForm(QGroupBox):
    add_value_requested = Signal(str, str)
    moodle_filter_changed = Signal()
    FIELD_HEIGHT = 36
    FIELD_ROW_HEIGHT = 40
    ALL_MOODLE_FILTER_LABEL = "Все из файла"
    EMPTY_MOODLE_FILTER_LABEL = "Без инд. номера"
    SELECT_MOODLE_FILTER_LABEL = "Выберите инд. номер"

    test_started_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Данные ведомости", parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(256)
        self.setMaximumHeight(256)

        self.subject_combo = self._combo()
        self.group_combo = self._combo()
        self.specialty_combo = self._combo()
        self.teacher_combo = self._combo()
        self.semester_combo = self._combo()
        self.academic_year_combo = self._combo()
        self.control_form_combo = self._combo()
        self.exam_date_edit = self._date_edit()
        self.department_head_combo = self._combo()
        self.control_form_combo.setEditText("диф.зачет")
        self.ofo_widgets: list[QWidget] = []
        self.moodle_filter_values: list[str] = []
        self.selected_moodle_filters: set[str] = set()
        self.moodle_filter_edit = QLineEdit()
        self.moodle_filter_edit.setReadOnly(True)
        self.moodle_filter_edit.setFixedHeight(self.FIELD_HEIGHT)
        self.moodle_filter_edit.setAlignment(Qt.AlignVCenter)
        self.moodle_filter_menu = QMenu(self)
        self.moodle_filter_button = QToolButton()
        self.moodle_filter_button.setObjectName("fieldDropdownButton")
        self.moodle_filter_button.setText("⌄")
        self.moodle_filter_button.setFixedSize(34, self.FIELD_HEIGHT)
        self.moodle_filter_button.setToolTip("Выбрать инд. номера Moodle")
        self.moodle_filter_button.clicked.connect(self._show_moodle_filter_menu)

        self.test_started_filter = QComboBox()
        self.test_started_filter.setFixedHeight(self.FIELD_HEIGHT)
        self.test_started_filter.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.test_started_filter.setEditable(False)
        self.test_started_filter.addItem("Все даты")
        self.test_started_filter.currentTextChanged.connect(self._emit_test_started_changed)

        self.include_percent_checkbox = QCheckBox("Добавлять проценты в итоговую ведомость")
        self.include_percent_checkbox.setChecked(False)

        self.form_layout = QGridLayout(self)
        self.form_layout.setContentsMargins(18, 22, 18, 16)
        self.form_layout.setHorizontalSpacing(14)
        self.form_layout.setVerticalSpacing(10)
        self.form_layout.setColumnStretch(0, 0)
        self.form_layout.setColumnStretch(1, 1)
        self.form_layout.setColumnStretch(2, 0)
        self.form_layout.setColumnStretch(3, 1)
        self._add_grid_row(self.form_layout, 0, 0, "По предмету:", self._field_row("subjects", self.subject_combo))
        self._add_grid_row(self.form_layout, 0, 2, "Группа:", self._field_row("groups", self.group_combo))
        self._add_grid_row(self.form_layout, 1, 0, "Специальность:", self._field_row("specialties", self.specialty_combo))
        self._add_grid_row(self.form_layout, 1, 2, "Преподаватель:", self._field_row("teachers", self.teacher_combo))
        self._add_ofo_grid_row(self.form_layout, 2, 0, "Семестр:", self._field_row("semesters", self.semester_combo))
        self._add_ofo_grid_row(self.form_layout, 2, 2, "Учебный год:", self._field_row("academic_years", self.academic_year_combo))
        self._add_ofo_grid_row(self.form_layout, 3, 0, "Форма контроля:", self._field_row("control_forms", self.control_form_combo))
        self._add_ofo_grid_row(self.form_layout, 3, 2, "Дата проведения:", self.exam_date_edit)
        self._add_ofo_grid_row(self.form_layout, 4, 0, "Зав. отделением:", self._field_row("department_heads", self.department_head_combo), field_span=3)
        self.moodle_filter_label = QLabel("Инд. номер Moodle:", self)
        self.moodle_filter_label.setMinimumWidth(140)
        self.moodle_filter_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.moodle_filter_container = self._moodle_filter_row()
        self.form_layout.addWidget(self.moodle_filter_label, 5, 0)
        self.form_layout.addWidget(self.moodle_filter_container, 5, 1, 1, 3)
        self.form_layout.setRowMinimumHeight(6, 30)
        self.form_layout.addWidget(self.include_percent_checkbox, 6, 1, 1, 3)

        self.group_combo.currentTextChanged.connect(lambda _text: self.moodle_filter_changed.emit())
        self.set_mode("ИФО")

    def _add_grid_row(
        self,
        layout: QGridLayout,
        row_index: int,
        column_index: int,
        label_text: str,
        field_widget: QWidget,
        field_span: int = 1,
    ) -> None:
        label = QLabel(label_text, self)
        label.setMinimumWidth(140)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setRowMinimumHeight(row_index, self.FIELD_ROW_HEIGHT)
        layout.addWidget(label, row_index, column_index)
        layout.addWidget(field_widget, row_index, column_index + 1, 1, field_span)

    def _add_ofo_grid_row(
        self,
        layout: QGridLayout,
        row_index: int,
        column_index: int,
        label_text: str,
        field_widget: QWidget,
        field_span: int = 1,
    ) -> None:
        label = QLabel(label_text, self)
        label.setMinimumWidth(140)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setRowMinimumHeight(row_index, self.FIELD_ROW_HEIGHT)
        layout.addWidget(label, row_index, column_index)
        layout.addWidget(field_widget, row_index, column_index + 1, 1, field_span)
        self.ofo_widgets.extend([label, field_widget])

    @staticmethod
    def _combo() -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setMaxVisibleItems(12)
        combo.setFixedHeight(StatementForm.FIELD_HEIGHT)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if combo.lineEdit():
            combo.lineEdit().setFixedHeight(StatementForm.FIELD_HEIGHT - 2)
            combo.lineEdit().setAlignment(Qt.AlignVCenter)

        completer = QCompleter(combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)
        return combo

    @staticmethod
    def _line_edit(default_text: str = "") -> QLineEdit:
        edit = QLineEdit()
        edit.setFixedHeight(StatementForm.FIELD_HEIGHT)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        edit.setText(default_text)
        edit.setAlignment(Qt.AlignVCenter)
        return edit

    @staticmethod
    def _date_edit() -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        edit.setDate(QDate.currentDate())
        edit.setMinimumDate(QDate(1900, 1, 1))
        edit.setMaximumDate(QDate(2100, 12, 31))
        edit.setFixedHeight(StatementForm.FIELD_HEIGHT)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        edit.setAlignment(Qt.AlignVCenter)
        edit.setToolTip("Введите дату вручную или выберите в календаре")
        return edit

    def set_mode(self, mode: str) -> None:
        is_ofo = mode == "ОФО"
        for widget in self.ofo_widgets:
            widget.setVisible(is_ofo)
        self.form_layout.removeWidget(self.moodle_filter_label)
        self.form_layout.removeWidget(self.moodle_filter_container)
        moodle_row = 5 if is_ofo else 2
        checkbox_row = 6 if is_ofo else 3
        self.form_layout.addWidget(self.moodle_filter_label, moodle_row, 0)
        self.form_layout.addWidget(self.moodle_filter_container, moodle_row, 1, 1, 3)
        self.form_layout.removeWidget(self.include_percent_checkbox)
        self.form_layout.addWidget(self.include_percent_checkbox, checkbox_row, 1, 1, 3)
        for row in range(2, 7):
            self.form_layout.setRowMinimumHeight(row, self.FIELD_ROW_HEIGHT if row <= checkbox_row else 0)
        for row in (2, 3, 4):
            self.form_layout.setRowMinimumHeight(row, self.FIELD_ROW_HEIGHT if is_ofo else 0)
        self.form_layout.setRowMinimumHeight(moodle_row, self.FIELD_ROW_HEIGHT)
        height = 376 if is_ofo else 256
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def _field_row(self, directory: str, combo: QComboBox) -> QWidget:
        row = QWidget(self)
        row.setFixedHeight(self.FIELD_ROW_HEIGHT)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        dropdown_button = QToolButton(row)
        dropdown_button.setObjectName("fieldDropdownButton")
        dropdown_button.setText("⌄")
        dropdown_button.setFixedSize(34, self.FIELD_HEIGHT)
        dropdown_button.setToolTip("Открыть список")
        dropdown_button.clicked.connect(combo.showPopup)

        add_button = QPushButton("+", row)
        add_button.setObjectName("fieldAddButton")
        add_button.setFixedSize(40, self.FIELD_HEIGHT)
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
        row.setFixedHeight(self.FIELD_ROW_HEIGHT)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.moodle_filter_edit, stretch=1)
        layout.addWidget(self.moodle_filter_button)
        layout.addWidget(QLabel("Дата:"), alignment=Qt.AlignVCenter)
        layout.addWidget(self.test_started_filter)
        return row

    def set_values(
        self,
        subjects: list[str],
        groups: list[str],
        specialties: list[str],
        teachers: list[str],
        semesters: list[str] | None = None,
        academic_years: list[str] | None = None,
        control_forms: list[str] | None = None,
        department_heads: list[str] | None = None,
    ) -> None:
        self._fill(self.subject_combo, subjects)
        self._fill(self.group_combo, groups)
        self._fill(self.specialty_combo, specialties)
        self._fill(self.teacher_combo, teachers)
        self._fill(self.semester_combo, semesters or [])
        self._fill(self.academic_year_combo, academic_years or [])
        self._fill(self.control_form_combo, control_forms or [])
        self._fill(self.department_head_combo, department_heads or [])

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

    def set_exam_date(self, date_text: str) -> None:
        date_text = str(date_text or "").strip()
        if not date_text:
            self.exam_date_edit.setDate(QDate.currentDate())
            return

        for date_format in ("dd.MM.yyyy", "yyyy-MM-dd", "dd.MM.yy"):
            date = QDate.fromString(date_text, date_format)
            if date.isValid():
                self.exam_date_edit.setDate(date)
                return

        self.exam_date_edit.lineEdit().setText(date_text)

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

    def _emit_test_started_changed(self) -> None:
        self.test_started_changed.emit()

    def get_test_started_date(self) -> str | None:
        current = self.test_started_filter.currentText()
        if not current or current == "Все даты":
            return None
        return current

    def set_test_started_date(self, date_text: str | None) -> None:
        selected = date_text or "Все даты"
        if selected not in [self.test_started_filter.itemText(i) for i in range(self.test_started_filter.count())]:
            self.test_started_filter.addItem(selected)
        self.test_started_filter.blockSignals(True)
        self.test_started_filter.setCurrentText(selected)
        self.test_started_filter.blockSignals(False)
        self.test_started_changed.emit()

    def set_test_started_options(self, dates: list[str]) -> None:
        selected = self.get_test_started_date() or "Все даты"
        self.test_started_filter.blockSignals(True)
        self.test_started_filter.clear()
        self.test_started_filter.addItem("Все даты")
        for date in dates:
            self.test_started_filter.addItem(date)
        self.test_started_filter.setCurrentText(selected)
        if self.test_started_filter.currentText() != selected:
            self.test_started_filter.setCurrentText("Все даты")
        self.test_started_filter.blockSignals(False)

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
            "semester": self.semester_combo.currentText().strip(),
            "academic_year": self.academic_year_combo.currentText().strip(),
            "control_form": self.control_form_combo.currentText().strip(),
            "exam_date": self.exam_date_edit.text().strip(),
            "department_head": self.department_head_combo.currentText().strip(),
            "include_percent": self.include_percent_checkbox.isChecked(),
        }
