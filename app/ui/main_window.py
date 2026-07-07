from __future__ import annotations

import logging
import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QThread, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.db.connection import DatabaseConnection
from app.db.repositories import DirectoryRepository, GeneratedStatementRepository, GradeRuleRepository
from app.services.docx_generator import DocxGenerator, StatementData, StatementStudent
from app.services.excel_parser import StudentResult
from app.services.grade_service import GradeService
from app.services.pdf_exporter import PdfExporter
from app.services.print_service import PrintService
from app.ui.directory_dialog import DirectoryManagerDialog
from app.ui.excel_load_worker import ExcelLoadWorker
from app.ui.grade_rules_dialog import GradeRulesDialog
from app.ui.history_dialog import HistoryDialog
from app.ui.loading_overlay import LoadingOverlay
from app.ui.preview_table import PreviewTable
from app.ui.statement_form import StatementForm

logger = logging.getLogger(__name__)


class ModeSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_mode = ""
        self.setWindowTitle("Выберите режим ведомости")
        self.resize(360, 160)
        self.setModal(True)

        title_label = QLabel("Выберите режим работы:", self)
        title_label.setAlignment(Qt.AlignCenter)

        ifo_button = QPushButton("ИФО", self)
        ifo_button.clicked.connect(lambda: self._select_mode("ИФО"))
        ifo_button.setToolTip("Открыть окно для очно-заочной формы обучения")

        ofo_button = QPushButton("ОФО", self)
        ofo_button.clicked.connect(lambda: self._select_mode("ОФО"))
        ofo_button.setToolTip("Открыть окно для очной формы обучения")

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(ifo_button)
        buttons_layout.addWidget(ofo_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(title_label)
        layout.addLayout(buttons_layout)

    def _select_mode(self, mode: str) -> None:
        self.selected_mode = mode
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, mode: str = "ИФО"):
        super().__init__()
        self.config = config
        self.mode = mode
        self.setWindowTitle(f"Формирование ведомостей из Moodle — {self.mode}")
        self.resize(1100, 720)

        self.db = DatabaseConnection(config.database)
        self.directory_repo = DirectoryRepository(self.db)
        self.grade_rule_repo = GradeRuleRepository(self.db)
        self.grade_service = GradeService(self.grade_rule_repo)
        self.history_repo = GeneratedStatementRepository(self.db)
        self.pdf_exporter = PdfExporter()
        self.print_service = PrintService()

        self.current_excel_path: Path | None = None
        self.current_docx_path: Path | None = None
        self.parsed_students: list[StudentResult] = []
        self.statement_students: list[StatementStudent] = []
        self.available_individual_numbers: list[str] = []
        self.current_template_path: Path = self._default_template_path()
        self.ui_state_path = config.base_dir / "app_state.json"
        self.excel_load_thread: QThread | None = None
        self.excel_load_worker: ExcelLoadWorker | None = None

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.choose_button = QPushButton("Выбрать Excel-файл")
        self.generate_button = QPushButton("Сформировать ведомость")
        self.open_button = QPushButton("Открыть документ")
        self.export_pdf_button = QPushButton("Экспорт в PDF")
        self.print_button = QPushButton("Печать")
        self.reload_dict_button = QPushButton("Справочники")
        self.package_button = QPushButton("DOCX + PDF")
        self.open_folder_button = QPushButton("Папка")
        self.history_button = QPushButton("История")
        self.template_button = QPushButton("Шаблон")
        self.grade_rules_button = QPushButton("Оценки")
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.addItems(["ИФО", "ОФО"])
        self.mode_combo.setCurrentText(self.mode)
        self.mode_combo.setFixedWidth(104)
        self.mode_combo.setFixedHeight(34)

        for button, width in (
            (self.generate_button, 220),
            (self.open_button, 170),
            (self.export_pdf_button, 140),
            (self.print_button, 90),
            (self.package_button, 120),
            (self.open_folder_button, 90),
            (self.history_button, 100),
            (self.template_button, 100),
            (self.grade_rules_button, 100),
            (self.reload_dict_button, 140),
        ):
            button.setMinimumWidth(width)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.form = StatementForm()
        self.form.setTitle(f"Данные ведомости ({self.mode})")
        self.form.set_mode(self.mode)
        self.preview_search_edit = QLineEdit()
        self.preview_search_edit.setPlaceholderText("Поиск в предпросмотре")
        self.preview_grade_filter = QComboBox()
        self.preview_grade_filter.addItems(["Все оценки", "5", "4", "3", "2"])
        self.preview_table = PreviewTable()
        self.preview_table.setMinimumHeight(120)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.validation_box = QPlainTextEdit()
        self.validation_box.setReadOnly(True)
        self.validation_box.setMaximumHeight(46)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_box.setMaximumHeight(56)
        self.footer_label = QLabel()
        self.footer_label.setObjectName("footerLabel")
        self.footer_label.setTextFormat(Qt.RichText)
        self.footer_label.setOpenExternalLinks(True)
        self.footer_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.footer_label.setWordWrap(True)
        self.footer_label.setText(
            "&#1056;&#1072;&#1079;&#1088;&#1072;&#1073;&#1086;&#1090;&#1095;&#1080;&#1082;: "
            "<a style=\"color:#7dd3fc; text-decoration:none;\" "
            "href=\"https://github.com/UnicornisIT\">UnicornisIT</a>"
            " &middot; "
            "&#1048;&#1076;&#1077;&#1080; &#1080; "
            "&#1087;&#1088;&#1077;&#1076;&#1083;&#1086;&#1078;&#1077;&#1085;&#1080;&#1103;: "
            "<a style=\"color:#7dd3fc; text-decoration:none;\" "
            "href=\"mailto:earov18@outlook.com\">earov18@outlook.com</a>"
            " &middot; Telegram: "
            "<a style=\"color:#7dd3fc; text-decoration:none;\" "
            "href=\"https://t.me/unicornis_pulse\">t.me/unicornis_pulse</a>"
        )

        self._apply_button_roles()
        self._build_menu()
        self._build_layout()
        self._connect_signals()
        self._set_document_actions_enabled(False)
        self._load_dictionaries()
        self._load_ui_state()

    def closeEvent(self, event) -> None:
        if self.excel_load_thread and self.excel_load_thread.isRunning():
            QMessageBox.information(self, "Загрузка", "Дождитесь окончания загрузки Excel-файла.")
            event.ignore()
            return
        self._save_ui_state()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "loading_overlay") and self.loading_overlay.parentWidget():
            self.loading_overlay.setGeometry(self.loading_overlay.parentWidget().rect())

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        self.file_menu = menu_bar.addMenu("Файл")
        self.file_menu.addAction(self._menu_action("Выбрать Excel-файл", self.choose_excel_file))
        self.file_menu.addAction(self._menu_action("Выбрать шаблон", self.choose_template))
        self.file_menu.addSeparator()
        self.file_menu.addAction(self._menu_action("Сформировать ведомость", self.generate_statement))
        self.file_menu.addAction(self._menu_action("Сформировать DOCX + PDF", self.generate_statement_package))

        self.edit_menu = menu_bar.addMenu("Правка")
        self.edit_menu.addAction(self._menu_action("Справочники", self.open_directory_manager))
        self.edit_menu.addAction(self._menu_action("Оценки", self.open_grade_rules))

        self.view_menu = menu_bar.addMenu("Вид")
        self.mode_menu = self.view_menu.addMenu("Режим")
        self.mode_menu.addAction(self._menu_action("ИФО", lambda: self.set_mode("ИФО")))
        self.mode_menu.addAction(self._menu_action("ОФО", lambda: self.set_mode("ОФО")))
        self.view_menu.addSeparator()
        self.view_menu.addAction(self._menu_action("История", self.open_history))
        self.view_menu.addAction(self._menu_action("Папка результата", self.open_output_folder))

        self.help_menu = menu_bar.addMenu("Справка")
        self.help_menu.addAction(self._menu_action("Проверка данных", self.show_validation_report))
        self.help_menu.addAction(self._menu_action("Сообщения", self.show_messages))
        self.help_menu.addSeparator()
        self.help_menu.addAction(self._menu_action("О программе", self._show_about))

    def _menu_action(self, title: str, handler) -> QAction:
        action = QAction(title, self)
        action.triggered.connect(lambda _checked=False: handler())
        return action

    def _show_about(self) -> None:
        message = QMessageBox(self)
        message.setWindowTitle("О программе")
        message.setTextFormat(Qt.RichText)
        message.setText(
            "Формирование ведомостей из Moodle<br><br>"
            "Разработчик: <a href=\"https://github.com/UnicornisIT\">UnicornisIT</a><br>"
            "Почта: <a href=\"mailto:earov18@outlook.com\">earov18@outlook.com</a><br>"
            "Telegram: <a href=\"https://t.me/unicornis_pulse\">t.me/unicornis_pulse</a><br>"
            "GitHub: <a href=\"https://github.com/UnicornisIT\">github.com/UnicornisIT</a>"
        )
        message.exec()

    def show_validation_report(self) -> None:
        text = self.validation_box.toPlainText().strip() or "Проверка данных пока не выполнялась."
        self._show_text_dialog("Проверка данных", text)

    def show_messages(self) -> None:
        text = self.log_box.toPlainText().strip() or "Сообщений пока нет."
        self._show_text_dialog("Сообщения", text)

    def _show_text_dialog(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 420)

        text_box = QPlainTextEdit(dialog)
        text_box.setReadOnly(True)
        text_box.setPlainText(text)

        close_button = QPushButton("Закрыть", dialog)
        close_button.clicked.connect(dialog.accept)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(text_box, stretch=1)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
        dialog.exec()

    def _apply_button_roles(self) -> None:
        primary_buttons = (self.choose_button, self.generate_button)
        secondary_buttons = (
            self.open_button,
            self.export_pdf_button,
            self.package_button,
            self.reload_dict_button,
            self.history_button,
            self.template_button,
            self.grade_rules_button,
        )
        tertiary_buttons = (self.print_button, self.open_folder_button)

        for button in primary_buttons:
            button.setProperty("role", "primary")
        for button in secondary_buttons:
            button.setProperty("role", "secondary")
        for button in tertiary_buttons:
            button.setProperty("role", "tertiary")
        for button in (*primary_buttons, *secondary_buttons, *tertiary_buttons):
            button.style().unpolish(button)
            button.style().polish(button)

    def _build_layout(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        self.choose_button.setMinimumWidth(185)
        self.choose_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.path_edit.setMinimumWidth(220)
        file_row.addWidget(self.choose_button)
        file_row.addWidget(QLabel("Файл:"))
        file_row.addWidget(self.path_edit, stretch=1)
        root.addLayout(file_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.addStretch(1)
        self.mode_label = QLabel("Режим:")
        self.mode_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_combo)
        root.addLayout(mode_row)
        root.addWidget(self.form)

        preview_tools = QHBoxLayout()
        preview_tools.setSpacing(8)
        preview_tools.addWidget(QLabel("Предварительный просмотр:"))
        preview_tools.addStretch(1)
        preview_tools.addWidget(self.preview_search_edit)
        preview_tools.addWidget(QLabel("Оценка:"))
        preview_tools.addWidget(self.preview_grade_filter)
        root.addLayout(preview_tools)
        root.addWidget(self.preview_table, stretch=1)

        actions_bar = QWidget(central)
        actions_bar.setObjectName("actionsBar")
        actions_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        actions = QHBoxLayout(actions_bar)
        actions.setContentsMargins(0, 8, 0, 8)
        actions.setSpacing(8)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.export_pdf_button)
        actions.addWidget(self.package_button)
        actions.addWidget(self.print_button)
        actions.addWidget(self.open_folder_button)
        actions.addStretch(1)
        root.addWidget(actions_bar)

        root.addWidget(self.footer_label)

        self.setCentralWidget(central)
        self.loading_overlay = LoadingOverlay(central)

    def _connect_signals(self) -> None:
        self.choose_button.clicked.connect(self.choose_excel_file)
        self.generate_button.clicked.connect(self.generate_statement)
        self.open_button.clicked.connect(self.open_document)
        self.export_pdf_button.clicked.connect(self.export_pdf)
        self.package_button.clicked.connect(self.generate_statement_package)
        self.print_button.clicked.connect(self.print_document)
        self.open_folder_button.clicked.connect(self.open_output_folder)
        self.history_button.clicked.connect(self.open_history)
        self.template_button.clicked.connect(self.choose_template)
        self.grade_rules_button.clicked.connect(self.open_grade_rules)
        self.reload_dict_button.clicked.connect(self.open_directory_manager)
        self.mode_combo.currentTextChanged.connect(self.set_mode)
        self.form.add_value_requested.connect(self.add_current_directory_value)
        self.form.moodle_filter_changed.connect(self.apply_student_filter)
        self.form.test_started_changed.connect(self.apply_student_filter)
        self.preview_search_edit.textChanged.connect(self.apply_preview_filter)
        self.preview_grade_filter.currentTextChanged.connect(self.apply_preview_filter)
        self.preview_table.horizontalHeader().sectionClicked.connect(self._handle_preview_header_clicked)
        self.preview_table.itemChanged.connect(self._handle_preview_item_changed)

    def _set_document_actions_enabled(self, enabled: bool) -> None:
        self.open_button.setEnabled(enabled)
        self.export_pdf_button.setEnabled(enabled)
        self.package_button.setEnabled(enabled)
        self.print_button.setEnabled(enabled)
        self.open_folder_button.setEnabled(enabled)

    def _load_dictionaries(self) -> None:
        try:
            self.form.set_values(
                subjects=self.directory_repo.list_values("subjects"),
                groups=self.directory_repo.list_values("groups"),
                specialties=self.directory_repo.list_values("specialties"),
                teachers=self.directory_repo.list_values("teachers"),
                semesters=self.directory_repo.list_values("semesters"),
                academic_years=self.directory_repo.list_values("academic_years"),
                control_forms=self.directory_repo.list_values("control_forms"),
                department_heads=self.directory_repo.list_values("department_heads"),
            )
            self.grade_service.reload_rules()
            self._info("Справочники и правила оценивания загружены из PostgreSQL")
        except Exception as exc:
            logger.exception("Ошибка загрузки справочников")
            self._error(
                "Не удалось загрузить справочники или правила оценивания из PostgreSQL. "
                "Проверьте config.ini, доступность PostgreSQL и SQL-скрипты. "
                f"Техническая причина: {exc}"
            )

    def _load_ui_state(self) -> None:
        if not self.ui_state_path.exists():
            return
        try:
            data = json.loads(self.ui_state_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Не удалось загрузить состояние интерфейса")
            return

        self._set_combo_text(self.form.subject_combo, data.get("subject", ""))
        self._set_combo_text(self.form.group_combo, data.get("group", ""))
        self._set_combo_text(self.form.specialty_combo, data.get("specialty", ""))
        self._set_combo_text(self.form.teacher_combo, data.get("teacher", ""))
        self.form.include_percent_checkbox.setChecked(bool(data.get("include_percent", False)))

        template_value = str(data.get("template_path", "")).strip()
        if self.mode == "ОФО":
            template_value = str(data.get("template_path_ofo", "")).strip()
        elif self.mode == "ИФО":
            template_value = str(data.get("template_path_ifo", template_value)).strip()
            if "statement_template_ofo" in template_value.lower():
                template_value = ""
        template_path = Path(template_value) if template_value else None
        if template_path and template_path.exists():
            self.current_template_path = template_path

        self._set_combo_text(self.form.semester_combo, str(data.get("semester", "")))
        self._set_combo_text(self.form.academic_year_combo, str(data.get("academic_year", "")))
        self._set_combo_text(self.form.control_form_combo, str(data.get("control_form", "диф.зачет") or "диф.зачет"))
        self.form.set_exam_date(str(data.get("exam_date", "")))
        self._set_combo_text(self.form.department_head_combo, str(data.get("department_head", "")))

    def _save_ui_state(self) -> None:
        try:
            form_data = self.form.get_data()
            existing_data = {}
            if self.ui_state_path.exists():
                try:
                    existing_data = json.loads(self.ui_state_path.read_text(encoding="utf-8"))
                except Exception:
                    existing_data = {}
            data = {
                **existing_data,
                "subject": form_data.get("subject", ""),
                "group": form_data.get("group", ""),
                "specialty": form_data.get("specialty", ""),
                "teacher": form_data.get("teacher", ""),
                "semester": form_data.get("semester", ""),
                "academic_year": form_data.get("academic_year", ""),
                "control_form": form_data.get("control_form", ""),
                "exam_date": form_data.get("exam_date", ""),
                "department_head": form_data.get("department_head", ""),
                "include_percent": bool(form_data.get("include_percent", False)),
                self._template_state_key(): str(self.current_template_path),
            }
            if self.mode == "ИФО" or "template_path" not in data:
                data["template_path"] = str(self.current_template_path)
            self.ui_state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Не удалось сохранить состояние интерфейса")

    def _default_template_path(self) -> Path:
        templates_dir = self.config.base_dir / "app" / "templates"
        if self.mode == "ОФО":
            return templates_dir / "statement_template_ofo.docx"
        if self.config.app.template_path.exists():
            return self.config.app.template_path
        fallback = templates_dir / "statement_template_ifo_diff.docx"
        if fallback.exists():
            return fallback
        fallback = templates_dir / "statement_template_diff.docx"
        return fallback if fallback.exists() else self.config.app.template_path

    def _template_state_key(self) -> str:
        return "template_path_ofo" if self.mode == "ОФО" else "template_path_ifo"

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        value = str(value or "").strip()
        if value:
            combo.setEditText(value)

    def add_current_directory_value(self, directory: str, value: str) -> None:
        labels = {
            "subjects": "предмет",
            "groups": "группа",
            "specialties": "специальность",
            "teachers": "преподаватель",
            "semesters": "семестр",
            "academic_years": "учебный год",
            "control_forms": "форма контроля",
            "department_heads": "зав. отделением",
        }
        if not value:
            self._error("Введите значение перед добавлением в справочник")
            return

        try:
            self.directory_repo.add_value(directory, value)
            self._load_dictionaries()
            self._info(f"В справочник добавлено значение ({labels.get(directory, 'значение')}): {value}")
        except Exception as exc:
            logger.exception("Ошибка добавления значения в справочник")
            self._error(f"Не удалось добавить значение в справочник: {exc}")

    def open_directory_manager(self) -> None:
        dialog = DirectoryManagerDialog(self.directory_repo, self)
        dialog.data_changed.connect(self._load_dictionaries)
        dialog.exec()

    def open_history(self) -> None:
        HistoryDialog(self.history_repo, self.print_service, self).exec()

    def open_grade_rules(self) -> None:
        dialog = GradeRulesDialog(self.grade_rule_repo, self)
        dialog.rules_changed.connect(self._reload_grade_rules_after_edit)
        dialog.exec()

    def _reload_grade_rules_after_edit(self) -> None:
        try:
            self.grade_service.reload_rules()
            self.apply_student_filter()
            self._info("Правила оценивания обновлены")
        except Exception as exc:
            self._error(f"Не удалось обновить правила оценивания: {exc}")

    def choose_template(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите шаблон Word",
            str(self.current_template_path.parent),
            "Word document (*.docx)",
        )
        if not file_path:
            return
        self.current_template_path = Path(file_path)
        self._save_ui_state()
        self._info(f"Выбран шаблон: {self.current_template_path}")

    def choose_excel_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите Excel-файл Moodle",
            str(self.config.base_dir),
            "Excel files (*.xlsx)",
        )
        if not file_path:
            return

        self.current_excel_path = Path(file_path)
        self.current_docx_path = None
        self._set_document_actions_enabled(False)
        self.path_edit.setText(str(self.current_excel_path))
        logger.info("Выбран Excel-файл: %s", self.current_excel_path)
        self._start_excel_loading(self.current_excel_path)

    def _start_excel_loading(self, file_path: Path) -> None:
        if self.excel_load_thread and self.excel_load_thread.isRunning():
            return

        self._set_loading_state(True, "Идет обработка файла")

        self.excel_load_thread = QThread(self)
        self.excel_load_worker = ExcelLoadWorker(file_path, self.config.excel)
        self.excel_load_worker.moveToThread(self.excel_load_thread)

        self.excel_load_thread.started.connect(self.excel_load_worker.run)
        self.excel_load_worker.finished.connect(self._handle_excel_loaded)
        self.excel_load_worker.failed.connect(self._handle_excel_load_failed)
        self.excel_load_worker.finished.connect(self.excel_load_thread.quit)
        self.excel_load_worker.failed.connect(self.excel_load_thread.quit)
        self.excel_load_worker.finished.connect(self.excel_load_worker.deleteLater)
        self.excel_load_worker.failed.connect(self.excel_load_worker.deleteLater)
        self.excel_load_thread.finished.connect(self.excel_load_thread.deleteLater)
        self.excel_load_thread.finished.connect(self._finish_excel_loading)
        self.excel_load_thread.start()

    def _handle_excel_loaded(self, file_path: object, result: object, subject: str) -> None:
        self.current_excel_path = Path(file_path)
        self.parsed_students = result.students
        self.available_individual_numbers = result.individual_numbers or []
        has_empty_individual_numbers = any(not student.individual_number for student in self.parsed_students)
        self.form.set_moodle_filter_values(
            self.available_individual_numbers,
            include_empty=has_empty_individual_numbers,
        )
        self.apply_student_filter()

        if subject:
            self.form.set_subject(subject)

        filters_message = ""
        if self.available_individual_numbers or has_empty_individual_numbers:
            empty_message = " Есть строки без инд. номера." if has_empty_individual_numbers else ""
            filters_message = f" Найдено инд. номеров Moodle: {len(self.available_individual_numbers)}.{empty_message}"
        self._info(
            f"Файл загружен. Строка заголовков: {result.header_row}. "
            f"Строка начала данных: {result.data_start_row}. "
            f"Найдено студентов: {len(self.parsed_students)}.{filters_message}"
        )

    def _handle_excel_load_failed(self, error_type: str, message: str) -> None:
        if error_type == "parse":
            logger.error("Ошибка чтения Excel: %s", message)
            self._error(message)
            return

        logger.error("Ошибка обработки Excel: %s", message)
        self._error(f"Не удалось обработать Excel-файл: {message}")

    def _finish_excel_loading(self) -> None:
        self.excel_load_thread = None
        self.excel_load_worker = None
        self._set_loading_state(False)

    def _set_loading_state(self, loading: bool, message: str = "") -> None:
        self.menuBar().setEnabled(not loading)
        self.choose_button.setEnabled(not loading)
        self.generate_button.setEnabled(not loading)
        self.package_button.setEnabled(not loading and bool(self.current_docx_path))
        self.mode_combo.setEnabled(not loading)
        if loading:
            self.loading_overlay.start(message)
        else:
            self.loading_overlay.stop()
            self._set_document_actions_enabled(bool(self.current_docx_path))

    def generate_statement(self) -> None:
        if not self.current_excel_path:
            self._error("Сначала выберите Excel-файл")
            return
        if not self.statement_students:
            self._error("Нет данных студентов для формирования ведомости. Проверьте выбранный фильтр по инд. номеру Moodle.")
            return

        form_data = self.form.get_data()
        required_fields = {
            "subject": "предмет",
            "group": "группа",
            "specialty": "специальность",
            "teacher": "преподаватель",
        }
        if self.mode == "ОФО":
            required_fields.update(
                {
                    "semester": "семестр",
                    "academic_year": "учебный год",
                    "control_form": "форма контроля",
                    "exam_date": "дата проведения",
                }
            )
        missing = [label for key, label in required_fields.items() if not form_data[key]]
        if missing:
            self._error("Заполните поля: " + ", ".join(missing))
            return

        default_name = self._build_default_output_name(form_data)
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить ведомость",
            str(default_name),
            "Word document (*.docx)",
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".docx"):
            output_path += ".docx"

        try:
            self._save_dictionary_values(form_data)
            data = StatementData(
                subject=form_data["subject"],
                group=form_data["group"],
                specialty=form_data["specialty"],
                teacher=form_data["teacher"],
                students=self.statement_students,
                include_percent=bool(form_data["include_percent"]),
                mode=self.mode,
                semester=str(form_data.get("semester", "")),
                academic_year=str(form_data.get("academic_year", "")),
                control_form=str(form_data.get("control_form", "")),
                exam_date=str(form_data.get("exam_date", "")),
                department_head=str(form_data.get("department_head", "")),
            )
            generator = DocxGenerator(self.current_template_path, self.config.app.keep_empty_rows)
            self.current_docx_path = generator.generate(data, output_path)
            self.history_repo.save(
                subject_name=form_data["subject"],
                group_name=form_data["group"],
                specialty_name=form_data["specialty"],
                teacher_name=form_data["teacher"],
                source_excel_file=str(self.current_excel_path),
                output_docx_file=str(self.current_docx_path),
            )
            self._set_document_actions_enabled(True)
            self._save_ui_state()
            self._info(f"Ведомость сформирована: {self.current_docx_path}")
        except Exception as exc:
            logger.exception("Ошибка формирования ведомости")
            self._error(f"Не удалось сформировать ведомость: {exc}")

    def set_mode(self, mode: str) -> None:
        mode = str(mode or "").strip()
        if mode not in {"ИФО", "ОФО"} or mode == self.mode:
            return

        if self.excel_load_thread and self.excel_load_thread.isRunning():
            self._error("Дождитесь окончания загрузки Excel-файла перед сменой режима")
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText(self.mode)
            self.mode_combo.blockSignals(False)
            return

        self._save_ui_state()
        self.mode = mode
        self.current_template_path = self._default_template_path()
        self._load_ui_state()

        self.setWindowTitle(f"Формирование ведомостей из Moodle — {self.mode}")
        self.form.setTitle(f"Данные ведомости ({self.mode})")
        self.form.set_mode(self.mode)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(self.mode)
        self.mode_combo.blockSignals(False)

        self.current_docx_path = None
        self._set_document_actions_enabled(False)
        self.apply_student_filter()
        self._info(f"Режим изменен: {self.mode}. Шаблон: {self.current_template_path}")

    def apply_student_filter(self) -> None:
        selected_filters = {value.lower() for value in self._selected_individual_numbers()}
        if selected_filters:
            source_students = [
                student
                for student in self.parsed_students
                if student.individual_number.lower() in selected_filters
            ]
        else:
            source_students = self.parsed_students

        selected_date = self.form.get_test_started_date()
        if selected_date:
            source_students = [
                student
                for student in source_students
                if self._normalize_test_started_date(student.test_started) == selected_date
            ]

        self.statement_students, preview_students = self._build_attempt_views(source_students)
        self.preview_table.blockSignals(True)
        try:
            self.preview_table.set_students(preview_students)
        finally:
            self.preview_table.blockSignals(False)
        self.form.set_test_started_options(self._available_test_started_dates())
        self._update_validation(source_students, preview_students)
        self.apply_preview_filter()

    def _handle_preview_header_clicked(self, section: int) -> None:
        if section != 3:
            return
        menu = QMenu(self.preview_table)
        selected_date = self.form.get_test_started_date()
        action_all = menu.addAction("Все даты")
        action_all.setCheckable(True)
        action_all.setChecked(selected_date is None)
        action_all.triggered.connect(lambda: self.form.set_test_started_date(None))
        menu.addSeparator()

        dates = self._available_test_started_dates()
        for date in dates:
            action = menu.addAction(date)
            action.setCheckable(True)
            action.setChecked(date == selected_date)
            action.triggered.connect(lambda checked, date=date: self.form.set_test_started_date(date))

        header = self.preview_table.horizontalHeader()
        header_point = header.mapToGlobal(header.rect().topLeft() + QPoint(header.sectionPosition(section), header.height()))
        menu.exec(header_point)

    def _available_test_started_dates(self) -> list[str]:
        values: list[str] = []
        for row in range(self.preview_table.rowCount()):
            item = self.preview_table.item(row, 3)
            if not item:
                continue
            text = item.text().strip()
            normalized = self._normalize_test_started_date(text)
            if not normalized:
                continue
            if normalized not in values:
                values.append(normalized)
        return sorted(values, key=lambda value: value)

    @staticmethod
    def _normalize_test_started_date(value: str) -> str | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        if "." in text and len(text) == 5:
            parts = text.split(".")
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                day, month = parts
                return f"{day.zfill(2)}.{month.zfill(2)}.{datetime.now().year}"
        try:
            parsed = MainWindow._parse_moodle_datetime(text)
            if parsed == datetime.min:
                return None
            return parsed.strftime("%d.%m.%Y")
        except Exception:
            return None

    def apply_preview_filter(self, *_args) -> None:
        query = self.preview_search_edit.text().strip().casefold()
        grade_filter = self.preview_grade_filter.currentText().strip()
        for row in range(self.preview_table.rowCount()):
            row_text = " ".join(
                self.preview_table.item(row, col).text()
                for col in range(self.preview_table.columnCount())
                if self.preview_table.item(row, col)
            ).casefold()
            grade_text = self.preview_table.item(row, 5).text() if self.preview_table.item(row, 5) else ""
            matches_query = not query or query in row_text
            matches_grade = grade_filter == "Все оценки" or grade_text.startswith(grade_filter)
            self.preview_table.setRowHidden(row, not (matches_query and matches_grade))

    def _handle_preview_item_changed(self, item) -> None:
        if item.column() != 3:
            return

        student = item.data(Qt.UserRole)
        if not hasattr(student, "test_started"):
            return

        new_value = item.text().strip()
        student.test_started = new_value

        if getattr(student, "source_row", None) is not None:
            for parsed_student in self.parsed_students:
                if parsed_student.source_row == student.source_row:
                    parsed_student.test_started = new_value
                    break

        self.preview_table.blockSignals(True)
        try:
            self.preview_table.set_students(self._build_attempt_views(self.parsed_students)[1])
        finally:
            self.preview_table.blockSignals(False)

    def _update_validation(
        self,
        source_students: list[StudentResult],
        preview_students: list[StatementStudent],
    ) -> None:
        warnings: list[str] = []
        if not source_students:
            warnings.append("Нет студентов для выбранного фильтра.")

        empty_names = sum(1 for student in source_students if not student.full_name.strip())
        empty_numbers = sum(1 for student in source_students if not student.individual_number.strip())
        low_scores = sum(1 for student in source_students if student.percent < 50)

        identities: dict[str, int] = {}
        for student in source_students:
            identities[self._student_identity_key(student)] = identities.get(self._student_identity_key(student), 0) + 1
        repeated_attempts = sum(1 for count in identities.values() if count > 1)

        if empty_names:
            warnings.append(f"Пустые ФИО: {empty_names}.")
        if empty_numbers:
            warnings.append(f"Без инд. номера Moodle: {empty_numbers}.")
        if repeated_attempts:
            warnings.append(f"Студенты с несколькими попытками: {repeated_attempts}. В ведомость берется лучшая попытка.")
        if low_scores:
            warnings.append(f"Результаты ниже 50%: {low_scores}.")

        if warnings:
            self.validation_box.setPlainText("\n".join(warnings))
        else:
            self.validation_box.setPlainText(f"Ошибок не найдено. В предпросмотре строк: {len(preview_students)}.")

    def _selected_individual_numbers(self) -> list[str]:
        selected = self.form.get_moodle_filters()
        if selected:
            return [
                "" if value == self.form.EMPTY_MOODLE_FILTER_LABEL else value
                for value in selected
            ]

        group_value = str(self.form.get_data().get("group", "")).strip()
        if not group_value:
            return []

        normalized_group = group_value.lower()
        for value in self.available_individual_numbers:
            if value.lower() == normalized_group:
                return [value]
        return []

    def _build_attempt_views(
        self,
        students: list[StudentResult],
    ) -> tuple[list[StatementStudent], list[StatementStudent]]:
        attempts_by_student: dict[str, list[StudentResult]] = {}
        for student in students:
            attempts_by_student.setdefault(self._student_identity_key(student), []).append(student)

        best_by_student: dict[str, StudentResult] = {}
        for key, attempts in attempts_by_student.items():
            best_by_student[key] = max(attempts, key=self._best_attempt_key)

        final_sources = sorted(best_by_student.items(), key=lambda item: self._student_sort_key(item[1]))
        final_numbers = {key: index for index, (key, _student) in enumerate(final_sources, start=1)}
        statement_students = [
            self._make_statement_student(student, final_numbers[key], "")
            for key, student in final_sources
        ]

        preview_students: list[StatementStudent] = []
        for key, best_student in final_sources:
            attempts = sorted(attempts_by_student[key], key=self._attempt_sort_key)
            for attempt_index, student in enumerate(attempts, start=1):
                is_best = student.source_row == best_student.source_row
                note = self._attempt_note(len(attempts), attempt_index, is_best)
                preview_students.append(
                    self._make_statement_student(
                        student,
                        final_numbers[key] if is_best else 0,
                        note,
                    )
                )

        return statement_students, preview_students

    def _make_statement_student(self, student: StudentResult, number: int, note: str) -> StatementStudent:
        grade = self.grade_service.calculate(student.percent)
        return StatementStudent(
            number=number,
            full_name=student.full_name,
            percent=student.percent,
            grade=grade,
            individual_number=student.individual_number,
            test_started=student.test_started,
            note=note,
            source_row=student.source_row,
        )

    @staticmethod
    def _attempt_note(attempt_count: int, attempt_index: int, is_best: bool) -> str:
        if attempt_count <= 1:
            return ""
        if is_best:
            return f"В ведомость: максимум из {attempt_count} попыток"
        if attempt_index > 1:
            return "Пересдача, не входит в ведомость"
        return "Попытка 1, не входит в ведомость"

    @staticmethod
    def _student_identity_key(student: StudentResult) -> str:
        if student.login:
            return f"login:{student.login.strip().casefold()}"
        return f"name:{student.full_name.strip().casefold()}|group:{student.individual_number.strip().casefold()}"

    def _best_attempt_key(self, student: StudentResult) -> tuple:
        return student.percent, self._attempt_sort_key(student), student.source_row

    @staticmethod
    def _attempt_sort_key(student: StudentResult) -> tuple:
        return MainWindow._parse_moodle_datetime(student.test_started), student.source_row

    @staticmethod
    def _parse_moodle_datetime(value: str) -> datetime:
        if value is None:
            return datetime.min

        text = str(value).strip()
        if not text:
            return datetime.min

        normalized = text.replace("\u00a0", " ").strip()
        month_map = {
            "января": 1,
            "февраля": 2,
            "марта": 3,
            "апреля": 4,
            "мая": 5,
            "июня": 6,
            "июля": 7,
            "августа": 8,
            "сентября": 9,
            "октября": 10,
            "ноября": 11,
            "декабря": 12,
        }

        for pattern in (
            r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?",
            r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?",
            r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s*(\d{1,2}):(\d{2})(?::(\d{2}))?",
        ):
            match = re.fullmatch(pattern, normalized.casefold())
            if not match:
                continue
            if pattern.startswith(r"(\d{1,2})\s"):
                day, month_name, year, hour, minute, second = match.groups()
                month = month_map.get(month_name)
                if not month:
                    continue
                second_value = int(second or 0)
                return datetime(int(year), month, int(day), int(hour), int(minute), second_value)
            if pattern.startswith(r"(\d{4})"):
                year, month, day, hour, minute, second = match.groups()
                return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second or 0))
            day, month, year, hour, minute, second = match.groups()
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second or 0))

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.min


    def _build_statement_students(self, students: list[StudentResult]) -> list[StatementStudent]:
        statement_students: list[StatementStudent] = []
        for index, student in enumerate(sorted(students, key=self._student_sort_key), start=1):
            grade = self.grade_service.calculate(student.percent)
            statement_students.append(
                StatementStudent(
                    number=index,
                    full_name=student.full_name,
                    percent=student.percent,
                    grade=grade,
                    individual_number=student.individual_number,
                    test_started=student.test_started,
                )
            )
        return statement_students

    @staticmethod
    def _student_sort_key(student: StudentResult) -> tuple[str, str]:
        normalized_name = student.full_name.replace("Ё", "Е").replace("ё", "е").casefold()
        parts = normalized_name.split()
        surname = parts[0] if parts else ""
        return surname, normalized_name

    def _save_dictionary_values(self, form_data: dict[str, str]) -> None:
        self.directory_repo.add_value("subjects", form_data["subject"])
        self.directory_repo.add_value("groups", form_data["group"])
        self.directory_repo.add_value("specialties", form_data["specialty"])
        self.directory_repo.add_value("teachers", form_data["teacher"])
        if self.mode == "ОФО":
            self.directory_repo.add_value("semesters", str(form_data.get("semester", "")))
            self.directory_repo.add_value("academic_years", str(form_data.get("academic_year", "")))
            self.directory_repo.add_value("control_forms", str(form_data.get("control_form", "")))
            self.directory_repo.add_value("department_heads", str(form_data.get("department_head", "")))

    def _build_default_output_name(self, form_data: dict[str, str]) -> Path:
        safe_subject = self._safe_filename(form_data.get("subject") or "предмет")
        safe_group = self._safe_filename(form_data.get("group") or "группа")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.config.app.output_dir.mkdir(parents=True, exist_ok=True)
        return self.config.app.output_dir / f"Ведомость_{safe_subject}_{safe_group}_{timestamp}.docx"

    @staticmethod
    def _safe_filename(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in (" ", "_", "-") else "_" for ch in value).strip()

    def open_document(self) -> None:
        if not self.current_docx_path:
            self._error("Сначала сформируйте ведомость")
            return
        try:
            self.print_service.open_file(self.current_docx_path)
        except Exception as exc:
            self._error(str(exc))

    def export_pdf(self) -> None:
        if not self.current_docx_path:
            self._error("Сначала сформируйте ведомость")
            return
        pdf_path = self.current_docx_path.with_suffix(".pdf")
        try:
            result = self.pdf_exporter.export(self.current_docx_path, pdf_path)
            self._info(f"PDF создан: {result}")
        except Exception as exc:
            logger.exception("Ошибка экспорта PDF")
            self._error(str(exc))

    def generate_statement_package(self) -> None:
        previous_docx_path = self.current_docx_path
        self.generate_statement()
        if not self.current_docx_path or self.current_docx_path == previous_docx_path:
            return
        self.export_pdf()

    def open_output_folder(self) -> None:
        if not self.current_docx_path:
            self._error("Сначала сформируйте ведомость")
            return
        try:
            self.print_service.open_folder(self.current_docx_path.parent)
        except Exception as exc:
            self._error(str(exc))

    def print_document(self) -> None:
        if not self.current_docx_path:
            self._error("Сначала сформируйте ведомость")
            return
        try:
            self.print_service.print_file(self.current_docx_path)
            self._info("Документ отправлен на печать")
        except Exception as exc:
            logger.exception("Ошибка печати")
            self._error(str(exc))

    def _info(self, message: str) -> None:
        self.log_box.appendPlainText("[OK] " + message)
        logger.info(message)

    def _error(self, message: str) -> None:
        self.log_box.appendPlainText("[ОШИБКА] " + message)
        QMessageBox.warning(self, "Ошибка", message)
        logger.error(message)
