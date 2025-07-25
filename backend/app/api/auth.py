from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..telegram_auth import TelegramAuth
from .. import crud
from typing import Dict, Any

router = APIRouter()
telegram_auth = TelegramAuth()

@router.post("/telegram/verify")
async def verify_telegram_token(
    token_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Верификация Telegram токена"""
    try:
        token = token_data.get('token')
        uid = token_data.get('uid')
        
        if not token:
            raise HTTPException(status_code=400, detail="Token required")
        
        # Проверяем JWT токен
        user_id = telegram_auth.verify_token(token)
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Получаем пользователя
        user = crud.get_user_by_id(db, user_id)
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found or not approved")
        
        if str(user.status) != 'approved':
            raise HTTPException(status_code=401, detail="User not found or not approved")
        
        # Проверяем уникальный токен если есть
        if uid:
            token_user = crud.get_user_by_token(db, uid)
            if not token_user:
                raise HTTPException(status_code=401, detail="Invalid unique token")
            if getattr(token_user, 'id') != getattr(user, 'id'):
                raise HTTPException(status_code=401, detail="Invalid unique token")
        
        # Генерируем новый токен для веб-сессии
        new_token = telegram_auth.create_access_token(getattr(user, 'id'))
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "status": user.status,
                "role": user.role
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "status": current_user.status,
        "role": current_user.role
    }
