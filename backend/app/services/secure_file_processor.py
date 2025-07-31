import os
import asyncio
import secrets
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from io import BytesIO
import magic

# Импорты для безопасной валидации файлов
try:
    import defusedxml.ElementTree as ET
    XML_PARSER_SAFE = True
except ImportError:
    import xml.etree.ElementTree as ET
    import warnings
    warnings.warn("defusedxml не установлен. Используется небезопасный XML парсер.", UserWarning)
    XML_PARSER_SAFE = False

import pandas as pd
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from ..database import SessionLocal
from .. import crud, schemas
from ..utils.logger import get_logger, performance_logger, db_logger
from ..utils.exceptions import (
    FileProcessingError, 
    DatabaseError, 
    ValidationError,
    SecurityError,
    handle_file_processing_error,
    handle_database_error,
    handle_validation_error
)

logger = get_logger(__name__)

class SecureFileValidator:
    """Безопасный валидатор файлов с проверкой magic bytes"""
    
    MAGIC_SIGNATURES = {
        'csv': [b'', b'\xef\xbb\xbf'],  # UTF-8 BOM опционально
        'xlsx': [b'PK\x03\x04'],        # ZIP format
        'xls': [b'\xd0\xcf\x11\xe0'],   # MS Office compound
        'pdf': [b'%PDF'],
        'doc': [b'\xd0\xcf\x11\xe0'],   # MS Office compound
        'docx': [b'PK\x03\x04'],        # ZIP-based
        'json': [b'{', b'['],           # JSON start
        'xml': [b'<?xml', b'<'],        # XML start
        'zip': [b'PK\x03\x04'],         # ZIP signature
        'txt': [b''],                   # Любой текст
        'tsv': [b'', b'\xef\xbb\xbf']   # Как CSV
    }
    
    MAX_FILE_SIZES = {
        'csv': 100 * 1024 * 1024,      # 100MB
        'xlsx': 50 * 1024 * 1024,      # 50MB
        'xls': 50 * 1024 * 1024,       # 50MB
        'pdf': 20 * 1024 * 1024,       # 20MB
        'doc': 20 * 1024 * 1024,       # 20MB
        'docx': 20 * 1024 * 1024,      # 20MB
        'json': 10 * 1024 * 1024,      # 10MB
        'xml': 10 * 1024 * 1024,       # 10MB
        'zip': 100 * 1024 * 1024,      # 100MB
        'txt': 10 * 1024 * 1024,       # 10MB
        'tsv': 100 * 1024 * 1024       # 100MB
    }
    
    ALLOWED_MIME_TYPES = {
        'csv': ['text/csv', 'application/csv', 'text/plain'],
        'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'xls': ['application/vnd.ms-excel'],
        'pdf': ['application/pdf'],
        'doc': ['application/msword'],
        'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'json': ['application/json', 'text/json'],
        'xml': ['application/xml', 'text/xml'],
        'zip': ['application/zip'],
        'txt': ['text/plain'],
        'tsv': ['text/tab-separated-values', 'text/plain']
    }
    
    def validate_file(self, file_content: bytes, expected_format: str, filename: str) -> bool:
        """Комплексная валидация файла"""
        logger.info(f"Начинается валидация файла: {filename}, формат: {expected_format}")
        
        # 1. Проверка размера
        max_size = self.MAX_FILE_SIZES.get(expected_format, 10*1024*1024)
        if len(file_content) > max_size:
            raise ValidationError(f"Файл слишком большой для формата {expected_format}. Максимум: {max_size} байт")
        
        if len(file_content) == 0:
            raise ValidationError("Файл пустой")
        
        # 2. Проверка magic bytes
        valid_signatures = self.MAGIC_SIGNATURES.get(expected_format, [])
        if valid_signatures and not any(file_content.startswith(sig) for sig in valid_signatures if sig):
            # Для CSV и TXT файлов magic bytes могут быть пустыми
            if expected_format not in ['csv', 'txt', 'tsv', 'json', 'xml']:
                raise ValidationError(f"Неверный формат файла. Ожидался {expected_format}")
        
        # 3. Проверка MIME типа через python-magic (если доступен)
        try:
            detected_mime = magic.from_buffer(file_content, mime=True)
            allowed_mimes = self.ALLOWED_MIME_TYPES.get(expected_format, [])
            
            if allowed_mimes and detected_mime not in allowed_mimes:
                logger.warning(f"MIME тип не соответствует: {detected_mime}, ожидался один из {allowed_mimes}")
                # Не прерываем валидацию, только логируем предупреждение
        except Exception as e:
            logger.warning(f"Не удалось определить MIME тип: {e}")
        
        # 4. Проверка на вредоносное содержимое
        if self._contains_suspicious_content(file_content, filename):
            raise SecurityError("Обнаружено подозрительное содержимое в файле")
        
        # 5. Специфичные проверки по формату
        self._validate_format_specific(file_content, expected_format)
        
        logger.info(f"Файл {filename} успешно прошел валидацию")
        return True
    
    def _contains_suspicious_content(self, content: bytes, filename: str) -> bool:
        """Проверка на подозрительное содержимое"""
        # Проверяем на исполняемые файлы
        suspicious_signatures = [
            b'MZ',                    # PE executable
            b'\x7fELF',              # ELF executable
            b'\xca\xfe\xba\xbe',     # Java class file
            b'#!/bin/',              # Shell script
            b'<script',              # JavaScript
            b'javascript:',          # JavaScript URL
            b'vbscript:',            # VBScript URL
            b'data:text/html',       # HTML data URL
        ]
        
        content_lower = content[:1024].lower()  # Проверяем первые 1024 байта
        
        for signature in suspicious_signatures:
            if signature in content_lower:
                logger.warning(f"Обнаружена подозрительная сигнатура в файле {filename}: {signature}")
                return True
        
        # Проверяем на SQL инъекции в содержимом
        sql_patterns = [
            b'drop table', b'delete from', b'insert into',
            b'update set', b'union select', b'exec('
        ]
        
        for pattern in sql_patterns:
            if pattern in content_lower:
                logger.warning(f"Обнаружен подозрительный SQL паттерн в файле {filename}")
                return True
        
        return False
    
    def _validate_format_specific(self, content: bytes, format_type: str):
        """Специфичная валидация по типу файла"""
        if format_type == 'json':
            try:
                json.loads(content.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValidationError("Некорректный JSON формат")
        
        elif format_type == 'xml':
            try:
                if XML_PARSER_SAFE:
                    ET.fromstring(content)
                else:
                    # Дополнительная проверка для небезопасного парсера
                    if b'<!ENTITY' in content or b'<!DOCTYPE' in content:
                        raise SecurityError("XML содержит потенциально опасные конструкции")
                    ET.fromstring(content)
            except ET.ParseError:
                raise ValidationError("Некорректный XML формат")
        
        elif format_type in ['csv', 'tsv']:
            # Проверяем, что можно декодировать как текст
            encodings = ['utf-8', 'cp1251', 'iso-8859-1']
            decoded = False
            for encoding in encodings:
                try:
                    content.decode(encoding)
                    decoded = True
                    break
                except UnicodeDecodeError:
                    continue
            
            if not decoded:
                raise ValidationError("Не удалось определить кодировку текстового файла")

def secure_file_path(filename: str, upload_folder: str, user_id: int) -> str:
    """Безопасное создание пути к файлу с защитой от Path Traversal"""
    
    # 1. Очистка имени файла от опасных символов
    if not filename:
        raise SecurityError("Имя файла не может быть пустым")
    
    # Удаляем путь из имени файла, оставляем только название
    filename = os.path.basename(filename)
    
    # Проверяем на потенциально опасные имена файлов
    dangerous_names = [
        'con', 'prn', 'aux', 'nul',
        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
    ]
    
    name_without_ext = os.path.splitext(filename)[0].lower()
    if name_without_ext in dangerous_names:
        raise SecurityError(f"Недопустимое имя файла: {filename}")
    
    # 2. Удаление опасных символов и последовательностей
    # Удаляем все варианты path traversal
    dangerous_patterns = [
        '../', '..\\', './', '.\\',
        '..%2f', '..%2F', '..%5c', '..%5C',
        '%2e%2e%2f', '%2e%2e%5c',
        '..../', '....\\',
    ]
    
    filename_lower = filename.lower()
    for pattern in dangerous_patterns:
        if pattern in filename_lower:
            raise SecurityError(f"Обнаружена попытка Path Traversal в имени файла: {filename}")
    
    # 3. Очистка от недопустимых символов
    # Разрешаем только буквы, цифры, точки, дефисы и подчеркивания
    clean_filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    # Проверяем, что остались допустимые символы
    if not clean_filename or clean_filename == '.' or clean_filename == '..':
        # Генерируем безопасное имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extension = Path(filename).suffix.lower()
        clean_filename = f"file_{timestamp}_{secrets.token_hex(8)}{extension}"
    
    # 4. Добавляем префикс пользователя для изоляции
    user_prefix = f"user_{user_id}"
    final_filename = f"{user_prefix}_{clean_filename}"
    
    # 5. Создаем безопасный путь
    # Убеждаемся, что upload_folder - абсолютный путь
    upload_folder = os.path.abspath(upload_folder)
    
    # Создаем полный путь
    file_path = os.path.join(upload_folder, final_filename)
    file_path = os.path.abspath(file_path)
    
    # 6. КРИТИЧЕСКАЯ ПРОВЕРКА: убеждаемся, что файл остается в пределах upload_folder
    if not file_path.startswith(upload_folder):
        raise SecurityError("Попытка Path Traversal заблокирована")
    
    # 7. Проверяем, что папка существует и создаем если нужно
    os.makedirs(upload_folder, exist_ok=True)
    
    logger.info(f"Создан безопасный путь: {file_path} для пользователя {user_id}")
    return file_path

class SecureFileProcessor:
    """Безопасный процессор файлов с защитой от уязвимостей"""
    
    def __init__(self):
        self.validator = SecureFileValidator()
        self.temp_dir = tempfile.mkdtemp(prefix="secure_processor_")
        
        # Настройка безопасности
        os.chmod(self.temp_dir, 0o700)  # Только для владельца
        
        logger.info(f"Инициализирован безопасный процессор файлов: {self.temp_dir}")
    
    def __del__(self):
        """Безопасная очистка временных файлов"""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info("Временные файлы очищены")
        except Exception as e:
            logger.warning(f"Ошибка при очистке временных файлов: {e}")
    
    def get_db(self) -> Session:
        """Получает сессию базы данных"""
        return SessionLocal()
    
    async def process_file_secure(self, file_content: bytes, filename: str, user_id: int, 
                                  upload_folder: str) -> Dict[str, Any]:
        """Безопасная обработка файла с полной валидацией"""
        start_time = datetime.now()
        
        logger.info(f"Начинается безопасная обработка файла: {filename} для пользователя {user_id}")
        
        try:
            # 1. Определяем формат файла
            file_extension = Path(filename).suffix.lower().lstrip('.')
            if not file_extension:
                raise ValidationError("Файл должен иметь расширение")
            
            # 2. Валидируем файл
            self.validator.validate_file(file_content, file_extension, filename)
            
            # 3. Создаем безопасный путь для сохранения
            secure_path = secure_file_path(filename, upload_folder, user_id)
            
            # 4. Сохраняем файл безопасно
            with open(secure_path, 'wb') as f:
                f.write(file_content)
            
            # Устанавливаем безопасные права доступа
            os.chmod(secure_path, 0o600)  # Только для владельца
            
            # 5. Создаем хэш файла для проверки целостности
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # 6. Записываем информацию в базу данных
            db = self.get_db()
            try:
                file_record = crud.create_uploaded_file(db, {
                    'filename': os.path.basename(secure_path),
                    'original_filename': filename,
                    'file_path': secure_path,
                    'file_size': len(file_content),
                    'file_hash': file_hash,
                    'mime_type': self.validator.ALLOWED_MIME_TYPES.get(file_extension, ['application/octet-stream'])[0],
                    'uploaded_by': user_id,
                    'processing_status': 'pending',
                    'uploaded_at': datetime.utcnow()
                })
                
                logger.info(f"Файл безопасно сохранен: {secure_path}, ID: {file_record.id}")
                
                result = {
                    'file_id': file_record.id,
                    'secure_path': secure_path,
                    'file_hash': file_hash,
                    'file_size': len(file_content),
                    'processing_time': (datetime.now() - start_time).total_seconds(),
                    'status': 'uploaded_securely'
                }
                
                return result
                
            except SQLAlchemyError as e:
                # Удаляем файл если не удалось записать в БД
                try:
                    os.remove(secure_path)
                except:
                    pass
                raise handle_database_error("create_uploaded_file", "files", e)
            finally:
                db.close()
        
        except (SecurityError, ValidationError):
            # Перебрасываем ошибки безопасности и валидации как есть
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке файла {filename}: {e}")
            raise handle_file_processing_error(filename, "secure_processing", e)
    
    async def validate_and_sanitize_upload(self, file_content: bytes, filename: str, 
                                           user_id: int) -> Dict[str, Any]:
        """Валидация и очистка загружаемого файла"""
        try:
            # Определяем тип файла
            file_extension = Path(filename).suffix.lower().lstrip('.')
            
            # Проверяем разрешенные типы
            allowed_extensions = ['csv', 'xlsx', 'xls', 'json', 'xml', 'txt', 'tsv', 'pdf']
            if file_extension not in allowed_extensions:
                raise ValidationError(f"Тип файла '{file_extension}' не разрешен. Разрешены: {', '.join(allowed_extensions)}")
            
            # Валидируем содержимое
            self.validator.validate_file(file_content, file_extension, filename)
            
            # Создаем безопасное имя файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"user_{user_id}_{timestamp}_{secrets.token_hex(8)}.{file_extension}"
            
            # Вычисляем хэш для дедупликации
            content_hash = hashlib.sha256(file_content).hexdigest()
            
            return {
                'valid': True,
                'safe_filename': safe_filename,
                'original_filename': filename,
                'file_extension': file_extension,
                'file_size': len(file_content),
                'content_hash': content_hash,
                'validation_passed': True
            }
            
        except (SecurityError, ValidationError) as e:
            return {
                'valid': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'validation_passed': False
            }
        except Exception as e:
            logger.error(f"Ошибка валидации файла {filename}: {e}")
            return {
                'valid': False,
                'error': f"Внутренняя ошибка валидации: {str(e)}",
                'error_type': 'InternalError',
                'validation_passed': False
            }

# Глобальный экземпляр безопасного процессора
secure_file_processor = SecureFileProcessor()

# Функции для использования в других модулях
async def process_file_securely(file_content: bytes, filename: str, user_id: int, 
                                upload_folder: str) -> Dict[str, Any]:
    """Безопасная обработка файла"""
    return await secure_file_processor.process_file_secure(file_content, filename, user_id, upload_folder)

async def validate_upload_securely(file_content: bytes, filename: str, user_id: int) -> Dict[str, Any]:
    """Безопасная валидация загрузки"""
    return await secure_file_processor.validate_and_sanitize_upload(file_content, filename, user_id)
