"""
Celery задачи для асинхронной обработки
"""
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from celery import current_task
from celery.exceptions import Retry
from sqlalchemy.orm import Session
from sqlalchemy import text

from .celery_app import celery_app, task_logger
from .database import SessionLocal
from . import crud, schemas
from .services.file_processor import file_processor


@celery_app.task(bind=True, name="app.celery_tasks.process_file_task")
def process_file_task(self, file_path: str, order_id: int, user_id: int) -> Dict[str, Any]:
    """
    Асинхронная обработка файла
    """
    task_logger.info(f"Начинаем обработку файла: {file_path}, заказ: {order_id}")
    
    db = SessionLocal()
    try:
        # Обновляем статус задачи
        current_task.update_state(  # type: ignore
            state="PROCESSING",
            meta={"status": "Обработка файла начата", "progress": 0}
        )
        
        # Обновляем заказ
        order_data = {
            "status": "processing",
            "metadata": {"celery_task_id": self.request.id}
        }
        crud.update_order(db, order_id, order_data)
        
        # Обрабатываем файл
        import asyncio
        result = asyncio.run(file_processor.process_file(file_path, order_id, user_id))
        
        # Обновляем статус завершения
        current_task.update_state(  # type: ignore
            state="SUCCESS",
            meta={
                "status": "Файл успешно обработан",
                "progress": 100,
                "result": result
            }
        )
        
        # Отправляем уведомление
        send_telegram_notification.delay(  # type: ignore
            user_id,
            f"✅ Файл успешно обработан!\n"
            f"Заказ: #{order_id}\n"
            f"Обработано строк: {result.get('processed_rows', 0)}\n"
            f"Всего строк: {result.get('total_rows', 0)}"
        )
        
        task_logger.info(f"Файл {file_path} успешно обработан")
        return result
        
    except Exception as e:
        task_logger.error(f"Ошибка обработки файла {file_path}: {str(e)}")
        
        # Обновляем статус ошибки
        current_task.update_state(  # type: ignore
            state="FAILURE",
            meta={"status": f"Ошибка: {str(e)}", "progress": 0}
        )
        
        # Обновляем заказ
        order_data = {
            "status": "cancelled",
            "metadata": {"error": str(e)}
        }
        crud.update_order(db, order_id, order_data)
        
        # Отправляем уведомление об ошибке
        send_telegram_notification.delay(  # type: ignore
            user_id,
            f"❌ Ошибка обработки файла!\n"
            f"Заказ: #{order_id}\n"
            f"Ошибка: {str(e)}"
        )
        
        # Правильный способ retry в Celery
        if self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        else:
            # Если превышено максимальное количество попыток, просто поднимаем исключение
            raise e
        
    finally:
        db.close()


