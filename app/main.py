from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import load_config
from app.logging_config import setup_logging
from app.ui.main_window import MainWindow, ModeSelectionDialog


def main() -> int:
    try:
        config = load_config()
        setup_logging(config.base_dir)
        logging.info("Запуск приложения")
    except Exception as exc:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Ошибка запуска", str(exc))
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Deanery Statement App")

    try:
        qss_path = config.base_dir / "app" / "resources" / "styles" / "app.qss"
        if qss_path.exists():
            app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Не удалось загрузить стили")

    mode_dialog = ModeSelectionDialog()
    if not mode_dialog.exec():
        return 0

    window = MainWindow(config, mode=mode_dialog.selected_mode or "ИФО")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
