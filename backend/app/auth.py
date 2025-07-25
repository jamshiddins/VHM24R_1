from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import jwt
import secrets
import hashlib
import hmac
import os
from dotenv import load_dotenv

from .database import get_db
from . import crud, models, schemas

load_dotenv()

# Настройки JWT
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Telegram Bot Token для проверки подписи
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk")

security = HTTPBearer()

class TelegramAuth:
    """Класс для аутентификации через Telegram"""
    
    @staticmethod
    def verify_telegram_auth(auth_data: schemas.TelegramAuthData) -> bool:
        """Проверяет подлинность данных от Telegram"""
        try:
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
            secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
            
            # Вычисляем HMAC
            calculated_hash = hmac.new(
                secret_key,
                check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Проверяем, что данные не старше 24 часов
            current_time = datetime.now().timestamp()
            if current_time - auth_data.auth_date > 86400:  # 24 часа
                return False
            
            return calculated_hash == auth_data.hash
            
        except Exception:
            return False
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Создает JWT токен"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Проверяет JWT токен"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None

class AuthService:
    """Сервис для работы с аутентификацией"""
    
    def __init__(self):
        self.telegram_auth = TelegramAuth()
    
    def authenticate_telegram_user(self, auth_data: schemas.TelegramAuthData, db: Session) -> schemas.AuthResponse:
        """Аутентифицирует пользователя через Telegram"""
        
        # Проверяем подлинность данных
        if not self.telegram_auth.verify_telegram_auth(auth_data):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные данные аутентификации Telegram"
            )
        
        # Ищем пользователя в базе данных
        user = crud.get_user_by_telegram_id(db, str(auth_data.id))
        
        if not user:
            # Создаем нового пользователя
            user_create = schemas.UserCreate(
                telegram_id=str(auth_data.id),
                username=auth_data.username,
                first_name=auth_data.first_name,
                last_name=auth_data.last_name
            )
            user = crud.create_user(db, user_create)
        else:
            # Обновляем информацию о пользователе
            user_update = schemas.UserUpdate(
                username=auth_data.username,
                first_name=auth_data.first_name,
                last_name=auth_data.last_name
            )
            user = crud.update_user(db, user.id, user_update)
        
        # Проверяем, одобрен ли пользователь
        if user.status != "approved" and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ваш аккаунт ожидает одобрения администратора"
            )
        
        # Создаем JWT токен
        access_token = self.telegram_auth.create_access_token(
            data={"sub": str(user.id), "telegram_id": str(auth_data.id)}
        )
        
        # Создаем сессию в базе данных (опционально)
        session_token = secrets.token_urlsafe(32)
        
        return schemas.AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user,
            personal_link=user.personal_link
        )
    
    def get_current_user(self, credentials: HTTPAuthorizationCredentials, db: Session) -> models.User:
        """Получает текущего пользователя по токену"""
        
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = self.telegram_auth.verify_token(credentials.credentials)
            if payload is None:
                raise credentials_exception
            
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
                
        except jwt.PyJWTError:
            raise credentials_exception
        
        user = crud.get_user(db, user_id=int(user_id))
        if user is None:
            raise credentials_exception
        
        # Проверяем, что пользователь все еще одобрен
        if not user.status == "approved" and not user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен"
            )
        
        return user
    
    def get_current_admin_user(self, current_user: models.User = None) -> models.User:
        """Проверяет, что текущий пользователь - администратор"""
        if not current_user or current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав доступа"
            )
        return current_user
    
    def verify_personal_link(self, personal_link: str, db: Session) -> models.User:
        """Проверяет персональную ссылку пользователя"""
        user = crud.get_user_by_personal_link(db, personal_link)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Персональная ссылка не найдена"
            )
        
        if user.status != "approved" and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь не одобрен"
            )
        
        return user

# Создаем экземпляр сервиса аутентификации
auth_service = AuthService()

# Зависимости для FastAPI
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """Зависимость для получения текущего пользователя"""
    return auth_service.get_current_user(credentials, db)

def get_current_admin_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Зависимость для получения текущего администратора"""
    return auth_service.get_current_admin_user(current_user)

def get_user_by_personal_link(
    personal_link: str,
    db: Session = Depends(get_db)
) -> models.User:
    """Зависимость для получения пользователя по персональной ссылке"""
    return auth_service.verify_personal_link(personal_link, db)

# Опциональная аутентификация (для публичных эндпоинтов)
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """Опциональная зависимость для получения текущего пользователя"""
    if credentials is None:
        return None
    
    try:
        return auth_service.get_current_user(credentials, db)
    except HTTPException:
        return None
