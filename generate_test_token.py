#!/usr/bin/env python3
"""
Генерация тестового JWT токена для VHM24R
"""

import sys
import os
from pathlib import Path

# Добавляем backend в путь
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Меняем рабочую директорию
os.chdir(backend_dir)

try:
    from app.services.unified_auth import unified_auth_service
    from app import crud, database
    from app.models import User
    
    def create_test_user_and_token():
        """Создает тестового пользователя и генерирует токен"""
        
        # Получаем сессию БД
        db = next(database.get_db())
        
        # Проверяем, есть ли уже тестовый пользователь
        test_user = crud.get_user_by_telegram_id(db, 123456789)
        
        if not test_user:
            # Создаем тестового пользователя
            user_data = {
                'telegram_id': 123456789,
                'username': 'test_user',
                'first_name': 'Test',
                'last_name': 'User',
                'status': 'approved',
                'role': 'user'
            }
            test_user = crud.create_user(db, user_data)
            print(f"✅ Создан тестовый пользователь: {test_user.username}")
        else:
            print(f"✅ Найден существующий тестовый пользователь: {test_user.username}")
        
        # Генерируем JWT токен
        token_data = {
            'user_id': test_user.id,
            'telegram_id': test_user.telegram_id,
            'username': test_user.username,
            'role': test_user.role
        }
        
        token = unified_auth_service.create_access_token(token_data)
        
        print(f"🔑 JWT токен: {token}")
        print(f"👤 Пользователь ID: {test_user.id}")
        print(f"📱 Telegram ID: {test_user.telegram_id}")
        
        return token, test_user
    
    if __name__ == "__main__":
        print("🔐 Генерация тестового JWT токена...")
        token, user = create_test_user_and_token()
        
        # Сохраняем токен в файл для использования в тестах
        with open("test_token.txt", "w") as f:
            f.write(token)
        
        print("💾 Токен сохранен в файл test_token.txt")
        print("\n📋 Для использования в тестах:")
        print(f"TEST_TOKEN = '{token}'")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
