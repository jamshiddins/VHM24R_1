#!/usr/bin/env python3
"""
Скрипт для исправления базы данных - добавление недостающих колонок
"""
import os
import sys
sys.path.append('backend')

def main():
    print("🔧 Исправление базы данных...")
    
    try:
        from backend.app.database import engine
        from sqlalchemy import text
        
        # SQL команды для добавления недостающих колонок
        sql_commands = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_deactivated BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deactivated_by INTEGER;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMP;"
        ]
        
        with engine.connect() as conn:
            for sql in sql_commands:
                print(f"📝 Выполняем: {sql}")
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    print("✅ Успешно")
                except Exception as e:
                    print(f"⚠️ Предупреждение: {e}")
        
        print("✅ База данных исправлена!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
