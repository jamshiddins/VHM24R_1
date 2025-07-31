"""
Тесты для сервисов аутентификации
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.services.unified_auth import unified_auth_service
from app.services.simple_dynamic_auth import SimpleDynamicAuth
from app.telegram_auth import TelegramAuth
from app.models import User
from app.schemas import TelegramAuthData


class TestUnifiedAuthService:
    """Тесты для UnifiedAuthService"""
    
    def test_authenticate_telegram_user_success(self):
        """Тест успешной аутентификации через Telegram"""
        # Подготовка данных
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=int(datetime.now().timestamp()),
            hash="test_hash"
        )
        
        # Мок базы данных
        mock_db = Mock(spec=Session)
        
        # Мок пользователя
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.telegram_id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.status = "approved"
        mock_user.role = "user"
        
        with patch('app.services.unified_auth.crud') as mock_crud, \
             patch('app.services.unified_auth.TelegramAuth') as mock_telegram_auth:
            
            # Настройка моков
            mock_crud.get_user_by_telegram_id.return_value = mock_user
            mock_telegram_auth_instance = Mock()
            mock_telegram_auth_instance.verify_telegram_auth.return_value = True
            mock_telegram_auth_instance.create_access_token.return_value = "test_token"
            mock_telegram_auth.return_value = mock_telegram_auth_instance
            
            # Выполнение теста
            result = unified_auth_service.authenticate_telegram_user(auth_data, mock_db)
            
            # Проверки
            assert result["access_token"] == "test_token"
            assert result["token_type"] == "bearer"
            assert result["user"]["id"] == 1
            assert result["user"]["username"] == "testuser"
            
    def test_authenticate_telegram_user_invalid_hash(self):
        """Тест аутентификации с неверным хешем"""
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=int(datetime.now().timestamp()),
            hash="invalid_hash"
        )
        
        mock_db = Mock(spec=Session)
        
        with patch('app.services.unified_auth.TelegramAuth') as mock_telegram_auth:
            mock_telegram_auth_instance = Mock()
            mock_telegram_auth_instance.verify_telegram_auth.return_value = False
            mock_telegram_auth.return_value = mock_telegram_auth_instance
            
            with pytest.raises(Exception, match="Invalid Telegram authentication"):
                unified_auth_service.authenticate_telegram_user(auth_data, mock_db)


class TestSimpleDynamicAuth:
    """Тесты для SimpleDynamicAuth"""
    
    @pytest.fixture
    def auth_service(self):
        return SimpleDynamicAuth()
    
    @pytest.mark.asyncio
    async def test_create_session_token(self, auth_service):
        """Тест создания токена сессии"""
        mock_db = Mock(spec=Session)
        user_id = 123456789
        
        with patch.object(auth_service, '_save_session_to_db', new_callable=AsyncMock) as mock_save:
            token = await auth_service.create_session_token(user_id, mock_db)
            
            assert isinstance(token, str)
            assert len(token) > 10
            mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_session_token_success(self, auth_service):
        """Тест успешной валидации токена сессии"""
        mock_db = Mock(spec=Session)
        token = "test_token"
        user_id = 123456789
        
        # Мок сессии из БД
        mock_session = Mock()
        mock_session.telegram_user_id = user_id
        mock_session.expires_at = datetime.utcnow() + timedelta(minutes=30)
        mock_session.is_used = False
        
        with patch.object(auth_service, '_get_session_from_db', return_value=mock_session), \
             patch.object(auth_service, '_mark_session_used', new_callable=AsyncMock):
            
            result = await auth_service.validate_session_token(token, mock_db)
            assert result == user_id
    
    @pytest.mark.asyncio
    async def test_validate_session_token_expired(self, auth_service):
        """Тест валидации истекшего токена"""
        mock_db = Mock(spec=Session)
        token = "expired_token"
        
        # Мок истекшей сессии
        mock_session = Mock()
        mock_session.expires_at = datetime.utcnow() - timedelta(minutes=30)
        
        with patch.object(auth_service, '_get_session_from_db', return_value=mock_session):
            result = await auth_service.validate_session_token(token, mock_db)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_session_token_already_used(self, auth_service):
        """Тест валидации уже использованного токена"""
        mock_db = Mock(spec=Session)
        token = "used_token"
        
        # Мок использованной сессии
        mock_session = Mock()
        mock_session.expires_at = datetime.utcnow() + timedelta(minutes=30)
        mock_session.is_used = True
        
        with patch.object(auth_service, '_get_session_from_db', return_value=mock_session):
            result = await auth_service.validate_session_token(token, mock_db)
            assert result is None


class TestTelegramAuth:
    """Тесты для TelegramAuth"""
    
    @pytest.fixture
    def telegram_auth(self):
        return TelegramAuth()
    
    def test_create_access_token(self, telegram_auth):
        """Тест создания JWT токена"""
        user_id = 123
        
        with patch('app.telegram_auth.os.getenv', return_value='test_secret_key'):
            token = telegram_auth.create_access_token(user_id)
            
            assert isinstance(token, str)
            assert len(token) > 50  # JWT токены довольно длинные
    
    def test_verify_telegram_auth_success(self, telegram_auth):
        """Тест успешной верификации Telegram данных"""
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=int(datetime.now().timestamp()),
            hash="valid_hash"
        )
        
        with patch('app.telegram_auth.os.getenv', return_value='test_bot_token'), \
             patch('app.telegram_auth.hashlib.sha256') as mock_sha256:
            
            # Настройка мока для правильного хеша
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "valid_hash"
            mock_sha256.return_value = mock_hash
            
            result = telegram_auth.verify_telegram_auth(auth_data)
            assert result is True
    
    def test_verify_telegram_auth_invalid_hash(self, telegram_auth):
        """Тест верификации с неверным хешем"""
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=int(datetime.now().timestamp()),
            hash="invalid_hash"
        )
        
        with patch('app.telegram_auth.os.getenv', return_value='test_bot_token'), \
             patch('app.telegram_auth.hashlib.sha256') as mock_sha256:
            
            # Настройка мока для неправильного хеша
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "different_hash"
            mock_sha256.return_value = mock_hash
            
            result = telegram_auth.verify_telegram_auth(auth_data)
            assert result is False
    
    def test_verify_telegram_auth_expired(self, telegram_auth):
        """Тест верификации истекших данных"""
        # Данные старше 24 часов
        old_timestamp = int((datetime.now() - timedelta(hours=25)).timestamp())
        
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=old_timestamp,
            hash="any_hash"
        )
        
        result = telegram_auth.verify_telegram_auth(auth_data)
        assert result is False


class TestAuthIntegration:
    """Интеграционные тесты аутентификации"""
    
    @pytest.mark.asyncio
    async def test_full_auth_flow(self):
        """Тест полного потока аутентификации"""
        # Подготовка данных
        user_id = 123456789
        mock_db = Mock(spec=Session)
        
        # Создание сессии
        simple_auth = SimpleDynamicAuth()
        
        with patch.object(simple_auth, '_save_session_to_db', new_callable=AsyncMock), \
             patch.object(simple_auth, '_get_session_from_db') as mock_get_session, \
             patch.object(simple_auth, '_mark_session_used', new_callable=AsyncMock):
            
            # Создаем токен
            token = await simple_auth.create_session_token(user_id, mock_db)
            
            # Настраиваем мок для валидации
            mock_session = Mock()
            mock_session.telegram_user_id = user_id
            mock_session.expires_at = datetime.utcnow() + timedelta(minutes=30)
            mock_session.is_used = False
            mock_get_session.return_value = mock_session
            
            # Валидируем токен
            validated_user_id = await simple_auth.validate_session_token(token, mock_db)
            
            assert validated_user_id == user_id
    
    def test_auth_error_handling(self):
        """Тест обработки ошибок аутентификации"""
        auth_data = TelegramAuthData(
            id=123456789,
            first_name="Test",
            username="testuser",
            auth_date=int(datetime.now().timestamp()),
            hash="test_hash"
        )
        
        mock_db = Mock(spec=Session)
        
        with patch('app.services.unified_auth.crud') as mock_crud:
            # Симулируем ошибку базы данных
            mock_crud.get_user_by_telegram_id.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                unified_auth_service.authenticate_telegram_user(auth_data, mock_db)


if __name__ == "__main__":
    pytest.main([__file__])
