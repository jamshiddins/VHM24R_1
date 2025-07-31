"""
Оптимизированные настройки для Redis кэширования
"""
import os
from typing import Dict, Any

class RedisOptimizationConfig:
    """Конфигурация оптимизации Redis для production"""
    
    # Базовые настройки подключения
    CONNECTION_SETTINGS = {
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
        'retry_on_timeout': True,
        'retry_on_error': [ConnectionError, TimeoutError],
        'health_check_interval': 30,
        'max_connections': 50,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            'TCP_KEEPINTVL': 1,
            'TCP_KEEPCNT': 3,
            'TCP_USER_TIMEOUT': 5000,
        }
    }
    
    # Настройки кэширования по типам данных
    CACHE_POLICIES = {
        # Быстрые данные (пользовательские сессии)
        'session': {
            'expire': 3600,  # 1 час
            'serialize': 'pickle',
            'compression': False,
            'prefix': 'sess:'
        },
        
        # Аналитические данные (средняя частота обновления)
        'analytics': {
            'expire': 1800,  # 30 минут  
            'serialize': 'json',
            'compression': True,
            'prefix': 'analytics:'
        },
        
        # Файловые метаданные (редко изменяются)
        'file_metadata': {
            'expire': 7200,  # 2 часа
            'serialize': 'pickle', 
            'compression': True,
            'prefix': 'files:'
        },
        
        # Пользовательские данные
        'user_data': {
            'expire': 1800,  # 30 минут
            'serialize': 'pickle',
            'compression': False,
            'prefix': 'user:'
        },
        
        # Системная конфигурация (долгосрочное кэширование)
        'system_config': {
            'expire': 86400,  # 24 часа
            'serialize': 'json',
            'compression': False,
            'prefix': 'config:'
        },
        
        # Результаты обработки файлов
        'processing_results': {
            'expire': 3600,  # 1 час
            'serialize': 'pickle',
            'compression': True,
            'prefix': 'proc:'
        },
        
        # Статистика и метрики
        'metrics': {
            'expire': 300,  # 5 минут
            'serialize': 'json',
            'compression': False,
            'prefix': 'metrics:'
        },
        
        # JWT blacklist (время жизни токенов)
        'jwt_blacklist': {
            'expire': 3600,  # 1 час (или время жизни токена)
            'serialize': 'json',
            'compression': False,
            'prefix': 'jwt_bl:'
        }
    }
    
    # Паттерны инвалидации кэша
    INVALIDATION_PATTERNS = {
        'user_logout': ['sess:{user_id}:*', 'user:{user_id}:*'],
        'file_update': ['files:{file_id}:*', 'user:{user_id}:files:*'],
        'system_update': ['config:*', 'metrics:*'],
        'analytics_refresh': ['analytics:*', 'metrics:*']
    }
    
    # Настройки производительности
    PERFORMANCE_SETTINGS = {
        'pipeline_size': 100,  # Размер pipeline для массовых операций
        'cluster_mode': False,  # Для Railway обычно single instance
        'read_replica': False,  # Чтение с replica
        'memory_optimization': True,
        'compression_threshold': 1024,  # Сжимать данные > 1KB
        'max_memory_policy': 'allkeys-lru',  # Политика вытеснения при нехватке памяти
    }
    
    # Мониторинг и метрики
    MONITORING_CONFIG = {
        'track_hit_rate': True,
        'track_memory_usage': True,
        'track_response_time': True,
        'alert_thresholds': {
            'hit_rate_min': 80.0,  # Минимальный hit rate %
            'memory_usage_max': 80.0,  # Максимальное использование памяти %
            'response_time_max': 100.0,  # Максимальное время отклика в мс
            'error_rate_max': 5.0  # Максимальный % ошибок
        },
        'metrics_retention': 86400  # Хранить метрики 24 часа
    }

class CacheKeyGenerator:
    """Генератор оптимизированных ключей кэша"""
    
    @staticmethod
    def user_session(user_id: int, session_id: str) -> str:
        """Ключ для пользовательской сессии"""
        return f"sess:{user_id}:{session_id}"
    
    @staticmethod
    def user_files(user_id: int, page: int = 1, filters: str = "") -> str:
        """Ключ для списка файлов пользователя"""
        filter_hash = hash(filters) if filters else "all"
        return f"user:{user_id}:files:{page}:{filter_hash}"
    
    @staticmethod
    def file_metadata(file_id: int) -> str:
        """Ключ для метаданных файла"""
        return f"files:{file_id}:metadata"
    
    @staticmethod
    def analytics_dashboard(user_id: int, period: str) -> str:
        """Ключ для данных дашборда аналитики"""
        return f"analytics:{user_id}:dashboard:{period}"
    
    @staticmethod
    def processing_result(file_id: int, operation: str) -> str:
        """Ключ для результатов обработки файла"""
        return f"proc:{file_id}:{operation}"
    
    @staticmethod
    def system_metrics(metric_type: str) -> str:
        """Ключ для системных метрик"""
        return f"metrics:system:{metric_type}"
    
    @staticmethod
    def jwt_blacklist(jti: str) -> str:
        """Ключ для JWT blacklist"""
        return f"jwt_bl:{jti}"

