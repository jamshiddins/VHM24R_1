"""
Security middleware для FastAPI приложения
"""
import os
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware для принудительного перенаправления HTTP на HTTPS
    """
    
    def __init__(self, app, force_https: bool = False):
        super().__init__(app)
        # Автоматически определяем необходимость HTTPS в production
        if force_https is None:
            self.force_https = os.getenv("ENVIRONMENT", "development") == "production"
        else:
            self.force_https = bool(force_https)
        
        # Исключения для локальной разработки и health checks
        self.excluded_paths = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        
        logger.info(f"HTTPS Enforcement: {'enabled' if self.force_https else 'disabled'}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Пропускаем исключенные пути
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Пропускаем если HTTPS не требуется
        if not self.force_https:
            return await call_next(request)
        
        # Проверяем заголовки от прокси (Railway, Heroku, etc.)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_ssl = request.headers.get("x-forwarded-ssl")
        
        # Определяем, используется ли HTTPS
        is_https = (
            request.url.scheme == "https" or
            forwarded_proto == "https" or
            forwarded_ssl == "on"
        )
        
        # Если не HTTPS, перенаправляем
        if not is_https:
            # Строим HTTPS URL
            https_url = request.url.replace(scheme="https")
            
            logger.warning(f"Redirecting HTTP to HTTPS: {request.url} -> {https_url}")
            
            return RedirectResponse(
                url=str(https_url),
                status_code=301  # Permanent redirect
            )
        
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware для добавления security заголовков
    """
    
    def __init__(self, app):
        super().__init__(app)
        
        # Конфигурация security заголовков
        self.security_headers = {
            # Предотвращает clickjacking
            "X-Frame-Options": "DENY",
            
            # Предотвращает MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Включает XSS защиту браузера
            "X-XSS-Protection": "1; mode=block",
            
            # Строгая транспортная безопасность (только для HTTPS)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Контролирует referrer информацию
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://telegram.org; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https: wss:; "
                "frame-src 'self' https://telegram.org;"
            ),
            
            # Permissions Policy (замена Feature-Policy)
            "Permissions-Policy": (
                "camera=(), "
                "microphone=(), "
                "geolocation=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "accelerometer=(), "
                "gyroscope=()"
            )
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Добавляем security заголовки
        for header, value in self.security_headers.items():
            # HSTS только для HTTPS
            if header == "Strict-Transport-Security":
                if (request.url.scheme == "https" or 
                    request.headers.get("x-forwarded-proto") == "https"):
                    response.headers[header] = value
            else:
                response.headers[header] = value
        
        return response


class RateLimitSecurityMiddleware(BaseHTTPMiddleware):
    """
    Дополнительная защита от злоупотреблений
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.suspicious_patterns = [
            # SQL injection попытки
            "union select",
            "drop table",
            "insert into",
            "delete from",
            
            # XSS попытки
            "<script",
            "javascript:",
            "onerror=",
            "onload=",
            
            # Path traversal
            "../",
            "..\\",
            "/etc/passwd",
            "/proc/",
            
            # Command injection
            "; cat ",
            "| nc ",
            "&& curl",
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Проверяем URL и параметры на подозрительные паттерны
        full_url = str(request.url).lower()
        
        for pattern in self.suspicious_patterns:
            if pattern in full_url:
                client_host = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
                logger.warning(f"Suspicious request blocked: {client_host} -> {request.url}")
                
                # Возвращаем 403 Forbidden
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request blocked by security policy"}
                )
        
        # Проверяем размер запроса
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = 50 * 1024 * 1024  # 50MB
                
                if size > max_size:
                    client_host = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
                    logger.warning(f"Large request blocked: {size} bytes from {client_host}")
                    
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request too large"}
                    )
            except ValueError:
                pass
        
        return await call_next(request)


def setup_security_middleware(app):
    """
    Настройка всех security middleware
    """
    # Порядок важен - от внешнего к внутреннему
    
    # 1. HTTPS принуждение (самый внешний)
    app.add_middleware(HTTPSRedirectMiddleware)
    
    # 2. Security заголовки
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 3. Дополнительная защита от злоупотреблений
    app.add_middleware(RateLimitSecurityMiddleware)
    
    logger.info("Security middleware configured successfully")
