from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


class PdfExportError(Exception):
    pass


class PdfExporter:
    def export(self, docx_path: str | Path, pdf_path: str | Path | None = None) -> Path:
        docx = Path(docx_path).resolve()
        if not docx.exists():
            raise PdfExportError(f"Файл Word не найден: {docx}")

        pdf = Path(pdf_path).resolve() if pdf_path else docx.with_suffix(".pdf")
        pdf.parent.mkdir(parents=True, exist_ok=True)

        if platform.system() == "Windows":
            try:
                return self._export_with_word(docx, pdf)
            except Exception as word_exc:
                try:
                    return self._export_with_libreoffice(docx, pdf)
                except Exception as libre_exc:
                    raise PdfExportError(
                        "Не удалось экспортировать PDF через Microsoft Word или LibreOffice. "
                        f"Word: {word_exc}; LibreOffice: {libre_exc}"
                    ) from libre_exc

        return self._export_with_libreoffice(docx, pdf)

    @staticmethod
    def _export_with_word(docx: Path, pdf: Path) -> Path:
        import win32com.client  # type: ignore

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            document = word.Documents.Open(str(docx))
            document.SaveAs(str(pdf), FileFormat=17)
            document.Close(False)
            return pdf
        finally:
            word.Quit()

    @staticmethod
    def _export_with_libreoffice(docx: Path, pdf: Path) -> Path:
        candidates = ["soffice", "libreoffice"]
        executable = next((cmd for cmd in candidates if shutil.which(cmd)), None)
        if not executable:
            raise PdfExportError("LibreOffice не найден")

        result = subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf.parent),
                str(docx),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PdfExportError(result.stderr or result.stdout or "Ошибка LibreOffice")

        generated = pdf.parent / f"{docx.stem}.pdf"
        if generated != pdf and generated.exists():
            if pdf.exists():
                pdf.unlink()
            generated.rename(pdf)
        if not pdf.exists():
            raise PdfExportError("PDF-файл не был создан")
        return pdf
