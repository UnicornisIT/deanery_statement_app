from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config import ExcelSettings
from app.services.excel_parser import ExcelParseError, ExcelParser
from app.services.subject_detector import SubjectDetector


class ExcelLoadWorker(QObject):
    finished = Signal(object, object, str)
    failed = Signal(str, str)

    def __init__(self, file_path: str | Path, settings: ExcelSettings):
        super().__init__()
        self.file_path = Path(file_path)
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            result = ExcelParser(self.settings).parse(self.file_path)
            subject = SubjectDetector.detect(self.file_path)
            self.finished.emit(self.file_path, result, subject)
        except ExcelParseError as exc:
            self.failed.emit("parse", str(exc))
        except Exception as exc:
            self.failed.emit("unexpected", str(exc))
