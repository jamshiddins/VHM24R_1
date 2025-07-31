"""
Comprehensive система мониторинга для VHM24R
"""
import os
import sys
import time
import psutil
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

from prometheus_client import Counter, Histogram, Gauge, generate_latest, Info, CollectorRegistry, REGISTRY
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

from .utils.logger import get_logger
from .database import get_db
from .services.cache_service import cache_service

logger = get_logger(__name__)

# ==================== PROMETHEUS МЕТРИКИ ====================

# Используем отдельный реестр для тестов
if os.getenv('TESTING') == 'true':
    METRICS_REGISTRY = CollectorRegistry()
else:
    METRICS_REGISTRY = REGISTRY

# Очищаем реестр метрик если он уже содержит метрики (для избежания дублирования)
try:
    # Проверяем есть ли уже наши метрики
    existing_names = []
    for collector, names in METRICS_REGISTRY._collector_to_names.items():
        existing_names.extend(names)
    
    # Если найдены существующие метрики VHM24R - очищаем реестр
    vhm24r_metrics_exist = any('vhm24r' in name for name in existing_names)
    if vhm24r_metrics_exist:
        METRICS_REGISTRY._collector_to_names.clear()
        METRICS_REGISTRY._names_to_collectors.clear()
except:
    # В случае ошибки просто продолжаем
    pass

# Функция для безопасного создания метрик
def create_metric_safe(metric_class, name, description, labels=None, registry=None):
    """Безопасно создает метрику"""
    if registry is None:
        registry = METRICS_REGISTRY
    
    try:
        if labels:
            return metric_class(name, description, labels, registry=registry)
        else:
            return metric_class(name, description, registry=registry)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            # Если метрика уже существует, пытаемся найти её в реестре по имени
            for collector, names in registry._collector_to_names.items():
                if name in names:
                    return collector
            # Если не нашли, создаем новую с измененным именем
            import time
            unique_name = f"{name}_{int(time.time())}"
            if labels:
                return metric_class(unique_name, description, labels, registry=registry)
            else:
                return metric_class(unique_name, description, registry=registry)
        raise

# HTTP метрики - создаем с уникальными именами для избежания конфликтов
HTTP_REQUESTS_TOTAL = create_metric_safe(
    Counter,
    'vhm24r_http_requests_total', 
    'Общее количество HTTP запросов',
    ['method', 'endpoint', 'status_code', 'user_type'],
    METRICS_REGISTRY
)

HTTP_REQUEST_DURATION = create_metric_safe(
    Histogram,
    'http_request_duration_seconds', 
    'Время обработки HTTP запросов',
    ['method', 'endpoint'],
    METRICS_REGISTRY
)

HTTP_REQUEST_SIZE = create_metric_safe(
    Histogram,
    'http_request_size_bytes',
    'Размер HTTP запросов',
    ['method', 'endpoint'],
    METRICS_REGISTRY
)

HTTP_RESPONSE_SIZE = create_metric_safe(
    Histogram,
    'http_response_size_bytes',
    'Размер HTTP ответов',
    ['method', 'endpoint'],
    METRICS_REGISTRY
)

# WebSocket метрики
WEBSOCKET_CONNECTIONS_ACTIVE = create_metric_safe(
    Gauge,
    'websocket_connections_active',
    'Активные WebSocket соединения',
    registry=METRICS_REGISTRY
)

WEBSOCKET_MESSAGES_TOTAL = create_metric_safe(
    Counter,
    'websocket_messages_total',
    'Общее количество WebSocket сообщений',
    ['message_type', 'direction'],
    METRICS_REGISTRY
)

# Метрики обработки файлов
FILE_PROCESSING_DURATION = create_metric_safe(
    Histogram,
    'file_processing_duration_seconds',
    'Время обработки файлов',
    ['file_type', 'processing_stage'],
    METRICS_REGISTRY
)

