"""
API для управления системой: мониторинг, бэкапы, кэш
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime

from ..services.connection_monitor import (
    connection_monitor,
    get_health_status,
    get_service_status,
    run_health_check
)
from ..services.backup_service import (
    backup_service,
    create_manual_backup,
    restore_from_backup,
    get_backup_list,
    get_backup_status
)
from ..services.cache_service import cache_service
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

# ===== МОНИТОРИНГ ПОДКЛЮЧЕНИЙ =====

@router.get("/health", summary="Общий статус здоровья системы")
async def get_system_health():
    """
    Получение общего статуса здоровья всех компонентов системы
    """
    try:
        health_data = await get_health_status()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "data": health_data
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса здоровья: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/{service_name}", summary="Статус конкретного сервиса")
async def get_service_health(service_name: str):
    """
    Получение детального статуса конкретного сервиса
    
    Доступные сервисы: postgresql, redis
    """
    try:
        service_data = await get_service_status(service_name)
        
        if 'error' in service_data:
            return {
                "success": False,
                "error": service_data['error'],
                "service": service_name
            }
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "service": service_name,
            "data": service_data
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса сервиса {service_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/health/check", summary="Запуск проверки здоровья")
async def run_system_health_check():
    """
    Принудительный запуск проверки здоровья всех сервисов
    """
    try:
        health_results = await run_health_check()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "results": health_results
        }
    except Exception as e:
        logger.error(f"Ошибка запуска проверки здоровья: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====

@router.get("/backup/status", summary="Статус системы резервного копирования")
async def backup_system_status():
    """
    Получение статуса системы резервного копирования
    """
    try:
        status_data = get_backup_status()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "data": status_data
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса бэкапов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/backup/list", summary="Список доступных резервных копий")
async def list_available_backups():
    """
    Получение списка всех доступных резервных копий
    """
    try:
        backup_data = get_backup_list()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "data": backup_data
        }
    except Exception as e:
        logger.error(f"Ошибка получения списка бэкапов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/create", summary="Создание резервной копии")
async def create_backup(background_tasks: BackgroundTasks):
    """
    Создание новой резервной копии базы данных
    """
    try:
        # Запускаем создание бэкапа в фоне
        result = await create_manual_backup()
        
        return {
            "success": result['success'],
            "timestamp": datetime.utcnow().isoformat(),
            "data": result
        }
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/restore/{filename}", summary="Восстановление из резервной копии")
async def restore_backup(filename: str):
    """
    Восстановление базы данных из резервной копии
    
    ⚠️ ВНИМАНИЕ: Эта операция перезапишет текущие данные!
    """
    try:
        result = await restore_from_backup(filename)
        
        return {
            "success": result['success'],
            "timestamp": datetime.utcnow().isoformat(),
            "data": result
        }
    except Exception as e:
        logger.error(f"Ошибка восстановления бэкапа: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== УПРАВЛЕНИЕ КЭШЕМ =====

@router.get("/cache/stats", summary="Статистика кэша")
async def get_cache_statistics():
    """
    Получение детальной статистики работы кэша
    """
    try:
        if not cache_service.connected:
            await cache_service.connect()
        
        stats = await cache_service.get_stats()
        health = await cache_service.health_check()
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "statistics": stats,
                "health": health
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear", summary="Очистка кэша")
async def clear_cache(pattern: Optional[str] = None):
    """
    Очистка кэша по паттерну или полная очистка
    
    - pattern: Паттерн для очистки (например: "user:123:*")
    - Если pattern не указан, очищается весь кэш
    """
    try:
        if not cache_service.connected:
            await cache_service.connect()
        
        if pattern:
            await cache_service.clear_pattern(pattern)
            message = f"Очищен кэш по паттерну: {pattern}"
        else:
            await cache_service.memory_cache.clear()
            message = "Очищен весь кэш в памяти"
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        }
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/warm-up", summary="Прогрев кэша")
async def warm_up_cache():
    """
    Прогрев кэша часто используемыми данными
    """
    try:
        if not cache_service.connected:
            await cache_service.connect()
        
        # Здесь можно добавить логику прогрева кэша
        # Например, загрузка конфигурации, статистики и т.д.
        
        await cache_service.set("system:warmed_up", True, 3600)
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Кэш прогрет успешно"
        }
    except Exception as e:
        logger.error(f"Ошибка прогрева кэша: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== СИСТЕМНАЯ ИНФОРМАЦИЯ =====

@router.get("/info", summary="Общая информация о системе")
async def get_system_info():
    """
    Получение общей информации о состоянии системы
    """
    try:
        # Собираем информацию из всех сервисов
        health_data = await get_health_status()
        backup_data = get_backup_status()
        
        cache_stats = {}
        try:
            if not cache_service.connected:
                await cache_service.connect()
            cache_stats = await cache_service.get_stats()
        except Exception:
            cache_stats = {"error": "Cache unavailable"}
        
        system_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "health_monitoring": {
                    "status": "active",
                    "overall_status": health_data.get('overall_status', 'unknown')
                },
                "backup_system": {
                    "status": "active" if backup_data['success'] else "error",
                    "last_backup": backup_data.get('last_backup'),
                    "total_backups": backup_data.get('total_backups', 0)
                },
                "cache_system": {
                    "status": "active" if cache_service.connected else "disconnected",
                    "hit_rate": cache_stats.get('hit_rate_percent', 0)
                }
            },
            "services": health_data.get('services', {}),
            "uptime": "System operational"
        }
        
        return {
            "success": True,
            "data": system_info
        }
    except Exception as e:
        logger.error(f"Ошибка получения системной информации: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== УПРАВЛЕНИЕ МОНИТОРИНГОМ =====

@router.post("/monitoring/start", summary="Запуск фонового мониторинга")
async def start_monitoring(background_tasks: BackgroundTasks):
    """
    Запуск фонового мониторинга подключений
    """
    try:
        # Запускаем мониторинг в фоне
        background_tasks.add_task(connection_monitor.start_monitoring)
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Мониторинг запущен в фоновом режиме"
        }
    except Exception as e:
        logger.error(f"Ошибка запуска мониторинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/schedule", summary="Запуск планировщика бэкапов")
async def start_backup_scheduler(background_tasks: BackgroundTasks):
    """
    Запуск планировщика автоматических резервных копий
    """
    try:
        # Запускаем планировщик в фоне
        background_tasks.add_task(backup_service.schedule_backups)
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Планировщик резервного копирования запущен"
        }
    except Exception as e:
        logger.error(f"Ошибка запуска планировщика бэкапов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== АДМИНИСТРАТИВНЫЕ ОПЕРАЦИИ =====

@router.post("/maintenance/start", summary="Включение режима обслуживания")
async def enable_maintenance_mode():
    """
    Включение режима обслуживания системы
    """
    try:
        # Сохраняем флаг в кэше
        await cache_service.set("system:maintenance_mode", True, 86400)
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Режим обслуживания включен"
        }
    except Exception as e:
        logger.error(f"Ошибка включения режима обслуживания: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/maintenance/stop", summary="Отключение режима обслуживания")
async def disable_maintenance_mode():
    """
    Отключение режима обслуживания системы
    """
    try:
        # Удаляем флаг из кэша
        await cache_service.delete("system:maintenance_mode")
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Режим обслуживания отключен"
        }
    except Exception as e:
        logger.error(f"Ошибка отключения режима обслуживания: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/maintenance/status", summary="Статус режима обслуживания")
async def get_maintenance_status():
    """
    Проверка статуса режима обслуживания
    """
    try:
        maintenance_mode = await cache_service.get("system:maintenance_mode")
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "maintenance_mode": bool(maintenance_mode),
            "message": "Режим обслуживания активен" if maintenance_mode else "Система работает в обычном режиме"
        }
    except Exception as e:
        logger.error(f"Ошибка проверки режима обслуживания: {e}")
        return {
            "success": False,
            "maintenance_mode": False,
            "error": str(e)
        }
