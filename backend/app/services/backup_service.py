"""
Сервис резервного копирования PostgreSQL для Railway
"""
import os
import asyncio
import subprocess
import gzip
import shutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)

class BackupService:
    """Сервис резервного копирования базы данных"""
    
    def __init__(self):
        self.backup_dir = Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Настройки бэкапа
        self.retention_days = 7  # Хранить бэкапы 7 дней
        self.daily_backups_count = 7  # Максимум 7 ежедневных бэкапов
        self.weekly_backups_count = 4  # Максимум 4 еженедельных бэкапа
        
        # Расписание бэкапов
        self.backup_schedule = {
            'daily': {'hour': 2, 'minute': 0},  # Ежедневно в 2:00
            'weekly': {'weekday': 0, 'hour': 3, 'minute': 0}  # Еженедельно по понедельникам в 3:00
        }
        
        logger.info("BackupService инициализирован")

    async def create_backup(self, backup_type: str = "manual") -> Dict[str, Any]:
        """Создание резервной копии базы данных"""
        try:
            from ..database import DATABASE_URL
            
            if not DATABASE_URL or DATABASE_URL.startswith('sqlite'):
                return {
                    'success': False,
                    'error': 'PostgreSQL не настроен, резервное копирование недоступно'
                }
            
            # Генерируем имя файла бэкапа
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            backup_filename = f"vhm24r_backup_{backup_type}_{timestamp}.sql.gz"
            backup_path = self.backup_dir / backup_filename
            
            # Извлекаем параметры подключения из URL
            db_params = self._parse_database_url(DATABASE_URL)
            
            logger.info(f"Создание резервной копии: {backup_filename}")
            
            # Создаем временный файл для pg_dump
            temp_sql_path = self.backup_dir / f"temp_{timestamp}.sql"
            
            # Команда pg_dump
            dump_command = [
                'pg_dump',
                f"--host={db_params['host']}",
                f"--port={db_params['port']}",
                f"--username={db_params['user']}",
                f"--dbname={db_params['database']}",
                '--verbose',
                '--clean',
                '--no-owner',
                '--no-privileges',
                f"--file={temp_sql_path}"
            ]
            
            # Устанавливаем переменную окружения для пароля
            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']
            
            # Выполняем pg_dump
            process = await asyncio.create_subprocess_exec(
                *dump_command,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_message = stderr.decode() if stderr else "Неизвестная ошибка pg_dump"
                logger.error(f"Ошибка создания бэкапа: {error_message}")
                
                # Очищаем временный файл
                if temp_sql_path.exists():
                    temp_sql_path.unlink()
                
                return {
                    'success': False,
                    'error': f'Ошибка pg_dump: {error_message}',
                    'return_code': process.returncode
                }
            
            # Сжимаем файл с помощью gzip
            with open(temp_sql_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Удаляем временный файл
            temp_sql_path.unlink()
            
            # Получаем информацию о файле
            backup_size = backup_path.stat().st_size
            backup_size_mb = round(backup_size / (1024 * 1024), 2)
            
            # Сохраняем метаданные бэкапа
            metadata = {
                'filename': backup_filename,
                'backup_type': backup_type,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'database_url': DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden',
                'size_bytes': backup_size,
                'size_mb': backup_size_mb,
                'compressed': True
            }
            
            metadata_path = self.backup_dir / f"{backup_filename}.metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Резервная копия создана успешно: {backup_filename} ({backup_size_mb} MB)")
            
            # Очищаем старые бэкапы
            await self._cleanup_old_backups()
            
            return {
                'success': True,
                'filename': backup_filename,
                'size_mb': backup_size_mb,
                'created_at': metadata['created_at'],
                'backup_type': backup_type,
                'path': str(backup_path)
            }
            
        except Exception as e:
            logger.error(f"Критическая ошибка создания бэкапа: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def restore_backup(self, backup_filename: str) -> Dict[str, Any]:
        """Восстановление из резервной копии"""
        try:
            from ..database import DATABASE_URL
            
            if not DATABASE_URL or DATABASE_URL.startswith('sqlite'):
                return {
                    'success': False,
                    'error': 'PostgreSQL не настроен, восстановление недоступно'
                }
            
            backup_path = self.backup_dir / backup_filename
            if not backup_path.exists():
                return {
                    'success': False,
                    'error': f'Файл бэкапа не найден: {backup_filename}'
                }
            
            # Проверяем метаданные
            metadata_path = self.backup_dir / f"{backup_filename}.metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            logger.info(f"Восстановление из резервной копии: {backup_filename}")
            
            # Извлекаем параметры подключения
            db_params = self._parse_database_url(DATABASE_URL)
            
            # Создаем временный файл для распакованного SQL
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            temp_sql_path = self.backup_dir / f"restore_temp_{timestamp}.sql"
            
            # Распаковываем gzip файл
            with gzip.open(backup_path, 'rb') as f_in:
                with open(temp_sql_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Команда psql для восстановления
            restore_command = [
                'psql',
                f"--host={db_params['host']}",
                f"--port={db_params['port']}",
                f"--username={db_params['user']}",
                f"--dbname={db_params['database']}",
                f"--file={temp_sql_path}",
                '--verbose'
            ]
            
            # Устанавливаем переменную окружения для пароля
            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']
            
            # Выполняем восстановление
            process = await asyncio.create_subprocess_exec(
                *restore_command,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Удаляем временный файл
            temp_sql_path.unlink()
            
            if process.returncode != 0:
                error_message = stderr.decode() if stderr else "Неизвестная ошибка psql"
                logger.error(f"Ошибка восстановления: {error_message}")
                
                return {
                    'success': False,
                    'error': f'Ошибка psql: {error_message}',
                    'return_code': process.returncode
                }
            
            logger.info(f"Восстановление завершено успешно: {backup_filename}")
            
            return {
                'success': True,
                'filename': backup_filename,
                'restored_at': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Критическая ошибка восстановления: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def list_backups(self) -> Dict[str, Any]:
        """Получение списка доступных резервных копий"""
        try:
            backups = []
            
            for backup_file in self.backup_dir.glob("*.sql.gz"):
                metadata_file = self.backup_dir / f"{backup_file.name}.metadata.json"
                
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                else:
                    # Создаем базовые метаданные если файл отсутствует
                    stat = backup_file.stat()
                    metadata = {
                        'filename': backup_file.name,
                        'created_at': datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
                        'size_bytes': stat.st_size,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'backup_type': 'unknown'
                    }
                
                backups.append(metadata)
            
            # Сортируем по дате создания (новые первыми)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            total_size_mb = sum(b['size_mb'] for b in backups)
            
            return {
                'success': True,
                'backups': backups,
                'total_count': len(backups),
                'total_size_mb': round(total_size_mb, 2),
                'backup_dir': str(self.backup_dir)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения списка бэкапов: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _cleanup_old_backups(self):
        """Очистка старых резервных копий"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            for backup_file in self.backup_dir.glob("*.sql.gz"):
                metadata_file = self.backup_dir / f"{backup_file.name}.metadata.json"
                
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    created_at = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                    
                    if created_at < cutoff_date:
                        backup_file.unlink()
                        metadata_file.unlink()
                        logger.info(f"Удален старый бэкап: {backup_file.name}")
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")

    def _parse_database_url(self, database_url: str) -> Dict[str, str]:
        """Парсинг URL базы данных"""
        # Пример: postgresql://user:password@host:port/database
        from urllib.parse import urlparse
        
        parsed = urlparse(database_url)
        
        return {
            'host': parsed.hostname or 'localhost',
            'port': str(parsed.port or 5432),
            'database': parsed.path.lstrip('/') or 'postgres',
            'user': parsed.username or 'postgres',
            'password': parsed.password or ''
        }

    async def schedule_backups(self):
        """Планировщик автоматических бэкапов"""
        logger.info("Запуск планировщика резервного копирования")
        
        while True:
            try:
                now = datetime.now(timezone.utc)
                
                # Проверяем ежедневный бэкап
                if (now.hour == self.backup_schedule['daily']['hour'] and 
                    now.minute == self.backup_schedule['daily']['minute']):
                    
                    logger.info("Запуск ежедневного резервного копирования")
                    result = await self.create_backup("daily")
                    
                    if result['success']:
                        logger.info(f"Ежедневный бэкап создан: {result['filename']}")
                    else:
                        logger.error(f"Ошибка ежедневного бэкапа: {result['error']}")
                
                # Проверяем еженедельный бэкап
                if (now.weekday() == self.backup_schedule['weekly']['weekday'] and
                    now.hour == self.backup_schedule['weekly']['hour'] and 
                    now.minute == self.backup_schedule['weekly']['minute']):
                    
                    logger.info("Запуск еженедельного резервного копирования")
                    result = await self.create_backup("weekly")
                    
                    if result['success']:
                        logger.info(f"Еженедельный бэкап создан: {result['filename']}")
                    else:
                        logger.error(f"Ошибка еженедельного бэкапа: {result['error']}")
                
                # Ждем минуту до следующей проверки
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике бэкапов: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке

    def get_backup_status(self) -> Dict[str, Any]:
        """Получение статуса системы резервного копирования"""
        try:
            backups_info = self.list_backups()
            
            if not backups_info['success']:
                return backups_info
            
            backups = backups_info['backups']
            now = datetime.now(timezone.utc)
            
            # Анализируем последние бэкапы
            daily_backups = [b for b in backups if b.get('backup_type') == 'daily']
            weekly_backups = [b for b in backups if b.get('backup_type') == 'weekly']
            manual_backups = [b for b in backups if b.get('backup_type') == 'manual']
            
            last_backup = backups[0] if backups else None
            last_backup_age = None
            
            if last_backup:
                last_backup_time = datetime.fromisoformat(last_backup['created_at'].replace('Z', '+00:00'))
                last_backup_age = (now - last_backup_time).total_seconds() / 3600  # часы
            
            # Определяем статус
            status = 'healthy'
            warnings = []
            
            if not backups:
                status = 'critical'
                warnings.append('Резервные копии отсутствуют')
            elif last_backup_age and last_backup_age > 48:  # Больше 2 дней
                status = 'warning'
                warnings.append(f'Последний бэкап создан {round(last_backup_age, 1)} часов назад')
            
            return {
                'success': True,
                'status': status,
                'warnings': warnings,
                'total_backups': len(backups),
                'daily_backups': len(daily_backups),
                'weekly_backups': len(weekly_backups),
                'manual_backups': len(manual_backups),
                'total_size_mb': backups_info['total_size_mb'],
                'last_backup': last_backup,
                'last_backup_age_hours': round(last_backup_age, 1) if last_backup_age else None,
                'retention_days': self.retention_days,
                'backup_dir': str(self.backup_dir)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса бэкапов: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Глобальный инстанс сервиса резервного копирования
backup_service = BackupService()

# API функции
async def create_manual_backup() -> Dict[str, Any]:
    """Создание ручной резервной копии"""
    return await backup_service.create_backup("manual")

async def restore_from_backup(filename: str) -> Dict[str, Any]:
    """Восстановление из резервной копии"""
    return await backup_service.restore_backup(filename)

def get_backup_list() -> Dict[str, Any]:
    """Получение списка резервных копий"""
    return backup_service.list_backups()

def get_backup_status() -> Dict[str, Any]:
    """Получение статуса системы резервного копирования"""
    return backup_service.get_backup_status()
