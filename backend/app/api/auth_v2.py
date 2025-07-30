"""
API эндпоинты для новой системы аутентификации v2.0
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import os

from ..database import get_db
from ..services.auth_v2 import AuthenticationService
from ..services.auth_v2.auth_models import (
    AuthResult, TokenResponse, StatusResponse,
    TelegramAuthData, AdminAuthData, SessionAuthData, RefreshTokenData,
    UserSessionInfo
)
from ..services.auth_v2.exceptions import (
    AuthenticationError, RateLimitError, TokenError,
    InvalidCredentialsError, UserNotApprovedError
)

# Инициализация
router = APIRouter(prefix="/api/v2/auth", tags=["Authentication v2.0"])
security = HTTPBearer()
auth_service = AuthenticationService()

# Pydantic модели для API
class TelegramAuthRequest(BaseModel):
    """Запрос аутентификации через Telegram"""
    id: int = Field(..., description="Telegram user ID")
    first_name: str = Field(..., description="Имя пользователя")
    auth_date: int = Field(..., description="Время аутентификации")
    hash: str = Field(..., description="Хеш для проверки")
    last_name: Optional[str] = Field(None, description="Фамилия пользователя")
    username: Optional[str] = Field(None, description="Username в Telegram")
    photo_url: Optional[str] = Field(None, description="URL фото профиля")

class AdminAuthRequest(BaseModel):
    """Запрос административной аутентификации"""
    username: str = Field(..., description="Логин администратора")
    password: str = Field(..., description="Пароль администратора")

class SessionAuthRequest(BaseModel):
    """Запрос аутентификации по токену сессии"""
    session_token: str = Field(..., description="Токен сессии")
    password: Optional[str] = Field(None, description="Дополнительный пароль")

class RefreshTokenRequest(BaseModel):
    """Запрос обновления токена"""
    refresh_token: str = Field(..., description="Refresh токен")

class LogoutRequest(BaseModel):
    """Запрос выхода из системы"""
    revoke_all_sessions: bool = Field(False, description="Завершить все сессии")

class AuthResponse(BaseModel):
    """Успешный ответ аутентификации"""
    success: bool = True
    message: str = "Аутентификация успешна"
    user: Dict[str, Any]
    tokens: Dict[str, Any]
    session_id: str
    expires_at: str

class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    success: bool = False
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None

# Вспомогательные функции
def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Получает IP адрес и User-Agent клиента"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Получает текущего пользователя из токена"""
    if not credentials:
        return None
    
    return await auth_service.validate_access_token(credentials.credentials, db)

# API Endpoints

