"""
Исключения для системы аутентификации v2.0
"""

from typing import Optional


class AuthenticationError(Exception):
    """Базовое исключение аутентификации"""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class TokenError(AuthenticationError):
    """Ошибки работы с токенами"""
    pass


class SecurityError(AuthenticationError):
    """Ошибки безопасности"""
    pass


class SessionError(AuthenticationError):
    """Ошибки работы с сессиями"""
    pass


class RateLimitError(SecurityError):
    """Превышен лимит запросов"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after


class InvalidCredentialsError(AuthenticationError):
    """Неверные учетные данные"""
    
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, "INVALID_CREDENTIALS")


class UserNotFoundError(AuthenticationError):
    """Пользователь не найден"""
    
    def __init__(self, message: str = "User not found"):
        super().__init__(message, "USER_NOT_FOUND")


class UserNotApprovedError(AuthenticationError):
    """Пользователь не одобрен"""
    
    def __init__(self, message: str = "User not approved"):
        super().__init__(message, "USER_NOT_APPROVED")


class SessionExpiredError(SessionError):
    """Сессия истекла"""
    
    def __init__(self, message: str = "Session expired"):
        super().__init__(message, "SESSION_EXPIRED")


class TokenExpiredError(TokenError):
    """Токен истек"""
    
    def __init__(self, message: str = "Token expired"):
        super().__init__(message, "TOKEN_EXPIRED")


class InvalidTokenError(TokenError):
    """Недействительный токен"""
    
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, "INVALID_TOKEN")
