-- Добавление недостающих колонок в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deactivated BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_by INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP;

-- Проверяем структуру таблицы
\d users;
