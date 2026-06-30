-- Initial data for PostgreSQL.
-- Run after init_db.sql, for example:
-- psql -U postgres -d deanery_statement_app -f sql/seed_data.sql

INSERT INTO grade_rules
(min_percent, max_percent, grade_number, grade_short, grade_full)
VALUES
(91, 100, 5, 'отл', 'отлично'),
(81, 90, 4, 'хор', 'хорошо'),
(71, 80, 3, 'удовл', 'удовлетворительно'),
(0, 70, 2, 'неуд', 'неудовлетворительно')
ON CONFLICT (min_percent, max_percent) DO UPDATE SET
    grade_number = EXCLUDED.grade_number,
    grade_short = EXCLUDED.grade_short,
    grade_full = EXCLUDED.grade_full;

INSERT INTO subjects (name) VALUES
('Химия'),
('Биология'),
('Анатомия'),
('Фармакология')
ON CONFLICT (name) DO NOTHING;

INSERT INTO student_groups (name) VALUES
('ОФО-л26'),
('СД-101'),
('ЛД-101')
ON CONFLICT (name) DO NOTHING;

INSERT INTO specialties (name) VALUES
('Сестринское дело'),
('Лечебное дело'),
('Фармация')
ON CONFLICT (name) DO NOTHING;

INSERT INTO teachers (full_name) VALUES
('Иванова Мария Петровна'),
('Петров Сергей Иванович')
ON CONFLICT (full_name) DO NOTHING;
