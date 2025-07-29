"""
Enhanced Authentication Service with Security Improvements
Улучшенный сервис аутентификации с мерами безопасности
"""

import os
import jwt
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..models import User
from .. import crud

# Конфигурация из переменных окружения
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "your-refresh-secret-key")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Простое хранилище в памяти для демонстрации (в продакшене использовать Redis)
_memory_store: Dict[str, Any] = {}
_auth_attempts: Dict[str, Dict[str, Any]] = {}

class EnhancedAuthService:
    """Улучшенный сервис аутентификации с мерами безопасности"""
    
    def __init__(self):
        self.jwt_secret = JWT_SECRET_KEY
        self.refresh_secret = REFRESH_SECRET_KEY
        self.admin_username = ADMIN_USERNAME
        self.admin_telegram_id = ADMIN_TELEGRAM_ID
        
    def create_access_token(self, user_data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Создание access токена"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=30)  # Короткий срок жизни
            
        user_id = user_data.get("user_id")
        if user_id is None:
            raise ValueError("user_id is required")
            
        to_encode = user_data.copy()
        to_encode.update({
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow(),
            "jti": self._generate_jti(user_id)  # JWT ID для отзыва
        })
        
        return jwt.encode(to_encode, self.jwt_secret, algorithm="HS256")
    
    def create_refresh_token(self, user_id: int) -> str:
        """Создание refresh токена"""
        expire = datetime.utcnow() + timedelta(days=30)  # Длительный срок жизни
        
        to_encode = {
            "user_id": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": self._generate_jti(user_id, token_type="refresh")
        }
        
        refresh_token = jwt.encode(to_encode, self.refresh_secret, algorithm="HS256")
        
        # Сохраняем refresh токен
        self._store_refresh_token(user_id, refresh_token, expire)
        
        return refresh_token
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Проверка access токена"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            
            # Проверяем тип токена
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            # Проверяем, не отозван ли токен
            jti = payload.get("jti")
            if jti and self._is_token_revoked(jti):
                raise HTTPException(status_code=401, detail="Token has been revoked")
                
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """Проверка refresh токена"""
        try:
            payload = jwt.decode(token, self.refresh_secret, algorithms=["HS256"])
            
            # Проверяем тип токена
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            user_id = payload.get("user_id")
            
            # Проверяем, существует ли токен
            if not self._is_refresh_token_valid(user_id, token):
                raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
                
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Refresh token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    def refresh_access_token(self, refresh_token: str, db: Session) -> Dict[str, str]:
        """Обновление access токена с помощью refresh токена"""
        payload = self.verify_refresh_token(refresh_token)
        user_id = payload.get("user_id")
        
        # Проверяем, что user_id существует и является целым числом
        if user_id is None or not isinstance(user_id, int):
            raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
        # Получаем пользователя из БД
        user = crud.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Создаем новый access токен
        access_token = self.create_access_token({
            "user_id": user.id,
            "username": user.username,
            "role": str(user.role),
            "status": str(user.status)
        })
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    
    def revoke_token(self, token: str, token_type: str = "access"):
        """Отзыв токена"""
        try:
            if token_type == "access":
                payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"], options={"verify_exp": False})
            else:
                payload = jwt.decode(token, self.refresh_secret, algorithms=["HS256"], options={"verify_exp": False})
            
            jti = payload.get("jti")
            if jti:
                # Добавляем токен в blacklist
                exp = payload.get("exp", 0)
                ttl = max(0, exp - int(datetime.utcnow().timestamp()))
                _memory_store[f"revoked_token:{jti}"] = {
                    "revoked_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
                }
                
            if token_type == "refresh":
                user_id = payload.get("user_id")
                self._remove_refresh_token(user_id, token)
                
        except jwt.InvalidTokenError:
            pass  # Игнорируем невалидные токены
    
    def revoke_all_user_tokens(self, user_id: int):
        """Отзыв всех токенов пользователя"""
        # Удаляем все refresh токены пользователя
        keys_to_remove = []
        for key in _memory_store.keys():
            if key.startswith(f"refresh_token:{user_id}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del _memory_store[key]
    
    def is_admin_user(self, user: User) -> bool:
        """Проверка, является ли пользователь администратором"""
        return bool(
            str(user.role) == "admin" or 
            user.username == self.admin_username or 
            (user.telegram_id is not None and user.telegram_id == self.admin_telegram_id)
        )
    
    def check_user_permissions(self, user: User, required_role: str = "user") -> bool:
        """Проверка прав пользователя"""
        if str(user.status) != "approved":
            return False
            
        if required_role == "admin":
            return self.is_admin_user(user)
            
        return True
    
    def log_auth_attempt(self, user_id: Optional[int], success: bool, ip_address: str, user_agent: str):
        """Логирование попыток аутентификации"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        # Сохраняем в памяти для анализа (в продакшене использовать Redis/БД)
        key = f"auth_log:{datetime.utcnow().strftime('%Y%m%d')}"
        if key not in _memory_store:
            _memory_store[key] = []
        _memory_store[key].append(log_data)
    
    def check_brute_force(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Проверка на brute force атаки"""
        if identifier not in _auth_attempts:
            return True
            
        attempt_data = _auth_attempts[identifier]
        current_time = datetime.utcnow()
        
        # Очищаем старые попытки
        if current_time - attempt_data.get("first_attempt", current_time) > timedelta(minutes=window_minutes):
            del _auth_attempts[identifier]
            return True
            
        return attempt_data.get("count", 0) < max_attempts
    
    def record_failed_attempt(self, identifier: str, window_minutes: int = 15):
        """Запись неудачной попытки аутентификации"""
        current_time = datetime.utcnow()
        
        if identifier not in _auth_attempts:
            _auth_attempts[identifier] = {
                "count": 1,
                "first_attempt": current_time,
                "last_attempt": current_time
            }
        else:
            _auth_attempts[identifier]["count"] += 1
            _auth_attempts[identifier]["last_attempt"] = current_time
    
    def clear_failed_attempts(self, identifier: str):
        """Очистка неудачных попыток после успешной аутентификации"""
        if identifier in _auth_attempts:
            del _auth_attempts[identifier]
    
    def _generate_jti(self, user_id: int, token_type: str = "access") -> str:
        """Генерация уникального идентификатора токена"""
        return f"{token_type}_{user_id}_{uuid.uuid4().hex[:8]}"
    
    def _store_refresh_token(self, user_id: int, token: str, expire: datetime):
        """Сохранение refresh токена"""
        key = f"refresh_token:{user_id}:{token[-8:]}"  # Используем последние 8 символов как ID
        _memory_store[key] = {
            "token": token,
            "expires_at": expire,
            "created_at": datetime.utcnow()
        }
    
    def _is_refresh_token_valid(self, user_id: int, token: str) -> bool:
        """Проверка валидности refresh токена"""
        key = f"refresh_token:{user_id}:{token[-8:]}"
        stored_data = _memory_store.get(key)
        
        if not stored_data:
            return False
            
        # Проверяем срок действия
        if datetime.utcnow() > stored_data["expires_at"]:
            del _memory_store[key]
            return False
            
        return stored_data["token"] == token
    
    def _remove_refresh_token(self, user_id: int, token: str):
        """Удаление refresh токена"""
        key = f"refresh_token:{user_id}:{token[-8:]}"
        if key in _memory_store:
            del _memory_store[key]
    
    def _is_token_revoked(self, jti: str) -> bool:
        """Проверка, отозван ли токен"""
        revoked_data = _memory_store.get(f"revoked_token:{jti}")
        if not revoked_data:
            return False
            
        # Проверяем, не истек ли срок хранения в blacklist
        if datetime.utcnow() > revoked_data["expires_at"]:
            del _memory_store[f"revoked_token:{jti}"]
            return False
            
        return True

# Глобальный экземпляр сервиса
enhanced_auth_service = EnhancedAuthService()

def get_remote_address(request: Request) -> str:
    """Получение IP адреса клиента"""
    return request.client.host if request.client else "unknown"

def rate_limit_check(request: Request, max_requests: int = 100, window_minutes: int = 60) -> bool:
    """Простая проверка rate limiting"""
    ip_address = get_remote_address(request)
    current_time = datetime.utcnow()
    key = f"rate_limit:{ip_address}"
    
    if key not in _memory_store:
        _memory_store[key] = {
            "requests": 1,
            "window_start": current_time
        }
        return True
    
    rate_data = _memory_store[key]
    
    # Сброс окна если прошло время
    if current_time - rate_data["window_start"] > timedelta(minutes=window_minutes):
        _memory_store[key] = {
            "requests": 1,
            "window_start": current_time
        }
        return True
    
    # Проверяем лимит
    if rate_data["requests"] >= max_requests:
        return False
    
    rate_data["requests"] += 1
    return True
