from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..telegram_auth import TelegramAuth
from .. import crud
from typing import Dict, Any
from pydantic import BaseModel
import hashlib

class LoginRequest(BaseModel):
    username: str
    password: str

router = APIRouter()
telegram_auth = TelegramAuth()

@router.post("/login")
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Обычная авторизация с логином и паролем"""
    try:
        # Простая проверка для демо (admin/admin123)
        if login_data.username == "admin" and login_data.password == "admin123":
            # Создаем или получаем admin пользователя
            admin_user = crud.get_user_by_telegram_id(db, 999999999)  # Фиктивный telegram_id для admin
            
            if not admin_user:
                # Создаем admin пользователя если не существует
                from ..models import User
                admin_user = User(
                    telegram_id=999999999,
                    username="admin",
                    first_name="Administrator",
                    status="approved",
                    role="admin",
                    personal_link="admin_direct_access"
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)
            
            # Генерируем токен
            user_id = getattr(admin_user, 'id')
            access_token = telegram_auth.create_access_token(user_id)
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": admin_user.id,
                    "username": admin_user.username,
                    "first_name": admin_user.first_name,
                    "status": admin_user.status,
                    "role": admin_user.role
                }
            }
        else:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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

@router.get("/users/pending")
async def get_pending_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка пользователей, ожидающих одобрения (только для админов)"""
    if str(current_user.role) != "admin":
        raise HTTPException(status_code=403, detail="Access denied: admin rights required")
    
    return crud.get_pending_users(db)

@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Одобрение пользователя (только для админов)"""
    if str(current_user.role) != "admin":
        raise HTTPException(status_code=403, detail="Access denied: admin rights required")
    
    user = crud.approve_user(db, user_id, getattr(current_user, 'id'))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User approved successfully"}
