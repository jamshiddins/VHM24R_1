"""
Middleware для обработки ошибок в VHM24R системе
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import traceback
from typing import Any, Dict
import time

from ..utils.logger import get_logger, security_logger
from ..utils.exceptions import (
    VHMException, 
    DatabaseError, 
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    FileProcessingError,
    ExternalServiceError,
    RateLimitError,
    SecurityError,
    convert_exception
)

logger = get_logger(__name__)

class ErrorHandlerMiddleware:
    """
    Middleware для централизованной обработки ошибок
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        start_time = time.time()
        
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            # Обрабатываем исключение и отправляем ответ
            response = await self.handle_exception(request, e, start_time)
            await response(scope, receive, send)

    async def handle_exception(self, request: Request, exc: Exception, start_time: float) -> JSONResponse:
        """
        Обрабатывает исключение и возвращает JSON ответ
        """
        
        # Получаем информацию о запросе
        method = request.method
        url = str(request.url)
        user_agent = request.headers.get("user-agent", "")
        client_ip = self.get_client_ip(request)
        execution_time = time.time() - start_time
        
        # Преобразуем исключение в VHM исключение если нужно
        if not isinstance(exc, VHMException):
            exc = convert_exception(exc)
        
        # Логируем ошибку
        error_context = {
            'method': method,
            'url': url,
            'client_ip': client_ip,
            'user_agent': user_agent,
            'execution_time': execution_time,
            **exc.to_dict()
        }
        
        # Определяем уровень логирования
        if isinstance(exc, (SecurityError, AuthenticationError)):
            logger.error("Security/Authentication error occurred", **error_context)
            security_logger.log_suspicious_activity(
                description=exc.message,
                user_id=exc.details.get('user_id'),
                ip_address=client_ip
            )
        elif isinstance(exc, DatabaseError):
            logger.error("Database error occurred", **error_context)
        elif isinstance(exc, ExternalServiceError):
            logger.warning("External service error occurred", **error_context)
        elif isinstance(exc, ValidationError):
            logger.info("Validation error occurred", **error_context)
        else:
            logger.error("Unexpected error occurred", **error_context)
        
        # Формируем ответ
        status_code, response_data = self.get_error_response(exc, client_ip)
        
        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={
                "X-Error-ID": f"{exc.error_code}-{int(time.time())}",
                "X-Request-ID": request.headers.get("X-Request-ID", "unknown")
            }
        )
    
    def get_error_response(self, exc: VHMException, client_ip: str) -> tuple[int, Dict[str, Any]]:
        """
        Формирует ответ об ошибке
        """
        
        # Базовая структура ответа
        response_data = {
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "timestamp": exc.timestamp.isoformat()
        }
        
        # Определяем статус код и детали в зависимости от типа ошибки
        if isinstance(exc, AuthenticationError):
            status_code = 401
            response_data["details"] = "Требуется аутентификация"
            
        elif isinstance(exc, AuthorizationError):
            status_code = 403
            response_data["details"] = "Недостаточно прав доступа"
            
        elif isinstance(exc, ValidationError):
            status_code = 422
            response_data["details"] = {
                "field": exc.details.get("field"),
                "validation_rule": exc.details.get("validation_rule")
            }
            
        elif isinstance(exc, FileProcessingError):
            status_code = 400
            response_data["details"] = {
                "filename": exc.details.get("filename"),
                "processing_stage": exc.details.get("processing_stage")
            }
            
        elif isinstance(exc, DatabaseError):
            status_code = 500
            response_data["message"] = "Внутренняя ошибка сервера"
            response_data["details"] = "Временные проблемы с базой данных"
            
        elif isinstance(exc, ExternalServiceError):
            status_code = 502
            response_data["details"] = {
                "service": exc.details.get("service_name", "external"),
                "retry_after": 30
            }
            
        elif isinstance(exc, RateLimitError):
            status_code = 429
            response_data["details"] = {
                "limit": exc.details.get("limit"),
                "retry_after": exc.details.get("retry_after", 60)
            }
            
        elif isinstance(exc, SecurityError):
            status_code = 403
            response_data["message"] = "Доступ запрещен"
            response_data["details"] = "Обнаружена подозрительная активность"
            
        else:
            status_code = 500
            response_data["message"] = "Внутренняя ошибка сервера"
            response_data["details"] = "Попробуйте позже"
        
        # В продакшене не показываем детали системных ошибок
        import os
        if os.getenv("ENVIRONMENT") == "production" and status_code >= 500:
            response_data.pop("details", None)
            if "original_exception" in response_data:
                response_data.pop("original_exception")
        
        return status_code, response_data
    
    def get_client_ip(self, request: Request) -> str:
        """
        Получает IP адрес клиента с учетом прокси
        """
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Берем первый IP из списка
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback на client host
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


# Функции для обработки специфичных исключений FastAPI

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Обработчик ошибок валидации Pydantic
    """
    logger.info(
        "Pydantic validation error",
        url=str(request.url),
        method=request.method,
        errors=exc.errors()
    )
    
    # Формируем читаемое сообщение об ошибке
    error_messages = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": "Ошибка валидации данных",
            "details": {
                "errors": error_messages,
                "fields": [error["loc"][-1] for error in exc.errors()]
            }
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Обработчик HTTP исключений
    """
    logger.info(
        "HTTP exception",
        url=str(request.url),
        method=request.method,
        status_code=exc.status_code,
        detail=exc.detail
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail or "HTTP ошибка",
            "details": {
                "status_code": exc.status_code
            }
        }
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Обработчик Starlette HTTP исключений
    """
    logger.info(
        "Starlette HTTP exception",
        url=str(request.url),
        method=request.method,
        status_code=exc.status_code,
        detail=getattr(exc, 'detail', None)
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": f"HTTP_{exc.status_code}",
            "message": getattr(exc, 'detail', 'HTTP ошибка'),
            "details": {
                "status_code": exc.status_code
            }
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Обработчик ошибок SQLAlchemy
    """
    logger.error(
        "SQLAlchemy error",
        url=str(request.url),
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__
    )
    
    # Преобразуем в DatabaseError
    if isinstance(exc, IntegrityError):
        message = "Нарушение целостности данных"
        error_code = "DB_INTEGRITY_ERROR"
    elif isinstance(exc, OperationalError):
        message = "Ошибка выполнения операции базы данных"
        error_code = "DB_OPERATIONAL_ERROR"
    else:
        message = "Ошибка базы данных"
        error_code = "DB_ERROR"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": error_code,
            "message": message,
            "details": "Временные проблемы с базой данных"
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Общий обработчик исключений
    """
    logger.error(
        "Unhandled exception",
        url=str(request.url),
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
        traceback=traceback.format_exc()
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "INTERNAL_ERROR",
            "message": "Внутренняя ошибка сервера",
            "details": "Попробуйте позже"
        }
    )


# Функция для регистрации всех обработчиков
def register_error_handlers(app):
    """
    Регистрирует все обработчики ошибок в FastAPI приложении
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # Добавляем middleware для VHM исключений
    app.add_middleware(ErrorHandlerMiddleware)
    
    logger.info("Error handlers registered successfully")


def add_error_handling_middleware(app):
    """
    Добавляет middleware для обработки ошибок в FastAPI приложение
    Эта функция является алиасом для register_error_handlers
    """
    register_error_handlers(app)
