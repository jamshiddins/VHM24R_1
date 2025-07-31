"""
Унифицированная система аутентификации VHM24R

Этот пакет содержит все компоненты системы аутентификации:
- BaseAuthService - базовый абстрактный класс
- JWTService - управление JWT токенами  
- TelegramAuthService - аутентификация через Telegram
- SessionAuthService - управление сессиями
"""

from .base_auth import BaseAuthService, AuthResult
from .jwt_auth import JWTService
from .telegram_auth import TelegramAuthService
from .session_auth import SessionAuthService

__all__ = [
    'BaseAuthService',
    'AuthResult', 
    'JWTService',
    'TelegramAuthService',
    'SessionAuthService'
]

# Версия API аутентификации
AUTH_API_VERSION = "2.0"

# Экспортируем основные сервисы для удобства импорта
jwt_service = JWTService()
telegram_auth_service = TelegramAuthService()
session_auth_service = SessionAuthService()
