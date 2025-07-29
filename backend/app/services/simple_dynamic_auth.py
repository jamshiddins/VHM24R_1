import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional
from ..models import TelegramSession, User
from .. import crud

class SimpleDynamicAuth:
    """Упрощенная система динамической аутентификации без паролей"""
    
    def __init__(self):
        self.session_lifetime = timedelta(hours=2)  # Обычные пользователи - 2 часа
        self.admin_session_lifetime = timedelta(hours=8)  # Админ - 8 часов
    
    async def create_access_link(self, user_id: int, db: Session) -> str:
        """Создает простую временную ссылку без пароля"""
        
        # Деактивируем старые сессии пользователя через UPDATE
        db.query(TelegramSession).filter(
            TelegramSession.telegram_id == user_id,
            TelegramSession.is_active.is_(True)
        ).update({"is_active": False})
        
        # Создаем новую сессию
        session_token = secrets.token_urlsafe(48)  # Увеличиваем длину для безопасности
        expires_at = datetime.utcnow() + self.session_lifetime
        
        new_session = TelegramSession(
            telegram_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(new_session)
        db.commit()
        
        # Возвращаем готовую ссылку
        frontend_url = os.getenv('FRONTEND_URL', 'https://vhm24r1-production.up.railway.app')
        return f"{frontend_url}/auth/session/{session_token}"
    
    async def create_admin_access_link(self, admin_telegram_id: int, db: Session) -> str:
        """Создает административную ссылку с расширенным временем жизни"""
        
        # Деактивируем старые админские сессии через UPDATE
        db.query(TelegramSession).filter(
            TelegramSession.telegram_id == admin_telegram_id,
            TelegramSession.session_token.like('admin_%'),
            TelegramSession.is_active.is_(True)
        ).update({"is_active": False})
        
        # Создаем новую админскую сессию
        admin_token = secrets.token_urlsafe(64)  # Более длинный токен для админа
        expires_at = datetime.utcnow() + self.admin_session_lifetime
        
        new_session = TelegramSession(
            telegram_id=admin_telegram_id,
            session_token=f"admin_{admin_token}",
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(new_session)
        db.commit()
        
        frontend_url = os.getenv('FRONTEND_URL', 'https://vhm24r1-production.up.railway.app')
        return f"{frontend_url}/auth/admin/{admin_token}"
    
    async def validate_session_token(self, session_token: str, db: Session) -> Optional[int]:
        """Проверяет токен сессии и возвращает telegram_id"""
        
        session: Optional[TelegramSession] = db.query(TelegramSession).filter(
            TelegramSession.session_token == session_token,
            TelegramSession.is_active.is_(True),
            TelegramSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
            
        # НЕ деактивируем сессию сразу - позволяем использовать токен для входа в WebApp
        # Токен будет деактивирован автоматически по истечении времени
        
        # Явно приводим к int, чтобы избежать ошибок типизации
        return int(getattr(session, 'telegram_id'))
    
    async def validate_admin_session(self, admin_token: str, db: Session) -> Optional[int]:
        """Специальная валидация для админа"""
        
        full_token = f"admin_{admin_token}"
        
        session = db.query(TelegramSession).filter(
            TelegramSession.session_token == full_token,
            TelegramSession.is_active.is_(True),
            TelegramSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        # Проверяем, что это действительно админ
        telegram_id = int(getattr(session, 'telegram_id'))
        user = crud.get_user_by_telegram_id(db, telegram_id)
        if not user or str(user.role) != 'admin':
            return None
        
        # НЕ деактивируем админскую сессию после использования
        # Админ может использовать ссылку многократно в течение 8 часов
        
        return telegram_id
    
    async def cleanup_expired_sessions(self, db: Session):
        """Очистка истекших сессий"""
        try:
            expired_sessions = db.query(TelegramSession).filter(
                TelegramSession.expires_at < datetime.utcnow()
            ).all()
            
            for session in expired_sessions:
                db.delete(session)
            
            db.commit()
            
            if expired_sessions:
                print(f"Cleaned up {len(expired_sessions)} expired sessions")
                
        except Exception as e:
            print(f"Error cleaning up sessions: {e}")
            db.rollback()
    
    async def get_active_sessions_count(self, db: Session) -> int:
        """Получает количество активных сессий"""
        return db.query(TelegramSession).filter(
            TelegramSession.is_active.is_(True),
            TelegramSession.expires_at > datetime.utcnow()
        ).count()
    
    async def deactivate_user_sessions(self, telegram_id: int, db: Session):
        """Деактивирует все сессии пользователя"""
        count = db.query(TelegramSession).filter(
            TelegramSession.telegram_id == telegram_id,
            TelegramSession.is_active.is_(True)
        ).count()
        
        db.query(TelegramSession).filter(
            TelegramSession.telegram_id == telegram_id,
            TelegramSession.is_active.is_(True)
        ).update({"is_active": False})
        
        db.commit()
        
        return count
