from __future__ import annotations

import re
from pathlib import Path


class SubjectDetector:
    STOP_WORDS = {
        "оценки",
        "оценка",
        "тестирование",
        "тест",
        "лето",
        "зима",
        "весна",
        "осень",
        "офо",
        "зфо",
        "очно",
        "заочно",
        "экзамен",
        "зачет",
        "дифференцированный",
        "ведомость",
        "итог",
        "итоговая",
        "moodle",
    }

    @classmethod
    def detect(cls, file_path: str | Path) -> str:
        stem = Path(file_path).stem
        text = stem.replace("_", " ")
        text = re.sub(r"\s+", " ", text).strip()

        match = re.search(r"тестирование\s*\.\s*(.+)$", text, flags=re.IGNORECASE)
        if match:
            candidate = cls._clean_candidate(match.group(1))
            if candidate:
                return candidate

        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text).strip()

        # Самый частый формат: "... Тестирование. Химия лето 2026-оценки.xlsx".
        dot_parts = [part.strip() for part in re.split(r"[.;]", text) if part.strip()]
        if len(dot_parts) >= 2:
            candidate = cls._clean_candidate(dot_parts[-1])
            if candidate:
                return candidate

        candidate = cls._clean_candidate(text)
        return candidate

    @classmethod
    def _clean_candidate(cls, value: str) -> str:
        value = re.sub(r"\s*[-–—]\s*оценк[аи].*$", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+(лето|зима|весна|осень)\s+\d{4}\s*$", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"\b\d{4}\b", " ", value)
        value = re.sub(r"\b[а-яa-z]{1,3}\d{1,3}\b", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"[^A-Za-zА-Яа-яЁё\s]", " ", value)
        tokens = []
        for token in re.split(r"\s+", value):
            cleaned = token.strip(" .,_-—–").lower().replace("ё", "е")
            if not cleaned or cleaned in cls.STOP_WORDS:
                continue
            # Отбрасываем служебные короткие коды, но оставляем реальные короткие слова.
            if len(cleaned) <= 2 and cleaned.isascii():
                continue
            tokens.append(token.strip())

        if not tokens:
            return ""

        result = " ".join(tokens)
        result = re.sub(r"\s+", " ", result).strip()
        return result[:1].upper() + result[1:]
