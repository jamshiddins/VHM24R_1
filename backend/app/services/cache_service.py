"""
Асинхронный сервис кэширования с поддержкой Redis и fallback к памяти
"""
import os
import json
import pickle
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Callable, Union
from functools import wraps
import redis.asyncio as redis
from contextlib import asynccontextmanager

from ..utils.logger import get_logger
from ..utils.exceptions import CacheError

logger = get_logger(__name__)

class InMemoryCache:
    """Fallback кэш в памяти когда Redis недоступен"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, datetime] = {}
        self.max_size = max_size
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша памяти"""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry['expires_at']:
                self._access_times[key] = datetime.now()
                return entry['value']
            else:
                # Удаляем истекший ключ
                await self.delete(key)
        return None
    
    async def set(self, key: str, value: Any, expire: int = 3600):
        """Сохранить значение в кэш памяти"""
        # Очищаем кэш если превышен размер
        if len(self._cache) >= self.max_size:
            await self._evict_lru()
        
        self._cache[key] = {
            'value': value,
            'expires_at': datetime.now() + timedelta(seconds=expire),
            'created_at': datetime.now()
        }
        self._access_times[key] = datetime.now()
    
    async def delete(self, key: str):
        """Удалить ключ из кэша"""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
    
    async def clear(self):
        """Очистить весь кэш"""
        self._cache.clear()
        self._access_times.clear()
    
    async def _evict_lru(self):
        """Удаляет наименее используемые ключи (LRU)"""
        if not self._access_times:
            return
        
        # Удаляем 10% самых старых ключей
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        keys_to_remove = [key for key, _ in sorted_keys[:max(1, len(sorted_keys) // 10)]]
        
        for key in keys_to_remove:
            await self.delete(key)

class AsyncCacheService:
    """Асинхронный сервис кэширования с поддержкой Redis и fallback"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache = InMemoryCache()
        self.connected = False
        self._connection_lock = asyncio.Lock()
        
        # Настройки кэширования
        self.default_expire = 3600  # 1 час
        self.key_prefix = "vhm24r_cache:"
        
        # Статистика
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'redis_ops': 0,
            'memory_ops': 0
        }
        
        logger.info("AsyncCacheService инициализирован")
    
    async def connect(self):
        """Подключение к Redis"""
        if self.connected:
            return
            
        async with self._connection_lock:
            if self.connected:
                return
                
            try:
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
                self.redis_client = redis.from_url(
                    redis_url, 
                    encoding="utf-8", 
                    decode_responses=False,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # Проверяем подключение
                await self.redis_client.ping()
                self.connected = True
                logger.info("Подключение к Redis установлено")
                
            except Exception as e:
                logger.warning(f"Не удалось подключиться к Redis: {e}")
                self.redis_client = None
                self.connected = False
    
    async def disconnect(self):
        """Отключение от Redis"""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Отключение от Redis")
            except Exception as e:
                logger.warning(f"Ошибка отключения от Redis: {e}")
        
        self.redis_client = None
        self.connected = False
    
    def _make_key(self, key: str) -> str:
        """Создает полный ключ с префиксом"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        full_key = self._make_key(key)
        
        try:
            # Сначала пробуем Redis
            if self.connected and self.redis_client:
                try:
                    value = await self.redis_client.get(full_key)
                    if value is not None:
                        self.stats['hits'] += 1
                        self.stats['redis_ops'] += 1
                        return pickle.loads(value)
                except Exception as e:
                    logger.warning(f"Ошибка чтения из Redis: {e}")
                    self.stats['errors'] += 1
            
            # Fallback к памяти
            value = await self.memory_cache.get(full_key)
            if value is not None:
                self.stats['hits'] += 1
                self.stats['memory_ops'] += 1
                return value
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения из кэша {key}: {e}")
            self.stats['errors'] += 1
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Сохранить значение в кэш"""
        if expire is None:
            expire = self.default_expire
            
        full_key = self._make_key(key)
        
        try:
            # Сохраняем в Redis
            if self.connected and self.redis_client:
                try:
                    serialized_value = pickle.dumps(value)
                    await self.redis_client.setex(full_key, expire, serialized_value)
                    self.stats['redis_ops'] += 1
                except Exception as e:
                    logger.warning(f"Ошибка записи в Redis: {e}")
                    self.stats['errors'] += 1
            
            # Всегда сохраняем в память как backup
            await self.memory_cache.set(full_key, value, expire)
            self.stats['memory_ops'] += 1
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш {key}: {e}")
            self.stats['errors'] += 1
    
    async def delete(self, key: str):
        """Удалить ключ из кэша"""
        full_key = self._make_key(key)
        
        try:
            # Удаляем из Redis
            if self.connected and self.redis_client:
                try:
                    await self.redis_client.delete(full_key)
                    self.stats['redis_ops'] += 1
                except Exception as e:
                    logger.warning(f"Ошибка удаления из Redis: {e}")
                    self.stats['errors'] += 1
            
            # Удаляем из памяти
            await self.memory_cache.delete(full_key)
            self.stats['memory_ops'] += 1
            
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша {key}: {e}")
            self.stats['errors'] += 1
    
    async def clear_pattern(self, pattern: str):
        """Удаляет все ключи по паттерну"""
        full_pattern = self._make_key(pattern)
        
        try:
            if self.connected and self.redis_client:
                try:
                    keys = await self.redis_client.keys(full_pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                    self.stats['redis_ops'] += len(keys) if keys else 0
                except Exception as e:
                    logger.warning(f"Ошибка очистки паттерна в Redis: {e}")
                    self.stats['errors'] += 1
            
            # Для памяти очищаем по паттерну (простая реализация)
            keys_to_delete = [
                key for key in self.memory_cache._cache.keys() 
                if key.startswith(full_pattern.replace('*', ''))
            ]
            for key in keys_to_delete:
                await self.memory_cache.delete(key)
            
        except Exception as e:
            logger.error(f"Ошибка очистки паттерна {pattern}: {e}")
            self.stats['errors'] += 1
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Инкремент значения в кэше"""
        full_key = self._make_key(key)
        
        try:
            if self.connected and self.redis_client:
                try:
                    result = await self.redis_client.incrby(full_key, amount)
                    self.stats['redis_ops'] += 1
                    return result
                except Exception as e:
                    logger.warning(f"Ошибка инкремента в Redis: {e}")
                    self.stats['errors'] += 1
            
            # Fallback к памяти
            current = await self.memory_cache.get(full_key) or 0
            new_value = current + amount
            await self.memory_cache.set(full_key, new_value)
            self.stats['memory_ops'] += 1
            return new_value
            
        except Exception as e:
            logger.error(f"Ошибка инкремента {key}: {e}")
            self.stats['errors'] += 1
            return amount
    
    def cached(self, expire: Optional[int] = None, key_prefix: str = "", 
               key_func: Optional[Callable] = None):
        """Декоратор для кэширования результатов функций"""
        
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Генерируем ключ кэша
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Создаем ключ на основе имени функции и аргументов
                    args_str = str(args) + str(sorted(kwargs.items()))
                    key_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                    cache_key = f"{key_prefix}{func.__name__}:{key_hash}"
                
                # Проверяем кэш
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Кэш HIT для {cache_key}")
                    return cached_result
                
                # Выполняем функцию
                logger.debug(f"Кэш MISS для {cache_key}")
                
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Кэшируем результат
                await self.set(cache_key, result, expire)
                return result
            
            # Для синхронных функций
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return asyncio.create_task(async_wrapper(*args, **kwargs))
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        hit_rate = 0
        if self.stats['hits'] + self.stats['misses'] > 0:
            hit_rate = self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) * 100
        
        redis_info = {}
        if self.connected and self.redis_client:
            try:
                info = await self.redis_client.info('memory')
                redis_info = {
                    'used_memory': info.get('used_memory_human', 'N/A'),
                    'used_memory_peak': info.get('used_memory_peak_human', 'N/A'),
                    'keys': await self.redis_client.dbsize()
                }
            except Exception as e:
                logger.warning(f"Ошибка получения информации Redis: {e}")
        
        return {
            'connected_to_redis': self.connected,
            'hit_rate_percent': round(hit_rate, 2),
            'total_operations': sum(self.stats.values()),
            'stats': self.stats.copy(),
            'memory_cache_size': len(self.memory_cache._cache),
            'redis_info': redis_info
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья кэша"""
        status = {
            'redis_available': False,
            'memory_cache_available': True,
            'response_time_ms': None,
            'status': 'degraded'
        }
        
        # Проверяем Redis
        if self.redis_client:
            try:
                start_time = asyncio.get_event_loop().time()
                await self.redis_client.ping()
                response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                status['redis_available'] = True
                status['response_time_ms'] = round(response_time, 2)
                status['status'] = 'healthy'
                
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
        
        # Проверяем память
        try:
            test_key = f"health_check_{datetime.now().timestamp()}"
            await self.memory_cache.set(test_key, "test", 1)
            test_value = await self.memory_cache.get(test_key)
            await self.memory_cache.delete(test_key)
            
            if test_value != "test":
                status['memory_cache_available'] = False
                status['status'] = 'unhealthy'
                
        except Exception as e:
            logger.error(f"Memory cache health check failed: {e}")
            status['memory_cache_available'] = False
            status['status'] = 'unhealthy'
        
        return status

# Глобальный экземпляр кэша
cache_service = AsyncCacheService()

# Context manager для автоматического подключения/отключения
@asynccontextmanager
async def cache_context():
    """Context manager для управления подключением к кэшу"""
    await cache_service.connect()
    try:
        yield cache_service
    finally:
        await cache_service.disconnect()

# Предустановленные конфигурации кэширования
class CacheConfig:
    """Конфигурации кэширования для разных типов данных"""
    
    # Аналитические данные (30 минут)
    ANALYTICS = {'expire': 1800, 'key_prefix': 'analytics:'}
    
    # Списки файлов пользователей (5 минут)
    USER_FILES = {'expire': 300, 'key_prefix': 'user_files:'}
    
    # Статистика системы (15 минут)
    SYSTEM_STATS = {'expire': 900, 'key_prefix': 'stats:'}
    
    # Пользовательские сессии (1 час)
    USER_SESSIONS = {'expire': 3600, 'key_prefix': 'session:'}
    
    # Конфигурация системы (24 часа)
    SYSTEM_CONFIG = {'expire': 86400, 'key_prefix': 'config:'}

# Готовые декораторы для часто используемых случаев
def cache_analytics(expire: int = CacheConfig.ANALYTICS['expire']):
    """Декоратор для кэширования аналитических данных"""
    return cache_service.cached(expire=expire, key_prefix=CacheConfig.ANALYTICS['key_prefix'])

def cache_user_data(expire: int = CacheConfig.USER_FILES['expire']):
    """Декоратор для кэширования пользовательских данных"""
    return cache_service.cached(expire=expire, key_prefix=CacheConfig.USER_FILES['key_prefix'])

def cache_system_stats(expire: int = CacheConfig.SYSTEM_STATS['expire']):
    """Декоратор для кэширования системной статистики"""
    return cache_service.cached(expire=expire, key_prefix=CacheConfig.SYSTEM_STATS['key_prefix'])

# Утилитарные функции
async def invalidate_user_cache(user_id: int):
    """Инвалидация всего кэша пользователя"""
    await cache_service.clear_pattern(f"user_files:{user_id}:*")
    await cache_service.clear_pattern(f"session:{user_id}:*")
    logger.info(f"Инвалидирован кэш пользователя {user_id}")

async def invalidate_analytics_cache():
    """Инвалидация кэша аналитики"""
    await cache_service.clear_pattern("analytics:*")
    logger.info("Инвалидирован кэш аналитики")

async def warm_up_cache():
    """Предварительный прогрев кэша"""
    logger.info("Запуск прогрева кэша...")
    
    # Можно добавить прогрев часто используемых данных
    # Например, общие настройки системы, статистика и т.д.
    
    logger.info("Прогрев кэша завершен")
