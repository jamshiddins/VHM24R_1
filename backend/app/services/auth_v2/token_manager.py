"""
Управление токенами для системы аутентификации v2.0
"""

import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from .auth_models import TokenPayload, TokenType, TokenResponse
from .exceptions import TokenError, TokenExpiredError, InvalidTokenError


class TokenManager:
    """Централизованное управление JWT токенами"""
    
    def __init__(self):
        self.secret_key = self._get_secret_key()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60  # 1 час
        self.refresh_token_expire_days = 30    # 30 дней
        self.session_token_expire_hours = 2    # 2 часа
        
    def _get_secret_key(self) -> str:
        """Получает единый секретный ключ"""
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            # Используем резервный ключ если не задан в env
            secret_key = os.getenv("JWT_SECRET_KEY")
            if not secret_key:
                raise ValueError("SECRET_KEY или JWT_SECRET_KEY должен быть установлен в переменных окружения")
        return secret_key
    
    def _create_token_payload(
        self, 
        user_id: int, 
        session_id: str,
        token_type: TokenType,
        expires_delta: timedelta,
        permissions: Optional[list] = None,
        **extra_data
    ) -> Dict[str, Any]:
        """Создает payload для JWT токена"""
        now = datetime.utcnow()
        expires_at = now + expires_delta
        
        payload = {
            # Стандартные JWT поля
            "sub": str(user_id),  # Subject (пользователь)
            "iat": int(now.timestamp()),  # Issued at
            "exp": int(expires_at.timestamp()),  # Expires at
            "jti": str(uuid4()),  # JWT ID (уникальный идентификатор токена)
            
            # Наши поля
            "user_id": user_id,
            "session_id": session_id,
            "token_type": token_type.value,
            "permissions": permissions or [],
            "version": "2.0"  # Версия токена для совместимости
        }
        
        # Добавляем дополнительные данные
        payload.update(extra_data)
        
        return payload
    
    def create_access_token(
        self, 
        user_id: int, 
        session_id: str,
        permissions: Optional[list] = None,
        **extra_data
    ) -> str:
        """Создает access токен"""
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        
        payload = self._create_token_payload(
            user_id=user_id,
            session_id=session_id,
            token_type=TokenType.ACCESS,
            expires_delta=expires_delta,
            permissions=permissions,
            **extra_data
        )
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(
        self, 
        user_id: int, 
        session_id: str,
        **extra_data
    ) -> str:
        """Создает refresh токен"""
        expires_delta = timedelta(days=self.refresh_token_expire_days)
        
        payload = self._create_token_payload(
            user_id=user_id,
            session_id=session_id,
            token_type=TokenType.REFRESH,
            expires_delta=expires_delta,
            permissions=[],  # Refresh токены не имеют разрешений
            **extra_data
        )
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_session_token(
        self, 
        user_id: int, 
        session_id: str,
        **extra_data
    ) -> str:
        """Создает токен сессии"""
        expires_delta = timedelta(hours=self.session_token_expire_hours)
        
        payload = self._create_token_payload(
            user_id=user_id,
            session_id=session_id,
            token_type=TokenType.SESSION,
            expires_delta=expires_delta,
            permissions=[],  # Сессионные токены не имеют разрешений
            **extra_data
        )
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_token(self, token: str) -> TokenPayload:
        """Валидирует токен и возвращает payload"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": True}
            )
            
            # Проверяем обязательные поля
            required_fields = ["user_id", "session_id", "token_type"]
            for field in required_fields:
                if field not in payload:
                    raise InvalidTokenError(f"Отсутствует обязательное поле: {field}")
            
            # Создаем объект TokenPayload
            token_payload = TokenPayload(
                user_id=payload["user_id"],
                session_id=payload["session_id"],
                token_type=TokenType(payload["token_type"]),
                issued_at=datetime.fromtimestamp(payload["iat"]),
                expires_at=datetime.fromtimestamp(payload["exp"]),
                permissions=payload.get("permissions", []),
                telegram_id=payload.get("telegram_id"),
                username=payload.get("username"),
                role=payload.get("role")
            )
            
            return token_payload
            
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Токен истек")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Недействительный токен: {str(e)}")
        except Exception as e:
            raise TokenError(f"Ошибка валидации токена: {str(e)}")
    
    def refresh_access_token(
        self,
        refresh_token: str,
        permissions: Optional[list] = None
    ) -> TokenResponse:
        """Обновляет access токен используя refresh токен"""
        # Валидируем refresh токен
        payload = self.validate_token(refresh_token)
        
        if payload.token_type != TokenType.REFRESH:
            raise InvalidTokenError("Ожидается refresh токен")
        
        # Создаем новый access токен
        access_token = self.create_access_token(
            user_id=payload.user_id,
            session_id=payload.session_id,
            permissions=permissions or payload.permissions,
            telegram_id=payload.telegram_id,
            username=payload.username,
            role=payload.role
        )
        
        # Вычисляем время истечения access токена
        expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=None,  # Refresh токен не обновляется
            expires_at=expires_at
        )
    
    def create_token_pair(
        self,
        user_id: int,
        session_id: str,
        permissions: Optional[list] = None,
        **extra_data
    ) -> TokenResponse:
        """Создает пару access + refresh токенов"""
        access_token = self.create_access_token(
            user_id=user_id,
            session_id=session_id,
            permissions=permissions,
            **extra_data
        )
        
        refresh_token = self.create_refresh_token(
            user_id=user_id,
            session_id=session_id,
            **extra_data
        )
        
        expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
    
    def get_token_hash(self, token: str) -> str:
        """Создает хеш токена для хранения в БД"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_token_revoked(self, token_hash: str) -> bool:
        """Проверяет, отозван ли токен (заглушка для будущей реализации с БД)"""
        # TODO: Реализовать проверку в таблице revoked_tokens
        return False
    
    def revoke_token(self, token: str) -> bool:
        """Отзывает токен (заглушка для будущей реализации с БД)"""
        # TODO: Реализовать добавление в таблицу revoked_tokens
        return True
