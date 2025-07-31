#!/usr/bin/env python3
"""
Тест системы с генерацией JWT токена
"""

import requests
import json
import os
import sys
from pathlib import Path
import jwt
from datetime import datetime, timedelta

# Конфигурация
API_BASE = "http://localhost:8000"
SECRET_KEY = "test-secret-key-for-development-only-change-in-production"

def generate_test_jwt_token():
    """Генерирует тестовый JWT токен"""
    payload = {
        'user_id': 1,
        'telegram_id': 123456789,
        'username': 'test_user',
        'role': 'user',
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def create_test_csv():
    """Создает тестовый CSV файл"""
    test_data = """order_number,machine_code,goods_name,order_price,payment_status
ORD001,VM001,Coffee,5000,paid
ORD002,VM002,Tea,3000,paid
ORD003,VM001,Juice,4000,pending
"""
    
    with open("test_orders.csv", "w", encoding="utf-8") as f:
        f.write(test_data)
    
    print("✅ Создан тестовый файл test_orders.csv")

def test_health_check():
    """Проверка работоспособности API"""
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check: {data['status']}")
            print(f"   Database: {data['services'].get('database', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_file_upload_with_token(token):
    """Тест загрузки файла с JWT токеном"""
    try:
        # Создаем тестовый файл если его нет
        if not os.path.exists("test_orders.csv"):
            create_test_csv()
        
        # Подготавливаем файл для загрузки
        files = {
            'files': ('test_orders.csv', open('test_orders.csv', 'rb'), 'text/csv')
        }
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        print("📤 Загружаем файл с JWT токеном...")
        response = requests.post(
            f"{API_BASE}/api/v1/files/upload",
            files=files,
            headers=headers
        )
        
        files['files'][1].close()  # Закрываем файл
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Файл успешно загружен!")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Files processed: {len(data.get('files', []))}")
            
            for file_info in data.get('files', []):
                if 'error' in file_info:
                    print(f"   ❌ {file_info['filename']}: {file_info['error']}")
                else:
                    print(f"   ✅ {file_info['filename']}: {file_info['size']} bytes")
            
            return data.get('session_id')
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def test_swagger_ui():
    """Тест доступности Swagger UI"""
    try:
        response = requests.get(f"{API_BASE}/docs")
        if response.status_code == 200:
            print("✅ Swagger UI доступен: http://localhost:8000/docs")
            return True
        else:
            print(f"❌ Swagger UI недоступен: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Swagger UI error: {e}")
        return False

def test_api_endpoints():
    """Тест основных API эндпоинтов"""
    token = generate_test_jwt_token()
    headers = {'Authorization': f'Bearer {token}'}
    
    endpoints = [
        ('/api/v1/files/', 'GET', 'Files list'),
        ('/api/v1/orders?page=1&page_size=5', 'GET', 'Orders list'),
        ('/api/v1/analytics/summary', 'GET', 'Analytics summary')
    ]
    
    for endpoint, method, description in endpoints:
        try:
            if method == 'GET':
                response = requests.get(f"{API_BASE}{endpoint}", headers=headers)
            
            if response.status_code == 200:
                print(f"✅ {description}: OK")
            else:
                print(f"❌ {description}: {response.status_code}")
                
        except Exception as e:
            print(f"❌ {description}: {e}")

def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование VHM24R системы с JWT токеном")
    print("=" * 50)
    
    # 1. Проверка здоровья системы
    print("\n1️⃣ Проверка работоспособности API...")
    if not test_health_check():
        print("❌ Система недоступна. Проверьте, что сервер запущен на localhost:8000")
        return
    
    # 2. Проверка Swagger UI
    print("\n2️⃣ Проверка Swagger UI...")
    test_swagger_ui()
    
    # 3. Генерация JWT токена
    print("\n3️⃣ Генерация JWT токена...")
    token = generate_test_jwt_token()
    print(f"🔑 JWT токен сгенерирован: {token[:50]}...")
    
    # 4. Тест загрузки файла
    print("\n4️⃣ Тестирование загрузки файла...")
    session_id = test_file_upload_with_token(token)
    
    if session_id:
        print(f"✅ Файл загружен, session_id: {session_id}")
    else:
        print("❌ Загрузка файла не удалась")
    
    # 5. Тест API эндпоинтов
    print("\n5️⃣ Тестирование API эндпоинтов...")
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    print("🌐 Swagger UI: http://localhost:8000/docs")
    print("📊 Health Check: http://localhost:8000/health")
    
    # Очистка
    if os.path.exists("test_orders.csv"):
        os.remove("test_orders.csv")
        print("🧹 Тестовый файл удален")

if __name__ == "__main__":
    main()
