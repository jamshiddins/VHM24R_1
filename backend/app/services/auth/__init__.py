"""
Унифицированная система аутентификации VHM24R

Этот пакет содержит все компоненты системы аутентификации:
- BaseAuthService - базовый абстрактный класс
- JWTService - управление JWT токенами  
- TelegramAuthService - аутентификация через Telegram
- SessionAuthService - управление сессиями
"""

from .base_auth import BaseAuthService, AuthResult, AuthStatus, AuthCredentials
from .jwt_auth import JWTService, JWTCredentials
from .telegram_auth import TelegramAuthService, TelegramCredentials
from .session_auth import SessionAuthService, SessionCredentials

__all__ = [
    'BaseAuthService',
    'AuthResult',
    'AuthStatus',
    'AuthCredentials',
    'JWTService',
    'JWTCredentials',
    'TelegramAuthService',
    'TelegramCredentials',
    'SessionAuthService',
    'SessionCredentials'
]

# Версия API аутентификации
AUTH_API_VERSION = "2.0"

# Экспортируем основные сервисы для удобства импорта
jwt_service = JWTService()
telegram_auth_service = TelegramAuthService()
session_auth_service = SessionAuthService()
