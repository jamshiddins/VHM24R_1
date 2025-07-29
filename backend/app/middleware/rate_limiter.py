"""
Rate Limiting Middleware для защиты от DDoS атак
"""
import time
import redis
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate Limiter с поддержкой Redis и in-memory fallback
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client = None
        self.memory_store: Dict[str, Dict] = {}
        
        # Пытаемся подключиться к Redis
        if redis_url:
            try:
                redis_client = redis.from_url(redis_url, decode_responses=True)
                redis_client.ping()
                self.redis_client = redis_client
                logger.info("Rate limiter connected to Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory store.")
                self.redis_client = None
        else:
            logger.info("No Redis URL provided. Using in-memory rate limiting.")
    
    def _get_client_id(self, request: Request) -> str:
        """Получение идентификатора клиента"""
        # Приоритет: Authorization header > X-Forwarded-For > Remote IP
        auth_header = request.headers.get("authorization")
        if auth_header:
            return f"auth:{hash(auth_header)}"
        
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _get_rate_limit_key(self, client_id: str, endpoint: str, window: str) -> str:
        """Генерация ключа для rate limiting"""
        return f"rate_limit:{client_id}:{endpoint}:{window}"
    
    def _check_redis_limit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Проверка лимита через Redis"""
        if not self.redis_client:
            return True, 0, limit
            
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = pipe.execute()
            
            current_count = results[0]
            remaining = max(0, limit - current_count)
            
            return current_count <= limit, current_count, remaining
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return True, 0, limit  # Fallback: разрешаем запрос
    
    def _check_memory_limit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Проверка лимита через in-memory store"""
        now = time.time()
        
        # Очистка старых записей
        self._cleanup_memory_store(now)
        
        if key not in self.memory_store:
            self.memory_store[key] = {
                'count': 0,
                'window_start': now,
                'expires_at': now + window_seconds
            }
        
        entry = self.memory_store[key]
        
        # Если окно истекло, сбрасываем счетчик
        if now >= entry['expires_at']:
            entry['count'] = 0
            entry['window_start'] = now
            entry['expires_at'] = now + window_seconds
        
        entry['count'] += 1
        current_count = entry['count']
        remaining = max(0, limit - current_count)
        
        return current_count <= limit, current_count, remaining
    
    def _cleanup_memory_store(self, now: float):
        """Очистка устаревших записей из памяти"""
        expired_keys = [
            key for key, entry in self.memory_store.items()
            if now >= entry['expires_at']
        ]
        for key in expired_keys:
            del self.memory_store[key]
    
    def check_rate_limit(
        self, 
        request: Request, 
        limit: int, 
        window_seconds: int,
        endpoint: Optional[str] = None
    ) -> tuple[bool, int, int]:
        """
        Проверка rate limit
        
        Returns:
            (allowed, current_count, remaining)
        """
        client_id = self._get_client_id(request)
        endpoint = endpoint or request.url.path
        window = str(window_seconds)
        
        key = self._get_rate_limit_key(client_id, endpoint, window)
        
        if self.redis_client:
            return self._check_redis_limit(key, limit, window_seconds)
        else:
            return self._check_memory_limit(key, limit, window_seconds)


# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter(os.getenv("REDIS_URL"))


def create_rate_limit_middleware(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10
):
    """
    Создание middleware для rate limiting
    """
    
    async def rate_limit_middleware(request: Request, call_next):
        """Rate limiting middleware"""
        
        # Исключения для определенных путей
        excluded_paths = ["/health", "/docs", "/openapi.json", "/favicon.ico"]
        if request.url.path in excluded_paths:
            return await call_next(request)
        
        # Проверка burst limit (10 запросов в 10 секунд)
        allowed, current, remaining = rate_limiter.check_rate_limit(
            request, burst_limit, 10, "burst"
        )
        
        if not allowed:
            logger.warning(f"Burst limit exceeded for {rate_limiter._get_client_id(request)}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too many requests",
                    "detail": "Burst limit exceeded. Please slow down.",
                    "retry_after": 10
                },
                headers={
                    "X-RateLimit-Limit": str(burst_limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time()) + 10),
                    "Retry-After": "10"
                }
            )
        
        # Проверка минутного лимита
        allowed, current, remaining = rate_limiter.check_rate_limit(
            request, requests_per_minute, 60, "minute"
        )
        
        if not allowed:
            logger.warning(f"Minute limit exceeded for {rate_limiter._get_client_id(request)}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too many requests",
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit": str(requests_per_minute),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time()) + 60),
                    "Retry-After": "60"
                }
            )
        
        # Проверка часового лимита
        allowed, current, remaining = rate_limiter.check_rate_limit(
            request, requests_per_hour, 3600, "hour"
        )
        
        if not allowed:
            logger.warning(f"Hour limit exceeded for {rate_limiter._get_client_id(request)}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too many requests",
                    "detail": "Hourly rate limit exceeded. Please try again later.",
                    "retry_after": 3600
                },
                headers={
                    "X-RateLimit-Limit": str(requests_per_hour),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time()) + 3600),
                    "Retry-After": "3600"
                }
            )
        
        # Добавляем заголовки rate limit к ответу
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit-Minute"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining)
        response.headers["X-RateLimit-Reset-Minute"] = str(int(time.time()) + 60)
        
        return response
    
    return rate_limit_middleware


