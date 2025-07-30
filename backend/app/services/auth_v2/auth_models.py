"""
Модели данных для системы аутентификации v2.0
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID


class SessionType(Enum):
    """Типы сессий"""
    TELEGRAM = "telegram"
    ADMIN = "admin"
    WEB = "web"
    API = "api"


class TokenType(Enum):
    """Типы токенов"""
    ACCESS = "access"
    REFRESH = "refresh"
    SESSION = "session"


class AuthMethod(Enum):
    """Методы аутентификации"""
    TELEGRAM = "telegram"
    ADMIN_PASSWORD = "admin_password"
    SESSION_TOKEN = "session_token"
    DYNAMIC_LINK = "dynamic_link"


@dataclass
class TokenPayload:
    """Данные JWT токена"""
    user_id: int
    session_id: str
    token_type: TokenType
    issued_at: datetime
    expires_at: datetime
    permissions: List[str]
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


@dataclass
class Session:
    """Сессия пользователя"""
    id: str
    user_id: int
    session_type: SessionType
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    is_active: bool
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    access_token_hash: Optional[str] = None
    refresh_token_hash: Optional[str] = None


@dataclass
class AuthResult:
    """Результат аутентификации"""
    success: bool
    user: Optional[Dict[str, Any]]
    access_token: Optional[str]
    refresh_token: Optional[str]
    session_id: Optional[str]
    expires_at: Optional[datetime]
    error_message: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class AuthAttempt:
    """Попытка аутентификации для логирования"""
    user_id: Optional[int]
    method: AuthMethod
    success: bool
    ip_address: Optional[str]
    user_agent: Optional[str]
    error_message: Optional[str]
    timestamp: datetime
    session_id: Optional[str] = None
    telegram_id: Optional[int] = None


@dataclass
class TelegramAuthData:
    """Данные аутентификации от Telegram"""
    id: int
    first_name: str
    auth_date: int
    hash: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None


@dataclass
class AdminAuthData:
    """Данные административной аутентификации"""
    username: str
    password: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class SessionAuthData:
    """Данные аутентификации по токену сессии"""
    session_token: str
    password: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class RefreshTokenData:
    """Данные для обновления токена"""
    refresh_token: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class TokenResponse:
    """Ответ с новыми токенами"""
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    token_type: str = "bearer"


@dataclass
class StatusResponse:
    """Статусный ответ"""
    success: bool
    message: str
    code: Optional[str] = None


@dataclass
class UserSessionInfo:
    """Информация о сессии пользователя"""
    session_id: str
    session_type: SessionType
    created_at: datetime
    last_activity: datetime
    is_current: bool
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class SecurityContext:
    """Контекст безопасности"""
    user_id: int
    session_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    permissions: List[str]
    rate_limit_key: str
    created_at: datetime
