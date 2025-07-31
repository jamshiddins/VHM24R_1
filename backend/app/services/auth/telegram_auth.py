"""
Рефакторенный сервис аутентификации через Telegram для VHM24R
"""

import hashlib
import hmac
import os
from typing import Dict, Any, Optional
from urllib.parse import unquote
from sqlalchemy.orm import Session

from .base_auth import BaseAuthService, AuthResult, AuthStatus, AuthCredentials
from .jwt_auth import JWTService, JWTCredentials
from ...utils.logger import get_logger
from ...utils.exceptions import AuthenticationError, ValidationError
from ... import crud

logger = get_logger(__name__)


class TelegramCredentials(AuthCredentials):
    """Учетные данные для Telegram аутентификации"""
    
    def __init__(self, telegram_data: Dict[str, Any]):
        super().__init__("telegram", telegram_data)
        
    def validate(self) -> bool:
        """Валидация Telegram данных"""
        required_fields = ['id', 'first_name', 'auth_date', 'hash']
        return all(str(self.data.get(field, '')).strip() for field in required_fields)


class TelegramAuthService(BaseAuthService):
    """
    Рефакторенный сервис аутентификации через Telegram
    
    Использует унифицированную архитектуру auth системы:
    - Базовый класс BaseAuthService
    - JWT сервис для создания токенов
    - Структурированное логирование
    - Унифицированная обработка ошибок
    """
    
    def __init__(self):
        super().__init__("Telegram")
        
        # Инициализируем JWT сервис для создания токенов
        self.jwt_service = JWTService()
        
        # Получаем Telegram bot token из окружения
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set - Telegram auth will not work")
    
    async def authenticate(self, credentials: TelegramCredentials) -> AuthResult:
        """
        Аутентификация пользователя через Telegram
        
        Args:
            credentials: Telegram данные от пользователя
            
        Returns:
            AuthResult: Результат аутентификации с JWT токенами
        """
        try:
            # Валидируем учетные данные
            self._validate_credentials(credentials)
            
            telegram_data = credentials.data
            
            # Проверяем подпись Telegram
            if not self._verify_telegram_auth(telegram_data):
                result = self._create_error_result(
                    "Invalid Telegram authentication signature",
                    AuthStatus.FAILED
                )
                self._log_auth_attempt(credentials, result)
                return result
            
            # Получаем или создаем пользователя в БД
            # Примечание: требуется передать db session извне
            # Для демонстрации используем базовую логику
            user_info = self._process_telegram_user(telegram_data)
            
            if not user_info:
                result = self._create_error_result(
                    "Failed to process Telegram user",
                    AuthStatus.FAILED
                )
                self._log_auth_attempt(credentials, result)
                return result
            
            # Создаем JWT токены через унифицированный сервис
            jwt_credentials = JWTCredentials(user_info)
            auth_result = await self.jwt_service.authenticate(jwt_credentials)
            
            if not auth_result.is_success:
                result = self._create_error_result(
                    "Failed to create authentication tokens",
                    AuthStatus.FAILED
                )
                self._log_auth_attempt(credentials, result)
                return result
            
            # Логируем успешную аутентификацию
            self._log_auth_attempt(credentials, auth_result, user_info.get('user_id'))
            
            logger.info(
                "Telegram authentication successful",
                telegram_id=telegram_data.get('id'),
                username=telegram_data.get('username'),
                user_id=user_info.get('user_id')
            )
            
            return auth_result
            
        except ValidationError as e:
            result = self._create_error_result(str(e), AuthStatus.FAILED)
            self._log_auth_attempt(credentials, result)
            return result
            
        except Exception as e:
            logger.error("Telegram authentication failed", error=str(e))
            result = self._create_error_result(
                "Telegram authentication failed",
                AuthStatus.FAILED
            )
            self._log_auth_attempt(credentials, result)
            return result
    
    async def validate_token(self, token: str) -> AuthResult:
        """
        Валидация токена (делегируем JWT сервису)
        
        Args:
            token: JWT токен для проверки
            
        Returns:
            AuthResult: Результат валидации
        """
        return await self.jwt_service.validate_token(token)
    
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """
        Обновление токена (делегируем JWT сервису)
        
        Args:
            refresh_token: Refresh токен
            
        Returns:
            AuthResult: Новые токены
        """
        return await self.jwt_service.refresh_token(refresh_token)
    
    def authenticate_with_db(self, telegram_data: Dict[str, Any], db: Session) -> AuthResult:
        """
        Синхронная аутентификация с доступом к БД
        
        Args:
            telegram_data: Данные от Telegram
            db: Сессия базы данных
            
        Returns:
            AuthResult: Результат аутентификации
        """
        try:
            credentials = TelegramCredentials(telegram_data)
            
            # Валидируем данные
            self._validate_credentials(credentials)
            
            # Проверяем подпись
            if not self._verify_telegram_auth(telegram_data):
                return self._create_error_result(
                    "Invalid Telegram authentication signature"
                )
            
            # Получаем или создаем пользователя
            user = self._get_or_create_user(telegram_data, db)
            
            if not user:
                return self._create_error_result("Failed to process user")
            
            # Проверяем статус пользователя
            if str(getattr(user, 'status', 'pending')) != 'approved':
                return self._create_error_result(
                    "User access pending approval",
                    AuthStatus.PENDING
                )
            
            # Подготавливаем данные для JWT
            user_data = {
                'user_id': getattr(user, 'id', 0),
                'username': getattr(user, 'username', ''),
                'role': str(getattr(user, 'role', 'user')),
                'status': str(getattr(user, 'status', 'active')),
                'telegram_id': getattr(user, 'telegram_id', 0)
            }
            
            # Создаем JWT токены
            access_token = self.jwt_service.create_access_token(user_data)
            refresh_token = self.jwt_service.create_refresh_token(user_data)
            
            # Формируем ответ
            user_info = {
                "id": user_data['user_id'],
                "username": user_data['username'],
                "first_name": getattr(user, 'first_name', ''),
                "role": user_data['role'],
                "status": user_data['status']
            }
            
            result = self._create_success_result(
                access_token=access_token,
                refresh_token=refresh_token,
                user_info=user_info,
                expires_in=self.jwt_service.access_token_lifetime
            )
            
            logger.info(
                "Telegram DB authentication successful",
                telegram_id=telegram_data.get('id'),
                user_id=user_data['user_id']
            )
            
            return result
            
        except Exception as e:
            logger.error("Telegram DB authentication failed", error=str(e))
            return self._create_error_result("Authentication failed")
    
    def _verify_telegram_auth(self, auth_data: Dict[str, Any]) -> bool:
        """
        Проверка подписи Telegram WebApp данных
        
        Args:
            auth_data: Данные от Telegram для проверки
            
        Returns:
            bool: True если подпись валидная
        """
        if not self.bot_token:
            logger.warning("Cannot verify Telegram auth - bot token not configured")
            return False
        
        try:
            # Извлекаем hash из данных
            received_hash = auth_data.get('hash')
            if not received_hash:
                logger.warning("No hash provided in Telegram auth data")
                return False
            
            # Создаем копию данных без hash
            auth_data_copy = {k: v for k, v in auth_data.items() if k != 'hash'}
            
            # Сортируем параметры и создаем строку для проверки
            data_check_arr = []
            for key in sorted(auth_data_copy.keys()):
                value = auth_data_copy[key]
                # URL decode значений
                if isinstance(value, str):
                    value = unquote(value)
                data_check_arr.append(f"{key}={value}")
            
            data_check_string = '\n'.join(data_check_arr)
            
            # Создаем секретный ключ
            secret_key = hashlib.sha256(self.bot_token.encode()).digest()
            
            # Вычисляем HMAC
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Сравниваем хеши
            is_valid = hmac.compare_digest(calculated_hash, received_hash)
            
            if not is_valid:
                logger.warning(
                    "Telegram auth signature verification failed",
                    telegram_id=auth_data.get('id'),
                    received_hash=received_hash[:10] + "...",
                    calculated_hash=calculated_hash[:10] + "..."
                )
            
            return is_valid
            
        except Exception as e:
            logger.error("Error verifying Telegram auth signature", error=str(e))
            return False
    
    def _get_or_create_user(self, telegram_data: Dict[str, Any], db: Session):
        """
        Получение или создание пользователя в БД
        
        Args:
            telegram_data: Данные пользователя из Telegram
            db: Сессия БД
            
        Returns:
            User: Объект пользователя или None
        """
        try:
            telegram_id = int(telegram_data.get('id', 0))
            
            # Пытаемся найти существующего пользователя
            user = crud.get_user_by_telegram_id(db, telegram_id)
            
            if user:
                # Обновляем информацию пользователя
                update_data = {}
                
                if telegram_data.get('username') and telegram_data['username'] != getattr(user, 'username', ''):
                    update_data['username'] = telegram_data['username']
                
                if telegram_data.get('first_name') and telegram_data['first_name'] != getattr(user, 'first_name', ''):
                    update_data['first_name'] = telegram_data['first_name']
                
                if telegram_data.get('last_name') and telegram_data['last_name'] != getattr(user, 'last_name', ''):
                    update_data['last_name'] = telegram_data['last_name']
                
                if update_data:
                    # Обновляем пользователя напрямую
                    for key, value in update_data.items():
                        if hasattr(user, key):
                            setattr(user, key, value)
                    db.commit()
                    db.refresh(user)
                    logger.info(
                        "Updated existing Telegram user",
                        telegram_id=telegram_id,
                        updates=list(update_data.keys())
                    )
                
                return user
            else:
                # Создаем нового пользователя
                user_data = {
                    'telegram_id': telegram_id,
                    'username': telegram_data.get('username', ''),
                    'first_name': telegram_data.get('first_name', ''),
                    'last_name': telegram_data.get('last_name', ''),
                    'status': 'pending',  # По умолчанию ожидает одобрения
                    'role': 'user'
                }
                
                user = crud.create_user(db, user_data)
                
                logger.info(
                    "Created new Telegram user",
                    telegram_id=telegram_id,
                    username=telegram_data.get('username', '')
                )
                
                return user
                
        except Exception as e:
            logger.error(
                "Failed to get or create Telegram user",
                telegram_id=telegram_data.get('id'),
                error=str(e)
            )
            return None
    
    def _process_telegram_user(self, telegram_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Обработка пользователя Telegram (без доступа к БД)
        
        Args:
            telegram_data: Данные пользователя из Telegram
            
        Returns:
            Optional[Dict[str, Any]]: Данные пользователя для JWT или None
        """
        try:
            # Базовая обработка без БД - для демонстрации
            # В реальном использовании требуется доступ к БД
            
            telegram_id = int(telegram_data.get('id', 0))
            
            return {
                'user_id': telegram_id,  # Временно используем telegram_id как user_id
                'username': telegram_data.get('username', ''),
                'role': 'user',
                'status': 'active',  # Упрощение для демо
                'telegram_id': telegram_id
            }
            
        except Exception as e:
            logger.error("Failed to process Telegram user", error=str(e))
            return None
    
    def create_access_token(self, user_id: int) -> str:
        """
        Создание access токена (обратная совместимость)
        
        Args:
            user_id: ID пользователя
            
        Returns:
            str: JWT токен
        """
        user_data = {'user_id': user_id}
        return self.jwt_service.create_access_token(user_data)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Проверка токена (обратная совместимость)
        
        Args:
            token: JWT токен
            
        Returns:
            Optional[Dict[str, Any]]: Данные пользователя или None
        """
        try:
            result = self.jwt_service._decode_token(token)
            return result
        except:
            return None
    
    def verify_telegram_auth(self, auth_data: Dict[str, Any]) -> bool:
        """
        Публичный метод для проверки подписи Telegram (для обратной совместимости)
        
        Args:
            auth_data: Данные от Telegram для проверки
            
        Returns:
            bool: True если подпись валидная
        """
        return self._verify_telegram_auth(auth_data)


# Глобальный экземпляр для использования в приложении
telegram_auth_service = TelegramAuthService()
