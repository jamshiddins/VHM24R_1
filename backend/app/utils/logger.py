import logging
import structlog
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json
import os

def setup_logging(level: str = "INFO", use_json: bool = True) -> None:
    """
    Настройка структурированного логирования для VHM24R
    
    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        use_json: Использовать JSON формат для логов
    """
    
    # Очищаем существующие handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Настройка уровня логирования
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    if use_json:
        # JSON формат для production
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': self.formatTime(record, self.datefmt),
                    'name': record.name,
                    'level': record.levelname,
                    'message': record.getMessage(),
                }
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                return json.dumps(log_entry, ensure_ascii=False)
        
        formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
    else:
        # Человеко-читаемый формат для development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Создаем handler для stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    
    # Настройка корневого логгера
    logging.root.setLevel(log_level)
    logging.root.addHandler(handler)
    
    # Настройка structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str):
    """
    Получение структурированного логгера
    
    Args:
        name: Имя логгера (обычно __name__)
    
    Returns:
        Настроенный structlog логгер
    """
    return structlog.get_logger(name)

class ContextLogger:
    """
    Контекстный логгер для добавления дополнительной информации в логи
    """
    
    def __init__(self, logger, **context):
        self.logger = logger.bind(**context)
        self.context = context
    
    def bind(self, **kwargs) -> 'ContextLogger':
        """Добавление дополнительного контекста"""
        new_context = {**self.context, **kwargs}
        return ContextLogger(
            structlog.get_logger(self.logger._logger.name), 
            **new_context
        )
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        self.logger.exception(message, **kwargs)

def get_context_logger(name: str, **context) -> ContextLogger:
    """
    Получение контекстного логгера
    
    Args:
        name: Имя логгера
        **context: Контекстная информация
    
    Returns:
        ContextLogger с предустановленным контекстом
    """
    logger = get_logger(name)
    return ContextLogger(logger, **context)

def log_function_call(func_name: str, args: Optional[Dict[str, Any]] = None, **context):
    """
    Декоратор для логирования вызовов функций
    """
    def decorator(func):
        def wrapper(*args_inner, **kwargs_inner):
            logger = get_logger(func.__module__)
            
            # Логируем начало выполнения
            logger.info(
                f"Function {func_name} started",
                function=func_name,
                args_count=len(args_inner),
                kwargs_count=len(kwargs_inner),
                **context
            )
            
            start_time = datetime.now()
            
            try:
                result = func(*args_inner, **kwargs_inner)
                
                # Логируем успешное завершение
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Function {func_name} completed successfully",
                    function=func_name,
                    execution_time=execution_time,
                    **context
                )
                
                return result
                
            except Exception as e:
                # Логируем ошибку
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Function {func_name} failed",
                    function=func_name,
                    execution_time=execution_time,
                    error=str(e),
                    error_type=type(e).__name__,
                    **context
                )
                raise
        
        return wrapper
    return decorator

class DatabaseLogger:
    """
    Специализированный логгер для операций с базой данных
    """
    
    def __init__(self):
        self.logger = get_logger("database")
    
    def log_query(self, operation: str, table: str, filters: Optional[Dict] = None, **context):
        """Логирование SQL запросов"""
        self.logger.info(
            f"Database {operation} operation",
            operation=operation,
            table=table,
            filters=filters,
            **context
        )
    
    def log_transaction_start(self, transaction_id: str):
        """Логирование начала транзакции"""
        self.logger.info(
            "Database transaction started",
            transaction_id=transaction_id
        )
    
    def log_transaction_commit(self, transaction_id: str, operations_count: int = 0):
        """Логирование коммита транзакции"""
        self.logger.info(
            "Database transaction committed",
            transaction_id=transaction_id,
            operations_count=operations_count
        )
    
    def log_transaction_rollback(self, transaction_id: str, error: str):
        """Логирование отката транзакции"""
        self.logger.error(
            "Database transaction rolled back",
            transaction_id=transaction_id,
            error=error
        )

class SecurityLogger:
    """
    Специализированный логгер для событий безопасности
    """
    
    def __init__(self):
        self.logger = get_logger("security")
    
    def log_authentication_attempt(self, user_id: Optional[str], success: bool, method: str, ip_address: Optional[str] = None):
        """Логирование попыток аутентификации"""
        self.logger.info(
            "Authentication attempt",
            user_id=user_id,
            success=success,
            method=method,
            ip_address=ip_address,
            severity="high" if not success else "low"
        )
    
    def log_authorization_failure(self, user_id: str, resource: str, action: str, ip_address: Optional[str] = None):
        """Логирование неудачных попыток авторизации"""
        self.logger.warning(
            "Authorization failed",
            user_id=user_id,
            resource=resource,
            action=action,
            ip_address=ip_address,
            severity="medium"
        )
    
    def log_suspicious_activity(self, description: str, user_id: Optional[str] = None, ip_address: Optional[str] = None, **context):
        """Логирование подозрительной активности"""
        self.logger.error(
            f"Suspicious activity detected: {description}",
            user_id=user_id,
            ip_address=ip_address,
            severity="high",
            **context
        )

class PerformanceLogger:
    """
    Логгер для мониторинга производительности
    """
    
    def __init__(self):
        self.logger = get_logger("performance")
    
    def log_slow_query(self, query: str, execution_time: float, threshold: float = 1.0):
        """Логирование медленных запросов"""
        if execution_time > threshold:
            self.logger.warning(
                "Slow database query detected",
                query=query[:200] + "..." if len(query) > 200 else query,
                execution_time=execution_time,
                threshold=threshold,
                severity="medium"
            )
    
    def log_high_memory_usage(self, memory_usage: float, threshold: float = 80.0):
        """Логирование высокого использования памяти"""
        if memory_usage > threshold:
            self.logger.warning(
                "High memory usage detected",
                memory_usage=memory_usage,
                threshold=threshold,
                severity="medium"
            )
    
    def log_api_performance(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Логирование производительности API"""
        severity = "high" if response_time > 5.0 else "medium" if response_time > 2.0 else "low"
        
        self.logger.info(
            "API request performance",
            endpoint=endpoint,
            method=method,
            response_time=response_time,
            status_code=status_code,
            severity=severity
        )

# Глобальные экземпляры специализированных логгеров
db_logger = DatabaseLogger()
security_logger = SecurityLogger()
performance_logger = PerformanceLogger()

# Инициализация логирования при импорте модуля
if not os.getenv("TESTING"):  # Не инициализируем во время тестов
    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        use_json=os.getenv("LOG_FORMAT", "json").lower() == "json"
    )