class CacheInvalidationManager:
    """Менеджер инвалидации кэша"""
    
    def __init__(self, cache_service):
        self.cache_service = cache_service
    
    async def invalidate_user_data(self, user_id: int):
        """Инвалидация всех данных пользователя"""
        patterns = [
            f"sess:{user_id}:*",
            f"user:{user_id}:*",
            f"analytics:{user_id}:*"
        ]
        
        for pattern in patterns:
            await self.cache_service.clear_pattern(pattern)
    
    async def invalidate_file_data(self, file_id: int, user_id: int):
        """Инвалидация данных файла"""
        patterns = [
            f"files:{file_id}:*",
            f"proc:{file_id}:*",
            f"user:{user_id}:files:*"
        ]
        
        for pattern in patterns:
            await self.cache_service.clear_pattern(pattern)
    
    async def invalidate_system_cache(self):
        """Инвалидация системного кэша"""
        patterns = [
            "config:*",
            "metrics:system:*"
        ]
        
        for pattern in patterns:
            await self.cache_service.clear_pattern(pattern)

def get_redis_config() -> Dict[str, Any]:
    """Получение конфигурации Redis для текущей среды"""
    env = os.getenv('ENVIRONMENT', 'development')
    
    base_config = RedisOptimizationConfig.CONNECTION_SETTINGS.copy()
    
    if env == 'production':
        # Production оптимизации
        base_config.update({
            'max_connections': 100,
            'socket_timeout': 10,
            'health_check_interval': 60,
            'retry_on_timeout': True
        })
    elif env == 'development':
        # Development настройки
        base_config.update({
            'max_connections': 20,
            'socket_timeout': 5,
            'health_check_interval': 30
        })
    
    return base_config

def get_cache_policy(data_type: str) -> Dict[str, Any]:
    """Получение политики кэширования для типа данных"""
    return RedisOptimizationConfig.CACHE_POLICIES.get(
        data_type, 
        RedisOptimizationConfig.CACHE_POLICIES['user_data']
    )

# Готовые декораторы с оптимизированными настройками
def optimized_cache(data_type: str = 'user_data'):
    """Декоратор с оптимизированными настройками кэширования"""
    def decorator(func):
        policy = get_cache_policy(data_type)
        
        # Здесь можно добавить логику декоратора
        # Используя policy['expire'], policy['prefix'] и т.д.
        
        return func
    return decorator

# Утилиты для мониторинга производительности
class CachePerformanceMonitor:
    """Монитор производительности кэша"""
    
    def __init__(self):
        self.metrics = {
            'operations': 0,
            'hit_rate': 0.0,
            'avg_response_time': 0.0,
            'memory_usage': 0.0,
            'error_rate': 0.0
        }
    
    def record_operation(self, operation_type: str, response_time: float, success: bool = True):
        """Запись операции для анализа производительности"""
        self.metrics['operations'] += 1
        
        # Обновляем метрики
        # Здесь должна быть более сложная логика агрегации
        
    def get_performance_report(self) -> Dict[str, Any]:
        """Получение отчета о производительности"""
        config = RedisOptimizationConfig.MONITORING_CONFIG
        
        alerts = []
        status = 'healthy'
        
        # Проверяем пороги
        if self.metrics['hit_rate'] < config['alert_thresholds']['hit_rate_min']:
            alerts.append(f"Низкий hit rate: {self.metrics['hit_rate']:.1f}%")
            status = 'warning'
        
        if self.metrics['avg_response_time'] > config['alert_thresholds']['response_time_max']:
            alerts.append(f"Высокое время отклика: {self.metrics['avg_response_time']:.1f}ms")
            status = 'warning'
        
        if self.metrics['error_rate'] > config['alert_thresholds']['error_rate_max']:
            alerts.append(f"Высокий уровень ошибок: {self.metrics['error_rate']:.1f}%")
            status = 'critical'
        
        return {
            'status': status,
            'metrics': self.metrics.copy(),
            'alerts': alerts,
            'recommendations': self._get_recommendations()
        }
    
    def _get_recommendations(self) -> list:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        if self.metrics['hit_rate'] < 70:
            recommendations.append("Рассмотрите увеличение времени кэширования для часто используемых данных")
        
        if self.metrics['avg_response_time'] > 50:
            recommendations.append("Проверьте настройки сети и производительность Redis сервера")
        
        if self.metrics['memory_usage'] > 80:
            recommendations.append("Настройте политику вытеснения данных или увеличьте объем памяти")
        
        return recommendations

# Экспорт основных компонентов
__all__ = [
    'RedisOptimizationConfig',
    'CacheKeyGenerator', 
    'CacheInvalidationManager',
    'CachePerformanceMonitor',
    'get_redis_config',
    'get_cache_policy',
    'optimized_cache'
]