def create_strict_rate_limit_middleware(
    requests_per_minute: int = 10,
    requests_per_hour: int = 100
):
    """
    Создание строгого middleware для критических эндпоинтов
    """
    
    async def strict_rate_limit_middleware(request: Request, call_next):
        """Строгий rate limiting для критических операций"""
        
        # Применяется только к определенным путям
        strict_paths = ["/api/files/upload", "/api/auth/telegram", "/webhook/telegram"]
        if request.url.path not in strict_paths:
            return await call_next(request)
        
        # Проверка минутного лимита
        allowed, current, remaining = rate_limiter.check_rate_limit(
            request, requests_per_minute, 60, f"strict_minute_{request.url.path}"
        )
        
        if not allowed:
            logger.warning(f"Strict minute limit exceeded for {rate_limiter._get_client_id(request)} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests to {request.url.path}. Limit: {requests_per_minute}/minute",
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit": str(requests_per_minute),
                    "X-RateLimit-Remaining": str(remaining),
                    "Retry-After": "60"
                }
            )
        
        # Проверка часового лимита
        allowed, current, remaining = rate_limiter.check_rate_limit(
            request, requests_per_hour, 3600, f"strict_hour_{request.url.path}"
        )
        
        if not allowed:
            logger.warning(f"Strict hour limit exceeded for {rate_limiter._get_client_id(request)} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests to {request.url.path}. Limit: {requests_per_hour}/hour",
                    "retry_after": 3600
                },
                headers={
                    "X-RateLimit-Limit": str(requests_per_hour),
                    "X-RateLimit-Remaining": str(remaining),
                    "Retry-After": "3600"
                }
            )
        
        return await call_next(request)
    
    return strict_rate_limit_middleware


class IPWhitelist:
    """Whitelist для доверенных IP адресов"""
    
    def __init__(self, whitelist: Optional[list[str]] = None):
        self.whitelist = set(whitelist or [])
        # Добавляем локальные адреса по умолчанию
        self.whitelist.update([
            "127.0.0.1",
            "localhost",
            "::1"
        ])
    
    def is_whitelisted(self, ip: str) -> bool:
        """Проверка, находится ли IP в whitelist"""
        return ip in self.whitelist
    
    def add_ip(self, ip: str):
        """Добавление IP в whitelist"""
        self.whitelist.add(ip)
    
    def remove_ip(self, ip: str):
        """Удаление IP из whitelist"""
        self.whitelist.discard(ip)


# Глобальный whitelist
ip_whitelist = IPWhitelist()


def create_whitelist_middleware():
    """Создание middleware для IP whitelist"""
    
    async def whitelist_middleware(request: Request, call_next):
        """IP whitelist middleware"""
        
        # Получаем IP клиента
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Проверяем whitelist для административных путей
        admin_paths = ["/api/admin/", "/admin/"]
        is_admin_path = any(request.url.path.startswith(path) for path in admin_paths)
        
        if is_admin_path and not ip_whitelist.is_whitelisted(client_ip):
            logger.warning(f"Access denied for IP {client_ip} to admin path {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "detail": "Your IP address is not authorized to access this resource"
                }
            )
        
        return await call_next(request)
    
    return whitelist_middleware


def create_security_headers_middleware():
    """Создание middleware для добавления security headers"""
    
    async def security_headers_middleware(request: Request, call_next):
        """Security headers middleware"""
        
        response = await call_next(request)
        
        # Добавляем security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://telegram.org https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "font-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # HSTS для HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
    
    return security_headers_middleware
