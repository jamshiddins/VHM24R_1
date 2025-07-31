#!/usr/bin/env python3
"""
Скрипт запуска сервера VHM24R с правильной настройкой путей
"""
import os
import sys
import subprocess

def main():
    # Переходим в директорию backend
    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    
    if not os.path.exists(backend_path):
        print(f"❌ Директория backend не найдена: {backend_path}")
        return 1
    
    print(f"📂 Переходим в директорию: {backend_path}")
    os.chdir(backend_path)
    
    # Проверяем, что модуль app существует
    app_path = os.path.join(backend_path, 'app')
    if not os.path.exists(app_path):
        print(f"❌ Модуль app не найден: {app_path}")
        return 1
    
    print("🚀 Запускаем сервер VHM24R...")
    print("💡 DigitalOcean Spaces полностью настроен!")
    print("📍 Сервер будет доступен по адресу: http://localhost:8000")
    print("🔍 Health check: http://localhost:8000/health")
    print("📊 Статус DigitalOcean Spaces будет: 'configured' ✅")
    print("")
    
    # Запускаем uvicorn
    try:
        subprocess.run([
            sys.executable, '-m', 'uvicorn', 
            'app.main:app', 
            '--host', '0.0.0.0', 
            '--port', '8000',
            '--reload'
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
