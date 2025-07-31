"""
Сервис мониторинга подключений к внешним сервисам
"""
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

import redis
import redis.asyncio as async_redis
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..utils.logger import get_logger

logger = get_logger(__name__)

class ConnectionStatus(Enum):
    """Статусы подключений"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"

@dataclass
class ConnectionMetrics:
    """Метрики подключения"""
    service_name: str
    status: ConnectionStatus
    response_time_ms: float
    last_check: datetime
    error_message: Optional[str] = None
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    additional_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['status'] = self.status.value
        result['last_check'] = self.last_check.isoformat()
        return result

class ConnectionMonitor:
    """Мониторинг подключений к внешним сервисам"""
    
    def __init__(self):
        self.redis_client = None
        self.monitoring_interval = 30  # секунд
        self.history_retention_hours = 24
        self.alert_thresholds = {
            'response_time_ms': 5000,  # 5 секунд
            'consecutive_failures': 3,
            'uptime_percentage': 95.0
        }
        
        # История метрик (в памяти для демо, в production лучше в Redis/DB)
        self.metrics_history: Dict[str, List[ConnectionMetrics]] = {}
        
        logger.info("ConnectionMonitor инициализирован")

    async def start_monitoring(self):
        """Запуск мониторинга в фоновом режиме"""
        logger.info("🔍 Запуск мониторинга подключений...")
        
        while True:
            try:
                await self.check_all_connections()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(10)  # Короткая пауза при ошибке

    async def check_all_connections(self) -> Dict[str, ConnectionMetrics]:
        """Проверка всех подключений"""
        results = {}
        
        # Проверяем PostgreSQL
        postgres_metrics = await self.check_postgresql()
        results['postgresql'] = postgres_metrics
        self._store_metrics('postgresql', postgres_metrics)
        
        # Проверяем Redis
        redis_metrics = await self.check_redis()
        results['redis'] = redis_metrics
        self._store_metrics('redis', redis_metrics)
        
        # Анализируем общее состояние
        overall_status = self._analyze_overall_health(results)
        
        # Отправляем алерты если нужно
        await self._check_and_send_alerts(results)
        
        logger.info(f"Мониторинг завершен. Общий статус: {overall_status}")
        return results

    async def check_postgresql(self) -> ConnectionMetrics:
        """Проверка PostgreSQL подключения"""
        start_time = time.time()
        
        try:
            from ..database import DATABASE_URL
            database_url = DATABASE_URL
            
            if not database_url or database_url.startswith('sqlite'):
                return ConnectionMetrics(
                    service_name="postgresql",
                    status=ConnectionStatus.OFFLINE,
                    response_time_ms=0,
                    last_check=datetime.now(timezone.utc),
                    error_message="PostgreSQL не настроен, используется SQLite"
                )
            
            # Прямое подключение
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            
            # Простая проверка
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            
            # Проверка активных подключений
            cursor.execute("""
                SELECT count(*) as active_connections,
                       max_conn.setting::int as max_connections,
                       round(100.0 * count(*) / max_conn.setting::int, 2) as connection_usage_percent
                FROM pg_stat_activity 
                CROSS JOIN (SELECT setting FROM pg_settings WHERE name = 'max_connections') max_conn
                WHERE state = 'active';
            """)
            
            conn_stats = cursor.fetchone()
            if conn_stats:
                active_connections, max_connections, usage_percent = conn_stats
            else:
                active_connections, max_connections, usage_percent = 0, 100, 0.0
            
            # Проверка размера базы данных
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size;
            """)
            db_size_result = cursor.fetchone()
            db_size = db_size_result[0] if db_size_result else "unknown"
            
            cursor.close()
            conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            # Определяем статус на основе метрик
            if response_time > self.alert_thresholds['response_time_ms']:
                status = ConnectionStatus.DEGRADED
            elif usage_percent > 80:
                status = ConnectionStatus.DEGRADED
            else:
                status = ConnectionStatus.HEALTHY
            
            return ConnectionMetrics(
                service_name="postgresql",
                status=status,
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                additional_metrics={
                    'active_connections': active_connections,
                    'max_connections': max_connections,
                    'connection_usage_percent': usage_percent,
                    'database_size': db_size
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ConnectionMetrics(
                service_name="postgresql",
                status=ConnectionStatus.CRITICAL,
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )

    async def check_redis(self) -> ConnectionMetrics:
        """Проверка Redis подключения"""
        start_time = time.time()
        
        try:
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            
            # Асинхронное подключение
            client = async_redis.from_url(redis_url, decode_responses=True)
            
            # Проверка подключения
            await client.ping()
            
            # Получаем информацию о Redis
            info = await client.info()
            memory_info = await client.info('memory')
            
            # Тест записи/чтения
            test_key = f"monitor_test_{int(time.time())}"
            await client.set(test_key, "test_value", ex=60)
            test_result = await client.get(test_key)
            await client.delete(test_key)
            
            await client.close()
            
            response_time = (time.time() - start_time) * 1000
            
            # Анализируем метрики Redis
            used_memory_percent = (memory_info.get('used_memory', 0) / 
                                 memory_info.get('maxmemory', 1024*1024*1024)) * 100
            
            # Определяем статус
            if response_time > self.alert_thresholds['response_time_ms']:
                status = ConnectionStatus.DEGRADED
            elif used_memory_percent > 80:
                status = ConnectionStatus.DEGRADED
            elif test_result != "test_value":
                status = ConnectionStatus.DEGRADED
            else:
                status = ConnectionStatus.HEALTHY
            
            return ConnectionMetrics(
                service_name="redis",
                status=status,
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                additional_metrics={
                    'redis_version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),  
                    'used_memory_human': memory_info.get('used_memory_human'),
                    'used_memory_percent': round(used_memory_percent, 2),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'test_write_read': 'success' if test_result == "test_value" else 'failed'
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ConnectionMetrics(
                service_name="redis",
                status=ConnectionStatus.CRITICAL,
                response_time_ms=response_time,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )

    def _store_metrics(self, service_name: str, metrics: ConnectionMetrics):
        """Сохранение метрик в историю"""
        if service_name not in self.metrics_history:
            self.metrics_history[service_name] = []
        
        self.metrics_history[service_name].append(metrics)
        
        # Очистка старых метрик
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.history_retention_hours)
        self.metrics_history[service_name] = [
            m for m in self.metrics_history[service_name] 
            if m.last_check > cutoff_time
        ]

    def _analyze_overall_health(self, results: Dict[str, ConnectionMetrics]) -> ConnectionStatus:
        """Анализ общего состояния системы"""
        statuses = [metrics.status for metrics in results.values()]
        
        if any(status == ConnectionStatus.CRITICAL for status in statuses):
            return ConnectionStatus.CRITICAL
        elif any(status == ConnectionStatus.DEGRADED for status in statuses):
            return ConnectionStatus.DEGRADED
        elif any(status == ConnectionStatus.OFFLINE for status in statuses):
            return ConnectionStatus.DEGRADED
        else:
            return ConnectionStatus.HEALTHY

    async def _check_and_send_alerts(self, results: Dict[str, ConnectionMetrics]):
        """Проверка и отправка алертов"""
        for service_name, metrics in results.items():
            if metrics.status in [ConnectionStatus.CRITICAL, ConnectionStatus.DEGRADED]:
                await self._send_alert(service_name, metrics)

    async def _send_alert(self, service_name: str, metrics: ConnectionMetrics):
        """Отправка алерта"""
        alert_message = f"""
🚨 ALERT: {service_name.upper()} - {metrics.status.value.upper()}

Время отклика: {metrics.response_time_ms:.2f}ms
Последняя проверка: {metrics.last_check.strftime('%Y-%m-%d %H:%M:%S UTC')}
Ошибка: {metrics.error_message or 'Нет'}

Дополнительные метрики:
{json.dumps(metrics.additional_metrics or {}, indent=2, ensure_ascii=False)}
"""
        
        logger.error(f"🚨 ALERT: {service_name} - {metrics.status.value}", extra={
            'service': service_name,
            'status': metrics.status.value,
            'response_time_ms': metrics.response_time_ms,
            'error': metrics.error_message,
            'metrics': metrics.additional_metrics
        })

    def get_service_health_report(self, service_name: str) -> Dict[str, Any]:
        """Получение отчета о здоровье сервиса"""
        if service_name not in self.metrics_history:
            return {'error': f'Нет данных для сервиса {service_name}'}
        
        history = self.metrics_history[service_name]
        if not history:
            return {'error': f'История метрик пуста для {service_name}'}
        
        # Последние метрики
        latest = history[-1]
        
        # Вычисляем статистику
        recent_checks = history[-10:]  # Последние 10 проверок
        avg_response_time = sum(m.response_time_ms for m in recent_checks) / len(recent_checks)
        
        healthy_checks = sum(1 for m in recent_checks if m.status == ConnectionStatus.HEALTHY)
        uptime_percentage = (healthy_checks / len(recent_checks)) * 100
        
        return {
            'service_name': service_name,
            'current_status': latest.status.value,
            'last_check': latest.last_check.isoformat(),
            'avg_response_time_ms': round(avg_response_time, 2),
            'uptime_percentage': round(uptime_percentage, 2),
            'total_checks': len(history),
            'recent_checks': len(recent_checks),
            'latest_metrics': latest.additional_metrics,
            'error_message': latest.error_message
        }

    def get_overall_health_report(self) -> Dict[str, Any]:
        """Получение общего отчета о здоровье системы"""
        services_status = {}
        
        for service_name in self.metrics_history:
            services_status[service_name] = self.get_service_health_report(service_name)
        
        # Определяем общий статус
        all_services_healthy = all(
            report.get('current_status') == 'healthy' 
            for report in services_status.values()
            if 'error' not in report
        )
        
        overall_status = 'healthy' if all_services_healthy else 'degraded'
        
        return {
            'overall_status': overall_status,
            'last_check': datetime.now(timezone.utc).isoformat(),
            'services': services_status,
            'monitoring_config': {
                'interval_seconds': self.monitoring_interval,
                'retention_hours': self.history_retention_hours,
                'alert_thresholds': self.alert_thresholds
            }
        }

# Глобальный инстанс мониторинга
connection_monitor = ConnectionMonitor()

# Функции для использования в API
async def get_health_status() -> Dict[str, Any]:
    """API функция для получения статуса здоровья"""
    return connection_monitor.get_overall_health_report()

async def get_service_status(service_name: str) -> Dict[str, Any]:
    """API функция для получения статуса конкретного сервиса"""
    return connection_monitor.get_service_health_report(service_name)

async def run_health_check() -> Dict[str, Any]:
    """API функция для запуска проверки здоровья"""
    return await connection_monitor.check_all_connections()
