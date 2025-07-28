# Система динамических ссылок и паролей для VHM24R
# backend/app/services/dynamic_auth.py

import secrets
import string
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, TelegramSession
from .. import crud

class DynamicAuthService:
    """Сервис для генерации временных ссылок и паролей"""
    
    def __init__(self):
        self.active_sessions = {}  # В production использовать Redis
        
    def generate_password(self, length: int = 12) -> str:
        """Генерирует безопасный пароль"""
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def generate_session_token(self) -> str:
        """Генерирует уникальный токен сессии"""
        return secrets.token_urlsafe(32)
    
    async def create_dynamic_session(self, user_id: int, db: Session) -> Dict[str, str]:
        """Создает динамическую сессию с паролем"""
        
        # Генерируем данные сессии
        session_token = self.generate_session_token()
        password = self.generate_password()
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        
        # Сохраняем в БД
        session_data = {
            'telegram_id': user_id,
            'session_token': session_token,
            'expires_at': expires_at,
            'is_active': True
        }
        
        # Создаем запись в базе
        db_session = TelegramSession(**session_data)
        db.add(db_session)
        db.commit()
        
        # Временно сохраняем пароль в памяти (в production - Redis)
        self.active_sessions[session_token] = {
            'password': password,
            'user_id': user_id,
            'expires_at': expires_at,
            'used': False
        }
        
        return {
            'session_token': session_token,
            'password': password,
            'expires_at': expires_at.isoformat(),
            'url': f"{os.getenv('FRONTEND_URL', 'https://vhm24r1-production.up.railway.app')}/auth/dynamic/{session_token}"
        }
    
    async def validate_session(self, session_token: str, password: str) -> Optional[int]:
        """Проверяет валидность сессии и пароля"""
        
        session = self.active_sessions.get(session_token)
        if not session:
            return None
            
        # Проверяем срок действия
        if datetime.utcnow() > session['expires_at']:
            del self.active_sessions[session_token]
            return None
            
        # Проверяем пароль
        if session['password'] != password:
            return None
            
        # Проверяем, что сессия не использована
        if session['used']:
            return None
            
        # Помечаем как использованную
        session['used'] = True
        
        return session['user_id']
    
    async def cleanup_expired_sessions(self):
        """Очищает истекшие сессии"""
        current_time = datetime.utcnow()
        expired_tokens = [
            token for token, session in self.active_sessions.items()
            if current_time > session['expires_at']
        ]
        
        for token in expired_tokens:
            del self.active_sessions[token]
