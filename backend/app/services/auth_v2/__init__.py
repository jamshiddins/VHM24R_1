"""
Новая система аутентификации VHM24R v2.0
Единый сервис для всех типов аутентификации
"""

from .authentication_service import AuthenticationService
from .token_manager import TokenManager
from .security_service import SecurityService
from .auth_models import AuthResult, Session, TokenPayload, SessionType
from .exceptions import AuthenticationError, SecurityError, TokenError

__all__ = [
    'AuthenticationService',
    'TokenManager', 
    'SecurityService',
    'AuthResult',
    'Session',
    'TokenPayload',
    'SessionType',
    'AuthenticationError',
    'SecurityError', 
    'TokenError'
]