FILE_PROCESSING_TOTAL = create_metric_safe(
    Counter,
    'file_processing_total',
    'Общее количество обработанных файлов',
    ['file_type', 'status', 'user_type'],
    METRICS_REGISTRY
)

FILE_PROCESSING_ERRORS = create_metric_safe(
    Counter,
    'file_processing_errors_total',
    'Ошибки обработки файлов',
    ['file_type', 'error_type'],
    METRICS_REGISTRY
)

# Метрики базы данных
DATABASE_QUERY_DURATION = create_metric_safe(
    Histogram,
    'database_query_duration_seconds',
    'Время выполнения запросов к БД',
    ['operation', 'table'],
    METRICS_REGISTRY
)

DATABASE_CONNECTIONS_ACTIVE = create_metric_safe(
    Gauge,
    'database_connections_active',
    'Активные соединения с БД',
    registry=METRICS_REGISTRY
)

DATABASE_QUERY_ERRORS = create_metric_safe(
    Counter,
    'database_query_errors_total',
    'Ошибки запросов к БД',
    ['operation', 'error_type'],
    METRICS_REGISTRY
)

# Кэш метрики
CACHE_OPERATIONS_TOTAL = create_metric_safe(
    Counter,
    'cache_operations_total',
    'Операции с кэшем',
    ['operation', 'backend', 'status'],
    METRICS_REGISTRY
)

CACHE_HIT_RATIO = create_metric_safe(
    Gauge,
    'cache_hit_ratio',
    'Процент попаданий в кэш',
    registry=METRICS_REGISTRY
)

# Бизнес метрики
ORDERS_PROCESSED_TOTAL = create_metric_safe(
    Counter,
    'orders_processed_total',
    'Обработанные заказы',
    ['status', 'source'],
    METRICS_REGISTRY
)

USERS_ACTIVE = create_metric_safe(
    Gauge,
    'users_active',
    'Активные пользователи',
    ['period'],
    METRICS_REGISTRY
)

TELEGRAM_API_CALLS = create_metric_safe(
    Counter,
    'telegram_api_calls_total',
    'Вызовы Telegram API',
    ['method', 'status'],
    METRICS_REGISTRY
)

# Системные метрики
SYSTEM_CPU_USAGE = create_metric_safe(
    Gauge, 
    'system_cpu_usage_percent', 
    'Использование CPU', 
    registry=METRICS_REGISTRY
)

SYSTEM_MEMORY_USAGE = create_metric_safe(
    Gauge, 
    'system_memory_usage_percent', 
    'Использование памяти', 
    registry=METRICS_REGISTRY
)

SYSTEM_DISK_USAGE = create_metric_safe(
    Gauge, 
    'system_disk_usage_percent', 
    'Использование диска', 
    registry=METRICS_REGISTRY
)

SYSTEM_LOAD_AVERAGE = create_metric_safe(
    Gauge, 
    'system_load_average', 
    'Средняя нагрузка системы', 
    registry=METRICS_REGISTRY
)

# Информационные метрики
APPLICATION_INFO = create_metric_safe(
    Info,
    'application_info',
    'Информация о приложении',
    registry=METRICS_REGISTRY
)

# ==================== STRUCTURED LOGGING ====================

# Настройка структурированного логирования
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

struct_logger = structlog.get_logger()