@celery_app.task(bind=True, name="app.celery_tasks.export_data_task")
def export_data_task(self, export_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Асинхронный экспорт данных
    """
    task_logger.info(f"Начинаем экспорт данных: {export_request}")
    
    db = SessionLocal()
    try:
        # Обновляем статус
        current_task.update_state(  # type: ignore
            state="PROCESSING",
            meta={"status": "Экспорт данных начат", "progress": 0}
        )
        
        # Выполняем простой экспорт (базовая реализация)
        from .services.export_service import export_service
        
        # Создаем простой результат экспорта
        export_format = export_request.get("format", "csv")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{timestamp}.{export_format}"
        
        # Получаем данные для экспорта
        from .schemas import OrderFilters
        filters = OrderFilters()
        orders, _ = crud.get_orders_with_filters(db, filters, page=1, page_size=1000)
        
        # Создаем простой CSV файл
        import csv
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            if orders:
                fieldnames = ['order_number', 'machine_code', 'order_price', 'payment_type', 'status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for order in orders:
                    writer.writerow({
                        'order_number': getattr(order, 'order_number', ''),
                        'machine_code': getattr(order, 'machine_code', ''),
                        'order_price': getattr(order, 'order_price', ''),
                        'payment_type': getattr(order, 'payment_type', ''),
                        'status': getattr(order, 'status', '')
                    })
        
        result = {
            "file_path": file_path,
            "filename": filename,
            "records_count": len(orders),
            "export_format": export_format
        }
        
        # Обновляем статус
        current_task.update_state(  # type: ignore
            state="SUCCESS",
            meta={"status": "Экспорт завершен", "progress": 100, "file_path": result["file_path"]}
        )
        
        # Отправляем уведомление
        if export_request.get("user_id"):
            send_telegram_notification.delay(  # type: ignore
                export_request["user_id"],
                f"📊 Экспорт данных готов!\n"
                f"Формат: {export_request.get('format', 'CSV')}\n"
                f"Файл готов к скачиванию"
            )
        
        task_logger.info("Экспорт данных завершен успешно")
        return result
        
    except Exception as e:
        task_logger.error(f"Ошибка экспорта данных: {str(e)}")
        
        current_task.update_state(  # type: ignore
            state="FAILURE",
            meta={"status": f"Ошибка экспорта: {str(e)}", "progress": 0}
        )
        
        # Правильный способ retry в Celery
        if self.request.retries < 3:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        else:
            # Если превышено максимальное количество попыток, просто поднимаем исключение
            raise e
        
    finally:
        db.close()


@celery_app.task(name="app.celery_tasks.send_telegram_notification")
def send_telegram_notification(user_id: int, message: str) -> bool:
    """
    Отправка уведомления в Telegram
    """
    task_logger.info(f"Отправляем уведомление пользователю {user_id}")
    
    try:
        # Простая реализация отправки уведомления
        # В реальном приложении здесь будет использоваться Telegram Bot API
        task_logger.info(f"Уведомление для пользователя {user_id}: {message}")
        return True
        
    except Exception as e:
        task_logger.error(f"Ошибка отправки уведомления: {str(e)}")
        return False


@celery_app.task(name="app.celery_tasks.cleanup_temp_files")
def cleanup_temp_files() -> Dict[str, Any]:
    """
    Очистка временных файлов
    """
    task_logger.info("Начинаем очистку временных файлов")
    
    cleaned_files = 0
    freed_space = 0
    
    try:
        # Директории для очистки
        temp_dirs = [
            os.path.join(os.getcwd(), "backend", "temp"),
            os.path.join(os.getcwd(), "backend", "uploads"),
            tempfile.gettempdir()
        ]
        
        # Файлы старше 24 часов
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
                
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    try:
                        # Проверяем время создания файла
                        file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files += 1
                            freed_space += file_size
                            
                    except Exception as e:
                        task_logger.warning(f"Не удалось удалить файл {file_path}: {str(e)}")
        
        # Очистка пустых директорий
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    for root, dirs, files in os.walk(temp_dir, topdown=False):
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                except Exception as e:
                    task_logger.warning(f"Ошибка при удалении пустых директорий: {str(e)}")
        
        result = {
            "cleaned_files": cleaned_files,
            "freed_space_mb": round(freed_space / (1024 * 1024), 2),
            "timestamp": datetime.now().isoformat()
        }
        
        task_logger.info(f"Очистка завершена: {result}")
        return result
        
    except Exception as e:
        task_logger.error(f"Ошибка очистки временных файлов: {str(e)}")
        raise


@celery_app.task(name="app.celery_tasks.generate_analytics_report")
def generate_analytics_report() -> Dict[str, Any]:
    """
    Генерация ежедневного аналитического отчета
    """
    task_logger.info("Генерируем ежедневный аналитический отчет")
    
    db = SessionLocal()
    try:
        # Получаем статистику за последние 24 часа
        yesterday = datetime.now() - timedelta(days=1)
        
        # Получаем базовую статистику
        from .schemas import OrderFilters
        
        # Создаем фильтры для получения заказов
        filters = OrderFilters()
        orders, total_orders_count = crud.get_orders_with_filters(db, filters, page=1, page_size=1000)
        users = crud.get_all_users(db)
        
        total_orders = len(orders)
        completed_orders = len([o for o in orders if o.status == "completed"])
        failed_orders = len([o for o in orders if o.status == "cancelled"])
        
        new_users = len([u for u in users if hasattr(u, 'created_at') and getattr(u, 'created_at', None) and getattr(u, 'created_at') >= yesterday])
        active_users = len(users)
        
        report = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "orders": {
                "total": total_orders,
                "completed": completed_orders,
                "failed": failed_orders,
                "success_rate": round((completed_orders / max(total_orders, 1)) * 100, 2)
            },
            "users": {
                "new": new_users,
                "active": active_users
            },
            "files": {
                "processed": completed_orders,
                "total_size_mb": 0  # Заглушка
            },
            "timestamp": datetime.now().isoformat()
        }
        
        task_logger.info(f"Аналитический отчет сгенерирован: {report}")
        return report
        
    except Exception as e:
        task_logger.error(f"Ошибка генерации аналитического отчета: {str(e)}")
        raise
        
    finally:
        db.close()


@celery_app.task(name="app.celery_tasks.health_check_task")
def health_check_task() -> Dict[str, Any]:
    """
    Проверка здоровья системы
    """
    task_logger.info("Выполняем проверку здоровья системы")
    
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "database": False,
        "redis": False,
        "file_system": False,
        "celery_workers": False
    }
    
    # Проверка базы данных
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        health_status["database"] = True
        db.close()
    except Exception as e:
        task_logger.error(f"Проблема с базой данных: {str(e)}")
    
    # Проверка Redis
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        if redis_client is not None:
            redis_client.ping()
            health_status["redis"] = True
    except Exception as e:
        task_logger.error(f"Проблема с Redis: {str(e)}")
    
    # Проверка файловой системы
    try:
        temp_dir = os.path.join(os.getcwd(), "backend", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        test_file = os.path.join(temp_dir, f"health_check_{datetime.now().timestamp()}.tmp")
        with open(test_file, 'w') as f:
            f.write("health check")
        
        if os.path.exists(test_file):
            os.remove(test_file)
            health_status["file_system"] = True
            
    except Exception as e:
        task_logger.error(f"Проблема с файловой системой: {str(e)}")
    
    # Проверка Celery workers
    try:
        from .celery_app import celery_app
        stats = celery_app.control.inspect().stats()
        health_status["celery_workers"] = bool(stats)
    except Exception as e:
        task_logger.error(f"Проблема с Celery workers: {str(e)}")
    
    # Общий статус здоровья
    health_status["overall_healthy"] = all([
        health_status["database"],
        health_status["redis"],
        health_status["file_system"]
    ])
    
    task_logger.info(f"Проверка здоровья завершена: {health_status}")
    return health_status


@celery_app.task(name="app.celery_tasks.database_backup_task")
def database_backup_task() -> Dict[str, Any]:
    """
    Создание резервной копии базы данных
    """
    task_logger.info("Начинаем создание резервной копии базы данных")
    
    try:
        backup_dir = os.path.join(os.getcwd(), "backend", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"vhm24r_backup_{timestamp}.db")
        
        # Простое копирование файла базы данных (для SQLite)
        db_file = os.path.join(os.getcwd(), "backend", "vhm24r.db")
        if os.path.exists(db_file):
            shutil.copy2(db_file, backup_file)
            
            result = {
                "backup_file": backup_file,
                "backup_size": os.path.getsize(backup_file),
                "timestamp": datetime.now().isoformat()
            }
            
            task_logger.info(f"Резервная копия создана: {result}")
            return result
        else:
            raise FileNotFoundError("Файл базы данных не найден")
            
    except Exception as e:
        task_logger.error(f"Ошибка создания резервной копии: {str(e)}")
        raise


@celery_app.task(name="app.celery_tasks.optimize_database_task")
def optimize_database_task() -> Dict[str, Any]:
    """
    Оптимизация базы данных
    """
    task_logger.info("Начинаем оптимизацию базы данных")
    
    db = SessionLocal()
    try:
        # Выполняем VACUUM для SQLite
        db.execute(text("VACUUM"))
        db.execute(text("ANALYZE"))
        db.commit()
        
        result = {
            "optimization_completed": True,
            "timestamp": datetime.now().isoformat()
        }
        
        task_logger.info("Оптимизация базы данных завершена")
        return result
        
    except Exception as e:
        task_logger.error(f"Ошибка оптимизации базы данных: {str(e)}")
        raise
        
    finally:
        db.close()
