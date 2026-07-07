from app.services.subject_detector import SubjectDetector


def test_detect_subject_from_moodle_filename():
    assert SubjectDetector.detect("хм_БД_ОФО_л26-Тестирование. Химия лето 2026-оценки.xlsx") == "Химия"


def test_detect_subject_keeps_full_name_before_grades_suffix():
    assert (
        SubjectDetector.detect(
            "ОБЗР_ДЗ_ОФО_з26-Тестирование. Основы безопасности и защиты Родины-оценки.xlsx"
        )
        == "Основы безопасности и защиты Родины"
    )


def test_detect_subject_keeps_full_name_before_season_year_suffix():
    assert (
        SubjectDetector.detect(
            "АиФЧ_ОП_ЛД2_ОФО_л26-Тестирование. Анатомия и физиология человека Основы патологии лето 2026-оценки.xlsx"
        )
        == "Анатомия и физиология человека Основы патологии"
    )
