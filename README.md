# Deanery Statement App

Настольное Windows-приложение для сотрудников деканата. Формирует ведомости по Excel-выгрузке из Moodle: находит студентов, считает оценки по процентам, учитывает пересдачи и собирает Word-документ по шаблону.

## Возможности

- режимы ведомостей `ИФО` и `ОФО` с переключением без выхода из приложения;
- отдельные шаблоны Word для ИФО и ОФО;
- загрузка `.xlsx`-файлов с оценками из Moodle;
- автоматическое определение дисциплины из имени файла Moodle;
- справочники предметов, групп, специальностей, преподавателей, семестров, учебных годов, форм контроля и заведующих отделением;
- ручная дата проведения для ОФО с выбором через календарь;
- фильтрация студентов по одному или нескольким индивидуальным номерам Moodle;
- поддержка пустого индивидуального номера;
- учет нескольких попыток: в ведомость попадает лучший результат, остальные попытки видны в предпросмотре;
- расчет оценок по правилам из PostgreSQL;
- формирование `.docx`, экспорт в PDF и печать при наличии Microsoft Word или LibreOffice.

## Быстрый старт

Создайте виртуальное окружение и установите зависимости:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Создайте базу данных и начальные справочники:

```bat
psql -U postgres -f sql\init_db.sql
psql -U postgres -d deanery_statement_app -f sql\seed_data.sql
```

Создайте рабочий конфиг:

```bat
copy config.example.ini config.ini
```

Отредактируйте `config.ini`: укажите хост, пользователя и пароль PostgreSQL.

Запустите приложение:

```bat
python -m app.main
```

Или используйте:

```bat
run.bat
```

## Конфигурация

Пример безопасного конфига хранится в `config.example.ini`.

```ini
[database]
host=localhost
port=5432
user=deanery_app
password=change_me
database=deanery_statement_app

[app]
template_path=app/templates/statement_template_ifo_diff.docx
output_dir=output
keep_empty_rows=true

[excel]
header_search_rows=15
data_start_row=2
swap_first_last_names=true
```

`config.ini` не публикуется, потому что может содержать реальные пароли и локальные настройки.

## Шаблоны

Встроенные шаблоны находятся в `app/templates/`:

- `statement_template_ifo_diff.docx` - ИФО, дифференцированный зачет;
- `statement_template_ifo_exam.docx` - ИФО, экзамен;
- `statement_template_ofo.docx` - ОФО.

Пользователь может выбрать другой `.docx`-шаблон через кнопку `Шаблон`; выбранные пути сохраняются локально в `app_state.json`.

## Справочники БД

`sql/init_db.sql` создает основные таблицы и первично заполняет стабильные справочники:

- семестры `1`-`8`;
- учебные годы `2025/2026`, `2026/2027`;
- формы контроля `диф.зачет`, `экзамен`, `зачет`.

`sql/seed_data.sql` добавляет начальные правила оценивания и примеры значений для предметов, групп, специальностей и преподавателей. Повторный запуск SQL-скриптов безопасен: используется `ON CONFLICT DO NOTHING`.

## Формат Moodle Excel

Приложение ищет строку заголовков в первых строках файла и определяет нужные колонки по названиям. Поддерживаются поля:

- имя, фамилия и отчество студента;
- процент выполнения;
- индивидуальный номер Moodle;
- логин студента;
- дата и время начала теста.

Если у студента несколько попыток, итоговая ведомость получает лучшую попытку по проценту.

## Правила оценивания

Правила берутся из таблицы `grade_rules`.

Начальная шкала:

| Процент | Оценка |
|---:|---|
| 91-100 | 5 |
| 81-90 | 4 |
| 71-80 | 3 |
| 0-70 | 2 |

Границы диапазонов включительные.

## Сборка exe

```bat
build_exe.bat
```

После сборки исполняемый файл появится в:

```text
dist\DeaneryStatementApp\DeaneryStatementApp.exe
```

## Создание установщика

1. Установите Inno Setup.
2. Соберите `.exe` через `build_exe.bat`.
3. Откройте `installer\setup.iss` в Inno Setup Compiler.
4. Нажмите `Compile`.

Готовый установщик будет создан в `installer\Output`.

## Тесты

```bat
pytest
```

## Структура проекта

```text
deanery_statement_app/
  app/
    db/                 # PostgreSQL и репозитории
    resources/          # стили и иконки
    services/           # Excel, DOCX/PDF, печать, оценки
    templates/          # Word-шаблоны ведомостей
    ui/                 # окна и элементы интерфейса
    config.py
    main.py
  installer/            # Inno Setup
  sql/                  # создание БД и начальные данные
  tests/                # тесты
  build_exe.bat
  config.example.ini
  requirements.txt
  run.bat
```

## Не публикуется в GitHub

- `.venv/`, `venv/`, `env/`;
- `config.ini`;
- `app_state.json`;
- `logs/`, `output/`;
- `build/`, `dist/`;
- `installer/Output/`;
- `__pycache__/`, `.pytest_cache/`;
- локальные файлы IDE.

## Контакты

Разработчик: [UnicornisIT](https://github.com/UnicornisIT)

Идеи и предложения: [earov18@outlook.com](mailto:earov18@outlook.com)

Telegram: [t.me/unicornis_pulse](https://t.me/unicornis_pulse)
