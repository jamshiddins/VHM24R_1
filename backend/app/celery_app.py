"""
Celery application для асинхронной обработки задач
"""
import os
from celery import Celery
from celery.schedules import crontab
import logging

logger = logging.getLogger(__name__)

def create_celery_app() -> Celery:
    """Создание и настройка Celery приложения"""
    
    # Получаем настройки из переменных окружения
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Создаем Celery приложение
    celery_app = Celery(
        "vhm24r",
        broker=redis_url,
        backend=redis_url,
        include=["app.celery_tasks"]
    )
    
    # Конфигурация Celery
    celery_app.conf.update(
        # Настройки задач
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        
        # Настройки результатов
        result_expires=3600,  # Результаты хранятся 1 час
        result_backend_transport_options={
            "master_name": "mymaster",
            "retry_policy": {
                "timeout": 5.0
            }
        },
        
        # Настройки routing
        task_routes={
            "app.celery_tasks.process_file_task": {"queue": "file_processing"},
            "app.celery_tasks.export_data_task": {"queue": "exports"},
            "app.celery_tasks.cleanup_temp_files": {"queue": "maintenance"},
            "app.celery_tasks.send_telegram_notification": {"queue": "notifications"},
        },
        
        # Worker настройки
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        
        # Мониторинг
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Периодические задачи
        beat_schedule={
            "cleanup-temp-files": {
                "task": "app.celery_tasks.cleanup_temp_files",
                "schedule": crontab(minute="0", hour="2"),  # Каждый день в 2:00
            },
            "generate-daily-analytics": {
                "task": "app.celery_tasks.generate_analytics_report",
                "schedule": crontab(minute="30", hour="1"),  # Каждый день в 1:30
            },
            "health-check": {
                "task": "app.celery_tasks.health_check_task",
                "schedule": 300.0,  # Каждые 5 минут
            },
        },
        
        # Retry настройки
        task_default_retry_delay=60,  # 1 минута между повторами
        task_max_retries=3,
        
        # Безопасность
        worker_disable_rate_limits=False,
        task_time_limit=1800,  # 30 минут максимум на задачу
        task_soft_time_limit=1500,  # Soft limit 25 минут
        
        # Логирование
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    )
    
    return celery_app

# Создаем глобальный экземпляр Celery
celery_app = create_celery_app()

# Настройка логирования Celery
def setup_celery_logging():
    """Настраивает логирование для Celery"""
    from celery.utils.log import get_task_logger
    
    # Настраиваем основной логгер
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Настраиваем логгер для задач
    task_logger = get_task_logger(__name__)
    task_logger.setLevel(logging.INFO)
    
    return task_logger

# Инициализируем логирование
task_logger = setup_celery_logging()

if __name__ == "__main__":
    # Запуск Celery worker
    celery_app.start()
