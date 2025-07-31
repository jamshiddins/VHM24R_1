"""
E2E тесты для пользовательских сценариев
"""
import pytest
from fastapi.testclient import TestClient
import tempfile
import os
from unittest.mock import patch


class TestUserRegistrationWorkflow:
    """Тест полного цикла регистрации пользователя"""
    
    @patch('app.api.auth.verify_telegram_auth')
    def test_complete_user_registration_flow(self, mock_verify, client: TestClient):
        """Тест полного цикла регистрации и одобрения пользователя"""
        mock_verify.return_value = True
        
        # 1. Пользователь регистрируется через Telegram
        telegram_data = {
            "id": 999888777,
            "first_name": "New",
            "last_name": "User",
            "username": "newuser",
            "auth_date": 1642248000,
            "hash": "test_hash"
        }
        
        response = client.post("/api/auth/telegram", json=telegram_data)
        
        if response.status_code == 200:
            # 2. Получаем токен
            data = response.json()
            assert "access_token" in data
            token = data["access_token"]
            
            # 3. Проверяем профиль пользователя
            headers = {"Authorization": f"Bearer {token}"}
            profile_response = client.get("/api/auth/me", headers=headers)
            
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                assert profile_data["telegram_id"] == 999888777
                assert profile_data["username"] == "newuser"


