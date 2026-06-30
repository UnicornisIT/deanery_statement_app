from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.db.connection import DatabaseConnection
from app.db.repositories import DirectoryRepository, GeneratedStatementRepository, GradeRuleRepository
from app.services.docx_generator import DocxGenerator, StatementData, StatementStudent
from app.services.excel_parser import ExcelParseError, ExcelParser, StudentResult
from app.services.grade_service import GradeService
from app.services.pdf_exporter import PdfExporter
from app.services.print_service import PrintService
from app.services.subject_detector import SubjectDetector
from app.ui.directory_dialog import DirectoryManagerDialog
from app.ui.preview_table import PreviewTable
from app.ui.statement_form import StatementForm

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.setWindowTitle("Формирование ведомостей из Moodle")
        self.resize(1100, 720)

        self.db = DatabaseConnection(config.database)
        self.directory_repo = DirectoryRepository(self.db)
        self.grade_service = GradeService(GradeRuleRepository(self.db))
        self.history_repo = GeneratedStatementRepository(self.db)
        self.excel_parser = ExcelParser(config.excel)
        self.pdf_exporter = PdfExporter()
        self.print_service = PrintService()

        self.current_excel_path: Path | None = None
        self.current_docx_path: Path | None = None
        self.parsed_students: list[StudentResult] = []
        self.statement_students: list[StatementStudent] = []
        self.available_individual_numbers: list[str] = []

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.choose_button = QPushButton("Выбрать Excel-файл")
        self.generate_button = QPushButton("Сформировать ведомость")
        self.open_button = QPushButton("Открыть документ")
        self.export_pdf_button = QPushButton("Экспорт в PDF")
        self.print_button = QPushButton("Печать")
        self.reload_dict_button = QPushButton("Справочники")

        self.form = StatementForm()
        self.preview_table = PreviewTable()
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
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

        self._build_layout()
        self._connect_signals()
        self._set_document_actions_enabled(False)
        self._load_dictionaries()

    def _build_layout(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(self.choose_button)
        file_row.addWidget(QLabel("Файл:"))
        file_row.addWidget(self.path_edit, stretch=1)
        root.addLayout(file_row)

        root.addWidget(self.form)
        root.addWidget(QLabel("Предварительный просмотр:"))
        root.addWidget(self.preview_table, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.export_pdf_button)
        actions.addWidget(self.print_button)
        actions.addStretch(1)
        actions.addWidget(self.reload_dict_button)
        root.addLayout(actions)

        root.addWidget(QLabel("Сообщения:"))
        root.addWidget(self.log_box)
        root.addWidget(self.footer_label)

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.choose_button.clicked.connect(self.choose_excel_file)
        self.generate_button.clicked.connect(self.generate_statement)
        self.open_button.clicked.connect(self.open_document)
        self.export_pdf_button.clicked.connect(self.export_pdf)
        self.print_button.clicked.connect(self.print_document)
        self.reload_dict_button.clicked.connect(self.open_directory_manager)
        self.form.add_value_requested.connect(self.add_current_directory_value)
        self.form.moodle_filter_changed.connect(self.apply_student_filter)

    def _set_document_actions_enabled(self, enabled: bool) -> None:
        self.open_button.setEnabled(enabled)
        self.export_pdf_button.setEnabled(enabled)
        self.print_button.setEnabled(enabled)

    def _load_dictionaries(self) -> None:
        try:
            self.form.set_values(
                subjects=self.directory_repo.list_values("subjects"),
                groups=self.directory_repo.list_values("groups"),
                specialties=self.directory_repo.list_values("specialties"),
                teachers=self.directory_repo.list_values("teachers"),
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

    def add_current_directory_value(self, directory: str, value: str) -> None:
        labels = {
            "subjects": "предмет",
            "groups": "группа",
            "specialties": "специальность",
            "teachers": "преподаватель",
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
        self.path_edit.setText(str(self.current_excel_path))
        logger.info("Выбран Excel-файл: %s", self.current_excel_path)

        try:
            result = self.excel_parser.parse(self.current_excel_path)
            self.parsed_students = result.students
            self.available_individual_numbers = result.individual_numbers or []
            has_empty_individual_numbers = any(not student.individual_number for student in self.parsed_students)
            self.form.set_moodle_filter_values(
                self.available_individual_numbers,
                include_empty=has_empty_individual_numbers,
            )
            self.apply_student_filter()

            subject = SubjectDetector.detect(self.current_excel_path)
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
        except ExcelParseError as exc:
            logger.exception("Ошибка чтения Excel")
            self._error(str(exc))
        except Exception as exc:
            logger.exception("Ошибка обработки Excel")
            self._error(f"Не удалось обработать Excel-файл: {exc}")

    def generate_statement(self) -> None:
        if not self.current_excel_path:
            self._error("Сначала выберите Excel-файл")
            return
        if not self.statement_students:
            self._error("Нет данных студентов для формирования ведомости. Проверьте выбранный фильтр по инд. номеру Moodle.")
            return

        form_data = self.form.get_data()
        missing = [label for key, label in {
            "subject": "предмет",
            "group": "группа",
            "specialty": "специальность",
            "teacher": "преподаватель",
        }.items() if not form_data[key]]
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
            )
            generator = DocxGenerator(self.config.app.template_path, self.config.app.keep_empty_rows)
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
            self._info(f"Ведомость сформирована: {self.current_docx_path}")
        except Exception as exc:
            logger.exception("Ошибка формирования ведомости")
            self._error(f"Не удалось сформировать ведомость: {exc}")

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

        self.statement_students, preview_students = self._build_attempt_views(source_students)
        self.preview_table.set_students(preview_students)

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
        months = {
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
        match = re.search(
            r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+(\d{1,2}):(\d{2})",
            value.strip().casefold(),
        )
        if not match:
            return datetime.min

        day, month_name, year, hour, minute = match.groups()
        month = months.get(month_name)
        if not month:
            return datetime.min

        return datetime(int(year), month, int(day), int(hour), int(minute))

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
