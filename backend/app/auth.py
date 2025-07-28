from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from .database import get_db
from . import models
from .services.unified_auth import unified_auth_service
from .constants import HTTPStatus, ErrorMessages

security = HTTPBearer()


# Зависимости для FastAPI
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """Зависимость для получения текущего пользователя"""
    return unified_auth_service.get_current_user_from_token(credentials.credentials, db)

def get_current_admin_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Зависимость для получения текущего администратора"""
    return unified_auth_service.get_current_admin_user(current_user)

def get_user_by_personal_link(
    personal_link: str,
    db: Session = Depends(get_db)
) -> models.User:
    """Зависимость для получения пользователя по персональной ссылке"""
    return unified_auth_service.verify_personal_link(personal_link, db)

# Опциональная аутентификация (для публичных эндпоинтов)
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """Опциональная зависимость для получения текущего пользователя"""
    if credentials is None:
        return None
    
    try:
        return unified_auth_service.get_current_user_from_token(credentials.credentials, db)
    except HTTPException:
        return None