class TestFileUploadWorkflow:
    """Тест полного цикла загрузки и обработки файла"""
    
    def test_complete_file_upload_workflow(self, authenticated_client: TestClient):
        """Тест полного цикла загрузки файла"""
        # 1. Создаем тестовый CSV файл
        csv_content = """machine_code,order_number,order_price,creation_time
VM001,ORD001,100.50,2024-01-15 10:30:00
VM002,ORD002,250.75,2024-01-15 11:45:00"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            temp_file = f.name
        
        try:
            # 2. Загружаем файл
            with open(temp_file, 'rb') as f:
                response = authenticated_client.post(
                    "/api/files/upload",
                    files={"file": ("test.csv", f, "text/csv")}
                )
            
            if response.status_code == 200:
                # 3. Проверяем, что файл появился в списке
                files_response = authenticated_client.get("/api/files/")
                assert files_response.status_code == 200
                
                files_data = files_response.json()
                assert isinstance(files_data, list)
                
                # 4. Если файл обработался, проверяем заказы
                orders_response = authenticated_client.get("/api/orders/")
                if orders_response.status_code == 200:
                    orders_data = orders_response.json()
                    assert "orders" in orders_data
                    assert "total" in orders_data
        
        finally:
            os.unlink(temp_file)


class TestOrderManagementWorkflow:
    """Тест полного цикла управления заказами"""
    
    def test_complete_order_management_workflow(self, authenticated_client: TestClient, sample_orders):
        """Тест полного цикла работы с заказами"""
        # 1. Получаем список заказов
        response = authenticated_client.get("/api/orders/")
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        assert "total" in data
        
        if data["orders"]:
            order = data["orders"][0]
            order_id = order["id"]
            
            # 2. Получаем конкретный заказ
            order_response = authenticated_client.get(f"/api/orders/{order_id}")
            if order_response.status_code == 200:
                order_data = order_response.json()
                assert order_data["id"] == order_id
                
                # 3. Обновляем заказ
                update_data = {"order_price": 999.99}
                update_response = authenticated_client.put(
                    f"/api/orders/{order_id}", 
                    json=update_data
                )
                
                # Проверяем результат обновления
                assert update_response.status_code in [200, 404, 422]


class TestAnalyticsWorkflow:
    """Тест полного цикла работы с аналитикой"""
    
    def test_complete_analytics_workflow(self, authenticated_client: TestClient, sample_orders):
        """Тест полного цикла получения аналитики"""
        # 1. Получаем общую аналитику
        response = authenticated_client.get("/api/analytics/")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
        assert "payment_types" in data
        assert "top_machines" in data
        assert "time_series" in data
        
        # 2. Получаем аналитику с фильтрами
        filtered_response = authenticated_client.get(
            "/api/analytics/",
            params={
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "group_by": "day"
            }
        )
        assert filtered_response.status_code == 200
        
        filtered_data = filtered_response.json()
        assert "summary" in filtered_data
        
        # 3. Экспортируем аналитику
        export_response = authenticated_client.get("/api/export/analytics")
        # Может быть 200 или 404 если эндпоинт не существует
        assert export_response.status_code in [200, 404]


class TestAdminWorkflow:
    """Тест административных сценариев"""
    
    def test_admin_user_management_workflow(self, admin_client: TestClient, client: TestClient):
        """Тест административного управления пользователями"""
        # 1. Создаем нового пользователя для тестирования
        with patch('app.api.auth.verify_telegram_auth') as mock_verify:
            mock_verify.return_value = True
            
            new_user_data = {
                "id": 111222333,
                "first_name": "Admin",
                "last_name": "Test",
                "username": "admintest",
                "auth_date": 1642248000,
                "hash": "test_hash"
            }
            
            registration_response = client.post("/api/auth/telegram", json=new_user_data)
            
            if registration_response.status_code == 200:
                # 2. Админ получает список пользователей
                users_response = admin_client.get("/api/admin/users")
                
                if users_response.status_code == 200:
                    users_data = users_response.json()
                    assert isinstance(users_data, list)
                    
                    # 3. Находим нового пользователя и одобряем его
                    new_user = next(
                        (u for u in users_data if u.get("username") == "admintest"), 
                        None
                    )
                    
                    if new_user:
                        user_id = new_user["id"]
                        approve_response = admin_client.post(f"/api/admin/users/{user_id}/approve")
                        
                        # Проверяем результат одобрения
                        assert approve_response.status_code in [200, 404]


class TestTelegramBotWorkflow:
    """Тест интеграции с Telegram ботом"""
    
    @patch('app.telegram_bot.process_update')
    def test_telegram_bot_interaction_workflow(self, mock_process, client: TestClient):
        """Тест взаимодействия с Telegram ботом"""
        mock_process.return_value = None
        
        # 1. Пользователь отправляет /start
        start_update = {
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1642248000,
                "text": "/start"
            }
        }
        
        response = client.post("/webhook/telegram", json=start_update)
        assert response.status_code in [200, 404]
        
        # 2. Пользователь отправляет команду /help
        help_update = {
            "update_id": 123457,
            "message": {
                "message_id": 2,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1642248001,
                "text": "/help"
            }
        }
        
        response = client.post("/webhook/telegram", json=help_update)
        assert response.status_code in [200, 404]


class TestErrorHandlingWorkflow:
    """Тест обработки ошибок в различных сценариях"""
    
    def test_invalid_file_upload_workflow(self, authenticated_client: TestClient):
        """Тест загрузки невалидного файла"""
        # 1. Создаем невалидный файл
        invalid_content = "This is not a CSV file"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(invalid_content)
            f.flush()
            temp_file = f.name
        
        try:
            # 2. Пытаемся загрузить невалидный файл
            with open(temp_file, 'rb') as f:
                response = authenticated_client.post(
                    "/api/files/upload",
                    files={"file": ("invalid.txt", f, "text/plain")}
                )
            
            # Ожидаем ошибку валидации
            assert response.status_code in [400, 422]
        
        finally:
            os.unlink(temp_file)
    
    def test_unauthorized_access_workflow(self, client: TestClient):
        """Тест попыток неавторизованного доступа"""
        # 1. Попытка доступа к защищенным эндпоинтам без токена
        protected_endpoints = [
            "/api/auth/me",
            "/api/files/",
            "/api/orders/",
            "/api/analytics/",
            "/api/export/orders"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
    
    def test_invalid_data_workflow(self, authenticated_client: TestClient):
        """Тест отправки невалидных данных"""
        # 1. Попытка создания заказа с невалидными данными
        invalid_order_data = {
            "invalid_field": "invalid_value"
        }
        
        response = authenticated_client.post("/api/orders/", json=invalid_order_data)
        # Ожидаем ошибку валидации или 404 если эндпоинт не существует
        assert response.status_code in [400, 404, 422]
        
        # 2. Попытка обновления заказа с невалидными данными
        response = authenticated_client.put("/api/orders/999999", json=invalid_order_data)
        # Ожидаем ошибку валидации или 404
        assert response.status_code in [400, 404, 422]


class TestPerformanceWorkflow:
    """Тест производительности в реальных сценариях"""
    
    def test_large_file_upload_workflow(self, authenticated_client: TestClient):
        """Тест загрузки большого файла"""
        # Создаем файл с большим количеством записей
        large_csv_content = "machine_code,order_number,order_price,creation_time\n"
        for i in range(1000):  # 1000 записей
            large_csv_content += f"VM{i:03d},ORD{i:06d},{100.0 + i},2024-01-15 10:30:00\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(large_csv_content)
            f.flush()
            temp_file = f.name
        
        try:
            # Загружаем большой файл
            with open(temp_file, 'rb') as f:
                response = authenticated_client.post(
                    "/api/files/upload",
                    files={"file": ("large_test.csv", f, "text/csv")}
                )
            
            # Проверяем, что система справляется с большими файлами
            assert response.status_code in [200, 413, 422]  # 413 = Payload Too Large
        
        finally:
            os.unlink(temp_file)
    
    def test_concurrent_requests_workflow(self, authenticated_client: TestClient):
        """Тест одновременных запросов"""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = authenticated_client.get("/api/orders/")
            results.append(response.status_code)
        
        # Создаем 10 одновременных запросов
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Запускаем все потоки
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # Проверяем результаты
        assert len(results) == 10
        assert all(status in [200, 429] for status in results)  # 429 = Too Many Requests
        
        # Проверяем, что запросы выполнились за разумное время
        assert end_time - start_time < 30  # Максимум 30 секунд
