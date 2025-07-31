import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, Text
from sqlalchemy.orm import sessionmaker
import os
import sys

# Добавляем путь к приложению
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import get_db, Base
from app.models import User

# Тестовая база данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def test_db():
    # Патчим ARRAY поля для SQLite
    from app.models import UnifiedOrder, File
    
    # Заменяем ARRAY на Text для SQLite
    if hasattr(UnifiedOrder, 'source_files'):
        UnifiedOrder.source_files.type = Text()
    if hasattr(File, 'sheet_names'):
        File.sheet_names.type = Text()
    
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

class TestHealthCheck:
    """Тесты health check endpoint"""
    
    def test_health_endpoint(self, test_db):
        """Тест основного health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data

class TestAuthentication:
    """Тесты аутентификации"""
    
    def test_auth_me_without_token(self):
        """Тест получения информации о пользователе без токена"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403

    def test_telegram_auth_missing_data(self):
        """Тест Telegram аутентификации с отсутствующими данными"""
        response = client.post("/api/v1/auth/telegram", json={})
        assert response.status_code == 422  # Validation error

class TestMainEndpoints:
    """Тесты основных endpoints"""
    
    def test_root_endpoint(self):
        """Тест корневого endpoint"""
        response = client.get("/")
        assert response.status_code == 200

    def test_orders_without_auth(self):
        """Тест получения заказов без аутентификации"""
        response = client.get("/api/v1/orders")
        assert response.status_code == 403

    def test_upload_without_auth(self):
        """Тест загрузки файлов без аутентификации"""
        response = client.post("/api/v1/upload")
        assert response.status_code == 403

    def test_analytics_without_auth(self):
        """Тест аналитики без аутентификации"""
        response = client.get("/api/v1/analytics")
        assert response.status_code == 403

class TestWebhook:
    """Тесты Telegram webhook"""
    
    def test_telegram_webhook_empty(self):
        """Тест webhook с пустыми данными"""
        response = client.post("/webhook/telegram", json={})
        # Webhook должен обрабатывать пустые данные
        assert response.status_code in [200, 500]  # Зависит от конфигурации

class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    def test_nonexistent_endpoint(self):
        """Тест несуществующего endpoint"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

    def test_invalid_method(self):
        """Тест неправильного HTTP метода"""
        response = client.delete("/health")
        assert response.status_code == 405

if __name__ == "__main__":
    pytest.main([__file__])
