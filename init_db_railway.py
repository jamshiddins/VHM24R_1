#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных на Railway
"""
import os
import sys
sys.path.append('backend')

from backend.app.database import engine, init_db
from backend.app.models import Base

def main():
    print("🚀 Инициализация базы данных на Railway...")
    
    try:
        # Создаем все таблицы
        print("📊 Создание таблиц...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ База данных успешно инициализирована!")
        print("📋 Созданы все необходимые таблицы")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
