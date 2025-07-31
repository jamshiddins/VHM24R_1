"""
Сервис управления сессиями для VHM24R
"""

import os
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .base_auth import BaseAuthService, AuthResult, AuthStatus, AuthCredentials
from ...utils.logger import get_logger
from ...utils.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)


class SessionCredentials(AuthCredentials):
    """Учетные данные для сессионной аутентификации"""
    
    def __init__(self, session_data: Dict[str, Any]):
        super().__init__("session", session_data)
        
    def validate(self) -> bool:
        """Валидация сессионных данных"""
        return bool(self.data.get('session_token') or self.data.get('session_id'))


class SessionAuthService(BaseAuthService):
    """
    Сервис управления сессиями
    
    Обеспечивает:
    - Создание и валидацию сессий
    - Управление временными токенами  
    - Очистку истекших сессий
    - Интеграцию с унифицированной auth системой
    """
    
    def __init__(self):
        super().__init__("Session")
        
        # Настройки сессий
        self.session_lifetime = int(os.getenv("SESSION_LIFETIME", "3600"))  # 1 час
        self.cleanup_interval = int(os.getenv("SESSION_CLEANUP_INTERVAL", "300"))  # 5 минут
        
        # In-memory хранилище сессий (в production лучше использовать Redis)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup = datetime.utcnow()
    
    async def authenticate(self, credentials: SessionCredentials) -> AuthResult:
        """
        Аутентификация по сессии
        
        Args:
            credentials: Данные сессии
            
        Returns:
            AuthResult: Результат аутентификации
        """
        try:
            self._validate_credentials(credentials)
            
            session_data = credentials.data
            session_token = session_data.get('session_token')
            
            if not session_token:
                result = self._create_error_result("Session token is required")
                self._log_auth_attempt(credentials, result)
                return result
            
            # Проверяем сессию
            session_info = self.get_session(session_token)
            
            if not session_info:
                result = self._create_error_result(
                    "Invalid or expired session",
                    AuthStatus.EXPIRED
                )
                self._log_auth_attempt(credentials, result)
                return result
            
            # Извлекаем информацию о пользователе
            user_info = session_info.get('user_info', {})
            
            # Успешная аутентификация
            result = AuthResult(
                status=AuthStatus.SUCCESS,
                user_info=user_info,
                expires_at=session_info.get('expires_at'),
                additional_data={'session_token': session_token}
            )
            
            self._log_auth_attempt(credentials, result, user_info.get('id'))
            
            logger.info(
                "Session authentication successful",
                session_token=session_token[:10] + "...",
                user_id=user_info.get('id')
            )
            
            return result
            
        except ValidationError as e:
            result = self._create_error_result(str(e))
            self._log_auth_attempt(credentials, result)
            return result
            
        except Exception as e:
            logger.error("Session authentication failed", error=str(e))
            result = self._create_error_result("Session authentication failed")
            self._log_auth_attempt(credentials, result)
            return result
    
    async def validate_token(self, token: str) -> AuthResult:
        """
        Валидация токена сессии
        
        Args:
            token: Токен сессии
            
        Returns:
            AuthResult: Результат валидации
        """
        session_info = self.get_session(token)
        
        if not session_info:
            return self._create_error_result(
                "Invalid or expired session",
                AuthStatus.EXPIRED
            )
        
        return AuthResult(
            status=AuthStatus.SUCCESS,
            user_info=session_info.get('user_info', {}),
            expires_at=session_info.get('expires_at')
        )
    
    def create_session(
        self,
        user_info: Dict[str, Any],
        session_data: Optional[Dict[str, Any]] = None,
        expires_in: Optional[int] = None
    ) -> str:
        """
        Создание новой сессии
        
        Args:
            user_info: Информация о пользователе
            session_data: Дополнительные данные сессии
            expires_in: Время жизни сессии в секундах
            
        Returns:
            str: Токен сессии
        """
        # Генерируем уникальный токен сессии
        session_token = self._generate_session_token()
        
        # Определяем время истечения
        expires_in = expires_in or self.session_lifetime
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Сохраняем сессию
        session_info = {
            'user_info': user_info,
            'created_at': datetime.utcnow(),
            'expires_at': expires_at,
            'data': session_data or {}
        }
        
        self._sessions[session_token] = session_info
        
        logger.info(
            "New session created",
            session_token=session_token[:10] + "...",
            user_id=user_info.get('id'),
            expires_at=expires_at.isoformat()
        )
        
        # Запускаем очистку если нужно
        self._cleanup_if_needed()
        
        return session_token
    
    def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о сессии
        
        Args:
            session_token: Токен сессии
            
        Returns:
            Optional[Dict[str, Any]]: Информация о сессии или None
        """
        self._cleanup_if_needed()
        
        session_info = self._sessions.get(session_token)
        
        if not session_info:
            return None
        
        # Проверяем срок действия
        if datetime.utcnow() > session_info['expires_at']:
            self.invalidate_session(session_token)
            return None
        
        return session_info
    
    def invalidate_session(self, session_token: str) -> bool:
        """
        Инвалидация сессии
        
        Args:
            session_token: Токен сессии
            
        Returns:
            bool: True если сессия была найдена и удалена
        """
        if session_token in self._sessions:
            user_id = self._sessions[session_token].get('user_info', {}).get('id')
            del self._sessions[session_token]
            
            logger.info(
                "Session invalidated",
                session_token=session_token[:10] + "...",
                user_id=user_id
            )
            
            return True
        
        return False
    
    def update_session(
        self,
        session_token: str,
        user_info: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        extend_expiry: bool = False
    ) -> bool:
        """
        Обновление сессии
        
        Args:
            session_token: Токен сессии
            user_info: Обновленная информация о пользователе
            session_data: Обновленные данные сессии
            extend_expiry: Продлить срок действия сессии
            
        Returns:
            bool: True если сессия была обновлена
        """
        session_info = self.get_session(session_token)
        
        if not session_info:
            return False
        
        # Обновляем данные
        if user_info:
            session_info['user_info'].update(user_info)
        
        if session_data:
            session_info['data'].update(session_data)
        
        # Продлеваем срок действия если нужно
        if extend_expiry:
            session_info['expires_at'] = datetime.utcnow() + timedelta(seconds=self.session_lifetime)
        
        self._sessions[session_token] = session_info
        
        logger.info(
            "Session updated",
            session_token=session_token[:10] + "...",
            user_id=session_info['user_info'].get('id'),
            extended=extend_expiry
        )
        
        return True
    
    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получение всех сессий пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            List[Dict[str, Any]]: Список сессий пользователя
        """
        self._cleanup_if_needed()
        
        user_sessions = []
        
        for token, session_info in self._sessions.items():
            if session_info['user_info'].get('id') == user_id:
                user_sessions.append({
                    'session_token': token[:10] + "...",  # Частично скрываем токен
                    'created_at': session_info['created_at'],
                    'expires_at': session_info['expires_at'],
                    'is_expired': datetime.utcnow() > session_info['expires_at']
                })
        
        return user_sessions
    
    def invalidate_user_sessions(self, user_id: int, exclude_token: Optional[str] = None) -> int:
        """
        Инвалидация всех сессий пользователя
        
        Args:
            user_id: ID пользователя
            exclude_token: Токен, который не нужно инвалидировать
            
        Returns:
            int: Количество инвалидированных сессий
        """
        tokens_to_remove = []
        
        for token, session_info in self._sessions.items():
            if (session_info['user_info'].get('id') == user_id and 
                token != exclude_token):
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self._sessions[token]
        
        logger.info(
            "User sessions invalidated",
            user_id=user_id,
            count=len(tokens_to_remove),
            excluded_token=exclude_token[:10] + "..." if exclude_token else None
        )
        
        return len(tokens_to_remove)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Очистка истекших сессий
        
        Returns:
            int: Количество удаленных сессий
        """
        now = datetime.utcnow()
        expired_tokens = []
        
        for token, session_info in self._sessions.items():
            if now > session_info['expires_at']:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self._sessions[token]
        
        self._last_cleanup = now
        
        if expired_tokens:
            logger.info(
                "Expired sessions cleaned up",
                count=len(expired_tokens),
                total_sessions=len(self._sessions)
            )
        
        return len(expired_tokens)
    
    def get_sessions_stats(self) -> Dict[str, Any]:
        """
        Получение статистики сессий
        
        Returns:
            Dict[str, Any]: Статистика сессий
        """
        self._cleanup_if_needed()
        
        now = datetime.utcnow()
        active_sessions = 0
        expired_sessions = 0
        
        for session_info in self._sessions.values():
            if now > session_info['expires_at']:
                expired_sessions += 1
            else:
                active_sessions += 1
        
        return {
            'total_sessions': len(self._sessions),
            'active_sessions': active_sessions,
            'expired_sessions': expired_sessions,
            'last_cleanup': self._last_cleanup.isoformat()
        }
    
    def _generate_session_token(self) -> str:
        """
        Генерация токена сессии
        
        Returns:
            str: Уникальный токен сессии
        """
        # Используем secrets для генерации криптографически стойкого токена
        random_bytes = secrets.token_bytes(32)
        timestamp = str(datetime.utcnow().timestamp())
        
        # Добавляем timestamp для уникальности
        combined = random_bytes + timestamp.encode()
        
        # Создаем hash
        token = hashlib.sha256(combined).hexdigest()
        
        return token
    
    def _cleanup_if_needed(self) -> None:
        """
        Очистка сессий если прошло достаточно времени
        """
        now = datetime.utcnow()
        time_since_cleanup = (now - self._last_cleanup).total_seconds()
        
        if time_since_cleanup >= self.cleanup_interval:
            self.cleanup_expired_sessions()


# Глобальный экземпляр для использования в приложении
session_auth_service = SessionAuthService()
