"""
Унифицированный сервис аутентификации VHM24R
Объединяет все методы аутентификации в одном месте
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import secrets
import hashlib
import hmac
import os
from dotenv import load_dotenv

from ..constants import (
    ACCESS_TOKEN_EXPIRE_HOURS, 
    HASH_ALGORITHM, 
    HMAC_ALGORITHM,
    TELEGRAM_AUTH_TIMEOUT,
    TELEGRAM_SESSION_TIMEOUT,
    UserStatus,
    UserRole,
    ErrorMessages,
    HTTPStatus
)
from .. import crud, models, schemas

load_dotenv()

class UnifiedAuthService:
    """Унифицированный сервис аутентификации"""
    
    def __init__(self):
        self.secret_key = self._get_secret_key()
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
    def _get_secret_key(self) -> str:
        """Получает секретный ключ из переменных окружения"""
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            raise ValueError("SECRET_KEY must be set in environment variables")
        return secret_key
    
    def _verify_telegram_signature(self, auth_data: schemas.TelegramAuthData) -> bool:
        """Проверяет подлинность данных от Telegram"""
        try:
            if not self.telegram_bot_token:
                return False
                
            # Создаем строку для проверки подписи
            check_string = "\n".join([
                f"auth_date={auth_data.auth_date}",
                f"first_name={auth_data.first_name}",
                f"id={auth_data.id}",
            ])
            
            if auth_data.last_name:
                check_string += f"\nlast_name={auth_data.last_name}"
            if auth_data.username:
                check_string += f"\nusername={auth_data.username}"
            if auth_data.photo_url:
                check_string += f"\nphoto_url={auth_data.photo_url}"
            
            # Создаем секретный ключ из токена бота
            secret_key = hashlib.sha256(self.telegram_bot_token.encode()).digest()
            
            # Вычисляем HMAC
            calculated_hash = hmac.new(
                secret_key,
                check_string.encode(),
                getattr(hashlib, HMAC_ALGORITHM)
            ).hexdigest()
            
            # Проверяем, что данные не старше установленного времени
            current_time = datetime.now().timestamp()
            if current_time - auth_data.auth_date > TELEGRAM_AUTH_TIMEOUT:
                return False
            
            return calculated_hash == auth_data.hash
            
        except Exception:
            return False
    
    def _create_jwt_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Создает JWT токен"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=HASH_ALGORITHM)
        return encoded_jwt
    
    def _verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверяет JWT токен"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[HASH_ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None
    
    def _get_user_response_data(self, user: models.User) -> Dict[str, Any]:
        """Формирует данные пользователя для ответа"""
        return {
            "id": getattr(user, 'id', 0),
            "telegram_id": str(getattr(user, 'telegram_id', '')),
            "username": getattr(user, 'username', None),
            "first_name": getattr(user, 'first_name', None),
            "last_name": getattr(user, 'last_name', None),
            "personal_link": str(getattr(user, 'personal_link', '')),
            "status": UserStatus.APPROVED if getattr(user, 'is_approved', False) else UserStatus.PENDING,
            "role": UserRole.ADMIN if getattr(user, 'is_admin', False) else UserRole.USER,
            "created_at": getattr(user, 'created_at', datetime.now()),
            "last_active": getattr(user, 'last_active', None)
        }
    
    def _check_user_permissions(self, user: models.User, require_admin: bool = False) -> None:
        """Проверяет права пользователя"""
        is_approved = getattr(user, 'is_approved', False)
        is_admin = getattr(user, 'is_admin', False)
        
        if not is_approved and not is_admin:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=ErrorMessages.USER_NOT_APPROVED
            )
        
        if require_admin and not is_admin:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=ErrorMessages.ACCESS_DENIED
            )
    
    def authenticate_telegram_user(self, auth_data: schemas.TelegramAuthData, db: Session) -> schemas.AuthResponse:
        """Аутентифицирует пользователя через Telegram"""
        
        # Проверяем подлинность данных
        if not self._verify_telegram_signature(auth_data):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail=ErrorMessages.TELEGRAM_AUTH_FAILED
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
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=ErrorMessages.DATABASE_ERROR
            )
        
        # Проверяем права пользователя
        self._check_user_permissions(user)
        
        # Создаем JWT токен
        user_id = getattr(user, 'id', 0)
        access_token = self._create_jwt_token({
            "sub": str(user_id), 
            "telegram_id": str(auth_data.id)
        })
        
        # Формируем ответ
        user_data = self._get_user_response_data(user)
        user_schema = schemas.User(**user_data)
        
        return schemas.AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_schema,
            personal_link=str(getattr(user, 'personal_link', ''))
        )
    
    async def authenticate_with_session_token(self, session_token: str, db: Session) -> schemas.AuthResponse:
        """Аутентификация по токену сессии"""
        from .simple_dynamic_auth import SimpleDynamicAuth
        simple_auth = SimpleDynamicAuth()
        
        user_id = await simple_auth.validate_session_token(session_token, db)
        if not user_id:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail=ErrorMessages.SESSION_EXPIRED
            )
        
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND
            )
        
        # Проверяем права пользователя
        self._check_user_permissions(user)
        
        # Создаем JWT токен
        user_id = getattr(user, 'id', 0)
        access_token = self._create_jwt_token({"user_id": user_id})
        
        # Формируем ответ
        user_data = self._get_user_response_data(user)
        user_schema = schemas.User(**user_data)
        
        return schemas.AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_schema,
            personal_link=str(getattr(user, 'personal_link', ''))
        )
    
    async def authenticate_with_dynamic_auth(self, session_token: str, password: str, db: Session) -> schemas.AuthResponse:
        """Динамическая аутентификация с паролем"""
        from .dynamic_auth import DynamicAuthService
        dynamic_auth = DynamicAuthService()
        
        user_id = await dynamic_auth.validate_session(session_token, password)
        if not user_id:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail=ErrorMessages.INVALID_CREDENTIALS
            )
        
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND
            )
        
        # Проверяем права пользователя
        self._check_user_permissions(user)
        
        # Создаем JWT токен
        user_id = getattr(user, 'id', 0)
        access_token = self._create_jwt_token({"user_id": user_id})
        
        # Формируем ответ
        user_data = self._get_user_response_data(user)
        user_schema = schemas.User(**user_data)
        
        return schemas.AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_schema,
            personal_link=str(getattr(user, 'personal_link', ''))
        )
    
    async def authenticate_admin(self, admin_token: str, db: Session) -> schemas.AuthResponse:
        """Административная аутентификация"""
        from .simple_dynamic_auth import SimpleDynamicAuth
        simple_auth = SimpleDynamicAuth()
        
        user_id = await simple_auth.validate_admin_session(admin_token, db)
        if not user_id:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail=ErrorMessages.INVALID_CREDENTIALS
            )
        
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND
            )
        
        # Проверяем права администратора
        self._check_user_permissions(user, require_admin=True)
        
        # Создаем JWT токен
        user_id = getattr(user, 'id', 0)
        access_token = self._create_jwt_token({"user_id": user_id})
        
        # Формируем ответ
        user_data = self._get_user_response_data(user)
        user_schema = schemas.User(**user_data)
        
        return schemas.AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_schema,
            personal_link=str(getattr(user, 'personal_link', ''))
        )
    
    def get_current_user_from_token(self, token: str, db: Session) -> models.User:
        """Получает текущего пользователя по JWT токену"""
        credentials_exception = HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail=ErrorMessages.INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        payload = self._verify_jwt_token(token)
        if payload is None:
            raise credentials_exception
        
        user_id_raw = payload.get("sub") or payload.get("user_id")
        if user_id_raw is None:
            raise credentials_exception
        
        try:
            user_id = int(user_id_raw)
        except (ValueError, TypeError):
            raise credentials_exception
        
        user = crud.get_user_by_id(db, user_id)
        if user is None:
            raise credentials_exception
        
        # Проверяем права пользователя
        self._check_user_permissions(user)
        
        return user
    
    def get_current_admin_user(self, user: models.User) -> models.User:
        """Проверяет, что текущий пользователь - администратор"""
        self._check_user_permissions(user, require_admin=True)
        return user
    
    def verify_personal_link(self, personal_link: str, db: Session) -> models.User:
        """Проверяет персональную ссылку пользователя"""
        user = crud.get_user_by_personal_link(db, personal_link)
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND
            )
        return user
    
    def create_session_token(self) -> str:
        """Создает токен сессии"""
        return secrets.token_urlsafe(32)
    
    def generate_secure_password(self, length: int = 12) -> str:
        """Генерирует безопасный пароль"""
        return secrets.token_urlsafe(length)

# Создаем глобальный экземпляр сервиса
unified_auth_service = UnifiedAuthService()
