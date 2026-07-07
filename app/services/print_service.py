from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


class PrintError(Exception):
    pass


class PrintService:
    def open_file(self, file_path: str | Path) -> None:
        path = Path(file_path).resolve()
        if not path.exists():
            raise PrintError(f"Файл не найден: {path}")

        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def open_folder(self, folder_path: str | Path) -> None:
        path = Path(folder_path).resolve()
        if not path.exists():
            raise PrintError(f"Папка не найдена: {path}")

        system = platform.system()
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def print_file(self, file_path: str | Path) -> None:
        path = Path(file_path).resolve()
        if not path.exists():
            raise PrintError(f"Файл не найден: {path}")

        if platform.system() == "Windows":
            try:
                os.startfile(str(path), "print")  # type: ignore[attr-defined]
                return
            except Exception as exc:
                raise PrintError(f"Не удалось отправить файл на печать: {exc}") from exc

        raise PrintError("Автоматическая печать реализована только для Windows")
