#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных в Railway
"""
import os
import sys
sys.path.append('backend')

from backend.app.database import init_db, engine
from backend.app import models

def main():
    print("🔄 Инициализация базы данных...")
    
    # Получаем DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    print(f"📊 DATABASE_URL: {database_url}")
    
    try:
        # Создаем все таблицы
        models.Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы успешно!")
        
        # Проверяем подключение
        from backend.app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            # Простой запрос для проверки подключения
            result = db.execute(text("SELECT 1"))
            print("✅ Подключение к базе данных работает!")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при инициализации базы данных: {e}")
        sys.exit(1)
    
    print("🎉 Инициализация завершена успешно!")

if __name__ == "__main__":
    main()
