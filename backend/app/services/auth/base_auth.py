"""
Базовый абстрактный класс для всех сервисов аутентификации VHM24R
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ...utils.logger import get_logger
from ...utils.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)


class AuthStatus(Enum):
    """Статусы результата аутентификации"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass
class AuthResult:
    """Результат операции аутентификации"""
    status: AuthStatus
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    
    @property
    def is_success(self) -> bool:
        """Проверка успешности аутентификации"""
        return self.status == AuthStatus.SUCCESS
    
    @property 
    def is_expired(self) -> bool:
        """Проверка истечения срока действия"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для API ответа"""
        result = {
            "status": self.status.value,
            "success": self.is_success
        }
        
        if self.access_token:
            result["access_token"] = self.access_token
            result["token_type"] = "bearer"
            
        if self.refresh_token:
            result["refresh_token"] = self.refresh_token
            
        if self.user_info:
            result["user"] = self.user_info
            
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
            result["expires_in"] = int((self.expires_at - datetime.utcnow()).total_seconds())
            
        if self.error_message:
            result["error"] = self.error_message
            
        if self.additional_data:
            result.update(self.additional_data)
            
        return result


@dataclass
class AuthCredentials:
    """Базовый класс для учетных данных"""
    auth_type: str
    data: Dict[str, Any]
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения из данных"""
        return self.data.get(key, default)
    
    def validate(self) -> bool:
        """Валидация учетных данных"""
        return bool(self.data)


class BaseAuthService(ABC):
    """
    Базовый абстрактный класс для всех сервисов аутентификации
    
    Определяет общий интерфейс и базовую функциональность
    для всех типов аутентификации в системе VHM24R
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = get_logger(f"{__name__}.{service_name}")
        
    @abstractmethod
    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Основной метод аутентификации
        
        Args:
            credentials: Учетные данные для аутентификации
            
        Returns:
            AuthResult: Результат аутентификации
            
        Raises:
            AuthenticationError: При ошибке аутентификации
            ValidationError: При невалидных данных
        """
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> AuthResult:
        """
        Валидация токена доступа
        
        Args:
            token: Токен для проверки
            
        Returns:
            AuthResult: Результат валидации
        """
        pass
    
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """
        Обновление токена доступа
        
        Args:
            refresh_token: Токен обновления
            
        Returns:
            AuthResult: Новый токен или ошибка
        """
        # Базовая реализация - можно переопределить в наследниках
        return AuthResult(
            status=AuthStatus.FAILED,
            error_message="Token refresh not supported by this auth service"
        )
    
    async def logout(self, token: str) -> bool:
        """
        Выход из системы / инвалидация токена
        
        Args:
            token: Токен для инвалидации
            
        Returns:
            bool: Успешность операции
        """
        # Базовая реализация - можно переопределить в наследниках
        self.logger.info(f"Logout requested for service {self.service_name}")
        return True
    
    def _create_success_result(
        self,
        access_token: str,
        user_info: Dict[str, Any],
        refresh_token: Optional[str] = None,
        expires_in: int = 3600,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Создание успешного результата аутентификации
        
        Args:
            access_token: Токен доступа
            user_info: Информация о пользователе
            refresh_token: Токен обновления (опционально)
            expires_in: Время жизни токена в секундах
            additional_data: Дополнительные данные
            
        Returns:
            AuthResult: Результат аутентификации
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return AuthResult(
            status=AuthStatus.SUCCESS,
            access_token=access_token,
            refresh_token=refresh_token,
            user_info=user_info,
            expires_at=expires_at,
            additional_data=additional_data or {}
        )
    
    def _create_error_result(
        self,
        error_message: str,
        status: AuthStatus = AuthStatus.FAILED,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> AuthResult:
        """
        Создание результата с ошибкой
        
        Args:
            error_message: Сообщение об ошибке
            status: Статус результата
            additional_data: Дополнительные данные
            
        Returns:
            AuthResult: Результат с ошибкой
        """
        return AuthResult(
            status=status,
            error_message=error_message,
            additional_data=additional_data or {}
        )
    
    def _validate_credentials(self, credentials: AuthCredentials) -> None:
        """
        Базовая валидация учетных данных
        
        Args:
            credentials: Учетные данные для проверки
            
        Raises:
            ValidationError: При невалидных данных
        """
        if not credentials:
            raise ValidationError("Credentials are required")
        
        if not credentials.validate():
            raise ValidationError("Invalid credentials format")
        
        self.logger.info(
            f"Credentials validated for {self.service_name}",
            auth_type=credentials.auth_type
        )
    
    def _log_auth_attempt(
        self,
        credentials: AuthCredentials,
        result: AuthResult,
        user_id: Optional[Union[int, str]] = None
    ) -> None:
        """
        Логирование попытки аутентификации
        
        Args:
            credentials: Учетные данные
            result: Результат аутентификации
            user_id: ID пользователя (опционально)
        """
        self.logger.info(
            f"Authentication attempt for {self.service_name}",
            auth_type=credentials.auth_type,
            status=result.status.value,
            user_id=user_id,
            success=result.is_success,
            service=self.service_name
        )
        
        if not result.is_success:
            self.logger.warning(
                f"Authentication failed for {self.service_name}",
                error=result.error_message,
                auth_type=credentials.auth_type
            )


class TokenBasedAuthService(BaseAuthService):
    """
    Базовый класс для сервисов аутентификации на основе токенов
    """
    
    def __init__(self, service_name: str, token_lifetime: int = 3600):
        super().__init__(service_name)
        self.token_lifetime = token_lifetime
    
    @abstractmethod
    def _generate_token(self, user_data: Dict[str, Any]) -> str:
        """Генерация токена для пользователя"""
        pass
    
    @abstractmethod
    def _decode_token(self, token: str) -> Dict[str, Any]:
        """Декодирование токена"""
        pass
    
    def _is_token_expired(self, token_data: Dict[str, Any]) -> bool:
        """Проверка истечения срока действия токена"""
        if 'exp' not in token_data:
            return True
            
        exp_timestamp = token_data['exp']
        return datetime.utcnow().timestamp() > exp_timestamp
