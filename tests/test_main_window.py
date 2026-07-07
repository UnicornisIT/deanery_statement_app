from datetime import datetime

from app.ui.main_window import MainWindow


def test_parse_moodle_datetime_supports_iso_format():
    assert MainWindow._parse_moodle_datetime("2026-06-24 12:21:00") == datetime(2026, 6, 24, 12, 21)