# ==================== MONITORING MIDDLEWARE ====================

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора метрик HTTP запросов"""
    
    def __init__(self, app):
        super().__init__(app)
        self.active_requests = 0
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        self.active_requests += 1
        
        # Получаем информацию о запросе
        method = request.method
        url_path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = self._get_client_ip(request)
        request_size = int(request.headers.get("content-length", 0))
        
        # Определяем тип пользователя
        user_type = "anonymous"
        if "authorization" in request.headers:
            user_type = "authenticated"
        
        # Логируем начало запроса
        struct_logger.info(
            "request_started",
            method=method,
            path=url_path,
            client_ip=client_ip,
            user_agent=user_agent,
            request_size=request_size,
            user_type=user_type
        )
        
        try:
            response = await call_next(request)
            
            # Вычисляем метрики
            duration = time.time() - start_time
            response_size = int(response.headers.get("content-length", 0))
            
            # Обновляем Prometheus метрики
            try:
                if hasattr(HTTP_REQUESTS_TOTAL, 'labels'):
                    HTTP_REQUESTS_TOTAL.labels(  # type: ignore
                        method=method,
                        endpoint=self._normalize_endpoint(url_path),
                        status_code=response.status_code,
                        user_type=user_type
                    ).inc()
                
                if hasattr(HTTP_REQUEST_DURATION, 'labels'):
                    HTTP_REQUEST_DURATION.labels(  # type: ignore
                        method=method,
                        endpoint=self._normalize_endpoint(url_path)
                    ).observe(duration)
                
                if hasattr(HTTP_REQUEST_SIZE, 'labels'):
                    HTTP_REQUEST_SIZE.labels(  # type: ignore
                        method=method,
                        endpoint=self._normalize_endpoint(url_path)
                    ).observe(request_size)
                
                if hasattr(HTTP_RESPONSE_SIZE, 'labels'):
                    HTTP_RESPONSE_SIZE.labels(  # type: ignore
                        method=method,
                        endpoint=self._normalize_endpoint(url_path)
                    ).observe(response_size)
            except Exception as metric_error:
                logger.warning(f"Ошибка обновления метрик: {metric_error}")
            
            # Логируем завершение запроса
            struct_logger.info(
                "request_completed",
                method=method,
                path=url_path,
                status_code=response.status_code,
                duration_seconds=duration,
                response_size=response_size,
                user_type=user_type
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Обновляем метрики для ошибок
            try:
                if hasattr(HTTP_REQUESTS_TOTAL, 'labels'):
                    HTTP_REQUESTS_TOTAL.labels(  # type: ignore
                        method=method,
                        endpoint=self._normalize_endpoint(url_path),
                        status_code="500",
                        user_type=user_type
                    ).inc()
            except Exception as metric_error:
                logger.warning(f"Ошибка обновления метрик ошибок: {metric_error}")
            
            # Логируем ошибку
            struct_logger.error(
                "request_failed",
                method=method,
                path=url_path,
                duration_seconds=duration,
                error=str(e),
                user_type=user_type,
                exc_info=True
            )
            raise
        finally:
            self.active_requests -= 1
    
    def _get_client_ip(self, request: Request) -> str:
        """Получить IP клиента с учетом прокси"""
        # Проверяем заголовки от прокси
        for header in ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]:
            ip = request.headers.get(header)
            if ip:
                return ip.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _normalize_endpoint(self, path: str) -> str:
        """Нормализует endpoint для метрик (убирает ID)"""
        import re
        # Заменяем числовые ID на placeholder
        normalized = re.sub(r'/\d+', '/{id}', path)
        # Заменяем UUID на placeholder
        normalized = re.sub(r'/[0-9a-f-]{36}', '/{uuid}', normalized)
        return normalized

# ==================== BUSINESS METRICS ====================

class BusinessMetrics:
    """Класс для сбора бизнес-метрик"""
    
    @staticmethod
    def track_file_upload(file_type: str, user_type: str, status: str):
        """Отслеживание загрузки файлов"""
        FILE_PROCESSING_TOTAL.labels(  # type: ignore
            file_type=file_type,
            status=status,
            user_type=user_type
        ).inc()
        
        struct_logger.info(
            "file_uploaded",
            file_type=file_type,
            user_type=user_type,
            status=status
        )
    
    @staticmethod
    def track_file_processing_time(file_type: str, stage: str, duration: float):
        """Отслеживание времени обработки файлов"""
        FILE_PROCESSING_DURATION.labels(  # type: ignore
            file_type=file_type,
            processing_stage=stage
        ).observe(duration)
    
    @staticmethod
    def track_file_processing_error(file_type: str, error_type: str):
        """Отслеживание ошибок обработки файлов"""
        FILE_PROCESSING_ERRORS.labels(  # type: ignore
            file_type=file_type,
            error_type=error_type
        ).inc()
        
        struct_logger.error(
            "file_processing_error",
            file_type=file_type,
            error_type=error_type
        )
    
    @staticmethod
    def track_order_processing(status: str, source: str = "manual"):
        """Отслеживание обработки заказов"""
        ORDERS_PROCESSED_TOTAL.labels(  # type: ignore
            status=status,
            source=source
        ).inc()
        
        struct_logger.info(
            "order_processed",
            status=status,
            source=source
        )
    
    @staticmethod
    def track_telegram_api_call(method: str, status: str):
        """Отслеживание вызовов Telegram API"""
        TELEGRAM_API_CALLS.labels(  # type: ignore
            method=method,
            status=status
        ).inc()
    
    @staticmethod
    def update_active_users(period: str, count: int):
        """Обновление количества активных пользователей"""
        USERS_ACTIVE.labels(period=period).set(count)  # type: ignore

# ==================== DATABASE MONITORING ====================

class DatabaseMonitor:
    """Мониторинг базы данных"""
    
    @staticmethod
    def track_query(operation: str, table: str, duration: float):
        """Отслеживание запросов к БД"""
        DATABASE_QUERY_DURATION.labels(  # type: ignore
            operation=operation,
            table=table
        ).observe(duration)
    
    @staticmethod
    def track_query_error(operation: str, error_type: str):
        """Отслеживание ошибок БД"""
        DATABASE_QUERY_ERRORS.labels(  # type: ignore
            operation=operation,
            error_type=error_type
        ).inc()
    
    @staticmethod
    async def update_connection_count():
        """Обновление количества активных соединений"""
        try:
            # Здесь можно добавить запрос к БД для получения количества соединений
            # Пока что используем заглушку
            DATABASE_CONNECTIONS_ACTIVE.set(0)  # type: ignore
        except Exception as e:
            logger.error(f"Ошибка получения количества соединений БД: {e}")

# ==================== SYSTEM MONITORING ====================

class SystemMonitor:
    """Мониторинг системных ресурсов"""
    
    @staticmethod
    def update_system_metrics():
        """Обновление системных метрик"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            SYSTEM_CPU_USAGE.set(cpu_percent)  # type: ignore
            
            # Memory usage
            memory = psutil.virtual_memory()
            SYSTEM_MEMORY_USAGE.set(memory.percent)  # type: ignore
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            SYSTEM_DISK_USAGE.set(disk_percent)  # type: ignore
            
            # Load average
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
            SYSTEM_LOAD_AVERAGE.set(load_avg)  # type: ignore
            
        except Exception as e:
            logger.error(f"Ошибка обновления системных метрик: {e}")

