#!/usr/bin/env python3
"""
Тест загрузки файлов в VHM24R систему
"""

import requests
import json
import os
from pathlib import Path

# Конфигурация
API_BASE = "http://localhost:8000"
TEST_TOKEN = "test_token_123"  # Замените на реальный токен

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

def test_file_upload():
    """Тест загрузки файла"""
    try:
        # Создаем тестовый файл если его нет
        if not os.path.exists("test_orders.csv"):
            create_test_csv()
        
        # Подготавливаем файл для загрузки
        files = {
            'files': ('test_orders.csv', open('test_orders.csv', 'rb'), 'text/csv')
        }
        
        headers = {
            'Authorization': f'Bearer {TEST_TOKEN}'
        }
        
        print("📤 Загружаем файл...")
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

def test_files_list():
    """Тест получения списка файлов"""
    try:
        headers = {
            'Authorization': f'Bearer {TEST_TOKEN}'
        }
        
        response = requests.get(
            f"{API_BASE}/api/v1/files/",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Получен список файлов: {len(files)} файлов")
            
            for file_info in files[:3]:  # Показываем первые 3 файла
                print(f"   📄 {file_info.get('filename', 'unknown')}")
                print(f"      Size: {file_info.get('file_size', 0)} bytes")
                print(f"      Status: {file_info.get('processing_status', 'unknown')}")
            
            return True
        else:
            print(f"❌ Files list failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Files list error: {e}")
        return False

def test_orders_list():
    """Тест получения списка заказов"""
    try:
        headers = {
            'Authorization': f'Bearer {TEST_TOKEN}'
        }
        
        response = requests.get(
            f"{API_BASE}/api/v1/orders?page=1&page_size=5",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            orders = data.get('orders', [])
            pagination = data.get('pagination', {})
            
            print(f"✅ Получен список заказов: {len(orders)} из {pagination.get('total', 0)}")
            
            for order in orders[:3]:  # Показываем первые 3 заказа
                print(f"   📦 {order.get('order_number', 'unknown')}")
                print(f"      Machine: {order.get('machine_code', 'unknown')}")
                print(f"      Price: {order.get('order_price', 0)}")
            
            return True
        else:
            print(f"❌ Orders list failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Orders list error: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование системы загрузки файлов VHM24R")
    print("=" * 50)
    
    # 1. Проверка здоровья системы
    print("\n1️⃣ Проверка работоспособности API...")
    if not test_health_check():
        print("❌ Система недоступна. Проверьте, что сервер запущен на localhost:8000")
        return
    
    # 2. Тест загрузки файла
    print("\n2️⃣ Тестирование загрузки файла...")
    session_id = test_file_upload()
    
    if not session_id:
        print("❌ Загрузка файла не удалась")
        return
    
    # 3. Тест списка файлов
    print("\n3️⃣ Тестирование получения списка файлов...")
    test_files_list()
    
    # 4. Тест списка заказов
    print("\n4️⃣ Тестирование получения списка заказов...")
    test_orders_list()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
    
    # Очистка
    if os.path.exists("test_orders.csv"):
        os.remove("test_orders.csv")
        print("🧹 Тестовый файл удален")

if __name__ == "__main__":
    main()
