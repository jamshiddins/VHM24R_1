"""
Тесты для интеграции с Telegram
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.telegram_bot import EnhancedTelegramBot
from app.telegram_auth import TelegramAuth
from app.models import User, TelegramSession


class TestEnhancedTelegramBot:
    """Тесты для EnhancedTelegramBot"""
    
    @pytest.fixture
    def bot_token(self):
        return "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    
    @pytest.fixture
    def telegram_bot(self, bot_token):
        return EnhancedTelegramBot(bot_token)
    
    def test_bot_initialization(self, telegram_bot, bot_token):
        """Тест инициализации бота"""
        assert telegram_bot.token == bot_token
        assert telegram_bot.application is not None
    
    @pytest.mark.asyncio
    async def test_start_command(self, telegram_bot):
        """Тест команды /start"""
        # Мок update и context
        mock_update = Mock()
        mock_update.effective_user.id = 123456789
        mock_update.effective_user.username = "testuser"
        mock_update.effective_user.first_name = "Test"
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Пользователь не существует
            mock_crud.get_user_by_telegram_id.return_value = None
            mock_crud.create_user.return_value = Mock(id=1)
            
            await telegram_bot.start_command(mock_update, mock_context)
            
            # Проверяем, что пользователь был создан
            mock_crud.create_user.assert_called_once()
            mock_update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_start_command_existing_user(self, telegram_bot):
        """Тест команды /start для существующего пользователя"""
        mock_update = Mock()
        mock_update.effective_user.id = 123456789
        mock_update.effective_user.username = "testuser"
        mock_update.effective_user.first_name = "Test"
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Пользователь уже существует
            existing_user = Mock()
            existing_user.status = "approved"
            mock_crud.get_user_by_telegram_id.return_value = existing_user
            
            await telegram_bot.start_command(mock_update, mock_context)
            
            # Проверяем, что новый пользователь НЕ был создан
            mock_crud.create_user.assert_not_called()
            mock_update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_webapp_command(self, telegram_bot):
        """Тест команды /webapp"""
        mock_update = Mock()
        mock_update.effective_user.id = 123456789
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud, \
             patch('app.telegram_bot.SimpleDynamicAuth') as mock_auth:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Пользователь существует и одобрен
            approved_user = Mock()
            approved_user.status = "approved"
            mock_crud.get_user_by_telegram_id.return_value = approved_user
            
            # Мок для создания токена сессии
            mock_auth_instance = Mock()
            mock_auth_instance.create_session_token = AsyncMock(return_value="test_token")
            mock_auth.return_value = mock_auth_instance
            
            await telegram_bot.webapp_command(mock_update, mock_context)
            
            # Проверяем, что токен был создан и отправлен
            mock_auth_instance.create_session_token.assert_called_once()
            mock_update.message.reply_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_webapp_command_pending_user(self, telegram_bot):
        """Тест команды /webapp для неодобренного пользователя"""
        mock_update = Mock()
        mock_update.effective_user.id = 123456789
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Пользователь существует но не одобрен
            pending_user = Mock()
            pending_user.status = "pending"
            mock_crud.get_user_by_telegram_id.return_value = pending_user
            
            await telegram_bot.webapp_command(mock_update, mock_context)
            
            # Проверяем, что пользователю отправлено сообщение о необходимости одобрения
            mock_update.message.reply_text.assert_called()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "ожидает одобрения" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_help_command(self, telegram_bot):
        """Тест команды /help"""
        mock_update = Mock()
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        await telegram_bot.help_command(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "команды" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_status_command(self, telegram_bot):
        """Тест команды /status"""
        mock_update = Mock()
        mock_update.effective_user.id = 123456789
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = Mock()
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            
            # Пользователь существует
            user = Mock()
            user.username = "testuser"
            user.first_name = "Test"
            user.status = "approved"
            user.role = "user"
            user.created_at = datetime.now()
            mock_crud.get_user_by_telegram_id.return_value = user
            
            await telegram_bot.status_command(mock_update, mock_context)
            
            mock_update.message.reply_text.assert_called()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "статус" in call_args.lower()
    
    def test_error_handler(self, telegram_bot):
        """Тест обработчика ошибок"""
        mock_update = Mock()
        mock_context = Mock()
        mock_context.error = Exception("Test error")
        
        # Тест не должен вызывать исключение
        try:
            import asyncio
            asyncio.run(telegram_bot.error_handler(mock_update, mock_context))
        except Exception as e:
            pytest.fail(f"Error handler raised an exception: {e}")


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
            assert len(token) > 50
    
    def test_verify_access_token_valid(self, telegram_auth):
        """Тест верификации валидного токена"""
        user_id = 123
        
        with patch('app.telegram_auth.os.getenv', return_value='test_secret_key'):
            # Создаем токен
            token = telegram_auth.create_access_token(user_id)
            
            # Верифицируем токен
            decoded_user_id = telegram_auth.verify_access_token(token)
            
            assert decoded_user_id == user_id
    
    def test_verify_access_token_invalid(self, telegram_auth):
        """Тест верификации невалидного токена"""
        invalid_token = "invalid.jwt.token"
        
        with patch('app.telegram_auth.os.getenv', return_value='test_secret_key'):
            decoded_user_id = telegram_auth.verify_access_token(invalid_token)
            
            assert decoded_user_id is None
    
    def test_verify_access_token_expired(self, telegram_auth):
        """Тест верификации истекшего токена"""
        user_id = 123
        
        with patch('app.telegram_auth.os.getenv', return_value='test_secret_key'), \
             patch('app.telegram_auth.datetime') as mock_datetime:
            
            # Создаем токен в прошлом
            past_time = datetime.now() - timedelta(hours=25)
            mock_datetime.utcnow.return_value = past_time
            
            token = telegram_auth.create_access_token(user_id)
            
            # Возвращаем текущее время
            mock_datetime.utcnow.return_value = datetime.now()
            
            decoded_user_id = telegram_auth.verify_access_token(token)
            
            assert decoded_user_id is None


class TestTelegramIntegration:
    """Интеграционные тесты Telegram функциональности"""
    
    @pytest.mark.asyncio
    async def test_full_auth_flow(self):
        """Тест полного потока аутентификации через Telegram"""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        bot = EnhancedTelegramBot(bot_token)
        
        # Мок пользователя
        mock_user = Mock()
        mock_user.id = 1
        mock_user.telegram_id = 123456789
        mock_user.status = "approved"
        
        with patch('app.telegram_bot.get_db') as mock_get_db, \
             patch('app.telegram_bot.crud') as mock_crud:
            
            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_crud.get_user_by_telegram_id.return_value = mock_user
            
            # Создаем мок update для команды /webapp
            mock_update = Mock()
            mock_update.effective_user.id = 123456789
            mock_update.message.reply_text = AsyncMock()
            
            mock_context = Mock()
            
            with patch('app.telegram_bot.SimpleDynamicAuth') as mock_auth:
                mock_auth_instance = Mock()
                mock_auth_instance.create_session_token = AsyncMock(return_value="test_session_token")
                mock_auth.return_value = mock_auth_instance
                
                await bot.webapp_command(mock_update, mock_context)
                
                # Проверяем, что токен был создан
                mock_auth_instance.create_session_token.assert_called_once_with(123456789, mock_db)
                mock_update.message.reply_text.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
