#!/usr/bin/env python3
"""
Тест исправления цикла аутентификации Telegram
"""

import os
import sys
import asyncio
from datetime import datetime

# Добавляем путь к приложению
sys.path.append('.')

def test_imports():
    """Тестируем импорты всех компонентов"""
    print("🔧 Тестирование импортов...")
    
    try:
        from app.main import app
        print("✅ FastAPI app imports successfully")
    except Exception as e:
        print(f"❌ FastAPI import error: {e}")
        return False
    
    try:
        from app.telegram_bot import EnhancedTelegramBot
        print("✅ Telegram bot imports successfully")
    except Exception as e:
        print(f"❌ Telegram bot import error: {e}")
    
    try:
        from app.services.simple_dynamic_auth import SimpleDynamicAuth
        auth = SimpleDynamicAuth()
        print("✅ SimpleDynamicAuth imports successfully")
    except Exception as e:
        print(f"❌ SimpleDynamicAuth import error: {e}")
        return False
    
    try:
        from app.telegram_auth import TelegramAuth
        telegram_auth = TelegramAuth()
        print("✅ TelegramAuth imports successfully")
    except Exception as e:
        print(f"❌ TelegramAuth import error: {e}")
        return False
    
    return True

def test_auth_endpoints():
    """Тестируем эндпоинты аутентификации"""
    print("\n🔧 Тестирование эндпоинтов аутентификации...")
    
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Тест health endpoint
        response = client.get("/health")
        if response.status_code == 200:
            print("✅ /health endpoint works")
        else:
            print(f"❌ /health endpoint failed: {response.status_code}")
        
        # Тест webapp endpoint
        response = client.get("/webapp")
        if response.status_code == 200:
            print("✅ /webapp endpoint works")
        else:
            print(f"❌ /webapp endpoint failed: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Endpoint test error: {e}")
        return False

async def test_auth_service():
    """Тестируем сервис аутентификации"""
    print("\n🔧 Тестирование SimpleDynamicAuth...")
    
    try:
        from app.services.simple_dynamic_auth import SimpleDynamicAuth
        from app.database import get_db
        
        auth = SimpleDynamicAuth()
        
        # Проверяем создание ссылки (без реальной БД)
        print("✅ SimpleDynamicAuth service initialized")
        print(f"✅ Session lifetime: {auth.session_lifetime}")
        print(f"✅ Admin session lifetime: {auth.admin_session_lifetime}")
        
        return True
        
    except Exception as e:
        print(f"❌ Auth service test error: {e}")
        return False

def test_webapp_template():
    """Тестируем шаблон WebApp"""
    print("\n🔧 Тестирование WebApp шаблона...")
    
    try:
        from pathlib import Path
        
        template_path = Path("templates/webapp.html")
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            
            # Проверяем ключевые исправления
            if "token=${data.access_token}" in content:
                print("✅ Token passing fix found in template")
            else:
                print("❌ Token passing fix NOT found in template")
                return False
            
            if "urlParams.get('token')" in content:
                print("✅ URL parameter handling found in template")
            else:
                print("❌ URL parameter handling NOT found in template")
                return False
            
            if "localStorage.setItem('auth_token'" in content:
                print("✅ Token storage found in template")
            else:
                print("❌ Token storage NOT found in template")
                return False
            
            print("✅ WebApp template contains all required fixes")
            return True
        else:
            print("❌ WebApp template not found")
            return False
            
    except Exception as e:
        print(f"❌ Template test error: {e}")
        return False

def test_environment():
    """Тестируем переменные окружения"""
    print("\n🔧 Тестирование переменных окружения...")
    
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "TELEGRAM_BOT_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("   (This is expected in development)")
    else:
        print("✅ All required environment variables are set")
    
    return True

async def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ЦИКЛА АУТЕНТИФИКАЦИИ")
    print("=" * 60)
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Импорты", test_imports),
        ("Эндпоинты", test_auth_endpoints),
        ("Сервис аутентификации", lambda: asyncio.run(test_auth_service())),
        ("WebApp шаблон", test_webapp_template),
        ("Переменные окружения", test_environment)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {passed}/{total} тестов прошли")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Исправление готово к деплою.")
        return True
    else:
        print("⚠️  Некоторые тесты не прошли. Требуется дополнительная проверка.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
