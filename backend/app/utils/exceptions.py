"""
Пользовательские исключения для VHM24R системы
"""

from typing import Optional, Dict, Any
import traceback
from datetime import datetime


class VHMException(Exception):
    """Базовое исключение для VHM24R системы"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow()
        self.traceback_str = traceback.format_exc() if original_exception else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует исключение в словарь для логирования"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'original_exception': str(self.original_exception) if self.original_exception else None,
            'traceback': self.traceback_str
        }


class AuthenticationError(VHMException):
    """Ошибки аутентификации"""
    
    def __init__(
        self, 
        message: str = "Ошибка аутентификации",
        user_id: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs
    ):
        details = {
            'user_id': user_id,
            'authentication_method': method,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="AUTH_ERROR", details=details, **kwargs)


class AuthorizationError(VHMException):
    """Ошибки авторизации"""
    
    def __init__(
        self, 
        message: str = "Недостаточно прав доступа",
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs
    ):
        details = {
            'user_id': user_id,
            'resource': resource,
            'action': action,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="AUTHZ_ERROR", details=details, **kwargs)


class TokenError(AuthenticationError):
    """Ошибки работы с токенами"""
    
    def __init__(
        self, 
        message: str = "Ошибка токена",
        token_type: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ):
        details = {
            'token_type': token_type,
            'reason': reason,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="TOKEN_ERROR", details=details, **kwargs)


class DatabaseError(VHMException):
    """Ошибки работы с базой данных"""
    
    def __init__(
        self, 
        message: str = "Ошибка базы данных",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ):
        details = {
            'operation': operation,
            'table': table,
            'query': query[:200] + '...' if query and len(query) > 200 else query,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="DB_ERROR", details=details, **kwargs)


class FileProcessingError(VHMException):
    """Ошибки обработки файлов"""
    
    def __init__(
        self, 
        message: str = "Ошибка обработки файла",
        filename: Optional[str] = None,
        file_format: Optional[str] = None,
        file_size: Optional[int] = None,
        processing_stage: Optional[str] = None,
        **kwargs
    ):
        details = {
            'filename': filename,
            'file_format': file_format,
            'file_size': file_size,
            'processing_stage': processing_stage,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="FILE_ERROR", details=details, **kwargs)


class ValidationError(VHMException):
    """Ошибки валидации данных"""
    
    def __init__(
        self, 
        message: str = "Ошибка валидации",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        **kwargs
    ):
        details = {
            'field': field,
            'value': str(value) if value is not None else None,
            'validation_rule': validation_rule,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="VALIDATION_ERROR", details=details, **kwargs)


class BusinessLogicError(VHMException):
    """Ошибки бизнес-логики"""
    
    def __init__(
        self, 
        message: str = "Ошибка бизнес-логики",
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = {
            'operation': operation,
            'context': context,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="BUSINESS_ERROR", details=details, **kwargs)


class ExternalServiceError(VHMException):
    """Ошибки внешних сервисов"""
    
    def __init__(
        self, 
        message: str = "Ошибка внешнего сервиса",
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        **kwargs
    ):
        details = {
            'service_name': service_name,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_text': response_text[:500] + '...' if response_text and len(response_text) > 500 else response_text,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="EXTERNAL_ERROR", details=details, **kwargs)


class ConfigurationError(VHMException):
    """Ошибки конфигурации"""
    
    def __init__(
        self, 
        message: str = "Ошибка конфигурации",
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
        **kwargs
    ):
        details = {
            'config_key': config_key,
            'config_value': config_value,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="CONFIG_ERROR", details=details, **kwargs)


class RateLimitError(VHMException):
    """Ошибки превышения лимита запросов"""
    
    def __init__(
        self, 
        message: str = "Превышен лимит запросов",
        limit: Optional[int] = None,
        period: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = {
            'limit': limit,
            'period': period,
            'retry_after': retry_after,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="RATE_LIMIT_ERROR", details=details, **kwargs)


class SecurityError(VHMException):
    """Ошибки безопасности"""
    
    def __init__(
        self, 
        message: str = "Нарушение безопасности",
        security_violation: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        details = {
            'security_violation': security_violation,
            'user_id': user_id,
            'ip_address': ip_address,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="SECURITY_ERROR", details=details, **kwargs)


class TelegramAPIError(ExternalServiceError):
    """Ошибки Telegram API"""
    
    def __init__(
        self, 
        message: str = "Ошибка Telegram API",
        method: Optional[str] = None,
        chat_id: Optional[str] = None,
        **kwargs
    ):
        details = {
            'telegram_method': method,
            'chat_id': chat_id,
            **kwargs.get('details', {})
        }
        super().__init__(
            message, 
            service_name="telegram",
            error_code="TELEGRAM_ERROR",
            details=details,
            **kwargs
        )


class PaymentError(VHMException):
    """Ошибки платежной системы"""
    
    def __init__(
        self, 
        message: str = "Ошибка платежа",
        payment_system: Optional[str] = None,
        transaction_id: Optional[str] = None,
        amount: Optional[float] = None,
        **kwargs
    ):
        details = {
            'payment_system': payment_system,
            'transaction_id': transaction_id,
            'amount': amount,
            **kwargs.get('details', {})
        }
        super().__init__(message, error_code="PAYMENT_ERROR", details=details, **kwargs)


# Функции-хелперы для создания исключений

def handle_database_error(operation: str, table: Optional[str] = None, original_error: Optional[Exception] = None) -> DatabaseError:
    """
    Создает DatabaseError с контекстной информацией
    """
    message = f"Ошибка при выполнении операции '{operation}'"
    if table:
        message += f" над таблицей '{table}'"
    
    return DatabaseError(
        message=message,
        operation=operation,
        table=table,
        original_exception=original_error
    )


def handle_file_processing_error(
    filename: str, 
    stage: str, 
    original_error: Optional[Exception] = None
) -> FileProcessingError:
    """
    Создает FileProcessingError с контекстной информацией
    """
    return FileProcessingError(
        message=f"Ошибка при обработке файла '{filename}' на этапе '{stage}'",
        filename=filename,
        processing_stage=stage,
        original_exception=original_error
    )


def handle_validation_error(field: str, value: Any, rule: str) -> ValidationError:
    """
    Создает ValidationError с контекстной информацией
    """
    return ValidationError(
        message=f"Значение '{value}' поля '{field}' не прошло валидацию '{rule}'",
        field=field,
        value=value,
        validation_rule=rule
    )


def handle_authentication_error(user_id: Optional[str] = None, method: Optional[str] = None) -> AuthenticationError:
    """
    Создает AuthenticationError с контекстной информацией
    """
    message = "Не удалось аутентифицировать пользователя"
    if user_id:
        message += f" (ID: {user_id})"
    if method:
        message += f" методом '{method}'"
    
    return AuthenticationError(
        message=message,
        user_id=user_id,
        method=method
    )


def handle_authorization_error(
    user_id: str, 
    resource: str, 
    action: str
) -> AuthorizationError:
    """
    Создает AuthorizationError с контекстной информацией
    """
    return AuthorizationError(
        message=f"Пользователь {user_id} не имеет прав на действие '{action}' над ресурсом '{resource}'",
        user_id=user_id,
        resource=resource,
        action=action
    )


# Мапа для преобразования стандартных исключений в VHM исключения
EXCEPTION_MAPPING = {
    ConnectionError: lambda e: ExternalServiceError(
        message="Ошибка соединения с внешним сервисом",
        original_exception=e
    ),
    TimeoutError: lambda e: ExternalServiceError(
        message="Таймаут при обращении к внешнему сервису",
        original_exception=e
    ),
    ValueError: lambda e: ValidationError(
        message=f"Некорректное значение: {str(e)}",
        original_exception=e
    ),
    FileNotFoundError: lambda e: FileProcessingError(
        message=f"Файл не найден: {str(e)}",
        original_exception=e
    ),
    PermissionError: lambda e: AuthorizationError(
        message=f"Недостаточно прав: {str(e)}",
        original_exception=e
    )
}


def convert_exception(exception: Exception) -> VHMException:
    """
    Преобразует стандартное исключение в VHM исключение
    """
    if isinstance(exception, VHMException):
        return exception
    
    exception_type = type(exception)
    if exception_type in EXCEPTION_MAPPING:
        return EXCEPTION_MAPPING[exception_type](exception)
    
    # Если нет специального маппинга, создаем общее VHM исключение
    return VHMException(
        message=f"Неожиданная ошибка: {str(exception)}",
        error_code="UNEXPECTED_ERROR",
        original_exception=exception
    )
