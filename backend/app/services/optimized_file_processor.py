"""
Оптимизированный процессор файлов для VHM24R
Исправляет проблемы производительности при обработке больших файлов
"""

import asyncio
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pathlib import Path
import hashlib
import json

from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Order, OrderChange, UploadedFile
from ..crud_optimized import (
    optimized_order_crud, 
    optimized_order_change_crud,
    optimized_file_crud
)

logger = logging.getLogger(__name__)

class OptimizedFileProcessor:
    """Оптимизированный процессор файлов с батчевой обработкой"""
    
    # Константы для оптимизации
    BATCH_SIZE = 1000  # Размер батча для вставки в БД
    PROGRESS_UPDATE_INTERVAL = 5000  # Интервал обновления прогресса
    MAX_WORKERS = 4  # Максимальное количество воркеров
    CHUNK_SIZE = 10000  # Размер чанка для чтения файла
    
    def __init__(self):
        self.stats = {
            'total_processed': 0,
            'processing_time': 0,
            'batch_count': 0,
            'errors': []
        }
    
    async def process_file_optimized(
        self, 
        file_path: str, 
        file_id: int, 
        user_id: int,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Оптимизированная обработка файла с батчингом и асинхронностью
        """
        start_time = time.time()
        
        try:
            # Обновляем статус файла
            await self._update_file_status(file_id, 'processing')
            
            # Загружаем файл асинхронно
            df = await self._load_file_async(file_path)
            total_rows = len(df)
            
            logger.info(f"Loaded file {file_path} with {total_rows} rows")
            
            # Валидируем данные
            df = await self._validate_and_clean_data(df)
            
            # Обрабатываем данные батчами
            result = await self._process_data_in_batches(
                df, file_id, user_id, session_id
            )
            
            # Обновляем статус файла на завершенный
            await self._update_file_status(file_id, 'completed')
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'total_rows': total_rows,
                'processed_rows': result['processed_rows'],
                'new_orders': result['new_orders'],
                'updated_orders': result['updated_orders'],
                'processing_time': processing_time,
                'batches_processed': result['batches_processed'],
                'errors': result['errors']
            }
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            await self._update_file_status(file_id, 'failed', str(e))
            
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    async def _load_file_async(self, file_path: str) -> pd.DataFrame:
        """Асинхронная загрузка файла"""
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Определяем тип файла и загружаем соответствующим образом
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.csv':
                df = await loop.run_in_executor(
                    executor, 
                    self._load_csv_optimized, 
                    file_path
                )
            elif file_extension in ['.xlsx', '.xls']:
                df = await loop.run_in_executor(
                    executor, 
                    self._load_excel_optimized, 
                    file_path
                )
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            return df
    
    def _load_csv_optimized(self, file_path: str) -> pd.DataFrame:
        """Оптимизированная загрузка CSV файла"""
        try:
            # Читаем файл чанками для экономии памяти
            chunks = []
            for chunk in pd.read_csv(
                file_path, 
                chunksize=self.CHUNK_SIZE,
                dtype=str,  # Читаем все как строки для избежания ошибок типов
                na_filter=False  # Не конвертируем пустые значения в NaN
            ):
                chunks.append(chunk)
            
            df = pd.concat(chunks, ignore_index=True)
            logger.info(f"Loaded CSV file with {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading CSV file {file_path}: {e}")
            raise
    
    def _load_excel_optimized(self, file_path: str) -> pd.DataFrame:
        """Оптимизированная загрузка Excel файла"""
        try:
            df = pd.read_excel(
                file_path,
                dtype=str,  # Читаем все как строки
                na_filter=False
            )
            logger.info(f"Loaded Excel file with {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading Excel file {file_path}: {e}")
            raise
    
    async def _validate_and_clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Валидация и очистка данных"""
        logger.info("Starting data validation and cleaning")
        
        # Стандартизируем названия колонок
        df.columns = df.columns.str.strip().str.lower()
        
        # Удаляем полностью пустые строки
        df = df.dropna(how='all')
        
        # Заполняем пустые значения
        df = df.fillna('')
        
        # Удаляем дубликаты по номеру заказа (если есть колонка)
        if 'order_number' in df.columns:
            initial_count = len(df)
            df = df.drop_duplicates(subset=['order_number'], keep='first')
            removed_duplicates = initial_count - len(df)
            if removed_duplicates > 0:
                logger.info(f"Removed {removed_duplicates} duplicate orders")
        
        logger.info(f"Data validation completed. Final row count: {len(df)}")
        return df
    
    async def _process_data_in_batches(
        self, 
        df: pd.DataFrame, 
        file_id: int, 
        user_id: int,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Обработка данных батчами для оптимальной производительности"""
        
        total_rows = len(df)
        processed_rows = 0
        new_orders = 0
        updated_orders = 0
        batches_processed = 0
        errors = []
        
        # Разбиваем DataFrame на батчи
        for start_idx in range(0, total_rows, self.BATCH_SIZE):
            end_idx = min(start_idx + self.BATCH_SIZE, total_rows)
            batch_df = df.iloc[start_idx:end_idx]
            
            try:
                # Обрабатываем батч
                batch_result = await self._process_batch(
                    batch_df, file_id, user_id, start_idx
                )
                
                processed_rows += len(batch_df)
                new_orders += batch_result['new_orders']
                updated_orders += batch_result['updated_orders']
                batches_processed += 1
                
                # Обновляем прогресс
                if processed_rows % self.PROGRESS_UPDATE_INTERVAL == 0:
                    await self._update_progress(
                        file_id, processed_rows, total_rows
                    )
                
                logger.info(
                    f"Processed batch {batches_processed}: "
                    f"{processed_rows}/{total_rows} rows"
                )
                
            except Exception as e:
                error_msg = f"Error processing batch {start_idx}-{end_idx}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Финальное обновление прогресса
        await self._update_progress(file_id, processed_rows, total_rows, completed=True)
        
        return {
            'processed_rows': processed_rows,
            'new_orders': new_orders,
            'updated_orders': updated_orders,
            'batches_processed': batches_processed,
            'errors': errors
        }
    
    async def _process_batch(
        self, 
        batch_df: pd.DataFrame, 
        file_id: int, 
        user_id: int,
        batch_start_idx: int
    ) -> Dict[str, Any]:
        """Обработка одного батча данных"""
        
        orders_to_create = []
        orders_to_update = []
        changes_to_create = []
        
        # Получаем существующие заказы для проверки дубликатов
        order_numbers = batch_df.get('order_number', pd.Series()).tolist()
        existing_orders = await self._get_existing_orders(order_numbers)
        existing_orders_dict = {order.order_number: order for order in existing_orders}
        
        current_time = datetime.utcnow()
        
        for idx, row in batch_df.iterrows():
            try:
                order_data = self._extract_order_data(row, file_id, user_id)
                order_number = order_data.get('order_number')
                
                if order_number in existing_orders_dict:
                    # Обновляем существующий заказ
                    existing_order = existing_orders_dict[order_number]
                    changes = self._detect_changes(existing_order, order_data)
                    
                    if changes:
                        orders_to_update.append({
                            'id': existing_order.id,
                            **order_data
                        })
                        
                        # Создаем записи об изменениях
                        for field, (old_value, new_value) in changes.items():
                            changes_to_create.append({
                                'order_id': existing_order.id,
                                'field_name': field,
                                'old_value': str(old_value) if old_value is not None else '',
                                'new_value': str(new_value) if new_value is not None else '',
                                'change_type': 'update',
                                'changed_at': current_time,
                                'changed_by': user_id
                            })
                else:
                    # Создаем новый заказ
                    orders_to_create.append(order_data)
                    
            except Exception as e:
                logger.error(f"Error processing row {batch_start_idx + idx}: {e}")
        
        # Выполняем батчевые операции с БД
        new_orders_count = 0
        updated_orders_count = 0
        
        if orders_to_create:
            await self._create_orders_batch(orders_to_create)
            new_orders_count = len(orders_to_create)
        
        if orders_to_update:
            await self._update_orders_batch(orders_to_update)
            updated_orders_count = len(orders_to_update)
        
        if changes_to_create:
            await self._create_changes_batch(changes_to_create)
        
        return {
            'new_orders': new_orders_count,
            'updated_orders': updated_orders_count
        }
    
    def _extract_order_data(self, row: pd.Series, file_id: int, user_id: int) -> Dict[str, Any]:
        """Извлечение данных заказа из строки"""
        
        # Маппинг колонок (можно расширить)
        column_mapping = {
            'order_number': ['order_number', 'номер_заказа', 'order_id'],
            'machine_code': ['machine_code', 'код_автомата', 'machine_id'],
            'order_price': ['order_price', 'цена', 'price', 'amount'],
            'payment_type': ['payment_type', 'тип_оплаты', 'payment_method'],
            'creation_time': ['creation_time', 'дата_создания', 'created_at', 'date']
        }
        
        order_data = {
            'source_file_id': file_id,
            'created_by': user_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Извлекаем данные по маппингу
        for field, possible_columns in column_mapping.items():
            for col in possible_columns:
                if col in row.index and pd.notna(row[col]) and row[col] != '':
                    value = row[col]
                    
                    # Специальная обработка для разных типов полей
                    if field == 'order_price':
                        try:
                            # Очищаем от валютных символов и конвертируем в float
                            value = str(value).replace(',', '.').replace(' ', '')
                            value = float(''.join(c for c in value if c.isdigit() or c == '.'))
                        except (ValueError, TypeError):
                            value = 0.0
                    elif field == 'creation_time':
                        try:
                            value = pd.to_datetime(value)
                        except:
                            value = datetime.utcnow()
                    
                    order_data[field] = value
                    break
        
        # Устанавливаем значения по умолчанию
        order_data.setdefault('order_number', f"AUTO_{int(time.time())}")
        order_data.setdefault('machine_code', 'UNKNOWN')
        order_data.setdefault('order_price', 0.0)
        order_data.setdefault('payment_type', 'unknown')
        order_data.setdefault('creation_time', datetime.utcnow())
        order_data.setdefault('match_status', 'new')
        
        return order_data
    
    def _detect_changes(self, existing_order: Order, new_data: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        """Определение изменений в заказе"""
        changes = {}
        
        # Поля для сравнения
        fields_to_compare = [
            'machine_code', 'order_price', 'payment_type', 'match_status'
        ]
        
        for field in fields_to_compare:
            if field in new_data:
                old_value = getattr(existing_order, field, None)
                new_value = new_data[field]
                
                # Сравниваем значения
                if str(old_value) != str(new_value):
                    changes[field] = (old_value, new_value)
        
        return changes
    
    async def _get_existing_orders(self, order_numbers: List[str]) -> List[Order]:
        """Получение существующих заказов по номерам"""
        if not order_numbers:
            return []
        
        # Фильтруем пустые номера
        valid_numbers = [num for num in order_numbers if num and str(num).strip()]
        
        if not valid_numbers:
            return []
        
        # Используем синхронную сессию БД
        with next(get_db()) as db:
            return db.query(Order).filter(Order.order_number.in_(valid_numbers)).all()
    
    async def _create_orders_batch(self, orders_data: List[Dict[str, Any]]):
        """Батчевое создание заказов"""
        with next(get_db()) as db:
            optimized_order_crud.create_orders_batch(db, orders_data)
    
    async def _update_orders_batch(self, updates: List[Dict[str, Any]]):
        """Батчевое обновление заказов"""
        with next(get_db()) as db:
            optimized_order_crud.update_orders_batch(db, updates)
    
    async def _create_changes_batch(self, changes: List[Dict[str, Any]]):
        """Батчевое создание изменений"""
        with next(get_db()) as db:
            optimized_order_change_crud.create_changes_batch(db, changes)
    
    async def _update_file_status(
        self, 
        file_id: int, 
        status: str, 
        error_message: Optional[str] = None
    ):
        """Обновление статуса файла"""
        update_data = [{'file_id': file_id, 'status': status}]
        if error_message:
            update_data[0]['error_message'] = error_message
        
        with next(get_db()) as db:
            optimized_file_crud.update_files_processing_status_batch(db, update_data)
    
    async def _update_progress(
        self, 
        file_id: int, 
        processed: int, 
        total: int, 
        completed: bool = False
    ):
        """Обновление прогресса обработки"""
        progress_percentage = (processed / total * 100) if total > 0 else 0
        
        # Здесь можно добавить обновление прогресса в БД или отправку уведомлений
        logger.info(f"File {file_id} progress: {progress_percentage:.1f}% ({processed}/{total})")
        
        if completed:
            logger.info(f"File {file_id} processing completed")

# === ФАБРИКА ПРОЦЕССОРОВ ===

class FileProcessorFactory:
    """Фабрика для создания процессоров файлов"""
    
    @staticmethod
    def create_processor(file_type: str = 'optimized') -> OptimizedFileProcessor:
        """Создание процессора файлов"""
        if file_type == 'optimized':
            return OptimizedFileProcessor()
        else:
            raise ValueError(f"Unknown processor type: {file_type}")

# === ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ===

optimized_file_processor = OptimizedFileProcessor()
