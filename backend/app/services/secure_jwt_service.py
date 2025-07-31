"""
Безопасный JWT сервис с защитой от критических уязвимостей
"""
import os
import jwt
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass
import redis
import json
from enum import Enum

from ..utils.logger import get_logger
from ..utils.exceptions import SecurityError, ValidationError

logger = get_logger(__name__)

class TokenType(Enum):
    """Типы токенов"""
    ACCESS = "access"
    REFRESH = "refresh"
    API = "api"
    RESET_PASSWORD = "reset_password"

@dataclass
class TokenClaims:
    """Структура claims для JWT токена"""
    user_id: int
    username: Optional[str]
    roles: List[str]
    token_type: TokenType
    permissions: List[str]
    issued_at: datetime
    expires_at: datetime
    jwt_id: str
    issuer: str = "VHM24R"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sub': str(self.user_id),
            'username': self.username,
            'roles': self.roles,
            'token_type': self.token_type.value,
            'permissions': self.permissions,
            'iat': int(self.issued_at.timestamp()),
            'exp': int(self.expires_at.timestamp()),
            'jti': self.jwt_id,
            'iss': self.issuer
        }

class TokenBlacklist:
    """Управление черным списком токенов"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._memory_blacklist: Set[str] = set()
        
        if not self.redis_client:
            # Fallback к памяти если Redis недоступен
            logger.warning("Redis недоступен для blacklist, используется память")
    
    def add_token(self, jti: str, exp_timestamp: int, reason: str = "revoked"):
        """Добавляет токен в черный список"""
        try:
            if self.redis_client:
                # Сохраняем в Redis с TTL до истечения токена
                ttl = max(1, exp_timestamp - int(datetime.now(timezone.utc).timestamp()))
                self.redis_client.setex(
                    f"blacklist:{jti}", 
                    ttl, 
                    json.dumps({
                        'reason': reason,
                        'revoked_at': datetime.now(timezone.utc).isoformat()
                    })
                )
                logger.info(f"Токен помечен как отозванный в blacklist", extra={"jti": jti, "reason": reason})
            else:
                self._memory_blacklist.add(jti)
                
            logger.info(f"Токен добавлен в blacklist: {jti[:8]}..., причина: {reason}")
            
        except Exception as e:
            logger.error(f"Ошибка добавления токена в blacklist: {e}")
            # Fallback к памяти
            self._memory_blacklist.add(jti)
    
    def is_blacklisted(self, jti: str) -> bool:
        """Проверяет, находится ли токен в черном списке"""
        try:
            if self.redis_client:
                return self.redis_client.exists(f"blacklist:{jti}") == 1
            else:
                return jti in self._memory_blacklist
        except Exception as e:
            logger.error(f"Ошибка проверки blacklist: {e}")
            return jti in self._memory_blacklist
    
    def get_blacklist_info(self, jti: str) -> Optional[Dict]:
        """Получает информацию о заблокированном токене"""
        try:
            if self.redis_client:
                data = self.redis_client.get(f"blacklist:{jti}")
                if data:
                    # Приводим данные к строке, если они не являются строкой
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    elif not isinstance(data, str):
                        data = str(data)
                    return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о blacklist: {e}")
            return None

class SecureJWTService:
    """Безопасный JWT сервис с защитой от уязвимостей"""
    
    def __init__(self):
        self._validate_configuration()
        self.secret_key = self._get_secret_key()
        self.algorithm = "HS256"  # Только безопасный алгоритм
        self.issuer = "VHM24R_SECURE"
        
        # Инициализация Redis для blacklist
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Проверяем подключение
            if self.redis_client:
                self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis недоступен для JWT blacklist: {e}")
            self.redis_client = None
        
        self.blacklist = TokenBlacklist(self.redis_client)
        
        # Настройки времени жизни токенов
        self.token_lifetimes = {
            TokenType.ACCESS: timedelta(hours=1),
            TokenType.REFRESH: timedelta(days=7),
            TokenType.API: timedelta(days=30),
            TokenType.RESET_PASSWORD: timedelta(minutes=15)
        }
        
        logger.info("Безопасный JWT сервис инициализирован")
    
    def _validate_configuration(self):
        """Критическая валидация конфигурации"""
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        
        # Проверка 1: Секрет должен быть установлен
        if not jwt_secret:
            raise SecurityError("JWT_SECRET_KEY должен быть установлен в переменных окружения")
        
        # Проверка 2: Секрет не должен быть дефолтным
        dangerous_secrets = [
            "your-secret-key", "change-me", "secret", "jwt-secret",
            "default", "password", "123456", "qwerty"
        ]
        
        if jwt_secret.lower() in dangerous_secrets:
            raise SecurityError("JWT_SECRET_KEY не должен быть дефолтным значением")
        
        # Проверка 3: Минимальная длина ключа
        if len(jwt_secret) < 32:
            raise SecurityError("JWT_SECRET_KEY должен быть минимум 32 символа для безопасности")
        
        # Проверка 4: Сложность ключа
        if not self._is_key_complex(jwt_secret):
            logger.warning("JWT_SECRET_KEY имеет низкую сложность. Рекомендуется использовать более сложный ключ")
        
        logger.info("JWT конфигурация прошла валидацию безопасности")
    
    def _get_secret_key(self) -> str:
        """Безопасное получение секретного ключа"""
        secret = os.getenv("JWT_SECRET_KEY")
        
        # Дополнительная проверка во время выполнения
        if not secret or len(secret) < 32:
            raise SecurityError("Критическая ошибка конфигурации JWT")
        
        return secret
    
    def _is_key_complex(self, key: str) -> bool:
        """Проверка сложности ключа"""
        has_upper = any(c.isupper() for c in key)
        has_lower = any(c.islower() for c in key)
        has_digit = any(c.isdigit() for c in key)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in key)
        
        return sum([has_upper, has_lower, has_digit, has_special]) >= 3
    
    def create_token(self, user_id: int, username: Optional[str] = None, 
                     roles: Optional[List[str]] = None, permissions: Optional[List[str]] = None,
                     token_type: TokenType = TokenType.ACCESS,
                     custom_expires: Optional[timedelta] = None) -> str:
        """Создает безопасный JWT токен с обязательными claims"""
        
        try:
            now = datetime.now(timezone.utc)
            expires_delta = custom_expires or self.token_lifetimes.get(token_type, timedelta(hours=1))
            expires_at = now + expires_delta
            
            # Генерируем уникальный JWT ID
            jti = secrets.token_hex(16)
            
            # Создаем claims с обязательными полями
            claims = TokenClaims(
                user_id=user_id,
                username=username,
                roles=roles or [],
                token_type=token_type,
                permissions=permissions or [],
                issued_at=now,
                expires_at=expires_at,
                jwt_id=jti,
                issuer=self.issuer
            )
            
            # Добавляем дополнительные безопасные claims
            payload = claims.to_dict()
            payload.update({
                'aud': 'VHM24R_API',  # Audience
                'nbf': int(now.timestamp()),  # Not before
                'token_hash': hashlib.sha256(f"{user_id}:{jti}:{now.isoformat()}".encode()).hexdigest()[:16]
            })
            
            # Создаем токен
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Создан безопасный JWT токен для пользователя {user_id}, JTI: {jti[:8]}...", extra={
                "user_id": user_id,
                "token_type": token_type.value,
                "jti": jti,
                "expires_at": expires_at.isoformat()
            })
            
            return token
            
        except Exception as e:
            logger.error(f"Ошибка создания JWT токена: {e}")
            raise SecurityError(f"Ошибка создания JWT токена: {str(e)}")
    
    def verify_token(self, token: str, required_type: Optional[TokenType] = None) -> Dict[str, Any]:
        """Верифицирует JWT токен с комплексными проверками"""
        
        try:
            # Декодируем токен с полной валидацией
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    'require_exp': True,      # Обязательный exp claim
                    'require_iat': True,      # Обязательный iat claim
                    'require_nbf': True,      # Обязательный nbf claim
                    'verify_exp': True,       # Проверка истечения
                    'verify_iat': True,       # Проверка времени выдачи
                    'verify_nbf': True,       # Проверка "не раньше чем"
                    'verify_aud': True,       # Проверка audience
                    'verify_iss': True        # Проверка issuer
                },
                audience='VHM24R_API',
                issuer=self.issuer
            )
            
            # Проверяем обязательные claims
            required_claims = ['sub', 'jti', 'token_type', 'iat', 'exp']
            for claim in required_claims:
                if claim not in payload:
                    raise jwt.InvalidTokenError(f"Отсутствует обязательный claim: {claim}")
            
            jti = payload.get('jti')
            
            # Проверяем blacklist
            if self.blacklist.is_blacklisted(jti):
                blacklist_info = self.blacklist.get_blacklist_info(jti)
                reason = blacklist_info.get('reason', 'unknown') if blacklist_info else 'unknown'
                logger.warning(f"Попытка использования отозванного токена", extra={
                    "jti": jti,
                    "reason": reason
                })
                raise jwt.InvalidTokenError(f"Токен отозван: {reason}")
            
            # Проверяем тип токена если требуется
            token_type_str = payload.get('token_type')
            if required_type and token_type_str != required_type.value:
                raise jwt.InvalidTokenError(f"Неверный тип токена. Ожидался: {required_type.value}, получен: {token_type_str}")
            
            # Проверяем целостность токена
            user_id = payload.get('sub')
            token_hash = payload.get('token_hash')
            iat = payload.get('iat')
            
            if iat:
                expected_hash = hashlib.sha256(f"{user_id}:{jti}:{datetime.fromtimestamp(iat, timezone.utc).isoformat()}".encode()).hexdigest()[:16]
                
                if token_hash and token_hash != expected_hash:
                    logger.error(f"Нарушена целостность токена", extra={
                        "jti": jti,
                        "user_id": user_id
                    })
                    raise jwt.InvalidTokenError("Нарушена целостность токена")
            
            logger.info(f"JWT токен успешно верифицирован: JTI {jti[:8]}..., пользователь {user_id}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Попытка использования истекшего JWT токена")
            raise SecurityError("Токен истек")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Недействительный JWT токен: {e}")
            raise SecurityError(f"Недействительный токен: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка верификации JWT токена: {e}")
            raise SecurityError(f"Ошибка верификации JWT токена: {str(e)}")
    
    def revoke_token(self, token: str, reason: str = "revoked"):
        """Отзывает токен, добавляя его в blacklist"""
        try:
            # Декодируем токен чтобы получить claims
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={'verify_exp': False}  # Разрешаем отзыв истекшего токена
            )
            
            jti = payload.get('jti')
            exp = payload.get('exp', int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()))
            user_id = payload.get('sub')
            
            if jti:
                self.blacklist.add_token(jti, exp, reason)
                logger.info(f"Токен отозван: JTI {jti[:8]}..., причина: {reason}", extra={
                    "jti": jti,
                    "user_id": user_id,
                    "reason": reason
                })
            else:
                raise SecurityError("Токен не содержит JTI")
                
        except jwt.InvalidTokenError:
            # Даже если токен невалидный, логируем попытку отзыва
            logger.warning("Попытка отзыва невалидного токена")
            raise SecurityError("Невозможно отозвать невалидный токен")
        except Exception as e:
            logger.error(f"Ошибка отзыва токена: {e}")
            raise SecurityError(f"Ошибка отзыва токена: {str(e)}")
    
    def revoke_all_user_tokens(self, user_id: int, reason: str = "security_measure"):
        """Отзывает все токены пользователя"""
        try:
            if self.redis_client:
                # Используем паттерн для поиска токенов пользователя
                # В production нужно будет реализовать более эффективный способ
                pattern = f"user_tokens:{user_id}:*"
                try:
                    keys = self.redis_client.keys(pattern) or []
                except Exception:
                    keys = []
                
                for key in keys:
                    try:
                        token_data = self.redis_client.get(key)
                        if token_data:
                            token_info = json.loads(str(token_data))
                            jti = token_info.get('jti')
                            exp = token_info.get('exp')
                            
                            if jti and exp:
                                self.blacklist.add_token(jti, exp, reason)
                    except Exception as e:
                        logger.warning(f"Ошибка обработки ключа {key}: {e}")
                        continue
                
                logger.info(f"Отозваны все токены пользователя {user_id}: {len(keys)} токенов", extra={
                    "user_id": user_id,
                    "reason": reason,
                    "tokens_count": len(keys)
                })
            else:
                logger.warning("Redis недоступен для массового отзыва токенов")
                
        except Exception as e:
            logger.error(f"Ошибка массового отзыва токенов: {e}")
            raise SecurityError(f"Ошибка массового отзыва токенов: {str(e)}")
    
    def rotate_secret_key(self, new_secret: str):
        """Ротация секретного ключа (осторожно!)"""
        try:
            # Валидируем новый ключ
            if len(new_secret) < 32:
                raise SecurityError("Новый секретный ключ должен быть минимум 32 символа")
            
            if not self._is_key_complex(new_secret):
                logger.warning("Новый ключ имеет низкую сложность")
            
            old_secret = self.secret_key
            self.secret_key = new_secret
            
            logger.critical("JWT секретный ключ был ротирован! Все старые токены стали недействительными", extra={
                "rotated_at": datetime.now(timezone.utc).isoformat(),
                "old_key_hash": hashlib.sha256(old_secret.encode()).hexdigest()[:16],
                "new_key_hash": hashlib.sha256(new_secret.encode()).hexdigest()[:16]
            })
            
        except Exception as e:
            logger.error(f"Ошибка ротации секретного ключа: {e}")
            raise SecurityError(f"Ошибка ротации секретного ключа: {str(e)}")
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """Получает информацию о токене без верификации подписи"""
        try:
            # Декодируем только заголовок и payload, без проверки подписи
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            
            return {
                'jti': unverified_payload.get('jti'),
                'user_id': unverified_payload.get('sub'),
                'token_type': unverified_payload.get('token_type'),
                'issued_at': datetime.fromtimestamp(unverified_payload.get('iat', 0), timezone.utc).isoformat(),
                'expires_at': datetime.fromtimestamp(unverified_payload.get('exp', 0), timezone.utc).isoformat(),
                'is_expired': datetime.now(timezone.utc) > datetime.fromtimestamp(unverified_payload.get('exp', 0), timezone.utc),
                'issuer': unverified_payload.get('iss')
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о токене: {e}")
            return {'error': str(e)}

# Глобальный экземпляр безопасного JWT сервиса
secure_jwt_service = SecureJWTService()

# Функции-обертки для использования в других модулях
def create_access_token(user_id: int, username: Optional[str] = None, roles: Optional[List[str]] = None, 
                       permissions: Optional[List[str]] = None) -> str:
    """Создает access токен"""
    return secure_jwt_service.create_token(user_id, username, roles, permissions, TokenType.ACCESS)

def create_refresh_token(user_id: int, username: Optional[str] = None) -> str:
    """Создает refresh токен"""
    return secure_jwt_service.create_token(user_id, username, [], [], TokenType.REFRESH)

def verify_access_token(token: str) -> Dict[str, Any]:
    """Верифицирует access токен"""
    return secure_jwt_service.verify_token(token, TokenType.ACCESS)

def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Верифицирует refresh токен"""
    return secure_jwt_service.verify_token(token, TokenType.REFRESH)

def revoke_token(token: str, reason: str = "revoked"):
    """Отзывает токен"""
    return secure_jwt_service.revoke_token(token, reason)

def revoke_all_user_tokens(user_id: int, reason: str = "security_measure"):
    """Отзывает все токены пользователя"""
    return secure_jwt_service.revoke_all_user_tokens(user_id, reason)
