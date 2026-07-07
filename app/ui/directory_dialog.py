from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.db.repositories import DirectoryRepository


DIRECTORIES = (
    ("subjects", "Предметы", "Новый предмет"),
    ("groups", "Группы", "Новая группа"),
    ("specialties", "Специальности", "Новая специальность"),
    ("teachers", "Преподаватели", "ФИО преподавателя"),
    ("semesters", "Семестры", "Номер семестра"),
    ("academic_years", "Учебные годы", "Учебный год"),
    ("control_forms", "Формы контроля", "Форма контроля"),
    ("department_heads", "Зав. отделением", "ФИО заведующего отделением"),
)


class DirectoryManagerDialog(QDialog):
    data_changed = Signal()

    def __init__(self, repository: DirectoryRepository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Справочники")
        self.resize(720, 520)

        self.tabs = QTabWidget(self)
        for key, title, placeholder in DIRECTORIES:
            page = DirectoryPage(repository, key, placeholder, self)
            page.data_changed.connect(self.data_changed.emit)
            self.tabs.addTab(page, title)

        close_button = QPushButton("Закрыть", self)
        close_button.clicked.connect(self.accept)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.tabs)
        layout.addLayout(footer)


class DirectoryPage(QWidget):
    data_changed = Signal()

    def __init__(self, repository: DirectoryRepository, directory: str, placeholder: str, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.directory = directory
        self.values: list[str] = []

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Поиск")

        self.list_widget = QListWidget(self)

        self.value_edit = QLineEdit(self)
        self.value_edit.setPlaceholderText(placeholder)

        self.add_button = QPushButton("Добавить", self)
        self.rename_button = QPushButton("Изменить", self)
        self.delete_button = QPushButton("Удалить", self)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.add_button)
        actions.addWidget(self.rename_button)
        actions.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Найти значение:", self))
        layout.addWidget(self.search_edit)
        layout.addWidget(self.list_widget, stretch=1)
        layout.addWidget(QLabel("Значение:", self))
        layout.addWidget(self.value_edit)
        layout.addLayout(actions)

        self.search_edit.textChanged.connect(self._apply_filter)
        self.list_widget.currentTextChanged.connect(self.value_edit.setText)
        self.add_button.clicked.connect(self._add_value)
        self.rename_button.clicked.connect(self._rename_value)
        self.delete_button.clicked.connect(self._delete_value)

        self.reload()

    def reload(self) -> None:
        try:
            self.values = self.repository.list_values(self.directory)
            self._apply_filter()
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить справочник: {exc}")

    def _apply_filter(self, *_args) -> None:
        query = self.search_edit.text().strip().lower()
        current = self.list_widget.currentItem().text() if self.list_widget.currentItem() else ""

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for value in self.values:
            if not query or query in value.lower():
                self.list_widget.addItem(value)
        self.list_widget.blockSignals(False)

        matches = self.list_widget.findItems(current, Qt.MatchExactly) if current else []
        if matches:
            self.list_widget.setCurrentItem(matches[0])
        elif self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self.value_edit.clear()

    def _add_value(self) -> None:
        value = self.value_edit.text().strip()
        if not value:
            QMessageBox.warning(self, "Ошибка", "Введите значение для добавления")
            return

        try:
            self.repository.add_value(self.directory, value)
            self._after_change(value)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось добавить значение: {exc}")

    def _rename_value(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, "Ошибка", "Выберите значение для изменения")
            return

        old_value = item.text()
        new_value = self.value_edit.text().strip()
        if not new_value:
            QMessageBox.warning(self, "Ошибка", "Введите новое значение")
            return

        try:
            self.repository.update_value(self.directory, old_value, new_value)
            self._after_change(new_value)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось изменить значение: {exc}")

    def _delete_value(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, "Ошибка", "Выберите значение для удаления")
            return

        value = item.text()
        answer = QMessageBox.question(
            self,
            "Удаление",
            f"Удалить значение «{value}» из справочника?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.repository.delete_value(self.directory, value)
            self._after_change("")
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить значение: {exc}")

    def _after_change(self, selected_value: str) -> None:
        self.values = self.repository.list_values(self.directory)
        self._apply_filter()
        if selected_value:
            matches = self.list_widget.findItems(selected_value, Qt.MatchExactly)
            if matches:
                self.list_widget.setCurrentItem(matches[0])
        self.data_changed.emit()