@router.post("/telegram", response_model=AuthResponse, responses={
    400: {"model": ErrorResponse, "description": "Неверные данные"},
    401: {"model": ErrorResponse, "description": "Недействительные данные Telegram"},
    403: {"model": ErrorResponse, "description": "Пользователь не одобрен"},
    429: {"model": ErrorResponse, "description": "Превышен лимит запросов"},
    500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"}
})
async def authenticate_telegram(
    auth_data: TelegramAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    🔐 Аутентификация через Telegram
    
    Валидирует данные от Telegram и создает сессию пользователя.
    """
    try:
        ip_address, user_agent = get_client_info(request)
        
        # Преобразуем Pydantic модель в dataclass
        telegram_data = TelegramAuthData(
            id=auth_data.id,
            first_name=auth_data.first_name,
            auth_date=auth_data.auth_date,
            hash=auth_data.hash,
            last_name=auth_data.last_name,
            username=auth_data.username,
            photo_url=auth_data.photo_url
        )
        
        # Аутентифицируем
        result = await auth_service.authenticate_telegram(
            telegram_data, db, ip_address, user_agent
        )
        
        if not result.success:
            # Определяем статус код по типу ошибки
            error_code = result.error_code or "UNKNOWN_ERROR"
            status_code = {
                "INVALID_TELEGRAM_DATA": status.HTTP_401_UNAUTHORIZED,
                "USER_NOT_APPROVED": status.HTTP_403_FORBIDDEN,
                "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
                "SERVICE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
                "USER_CREATION_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }.get(error_code, status.HTTP_400_BAD_REQUEST)
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.error_message or "Неизвестная ошибка",
                    "error_code": error_code
                }
            )
        
        # Формируем успешный ответ
        return {
            "success": True,
            "message": "Аутентификация через Telegram успешна",
            "user": result.user,
            "tokens": {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": "bearer"
            },
            "session_id": result.session_id,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.post("/admin", response_model=AuthResponse)
async def authenticate_admin(
    auth_data: AdminAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    🔑 Административная аутентификация
    
    Аутентифицирует администратора по логину и паролю.
    """
    try:
        ip_address, user_agent = get_client_info(request)
        
        admin_data = AdminAuthData(
            username=auth_data.username,
            password=auth_data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        result = await auth_service.authenticate_admin(
            admin_data, db, ip_address, user_agent
        )
        
        if not result.success:
            error_code = result.error_code or "UNKNOWN_ERROR"
            status_code = {
                "INVALID_CREDENTIALS": status.HTTP_401_UNAUTHORIZED,
                "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
                "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }.get(error_code, status.HTTP_400_BAD_REQUEST)
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.error_message or "Неизвестная ошибка",
                    "error_code": error_code
                }
            )
        
        return {
            "success": True,
            "message": "Административная аутентификация успешна",
            "user": result.user,
            "tokens": {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": "bearer"
            },
            "session_id": result.session_id,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.post("/session", response_model=AuthResponse)
async def authenticate_session(
    auth_data: SessionAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    🎫 Аутентификация по токену сессии
    
    Аутентифицирует пользователя по существующему токену сессии.
    """
    try:
        ip_address, user_agent = get_client_info(request)
        
        session_data = SessionAuthData(
            session_token=auth_data.session_token,
            password=auth_data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        result = await auth_service.authenticate_session(
            session_data, db, ip_address, user_agent
        )
        
        if not result.success:
            error_code = result.error_code or "UNKNOWN_ERROR"
            status_code = {
                "INVALID_SESSION": status.HTTP_401_UNAUTHORIZED,
                "SESSION_EXPIRED": status.HTTP_401_UNAUTHORIZED,
                "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
                "USER_NOT_APPROVED": status.HTTP_403_FORBIDDEN,
                "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
            }.get(error_code, status.HTTP_400_BAD_REQUEST)
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "success": False,
                    "error": result.error_message or "Неизвестная ошибка",
                    "error_code": error_code
                }
            )
        
        return {
            "success": True,
            "message": "Аутентификация по сессии успешна",
            "user": result.user,
            "tokens": {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": "bearer"
            },
            "session_id": result.session_id,
            "expires_at": result.expires_at.isoformat() if result.expires_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.post("/refresh")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    🔄 Обновление access токена
    
    Обновляет access токен используя refresh токен.
    """
    try:
        token_data = RefreshTokenData(
            refresh_token=refresh_data.refresh_token
        )
        
        result = await auth_service.refresh_token(token_data, db)
        
        return {
            "success": True,
            "message": "Токен успешно обновлен",
            "access_token": result.access_token,
            "expires_at": result.expires_at.isoformat(),
            "token_type": "bearer"
        }
        
    except (TokenError, InvalidCredentialsError, UserNotApprovedError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": str(e),
                "error_code": "INVALID_REFRESH_TOKEN"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    🚪 Выход из системы
    
    Завершает текущую сессию или все сессии пользователя.
    """
    try:
        # Получаем session_id из токена
        user_data = await auth_service.validate_access_token(credentials.credentials, db)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "error": "Недействительный токен",
                    "error_code": "INVALID_TOKEN"
                }
            )
        
        # Получаем payload токена для session_id
        payload = auth_service.token_manager.validate_token(credentials.credentials)
        
        result = await auth_service.logout(
            payload.session_id, db, logout_data.revoke_all_sessions
        )
        
        return {
            "success": result.success,
            "message": result.message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Внутренняя ошибка сервера",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.get("/me")
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    👤 Информация о текущем пользователе
    
    Возвращает информацию о текущем аутентифицированном пользователе.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": "Требуется аутентификация",
                "error_code": "AUTHENTICATION_REQUIRED"
            }
        )
    
    return {
        "success": True,
        "user": current_user
    }

@router.get("/sessions")
async def get_user_sessions(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    📱 Список активных сессий
    
    Возвращает список всех активных сессий текущего пользователя.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": "Требуется аутентификация",
                "error_code": "AUTHENTICATION_REQUIRED"
            }
        )
    
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": "ID пользователя не найден",
                    "error_code": "USER_ID_NOT_FOUND"
                }
            )
        
        sessions = await auth_service.get_user_sessions(int(user_id), db)
        
        return {
            "success": True,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "session_type": session.session_type.value,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "is_current": session.is_current,
                    "user_agent": session.user_agent,
                    "ip_address": session.ip_address
                }
                for session in sessions
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Ошибка получения сессий",
                "error_code": "INTERNAL_ERROR"
            }
        )

@router.get("/health")
async def health_check():
    """
    ❤️ Проверка работоспособности
    
    Проверяет работоспособность сервиса аутентификации.
    """
    return {
        "success": True,
        "message": "Сервис аутентификации v2.0 работает",
        "version": "2.0",
        "features": [
            "telegram_auth",
            "admin_auth", 
            "session_auth",
            "token_refresh",
            "rate_limiting",
            "security_logging"
        ]
    }
