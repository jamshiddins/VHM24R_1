#!/usr/bin/env python3
"""
Скрипт для запуска VHM24R приложения
"""

import os
import sys
import asyncio
import uvicorn
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем текущую директорию в Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Основная функция запуска приложения"""
    
    # Получаем настройки из переменных окружения
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    reload = os.getenv("RELOAD", "True").lower() == "true"
    workers = int(os.getenv("WORKERS", 1))
    
    print(f"🚀 Запуск VHM24R сервера...")
    print(f"📍 Адрес: http://{host}:{port}")
    print(f"🔧 Режим отладки: {debug}")
    print(f"🔄 Автоперезагрузка: {reload}")
    print(f"👥 Количество воркеров: {workers}")
    
    # Настройки для uvicorn
    config = {
        "app": "app.main:app",
        "host": host,
        "port": port,
        "reload": reload and debug,
        "debug": debug,
        "access_log": True,
        "use_colors": True,
    }
    
    # В продакшене используем несколько воркеров
    if not debug and workers > 1:
        config["workers"] = workers
    
    # Запускаем сервер
    try:
        uvicorn.run(**config)
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
