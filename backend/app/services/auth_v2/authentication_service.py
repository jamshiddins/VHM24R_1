"""
Основной сервис аутентификации v2.0
Единая точка входа для всех типов аутентификации
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from uuid import uuid4

from .auth_models import (
    AuthResult, Session as AuthSession, SessionType, AuthMethod, AuthAttempt,
    TelegramAuthData, AdminAuthData, SessionAuthData, RefreshTokenData,
    TokenResponse, StatusResponse, UserSessionInfo
)
from .token_manager import TokenManager
from .security_service import SecurityService
from .exceptions import (
    AuthenticationError, InvalidCredentialsError, UserNotFoundError,
    UserNotApprovedError, SessionExpiredError, TokenExpiredError,
    InvalidTokenError, RateLimitError, TokenError
)

# Импорты из существующей системы (будет заменено позже)
from ... import crud, models


class AuthenticationService:
    """Единый сервис аутентификации для всех типов входа"""
    
    def __init__(self):
        self.token_manager = TokenManager()
        self.security_service = SecurityService()
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        # Временные настройки для совместимости
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_password_hash = None  # Будет установлен при первом запуске
        
    async def _get_user_data(self, user: models.User) -> Dict[str, Any]:
        """Формирует данные пользователя для ответа"""
        return {
            "id": getattr(user, 'id', 0),
            "telegram_id": str(getattr(user, 'telegram_id', '')),
            "username": getattr(user, 'username', None),
            "first_name": getattr(user, 'first_name', None),
            "last_name": getattr(user, 'last_name', None),
            "personal_link": str(getattr(user, 'personal_link', '')),
            "status": "approved" if getattr(user, 'is_approved', False) else "pending",
            "role": "admin" if getattr(user, 'is_admin', False) else "user",
            "created_at": getattr(user, 'created_at', datetime.now()),
            "last_active": getattr(user, 'last_active', None)
        }
    
    async def _check_user_permissions(self, user: models.User, require_admin: bool = False) -> None:
        """Проверяет права пользователя"""
        is_approved = getattr(user, 'is_approved', False)
        is_admin = getattr(user, 'is_admin', False)
        
        if not is_approved and not is_admin:
            raise UserNotApprovedError("Пользователь не одобрен")
        
        if require_admin and not is_admin:
            raise InvalidCredentialsError("Требуются права администратора")
    
    async def _create_session(
        self,
        user_id: int,
        session_type: SessionType,
        db: Session,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Создает новую сессию пользователя"""
        session_id = await self.security_service.generate_secure_session_id()
        
        # Создаем запись в БД (используя существующую таблицу TelegramSession)
        expires_at = datetime.utcnow() + timedelta(hours=8 if session_type == SessionType.ADMIN else 2)
        
        session_data = models.TelegramSession(
            telegram_id=user_id,  # Используем user_id как telegram_id для совместимости
            session_token=session_id,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(session_data)
        db.commit()
        
        return session_id
    
    async def _log_auth_attempt(
        self,
        method: AuthMethod,
        success: bool,
        user_id: Optional[int] = None,
        telegram_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Логирует попытку аутентификации"""
        attempt = AuthAttempt(
            user_id=user_id,
            method=method,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
            timestamp=datetime.utcnow(),
            session_id=session_id,
            telegram_id=telegram_id
        )
        
        await self.security_service.log_auth_attempt(attempt)
    
    async def authenticate_telegram(
        self,
        auth_data: TelegramAuthData,
        db: Session,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """Аутентифицирует пользователя через Telegram"""
        
        identifier = ip_address or str(auth_data.id)
        
        try:
            # Проверяем rate limiting
            await self.security_service.check_rate_limit(identifier, "telegram_auth")
            
            # Проверяем наличие токена бота
            if not self.telegram_bot_token:
                await self._log_auth_attempt(
                    AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Telegram bot token не настроен"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Сервис временно недоступен",
                    error_code="SERVICE_UNAVAILABLE"
                )
            
            # Валидируем данные от Telegram
            if not await self.security_service.validate_telegram_data(auth_data, self.telegram_bot_token):
                await self._log_auth_attempt(
                    AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Недействительные данные Telegram"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Недействительные данные Telegram",
                    error_code="INVALID_TELEGRAM_DATA"
                )
            
            # Ищем или создаем пользователя
            user = crud.get_user_by_telegram_id(db, auth_data.id)
            
            if not user:
                user_data = {
                    'telegram_id': auth_data.id,
                    'username': auth_data.username,
                    'first_name': auth_data.first_name,
                    'last_name': auth_data.last_name
                }
                user = crud.create_user(db, user_data)
            
            if not user:
                await self._log_auth_attempt(
                    AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Ошибка создания пользователя"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Ошибка создания пользователя",
                    error_code="USER_CREATION_ERROR"
                )
            
            # Проверяем права пользователя
            await self._check_user_permissions(user)
            
            # Создаем сессию
            user_id = getattr(user, 'id')
            session_id = await self._create_session(
                user_id, SessionType.TELEGRAM, db, user_agent, ip_address
            )
            
            # Создаем токены
            permissions = ["read", "write"] if getattr(user, 'is_admin', False) else ["read"]
            token_response = self.token_manager.create_token_pair(
                user_id=user_id,
                session_id=session_id,
                permissions=permissions,
                telegram_id=auth_data.id,
                username=auth_data.username,
                role="admin" if getattr(user, 'is_admin', False) else "user"
            )
            
            # Логируем успешную попытку
            await self._log_auth_attempt(
                AuthMethod.TELEGRAM, True, user_id=user_id,
                telegram_id=auth_data.id, ip_address=ip_address,
                user_agent=user_agent, session_id=session_id
            )
            
            # Формируем ответ
            user_data = await self._get_user_data(user)
            
            return AuthResult(
                success=True,
                user=user_data,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                session_id=session_id,
                expires_at=token_response.expires_at
            )
            
        except RateLimitError as e:
            await self._log_auth_attempt(
                AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                ip_address=ip_address, user_agent=user_agent,
                error_message=str(e)
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message=str(e),
                error_code="RATE_LIMIT_EXCEEDED"
            )
        except UserNotApprovedError as e:
            await self._log_auth_attempt(
                AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                ip_address=ip_address, user_agent=user_agent,
                error_message=str(e)
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message=str(e),
                error_code="USER_NOT_APPROVED"
            )
        except Exception as e:
            await self._log_auth_attempt(
                AuthMethod.TELEGRAM, False, telegram_id=auth_data.id,
                ip_address=ip_address, user_agent=user_agent,
                error_message=f"Неожиданная ошибка: {str(e)}"
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message="Внутренняя ошибка сервера",
                error_code="INTERNAL_ERROR"
            )

    async def authenticate_admin(
        self,
        auth_data: AdminAuthData,
        db: Session,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """Аутентифицирует администратора по логину и паролю"""
        
        identifier = ip_address or auth_data.username
        
        try:
            # Проверяем rate limiting
            await self.security_service.check_rate_limit(identifier, "admin_auth")
            
            # Временная реализация для совместимости с существующим кодом
            if auth_data.username == self.admin_username and auth_data.password == "admin123":
                # Ищем или создаем admin пользователя
                admin_user = crud.get_user_by_telegram_id(db, 999999999)  # Фиктивный telegram_id для admin
                
                if not admin_user:
                    # Создаем admin пользователя если не существует
                    admin_user_data = {
                        'telegram_id': 999999999,
                        'username': "admin",
                        'first_name': "Administrator",
                        'status': "approved",
                        'role': "admin",
                        'personal_link': "admin_direct_access"
                    }
                    admin_user = crud.create_user(db, admin_user_data)
                
                if not admin_user:
                    await self._log_auth_attempt(
                        AuthMethod.ADMIN_PASSWORD, False,
                        ip_address=ip_address, user_agent=user_agent,
                        error_message="Ошибка создания admin пользователя"
                    )
                    return AuthResult(
                        success=False,
                        user=None,
                        access_token=None,
                        refresh_token=None,
                        session_id=None,
                        expires_at=None,
                        error_message="Внутренняя ошибка сервера",
                        error_code="INTERNAL_ERROR"
                    )
                
                # Создаем сессию
                user_id = getattr(admin_user, 'id')
                session_id = await self._create_session(
                    user_id, SessionType.ADMIN, db, user_agent, ip_address
                )
                
                # Создаем токены
                token_response = self.token_manager.create_token_pair(
                    user_id=user_id,
                    session_id=session_id,
                    permissions=["read", "write", "admin"],
                    username="admin",
                    role="admin"
                )
                
                # Логируем успешную попытку
                await self._log_auth_attempt(
                    AuthMethod.ADMIN_PASSWORD, True, user_id=user_id,
                    ip_address=ip_address, user_agent=user_agent, session_id=session_id
                )
                
                # Формируем ответ
                user_data = await self._get_user_data(admin_user)
                
                return AuthResult(
                    success=True,
                    user=user_data,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    session_id=session_id,
                    expires_at=token_response.expires_at
                )
            else:
                await self._log_auth_attempt(
                    AuthMethod.ADMIN_PASSWORD, False,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Неверные учетные данные администратора"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Неверные учетные данные",
                    error_code="INVALID_CREDENTIALS"
                )
                
        except RateLimitError as e:
            await self._log_auth_attempt(
                AuthMethod.ADMIN_PASSWORD, False,
                ip_address=ip_address, user_agent=user_agent,
                error_message=str(e)
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message=str(e),
                error_code="RATE_LIMIT_EXCEEDED"
            )
        except Exception as e:
            await self._log_auth_attempt(
                AuthMethod.ADMIN_PASSWORD, False,
                ip_address=ip_address, user_agent=user_agent,
                error_message=f"Неожиданная ошибка: {str(e)}"
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message="Внутренняя ошибка сервера",
                error_code="INTERNAL_ERROR"
            )

    async def authenticate_session(
        self,
        auth_data: SessionAuthData,
        db: Session,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """Аутентифицирует пользователя по токену сессии"""
        
        identifier = ip_address or "session_auth"
        
        try:
            # Проверяем rate limiting
            await self.security_service.check_rate_limit(identifier, "session_auth")
            
            # Ищем сессию в БД (используем существующую функцию)
            session = crud.get_session_by_token(db, auth_data.session_token)
            
            if not session or not getattr(session, 'is_active', True):
                await self._log_auth_attempt(
                    AuthMethod.SESSION_TOKEN, False,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Недействительная сессия"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Недействительная сессия",
                    error_code="INVALID_SESSION"
                )
            
            # Проверяем истечение сессии
            if getattr(session, 'expires_at') < datetime.utcnow():
                await self._log_auth_attempt(
                    AuthMethod.SESSION_TOKEN, False,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Сессия истекла"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Сессия истекла",
                    error_code="SESSION_EXPIRED"
                )
            
            # Получаем пользователя
            user_id = getattr(session, 'telegram_id')  # Используем telegram_id как user_id
            user = crud.get_user_by_telegram_id(db, user_id)
            
            if not user:
                await self._log_auth_attempt(
                    AuthMethod.SESSION_TOKEN, False, user_id=user_id,
                    ip_address=ip_address, user_agent=user_agent,
                    error_message="Пользователь не найден"
                )
                return AuthResult(
                    success=False,
                    user=None,
                    access_token=None,
                    refresh_token=None,
                    session_id=None,
                    expires_at=None,
                    error_message="Пользователь не найден",
                    error_code="USER_NOT_FOUND"
                )
            
            # Проверяем права пользователя
            await self._check_user_permissions(user)
            
            # Создаем новые токены
            permissions = ["read", "write"] if getattr(user, 'is_admin', False) else ["read"]
            token_response = self.token_manager.create_token_pair(
                user_id=getattr(user, 'id'),
                session_id=auth_data.session_token,
                permissions=permissions,
                telegram_id=getattr(user, 'telegram_id'),
                username=getattr(user, 'username'),
                role="admin" if getattr(user, 'is_admin', False) else "user"
            )
            
            # Логируем успешную попытку
            await self._log_auth_attempt(
                AuthMethod.SESSION_TOKEN, True, user_id=getattr(user, 'id'),
                ip_address=ip_address, user_agent=user_agent, 
                session_id=auth_data.session_token
            )
            
            # Формируем ответ
            user_data = await self._get_user_data(user)
            
            return AuthResult(
                success=True,
                user=user_data,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                session_id=auth_data.session_token,
                expires_at=token_response.expires_at
            )
            
        except RateLimitError as e:
            await self._log_auth_attempt(
                AuthMethod.SESSION_TOKEN, False,
                ip_address=ip_address, user_agent=user_agent,
                error_message=str(e)
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message=str(e),
                error_code="RATE_LIMIT_EXCEEDED"
            )
        except (UserNotApprovedError, UserNotFoundError) as e:
            await self._log_auth_attempt(
                AuthMethod.SESSION_TOKEN, False,
                ip_address=ip_address, user_agent=user_agent,
                error_message=str(e)
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message=str(e),
                error_code="USER_NOT_APPROVED" if isinstance(e, UserNotApprovedError) else "USER_NOT_FOUND"
            )
        except Exception as e:
            await self._log_auth_attempt(
                AuthMethod.SESSION_TOKEN, False,
                ip_address=ip_address, user_agent=user_agent,
                error_message=f"Неожиданная ошибка: {str(e)}"
            )
            return AuthResult(
                success=False,
                user=None,
                access_token=None,
                refresh_token=None,
                session_id=None,
                expires_at=None,
                error_message="Внутренняя ошибка сервера",
                error_code="INTERNAL_ERROR"
            )

    async def refresh_token(
        self,
        refresh_data: RefreshTokenData,
        db: Session
    ) -> TokenResponse:
        """Обновляет access токен используя refresh токен"""
        
        try:
            # Валидируем refresh токен
            return self.token_manager.refresh_access_token(refresh_data.refresh_token)
            
        except (TokenExpiredError, InvalidTokenError) as e:
            raise e
        except Exception as e:
            raise TokenError(f"Ошибка обновления токена: {str(e)}")

    async def logout(
        self,
        session_id: str,
        db: Session,
        revoke_all_sessions: bool = False
    ) -> StatusResponse:
        """Завершает сессию пользователя"""
        
        try:
            if revoke_all_sessions:
                # Получаем пользователя по сессии
                session = crud.get_session_by_token(db, session_id)
                if session:
                    user_id = getattr(session, 'telegram_id')
                    crud.deactivate_user_sessions(db, user_id)
                    message = "Все сессии завершены"
                else:
                    message = "Сессия не найдена"
            else:
                # Деактивируем конкретную сессию
                crud.deactivate_session(db, session_id)
                message = "Сессия завершена"
            
            return StatusResponse(
                success=True,
                message=message
            )
            
        except Exception as e:
            return StatusResponse(
                success=False,
                message=f"Ошибка завершения сессии: {str(e)}",
                code="LOGOUT_ERROR"
            )

    async def validate_access_token(
        self,
        token: str,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Валидирует access токен и возвращает данные пользователя"""
        
        try:
            # Валидируем токен
            payload = self.token_manager.validate_token(token)
            
            # Проверяем сессию в БД
            session = crud.get_session_by_token(db, payload.session_id)
            if not session or not getattr(session, 'is_active', True):
                return None
            
            # Получаем пользователя
            user = crud.get_user_by_telegram_id(db, payload.user_id)
            if not user:
                return None
            
            # Проверяем права пользователя
            await self._check_user_permissions(user)
            
            # Возвращаем данные пользователя
            return await self._get_user_data(user)
            
        except Exception:
            return None

    async def get_user_sessions(
        self,
        user_id: int,
        db: Session
    ) -> List[UserSessionInfo]:
        """Получает список активных сессий пользователя"""
        
        try:
            sessions = crud.get_user_sessions(db, user_id)
            
            session_info_list = []
            for session in sessions:
                if getattr(session, 'is_active', True):
                    session_info = UserSessionInfo(
                        session_id=getattr(session, 'session_token'),
                        session_type=SessionType.TELEGRAM,  # По умолчанию
                        created_at=getattr(session, 'created_at', datetime.utcnow()),
                        last_activity=getattr(session, 'last_activity', datetime.utcnow()),
                        is_current=True,  # Можно добавить логику определения текущей сессии
                        user_agent=None,
                        ip_address=None
                    )
                    session_info_list.append(session_info)
            
            return session_info_list
            
        except Exception:
            return []
