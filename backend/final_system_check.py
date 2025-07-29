"""
Финальная проверка готовности системы к деплою
"""
import os
import sys
import subprocess
import importlib.util

def check_environment_variables():
    """Проверка переменных окружения"""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = [
        'DATABASE_URL',
        'TELEGRAM_BOT_TOKEN', 
        'SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Все необходимые переменные окружения установлены")
        return True

def check_imports():
    """Проверка импортов"""
    print("\n🔍 Проверка импортов...")
    
    # Устанавливаем тестовые переменные
    os.environ['DATABASE_URL'] = 'postgresql://test'
    os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
    os.environ['SECRET_KEY'] = 'test_key'
    
    try:
        from app.main import app
        print("✅ FastAPI app импортируется успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        return False

def check_requirements():
    """Проверка requirements.txt"""
    print("\n🔍 Проверка requirements.txt...")
    
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read()
        
        critical_packages = [
            'fastapi',
            'uvicorn',
            'sqlalchemy',
            'alembic',
            'python-telegram-bot',
            'jinja2==3.1.2'
        ]
        
        missing_packages = []
        for package in critical_packages:
            if package not in requirements:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Отсутствуют пакеты: {', '.join(missing_packages)}")
            return False
        else:
            print("✅ Все критические пакеты присутствуют")
            return True
            
    except FileNotFoundError:
        print("❌ Файл requirements.txt не найден")
        return False

def check_security():
    """Проверка безопасности"""
    print("\n🔍 Проверка безопасности...")
    
    # Проверяем, что токены не захардкожены
    security_issues = []
    
    # Проверяем основные файлы
    files_to_check = [
        'app/main.py',
        'app/telegram_bot.py',
        'app/api/auth.py'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Ищем захардкоженные токены
            if '8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk' in content:
                security_issues.append(f"Захардкоженный токен в {file_path}")
    
    if security_issues:
        print("❌ Проблемы безопасности:")
        for issue in security_issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ Критические проблемы безопасности не найдены")
        return True

def check_database_models():
    """Проверка моделей базы данных"""
    print("\n🔍 Проверка моделей базы данных...")
    
    try:
        from app.models import User, Order, UploadedFile
        print("✅ Основные модели импортируются успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта моделей: {e}")
        return False

def check_api_endpoints():
    """Проверка API эндпоинтов"""
    print("\n🔍 Проверка API эндпоинтов...")
    
    try:
        from app.api import auth, files, orders, analytics
        print("✅ API модули импортируются успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта API: {e}")
        return False

def check_telegram_bot():
    """Проверка Telegram бота"""
    print("\n🔍 Проверка Telegram бота...")
    
    try:
        import app.telegram_bot
        print("✅ Telegram бот модуль импортируется успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта Telegram бота: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка инициализации Telegram бота: {e}")
        return False

def check_templates():
    """Проверка шаблонов"""
    print("\n🔍 Проверка шаблонов...")
    
    template_files = [
        'templates/webapp.html'
    ]
    
    missing_templates = []
    for template in template_files:
        if not os.path.exists(template):
            missing_templates.append(template)
    
    if missing_templates:
        print(f"❌ Отсутствуют шаблоны: {', '.join(missing_templates)}")
        return False
    else:
        print("✅ Все шаблоны присутствуют")
        return True

def check_frontend():
    """Проверка frontend файлов"""
    print("\n🔍 Проверка frontend...")
    
    frontend_files = [
        '../frontend/index.html',
        '../frontend/src/main.js',
        '../frontend/src/App.vue'
    ]
    
    missing_files = []
    for file_path in frontend_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Отсутствуют frontend файлы: {', '.join(missing_files)}")
        return False
    else:
        print("✅ Основные frontend файлы присутствуют")
        return True

def main():
    """Основная функция проверки"""
    print("🚀 ФИНАЛЬНАЯ ПРОВЕРКА ГОТОВНОСТИ СИСТЕМЫ К ДЕПЛОЮ")
    print("=" * 60)
    
    checks = [
        ("Переменные окружения", check_environment_variables),
        ("Импорты", check_imports),
        ("Requirements", check_requirements),
        ("Безопасность", check_security),
        ("Модели БД", check_database_models),
        ("API эндпоинты", check_api_endpoints),
        ("Telegram бот", check_telegram_bot),
        ("Шаблоны", check_templates),
        ("Frontend", check_frontend)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ Ошибка при проверке {name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 РЕЗУЛЬТАТ: {passed}/{total} проверок пройдено")
    
    if passed == total:
        print("🎉 СИСТЕМА ГОТОВА К ДЕПЛОЮ!")
        return True
    else:
        print("⚠️  СИСТЕМА НЕ ГОТОВА К ДЕПЛОЮ")
        print("Необходимо исправить указанные проблемы")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
