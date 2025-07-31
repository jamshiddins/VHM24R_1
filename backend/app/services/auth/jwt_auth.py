"""
Унифицированный сервис для работы с JWT токенами в VHM24R
"""

import jwt
import os
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta

from .base_auth import TokenBasedAuthService, AuthResult, AuthStatus, AuthCredentials
from ...utils.logger import get_logger
from ...utils.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)


class JWTCredentials(AuthCredentials):
    """Учетные данные для JWT аутентификации"""
    
    def __init__(self, user_data: Dict[str, Any]):
        super().__init__("jwt", user_data)
        
    def validate(self) -> bool:
        """Валидация данных пользователя для JWT"""
        required_fields = ['user_id']
        return all(self.data.get(field) for field in required_fields)


class JWTService(TokenBasedAuthService):
    """
    Унифицированный сервис для работы с JWT токенами
    
    Предоставляет единую логику для:
    - Создания JWT токенов
    - Валидации токенов  
    - Обновления токенов
    - Извлечения данных из токенов
    """
    
    def __init__(self):
        super().__init__("JWT", token_lifetime=1800)  # 30 минут по умолчанию
        
        # Загружаем настройки из переменных окружения
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        
        # Для тестов используем более длительные токены
        if os.getenv("TESTING") == "true":
            self.access_token_lifetime = 3600  # 1 час для тестов
            self.refresh_token_lifetime = 86400  # 24 часа для тестов
        else:
            self.access_token_lifetime = int(os.getenv("JWT_ACCESS_LIFETIME", "1800"))  # 30 мин
            self.refresh_token_lifetime = int(os.getenv("JWT_REFRESH_LIFETIME", "604800"))  # 7 дней
        
        if self.secret_key == "your-secret-key-here":
            logger.warning("Using default JWT secret key - change it in production!")
    
    async def authenticate(self, credentials: JWTCredentials) -> AuthResult:
        """
        Создание JWT токена для пользователя
        
        Args:
            credentials: Данные пользователя для токена
            
        Returns:
            AuthResult: JWT токены и информация о пользователе
        """
        try:
            self._validate_credentials(credentials)
            
            # Извлекаем данные пользователя
            user_data = credentials.data
            user_id = user_data.get('user_id')
            
            # Создаем access токен
            access_token = self.create_access_token(user_data)
            
            # Создаем refresh токен  
            refresh_token = self.create_refresh_token(user_data)
            
            # Формируем информацию о пользователе для ответа
            user_info = {
                "id": user_id,
                "username": user_data.get('username'),
                "role": user_data.get('role', 'user'),
                "status": user_data.get('status', 'active')
            }
            
            result = self._create_success_result(
                access_token=access_token,
                refresh_token=refresh_token,
                user_info=user_info,
                expires_in=self.access_token_lifetime
            )
            
            self._log_auth_attempt(credentials, result, user_id)
            
            logger.info(
                "JWT tokens created successfully",
                user_id=user_id,
                username=user_data.get('username')
            )
            
            return result
            
        except ValidationError as e:
            result = self._create_error_result(str(e), AuthStatus.FAILED)
            self._log_auth_attempt(credentials, result)
            return result
            
        except Exception as e:
            logger.error("JWT token creation failed", error=str(e))
            result = self._create_error_result(
                "Failed to create authentication tokens",
                AuthStatus.FAILED
            )
            self._log_auth_attempt(credentials, result)
            return result
    
    async def validate_token(self, token: str) -> AuthResult:
        """
        Валидация JWT токена
        
        Args:
            token: JWT токен для проверки
            
        Returns:
            AuthResult: Результат валидации с данными пользователя
        """
        try:
            if not token:
                return self._create_error_result("Token is required")
            
            # Декодируем токен
            payload = self._decode_token(token)
            
            # Проверяем срок действия
            if self._is_token_expired(payload):
                return self._create_error_result(
                    "Token has expired",
                    AuthStatus.EXPIRED
                )
            
            # Извлекаем данные пользователя
            user_info = {
                "id": payload.get('user_id'),  
                "username": payload.get('username'),
                "role": payload.get('role', 'user'),
                "status": payload.get('status', 'active'),
                "telegram_id": payload.get('telegram_id')
            }
            
            result = AuthResult(
                status=AuthStatus.SUCCESS,
                user_info=user_info,
                expires_at=datetime.fromtimestamp(payload.get('exp', 0))
            )
            
            logger.info(
                "JWT token validated successfully",
                user_id=user_info.get('id'),
                token_type=payload.get('type', 'access')
            )
            
            return result
            
        except jwt.ExpiredSignatureError:
            logger.warning("Expired JWT token validation attempt")
            return self._create_error_result("Token has expired", AuthStatus.EXPIRED)
            
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token validation attempt", error=str(e))
            return self._create_error_result("Invalid token", AuthStatus.FAILED)
            
        except Exception as e:
            logger.error("JWT token validation failed", error=str(e))
            return self._create_error_result("Token validation failed", AuthStatus.FAILED)
    
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """
        Обновление access токена используя refresh токен
        
        Args:
            refresh_token: Refresh токен
            
        Returns:
            AuthResult: Новые токены или ошибка
        """
        try:
            if not refresh_token:
                return self._create_error_result("Refresh token is required")
            
            # Декодируем refresh токен
            payload = self._decode_token(refresh_token)
            
            # Проверяем тип токена
            if payload.get('type') != 'refresh':
                return self._create_error_result("Invalid refresh token")
            
            # Проверяем срок действия
            if self._is_token_expired(payload):
                return self._create_error_result(
                    "Refresh token has expired",
                    AuthStatus.EXPIRED  
                )
            
            # Создаем новые токены с небольшой задержкой для уникальности
            import time
            time.sleep(0.001)  # 1 миллисекунда чтобы токены отличались
            
            user_data = {
                'user_id': payload.get('user_id'),
                'username': payload.get('username'),
                'role': payload.get('role'),
                'status': payload.get('status'),
                'telegram_id': payload.get('telegram_id')
            }
            
            new_access_token = self.create_access_token(user_data)
            new_refresh_token = self.create_refresh_token(user_data)
            
            user_info = {
                "id": payload.get('user_id'),
                "username": payload.get('username'),
                "role": payload.get('role', 'user'),
                "status": payload.get('status', 'active')
            }
            
            result = self._create_success_result(
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                user_info=user_info,
                expires_in=self.access_token_lifetime
            )
            
            logger.info(
                "JWT tokens refreshed successfully",
                user_id=payload.get('user_id')
            )
            
            return result
            
        except jwt.ExpiredSignatureError:
            return self._create_error_result(
                "Refresh token has expired",
                AuthStatus.EXPIRED
            )
            
        except jwt.InvalidTokenError:
            return self._create_error_result("Invalid refresh token")
            
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            return self._create_error_result("Failed to refresh token")
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """
        Создание access токена
        
        Args:
            user_data: Данные пользователя
            
        Returns:
            str: JWT access токен
        """
        import time
        now_timestamp = time.time()
        expires_timestamp = now_timestamp + self.access_token_lifetime
        
        payload = {
            'user_id': user_data.get('user_id'),
            'username': user_data.get('username'),
            'role': user_data.get('role', 'user'),
            'status': user_data.get('status', 'active'),
            'telegram_id': user_data.get('telegram_id'),
            'type': 'access',
            'iat': now_timestamp,
            'exp': expires_timestamp,
            'nbf': now_timestamp
        }
        
        return self._generate_token(payload)
    
    def create_refresh_token(self, user_data: Dict[str, Any]) -> str:
        """
        Создание refresh токена
        
        Args:
            user_data: Данные пользователя
            
        Returns:
            str: JWT refresh токен
        """
        import time
        now_timestamp = time.time()
        expires_timestamp = now_timestamp + self.refresh_token_lifetime
        
        payload = {
            'user_id': user_data.get('user_id'),
            'username': user_data.get('username'),
            'role': user_data.get('role', 'user'),
            'status': user_data.get('status', 'active'),
            'telegram_id': user_data.get('telegram_id'),
            'type': 'refresh',
            'iat': now_timestamp,
            'exp': expires_timestamp,
            'nbf': now_timestamp
        }
        
        return self._generate_token(payload)
    
    def _generate_token(self, payload: Dict[str, Any]) -> str:
        """
        Генерация JWT токена
        
        Args:
            payload: Данные для токена
            
        Returns:
            str: JWT токен
        """
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _decode_token(self, token: str) -> Dict[str, Any]:
        """
        Декодирование JWT токена
        
        Args:
            token: JWT токен
            
        Returns:
            Dict[str, Any]: Данные из токена
            
        Raises:
            jwt.InvalidTokenError: При ошибке декодирования
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
    
    def _is_token_expired(self, payload: Dict[str, Any]) -> bool:
        """
        Проверка истечения срока действия токена
        
        Args:
            payload: Декодированные данные токена
            
        Returns:
            bool: True если токен истек
        """
        exp_timestamp = payload.get('exp')
        if not exp_timestamp:
            return True  # Токен без времени истечения считается истекшим
        
        expiry_time = datetime.fromtimestamp(exp_timestamp)
        return datetime.utcnow() >= expiry_time
    
    def extract_user_id(self, token: str) -> Optional[int]:
        """
        Извлечение user_id из токена без валидации срока действия
        
        Args:
            token: JWT токен
            
        Returns:
            Optional[int]: ID пользователя или None
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # Игнорируем срок действия
            )
            return payload.get('user_id')
        except jwt.InvalidTokenError:
            return None
    
    def is_token_valid_format(self, token: str) -> bool:
        """
        Проверка формата токена без валидации срока действия
        
        Args:
            token: JWT токен
            
        Returns:
            bool: True если формат валидный
        """
        try:
            jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False, "verify_nbf": False}  
            )
            return True
        except jwt.InvalidTokenError:
            return False
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Получение времени истечения токена
        
        Args:
            token: JWT токен
            
        Returns:
            Optional[datetime]: Время истечения или None
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}
            )
            exp_timestamp = payload.get('exp')
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
            return None
        except jwt.InvalidTokenError:
            return None


# Глобальный экземпляр для использования в приложении
jwt_service = JWTService()
