import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt
from fastapi import HTTPException
import requests
import os

class TelegramAuth:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk")
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-jwt-secret-key")
        self.bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "vhm24rbot")
        
    def verify_auth_data(self, auth_data: Dict) -> bool:
        """Проверка подлинности данных от Telegram"""
        try:
            received_hash = auth_data.pop('hash', None)
            if not received_hash:
                return False
            
            # Создаём строку для проверки
            data_check_string = '\n'.join([
                f'{key}={value}' for key, value in sorted(auth_data.items())
            ])
            
            # Вычисляем ожидаемый хеш
            secret_key = hashlib.sha256(self.bot_token.encode()).digest()
            expected_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Проверяем актуальность (не старше 86400 сек = 24 часа)
            auth_date = auth_data.get('auth_date', 0)
            if time.time() - int(auth_date) > 86400:
                return False
            
            return hmac.compare_digest(expected_hash, received_hash)
            
        except Exception as e:
            print(f"Auth verification error: {e}")
            return False
    
    def create_access_token(self, user_id: int, unique_id: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> str:
        """Создание JWT токена"""
        if expires_delta is None:
            expires_delta = timedelta(days=30)
            
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + expires_delta,
            'iat': datetime.utcnow()
        }
        
        if unique_id:
            payload['unique_id'] = unique_id
            
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_token(self, token: str) -> Optional[int]:
        """Проверка JWT токена"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload.get('user_id')
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    def decode_token(self, token: str) -> Optional[Dict]:
        """Декодирование JWT токена с получением всех данных"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def send_notification(self, chat_id: int, message: str):
        """Отправка уведомления пользователю"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return None
    
    async def notify_admin_new_user(self, user_data: Dict):
        """Уведомление админа о новом пользователе"""
        admin_chat_id = os.getenv('ADMIN_CHAT_ID')
        if not admin_chat_id:
            print("ADMIN_CHAT_ID not set")
            return
            
        try:
            admin_chat_id = int(admin_chat_id)
        except ValueError:
            print("Invalid ADMIN_CHAT_ID format")
            return
        
        message = f"""
🔔 <b>Новый пользователь ожидает одобрения</b>

👤 <b>Имя:</b> {user_data.get('first_name', '')} {user_data.get('last_name', '')}
🔗 <b>Username:</b> @{user_data.get('username', 'не указан')}
🆔 <b>Telegram ID:</b> {user_data.get('telegram_id')}
📅 <b>Дата регистрации:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        
        await self.send_notification(admin_chat_id, message)
