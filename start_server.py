#!/usr/bin/env python3
"""
Скрипт для запуска FastAPI сервера VHM24R
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Переходим в папку backend
    backend_dir = Path(__file__).parent / "backend"
    
    if not backend_dir.exists():
        print("❌ Папка backend не найдена!")
        return
    
    # Меняем рабочую директорию
    os.chdir(backend_dir)
    print(f"📁 Рабочая директория: {os.getcwd()}")
    
    # Добавляем текущую директорию в PYTHONPATH
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    # Проверяем наличие .env файла
    env_file = backend_dir / ".env"
    if not env_file.exists():
        print("❌ Файл .env не найден!")
        return
    
    print("✅ Файл .env найден")
    
    # Проверяем импорт приложения
    try:
        from app.main import app
        print("✅ FastAPI приложение импортируется успешно")
    except Exception as e:
        print(f"❌ Ошибка импорта приложения: {e}")
        print(f"Python path: {sys.path}")
        return
    
    # Запускаем сервер
    print("🚀 Запускаем сервер...")
    try:
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен")
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")

if __name__ == "__main__":
    main()
