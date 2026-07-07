from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.db.models import GeneratedStatement
from app.db.repositories import GeneratedStatementRepository
from app.services.print_service import PrintService


class HistoryDialog(QDialog):
    HEADERS = ["Дата", "Предмет", "Группа", "Преподаватель", "Документ"]

    def __init__(self, repository: GeneratedStatementRepository, print_service: PrintService, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.print_service = print_service
        self.records: list[GeneratedStatement] = []

        self.setWindowTitle("История ведомостей")
        self.resize(980, 520)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        refresh_button = QPushButton("Обновить", self)
        open_button = QPushButton("Открыть документ", self)
        folder_button = QPushButton("Открыть папку", self)
        close_button = QPushButton("Закрыть", self)

        refresh_button.clicked.connect(self.reload)
        open_button.clicked.connect(self._open_selected_document)
        folder_button.clicked.connect(self._open_selected_folder)
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(refresh_button)
        buttons.addWidget(open_button)
        buttons.addWidget(folder_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(buttons)

        self.reload()

    def reload(self) -> None:
        try:
            self.records = self.repository.list_recent()
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить историю: {exc}")
            return

        self.table.setRowCount(len(self.records))
        for row_index, record in enumerate(self.records):
            created = record.created_at.strftime("%d.%m.%Y %H:%M") if record.created_at else ""
            values = [
                created,
                record.subject_name,
                record.group_name,
                record.teacher_name,
                record.output_docx_file,
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        if self.table.rowCount():
            self.table.setCurrentCell(0, 0)

    def _selected_record(self) -> GeneratedStatement | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            QMessageBox.information(self, "История", "Выберите запись в истории")
            return None
        return self.records[row]

    def _open_selected_document(self) -> None:
        record = self._selected_record()
        if not record:
            return
        try:
            self.print_service.open_file(record.output_docx_file)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))

    def _open_selected_folder(self) -> None:
        record = self._selected_record()
        if not record:
            return
        try:
            self.print_service.open_folder(Path(record.output_docx_file).parent)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
