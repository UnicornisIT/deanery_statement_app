from __future__ import annotations

import configparser
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class AppSettings:
    template_path: Path
    output_dir: Path
    keep_empty_rows: bool


@dataclass(frozen=True)
class ExcelSettings:
    header_search_rows: int
    data_start_row: int
    swap_first_last_names: bool


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    database: DatabaseConfig
    app: AppSettings
    excel: ExcelSettings


def get_base_dir() -> Path:
    """Возвращает корень приложения с учетом запуска из PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _read_bool(parser: configparser.ConfigParser, section: str, option: str, default: bool) -> bool:
    if parser.has_option(section, option):
        return parser.getboolean(section, option)
    return default


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_config(config_path: Path | None = None) -> AppConfig:
    base_dir = get_base_dir()
    config_file = config_path or base_dir / "config.ini"

    parser = configparser.ConfigParser()
    read_files = parser.read(config_file, encoding="utf-8")
    if not read_files:
        raise FileNotFoundError(f"Не найден файл настроек: {config_file}")

    db = DatabaseConfig(
        host=parser.get("database", "host", fallback="localhost"),
        port=parser.getint("database", "port", fallback=5432),
        user=parser.get("database", "user", fallback="postgres"),
        password=parser.get("database", "password", fallback=""),
        database=parser.get("database", "database", fallback="deanery_statement_app"),
    )

    template_path = _resolve_path(base_dir, parser.get("app", "template_path", fallback="app/templates/statement_template.docx"))
    output_dir = _resolve_path(base_dir, parser.get("app", "output_dir", fallback="output"))

    app = AppSettings(
        template_path=template_path,
        output_dir=output_dir,
        keep_empty_rows=_read_bool(parser, "app", "keep_empty_rows", True),
    )

    excel = ExcelSettings(
        header_search_rows=parser.getint("excel", "header_search_rows", fallback=15),
        data_start_row=parser.getint("excel", "data_start_row", fallback=10),
        swap_first_last_names=_read_bool(parser, "excel", "swap_first_last_names", True),
    )

    return AppConfig(base_dir=base_dir, database=db, app=app, excel=excel)