# ==================== HEALTH CHECKS ====================

@dataclass
class HealthCheck:
    """Результат проверки здоровья"""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: float
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthChecker:
    """Система проверки здоровья приложения"""
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'cache': self._check_cache,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
            'external_services': self._check_external_services
        }
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Запускает все проверки параллельно"""
        tasks = {}
        for name, check_func in self.checks.items():
            tasks[name] = asyncio.create_task(check_func())
        
        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await asyncio.wait_for(task, timeout=10.0)
            except asyncio.TimeoutError:
                results[name] = HealthCheck(
                    name=name,
                    status="unhealthy",
                    response_time_ms=10000,
                    error="Health check timeout"
                )
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status="unhealthy",
                    response_time_ms=0,
                    error=str(e)
                )
        
        return results
    
    async def _check_database(self) -> HealthCheck:
        """Проверка базы данных"""
        start_time = time.time()
        try:
            db = next(get_db())
            result = db.execute(text("SELECT 1"))
            response_time = (time.time() - start_time) * 1000
            
            status = "healthy" if response_time < 100 else "degraded"
            
            return HealthCheck(
                name="database",
                status=status,
                response_time_ms=response_time,
                details={"query": "SELECT 1"}
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def _check_cache(self) -> HealthCheck:
        """Проверка кэша"""
        start_time = time.time()
        try:
            health_info = await cache_service.health_check()
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="cache",
                status=health_info['status'],
                response_time_ms=response_time,
                details=health_info
            )
        except Exception as e:
            return HealthCheck(
                name="cache",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def _check_disk_space(self) -> HealthCheck:
        """Проверка дискового пространства"""
        start_time = time.time()
        try:
            disk = psutil.disk_usage('/')
            free_percent = (disk.free / disk.total) * 100
            
            if free_percent < 5:
                status = "unhealthy"
            elif free_percent < 15:
                status = "degraded"
            else:
                status = "healthy"
            
            return HealthCheck(
                name="disk_space",
                status=status,
                response_time_ms=(time.time() - start_time) * 1000,
                details={
                    "free_percent": round(free_percent, 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "total_gb": round(disk.total / (1024**3), 2)
                }
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def _check_memory(self) -> HealthCheck:
        """Проверка памяти"""
        start_time = time.time()
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                status = "unhealthy"
            elif memory.percent > 80:
                status = "degraded"
            else:
                status = "healthy"
            
            return HealthCheck(
                name="memory",
                status=status,
                response_time_ms=(time.time() - start_time) * 1000,
                details={
                    "used_percent": memory.percent,
                    "available_gb": round(memory.available / (1024**3), 2),
                    "total_gb": round(memory.total / (1024**3), 2)
                }
            )
        except Exception as e:
            return HealthCheck(
                name="memory",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def _check_external_services(self) -> HealthCheck:
        """Проверка внешних сервисов"""
        start_time = time.time()
        try:
            # Здесь можно добавить проверки внешних API
            # Пока что возвращаем заглушку
            return HealthCheck(
                name="external_services",
                status="healthy",
                response_time_ms=(time.time() - start_time) * 1000,
                details={"telegram_api": "not_checked", "do_spaces": "not_checked"}
            )
        except Exception as e:
            return HealthCheck(
                name="external_services",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )

# ==================== ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ ====================

business_metrics = BusinessMetrics()
db_monitor = DatabaseMonitor()
system_monitor = SystemMonitor()
health_checker = HealthChecker()

# ==================== PERIODIC TASKS ====================

async def start_background_monitoring():
    """Запуск фоновых задач мониторинга"""
    async def update_system_metrics_task():
        while True:
            try:
                system_monitor.update_system_metrics()
                await db_monitor.update_connection_count()
                
                # Обновляем метрики кэша
                cache_stats = await cache_service.get_stats()
                CACHE_HIT_RATIO.set(cache_stats.get('hit_rate_percent', 0))  # type: ignore
                
                await asyncio.sleep(30)  # Каждые 30 секунд
            except Exception as e:
                logger.error(f"Ошибка в задаче мониторинга: {e}")
                await asyncio.sleep(60)  # При ошибке ждем минуту
    
    # Запускаем фоновую задачу
    asyncio.create_task(update_system_metrics_task())
    
    # Устанавливаем информацию о приложении
    APPLICATION_INFO.info({  # type: ignore
        'version': os.getenv('APP_VERSION', 'development'),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'build_time': datetime.now(timezone.utc).isoformat(),
        'python_version': sys.version.split()[0]
    })
    
    logger.info("Фоновый мониторинг запущен")

# ==================== EXPORT FUNCTIONS ====================

def get_metrics() -> str:
    """Получить метрики в формате Prometheus"""
    return generate_latest().decode('utf-8')

def get_monitoring_middleware():
    """Получить middleware для мониторинга"""
    return MonitoringMiddleware
