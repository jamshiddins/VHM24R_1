"""
Сервис безопасности для системы аутентификации v2.0
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict, deque

from .auth_models import AuthAttempt, AuthMethod, TelegramAuthData
from .exceptions import RateLimitError, SecurityError


class SecurityService:
    """Сервис безопасности аутентификации"""
    
    def __init__(self):
        # Rate limiting (в production использовать Redis)
        self._rate_limits = defaultdict(deque)
        self._failed_attempts = defaultdict(int)
        self._lockout_until: Dict[str, datetime] = {}
        
        # Настройки rate limiting
        self.max_attempts_per_minute = 5
        self.max_attempts_per_hour = 20
        self.lockout_duration_minutes = 15
        self.max_failed_attempts = 5
        
        # Настройки Telegram
        self.telegram_auth_timeout = 86400  # 24 часа
        
    def _get_rate_limit_key(self, identifier: str, action: str) -> str:
        """Создает ключ для rate limiting"""
        return f"rate_limit:{action}:{identifier}"
    
    def _cleanup_old_attempts(self, attempts_queue: deque, window_seconds: int):
        """Очищает старые попытки из очереди"""
        cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        while attempts_queue and attempts_queue[0] < cutoff_time:
            attempts_queue.popleft()
    
    async def check_rate_limit(self, identifier: str, action: str = "auth") -> bool:
        """Проверяет rate limit для идентификатора"""
        now = datetime.utcnow()
        
        # Проверяем блокировку
        lockout_key = f"lockout:{identifier}"
        if lockout_key in self._lockout_until:
            if now < self._lockout_until[lockout_key]:
                raise RateLimitError(
                    f"Аккаунт заблокирован до {self._lockout_until[lockout_key]}",
                    retry_after=int((self._lockout_until[lockout_key] - now).total_seconds())
                )
            else:
                # Блокировка истекла
                del self._lockout_until[lockout_key]
                self._failed_attempts[identifier] = 0
        
        # Проверяем лимиты по времени
        minute_key = self._get_rate_limit_key(identifier, f"{action}_minute")
        hour_key = self._get_rate_limit_key(identifier, f"{action}_hour")
        
        # Очищаем старые записи
        self._cleanup_old_attempts(self._rate_limits[minute_key], 60)
        self._cleanup_old_attempts(self._rate_limits[hour_key], 3600)
        
        # Проверяем лимиты
        if len(self._rate_limits[minute_key]) >= self.max_attempts_per_minute:
            raise RateLimitError("Слишком много попыток в минуту", retry_after=60)
        
        if len(self._rate_limits[hour_key]) >= self.max_attempts_per_hour:
            raise RateLimitError("Слишком много попыток в час", retry_after=3600)
        
        # Добавляем текущую попытку
        self._rate_limits[minute_key].append(now)
        self._rate_limits[hour_key].append(now)
        
        return True
    
    async def log_auth_attempt(self, attempt: AuthAttempt) -> None:
        """Логирует попытку аутентификации"""
        identifier = attempt.ip_address or str(attempt.telegram_id) or "unknown"
        
        if not attempt.success:
            # Увеличиваем счетчик неудачных попыток
            self._failed_attempts[identifier] += 1
            
            # Блокируем после превышения лимита
            if self._failed_attempts[identifier] >= self.max_failed_attempts:
                lockout_until = datetime.utcnow() + timedelta(minutes=self.lockout_duration_minutes)
                self._lockout_until[f"lockout:{identifier}"] = lockout_until
                
                print(f"🚨 Заблокирован доступ для {identifier} до {lockout_until} "
                      f"(превышен лимит неудачных попыток: {self._failed_attempts[identifier]})")
        else:
            # Сбрасываем счетчик при успешном входе
            if identifier in self._failed_attempts:
                del self._failed_attempts[identifier]
            if f"lockout:{identifier}" in self._lockout_until:
                del self._lockout_until[f"lockout:{identifier}"]
        
        # Логируем попытку (в production записывать в БД)
        status = "✅ SUCCESS" if attempt.success else "❌ FAILED"
        print(f"🔐 AUTH ATTEMPT: {status} | Method: {attempt.method.value} "
              f"| User: {attempt.user_id} | IP: {attempt.ip_address} "
              f"| Time: {attempt.timestamp}")
        
        if attempt.error_message:
            print(f"   Error: {attempt.error_message}")
    
    async def detect_suspicious_activity(self, user_id: int, ip_address: Optional[str] = None) -> bool:
        """Детектирует подозрительную активность"""
        # Простая проверка на подозрительную активность
        # В production можно добавить более сложные алгоритмы
        
        if ip_address:
            # Проверяем количество неудачных попыток с этого IP
            failed_count = self._failed_attempts.get(ip_address, 0)
            if failed_count > self.max_failed_attempts // 2:
                return True
        
        # Проверяем блокировки пользователя
        user_key = f"user:{user_id}"
        if user_key in self._failed_attempts:
            if self._failed_attempts[user_key] > 3:
                return True
        
        return False
    
    async def validate_telegram_data(self, auth_data: TelegramAuthData, bot_token: str) -> bool:
        """Валидирует данные аутентификации от Telegram"""
        try:
            if not bot_token:
                return False
            
            # Проверяем актуальность данных (не старше 24 часов)
            current_time = int(time.time())
            if current_time - auth_data.auth_date > self.telegram_auth_timeout:
                return False
            
            # Создаем строку для проверки подписи
            check_string_parts = [
                f"auth_date={auth_data.auth_date}",
                f"first_name={auth_data.first_name}",
                f"id={auth_data.id}",
            ]
            
            if auth_data.last_name:
                check_string_parts.append(f"last_name={auth_data.last_name}")
            if auth_data.username:
                check_string_parts.append(f"username={auth_data.username}")
            if auth_data.photo_url:
                check_string_parts.append(f"photo_url={auth_data.photo_url}")
            
            # Сортируем и объединяем
            check_string_parts.sort()
            check_string = "\n".join(check_string_parts)
            
            # Создаем секретный ключ из токена бота
            secret_key = hashlib.sha256(bot_token.encode()).digest()
            
            # Вычисляем ожидаемый хеш
            calculated_hash = hmac.new(
                secret_key,
                check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Сравниваем с полученным хешем
            return hmac.compare_digest(calculated_hash, auth_data.hash)
            
        except Exception as e:
            print(f"❌ Ошибка валидации Telegram данных: {e}")
            return False
    
    async def generate_secure_session_id(self) -> str:
        """Генерирует безопасный ID сессии"""
        import secrets
        return secrets.token_urlsafe(32)
    
    async def generate_secure_password(self, length: int = 12) -> str:
        """Генерирует безопасный пароль"""
        import secrets
        import string
        
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    async def hash_password(self, password: str) -> str:
        """Хеширует пароль с солью"""
        import bcrypt
        
        # Генерируем соль и хешируем пароль
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    async def verify_password(self, password: str, hashed_password: str) -> bool:
        """Проверяет пароль против хеша"""
        import bcrypt
        
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    
    async def get_security_stats(self) -> Dict[str, Any]:
        """Возвращает статистику безопасности"""
        now = datetime.utcnow()
        active_lockouts = sum(
            1 for lockout_time in self._lockout_until.values()
            if lockout_time > now
        )
        
        return {
            "active_lockouts": active_lockouts,
            "total_failed_attempts": sum(self._failed_attempts.values()),
            "unique_blocked_ips": len(self._failed_attempts),
            "rate_limit_violations": len(self._rate_limits)
        }
    
    async def cleanup_expired_data(self):
        """Очищает устаревшие данные безопасности"""
        now = datetime.utcnow()
        
        # Очищаем истекшие блокировки
        expired_lockouts = [
            key for key, lockout_time in self._lockout_until.items()
            if lockout_time <= now
        ]
        for key in expired_lockouts:
            del self._lockout_until[key]
            # Также очищаем счетчик неудачных попыток
            identifier = key.replace("lockout:", "")
            if identifier in self._failed_attempts:
                del self._failed_attempts[identifier]
        
        # Очищаем старые rate limit записи
        for key, attempts_queue in list(self._rate_limits.items()):
            if "minute" in key:
                self._cleanup_old_attempts(attempts_queue, 60)
            elif "hour" in key:
                self._cleanup_old_attempts(attempts_queue, 3600)
            
            # Удаляем пустые очереди
            if not attempts_queue:
                del self._rate_limits[key]
