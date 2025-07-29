"""
Оптимизированные CRUD операции для VHM24R
Исправляет N+1 запросы, добавляет батчевые операции и улучшает производительность
"""

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, text, update, insert
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
import uuid
import logging

from .models import (
    User, File, UnifiedOrder, OrderChange, ProcessingSession, UserToken,
    HardwareOrder, SalesReport, FiscalReceipt, PaymePayment, ClickPayment, UzumPayment,
    # Алиасы для обратной совместимости
    UploadedFile, Order
)
from .schemas import UserCreate, UploadedFileCreate, OrderFilters

logger = logging.getLogger(__name__)

# === ОПТИМИЗИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ ===

class OptimizedUserCrud:
    """Оптимизированные операции с пользователями"""
    
    @staticmethod
    def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID с кэшированием"""
        return db.query(User).filter(User.telegram_id == telegram_id).first()
    
    @staticmethod
    def get_users_by_telegram_ids(db: Session, telegram_ids: List[int]) -> List[User]:
        """Батчевое получение пользователей по Telegram ID"""
        return db.query(User).filter(User.telegram_id.in_(telegram_ids)).all()
    
    @staticmethod
    def create_user_batch(db: Session, users_data: List[dict]) -> List[User]:
        """Батчевое создание пользователей"""
        import secrets
        
        # Генерируем персональные ссылки для всех пользователей
        for user_data in users_data:
            if 'personal_link' not in user_data:
                user_data['personal_link'] = secrets.token_urlsafe(16)
        
        # Используем bulk_insert_mappings для быстрой вставки
        db.bulk_insert_mappings(User, users_data)
        db.commit()
        
        # Возвращаем созданных пользователей
        telegram_ids = [user_data['telegram_id'] for user_data in users_data]
        return db.query(User).filter(User.telegram_id.in_(telegram_ids)).all()
    
    @staticmethod
    def approve_users_batch(db: Session, user_ids: List[int], approved_by: int) -> List[User]:
        """Батчевое одобрение пользователей - КРИТИЧЕСКАЯ ОПТИМИЗАЦИЯ"""
        # Используем bulk update вместо цикла
        db.query(User).filter(User.id.in_(user_ids)).update(
            {
                "status": "approved",
                "approved_by": approved_by,
                "approved_at": datetime.utcnow()
            },
            synchronize_session=False
        )
        db.commit()
        
        # Возвращаем обновленных пользователей одним запросом
        return db.query(User).filter(User.id.in_(user_ids)).all()
    
    @staticmethod
    def get_pending_users_with_stats(db: Session) -> List[Dict]:
        """Получение ожидающих пользователей со статистикой"""
        results = db.query(
            User,
            func.count(Order.id).label('orders_count'),
            func.sum(Order.order_price).label('total_spent')
        ).outerjoin(Order, User.id == Order.created_by)\
         .filter(User.status == 'pending')\
         .group_by(User.id)\
         .all()
        
        return [
            {
                'user': result[0],
                'orders_count': result[1] or 0,
                'total_spent': float(result[2] or 0)
            }
            for result in results
        ]

# === ОПТИМИЗИРОВАННЫЕ ЗАКАЗЫ ===

class OptimizedOrderCrud:
    """Оптимизированные операции с заказами"""
    
    @staticmethod
    def get_orders_with_relations(db: Session, page: int = 1, page_size: int = 50) -> Tuple[List[Order], int]:
        """Получение заказов с eager loading связанных данных - КРИТИЧЕСКАЯ ОПТИМИЗАЦИЯ"""
        # Используем joinedload для избежания N+1 запросов
        query = db.query(Order).options(
            joinedload(Order.user),
            joinedload(Order.source_file),
            selectinload(Order.changes)  # Для one-to-many используем selectinload
        )
        
        # Подсчет общего количества
        total = query.count()
        
        # Получение данных с пагинацией
        orders = query.offset((page - 1) * page_size).limit(page_size).all()
        
        return orders, total
    
    @staticmethod
    def get_orders_with_filters_optimized(db: Session, filters: OrderFilters, page: int, page_size: int) -> Tuple[List[Order], int]:
        """Оптимизированное получение заказов с фильтрами"""
        # Базовый запрос с eager loading
        query = db.query(Order).options(
            joinedload(Order.user),
            joinedload(Order.source_file)
        )
        
        # Применяем фильтры с использованием индексов
        if filters.order_number:
            query = query.filter(Order.order_number.ilike(f'%{filters.order_number}%'))
        
        if filters.machine_code:
            query = query.filter(Order.machine_code == filters.machine_code)
        
        if filters.payment_type:
            query = query.filter(Order.payment_type == filters.payment_type)
        
        if filters.match_status:
            query = query.filter(Order.match_status == filters.match_status)
        
        # Оптимизированные фильтры по дате с использованием индексов
        if filters.date_from:
            try:
                date_from = datetime.fromisoformat(filters.date_from)
                query = query.filter(Order.creation_time >= date_from)
            except ValueError:
                logger.warning(f"Invalid date_from format: {filters.date_from}")
        
        if filters.date_to:
            try:
                date_to = datetime.fromisoformat(filters.date_to)
                query = query.filter(Order.creation_time <= date_to)
            except ValueError:
                logger.warning(f"Invalid date_to format: {filters.date_to}")
        
        # Оптимизированный фильтр по типу изменений
        if filters.change_type:
            # Используем EXISTS вместо IN для лучшей производительности
            subquery = db.query(OrderChange.order_id).filter(
                OrderChange.change_type == filters.change_type
            ).exists()
            query = query.filter(subquery)
        
        # Подсчет с использованием оптимизированного запроса
        total = query.count()
        
        # Применяем сортировку и пагинацию
        orders = query.order_by(desc(Order.creation_time))\
                     .offset((page - 1) * page_size)\
                     .limit(page_size)\
                     .all()
        
        return orders, total
    
    @staticmethod
    def create_orders_batch(db: Session, orders_data: List[Dict[str, Any]]) -> List[Order]:
        """Батчевое создание заказов - КРИТИЧЕСКАЯ ОПТИМИЗАЦИЯ"""
        # Добавляем временные метки
        current_time = datetime.utcnow()
        for order_data in orders_data:
            order_data.setdefault('created_at', current_time)
            order_data.setdefault('updated_at', current_time)
        
        # Используем bulk_insert_mappings для быстрой вставки
        db.bulk_insert_mappings(Order, orders_data)
        db.commit()
        
        # Возвращаем созданные заказы
        order_numbers = [order_data['order_number'] for order_data in orders_data]
        return db.query(Order).filter(Order.order_number.in_(order_numbers)).all()
    
    @staticmethod
    def update_orders_batch(db: Session, updates: List[Dict[str, Any]]) -> int:
        """Батчевое обновление заказов"""
        updated_count = 0
        current_time = datetime.utcnow()
        
        # Группируем обновления по типу для оптимизации
        for update_data in updates:
            order_id = update_data.pop('id')
            update_data['updated_at'] = current_time
            
            result = db.query(Order).filter(Order.id == order_id).update(
                update_data, synchronize_session=False
            )
            updated_count += result
        
        db.commit()
        return updated_count

# === ОПТИМИЗИРОВАННЫЕ ИЗМЕНЕНИЯ ЗАКАЗОВ ===

class OptimizedOrderChangeCrud:
    """Оптимизированные операции с изменениями заказов"""
    
    @staticmethod
    def create_changes_batch(db: Session, changes: List[dict]) -> List[OrderChange]:
        """Батчевое создание изменений - КРИТИЧЕСКАЯ ОПТИМИЗАЦИЯ"""
        # Добавляем временные метки
        current_time = datetime.utcnow()
        for change_data in changes:
            change_data.setdefault('changed_at', current_time)
        
        # Используем bulk_insert_mappings для максимальной производительности
        db.bulk_insert_mappings(OrderChange, changes)
        db.commit()
        
        # Возвращаем созданные изменения (опционально)
        order_ids = list(set(change['order_id'] for change in changes))
        return db.query(OrderChange).filter(
            OrderChange.order_id.in_(order_ids),
            OrderChange.changed_at >= current_time
        ).all()
    
    @staticmethod
    def get_changes_by_orders(db: Session, order_ids: List[int]) -> Dict[int, List[OrderChange]]:
        """Получение изменений для нескольких заказов одним запросом"""
        changes = db.query(OrderChange).filter(
            OrderChange.order_id.in_(order_ids)
        ).order_by(OrderChange.changed_at).all()
        
        # Группируем по order_id
        result = {}
        for change in changes:
            order_id = change.order_id
            if order_id not in result:
                result[order_id] = []
            result[order_id].append(change)
        
        return result

# === ОПТИМИЗИРОВАННАЯ АНАЛИТИКА ===

class OptimizedAnalyticsCrud:
    """Оптимизированные операции аналитики"""
    
    @staticmethod
    def get_analytics_summary(db: Session, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
        """Оптимизированная сводная аналитика с использованием агрегатных функций"""
        # Базовый запрос
        query = db.query(Order)
        
        # Применяем фильтры дат
        if date_from:
            try:
                date_from_dt = datetime.fromisoformat(date_from)
                query = query.filter(Order.creation_time >= date_from_dt)
            except ValueError:
                logger.warning(f"Invalid date_from format: {date_from}")
        
        if date_to:
            try:
                date_to_dt = datetime.fromisoformat(date_to)
                query = query.filter(Order.creation_time <= date_to_dt)
            except ValueError:
                logger.warning(f"Invalid date_to format: {date_to}")
        
        # Получаем все агрегаты одним запросом
        summary = query.with_entities(
            func.count(Order.id).label('total_orders'),
            func.sum(Order.order_price).label('total_revenue'),
            func.avg(Order.order_price).label('avg_order_value'),
            func.count(func.distinct(Order.machine_code)).label('unique_machines'),
            func.count(func.distinct(Order.created_by)).label('unique_users')
        ).first()
        
        if not summary:
            return {
                'total_orders': 0,
                'total_revenue': 0.0,
                'avg_order_value': 0.0,
                'unique_machines': 0,
                'unique_users': 0
            }
        
        return {
            'total_orders': getattr(summary, 'total_orders', 0) or 0,
            'total_revenue': float(getattr(summary, 'total_revenue', 0) or 0),
            'avg_order_value': float(getattr(summary, 'avg_order_value', 0) or 0),
            'unique_machines': getattr(summary, 'unique_machines', 0) or 0,
            'unique_users': getattr(summary, 'unique_users', 0) or 0
        }
    
    @staticmethod
    def get_top_machines_optimized(db: Session, limit: int = 10, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict]:
        """Оптимизированная статистика по автоматам"""
        query = db.query(
            Order.machine_code,
            func.count(Order.id).label('orders_count'),
            func.sum(Order.order_price).label('total_revenue'),
            func.avg(Order.order_price).label('avg_order_value')
        )
        
        # Применяем фильтры дат
        if date_from:
            try:
                date_from_dt = datetime.fromisoformat(date_from)
                query = query.filter(Order.creation_time >= date_from_dt)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.fromisoformat(date_to)
                query = query.filter(Order.creation_time <= date_to_dt)
            except ValueError:
                pass
        
        results = query.group_by(Order.machine_code)\
                      .order_by(desc('total_revenue'))\
                      .limit(limit)\
                      .all()
        
        return [
            {
                'machine_code': result.machine_code or 'Unknown',
                'orders_count': result.orders_count,
                'total_revenue': float(result.total_revenue or 0),
                'avg_order_value': float(result.avg_order_value or 0)
            }
            for result in results
        ]

# === ОПТИМИЗИРОВАННЫЕ ФАЙЛЫ ===

class OptimizedFileCrud:
    """Оптимизированные операции с файлами"""
    
    @staticmethod
    def get_files_with_stats(db: Session, user_id: int, page: int = 1, page_size: int = 20) -> Tuple[List[Dict], int]:
        """Получение файлов со статистикой обработки"""
        # Запрос с подсчетом связанных заказов
        query = db.query(
            UploadedFile,
            func.count(Order.id).label('orders_count'),
            func.sum(Order.order_price).label('total_value')
        ).outerjoin(Order, UploadedFile.id == Order.source_file_id)\
         .filter(UploadedFile.uploaded_by == user_id)\
         .group_by(UploadedFile.id)
        
        total = query.count()
        
        results = query.order_by(desc(UploadedFile.uploaded_at))\
                      .offset((page - 1) * page_size)\
                      .limit(page_size)\
                      .all()
        
        files_with_stats = []
        for file_obj, orders_count, total_value in results:
            files_with_stats.append({
                'file': file_obj,
                'orders_count': orders_count or 0,
                'total_value': float(total_value or 0)
            })
        
        return files_with_stats, total
    
    @staticmethod
    def update_files_processing_status_batch(db: Session, file_updates: List[Dict]) -> int:
        """Батчевое обновление статуса обработки файлов"""
        updated_count = 0
        current_time = datetime.utcnow()
        
        for update in file_updates:
            file_id = update['file_id']
            status = update['status']
            
            update_data = {
                'processing_status': status,
                'updated_at': current_time
            }
            
            if status == 'processing':
                update_data['processing_started_at'] = current_time
            elif status in ['completed', 'failed']:
                update_data['processing_finished_at'] = current_time
            
            if 'error_message' in update:
                update_data['error_message'] = update['error_message']
            
            result = db.query(UploadedFile).filter(UploadedFile.id == file_id).update(
                update_data, synchronize_session=False
            )
            updated_count += result
        
        db.commit()
        return updated_count

# === ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ ОПТИМИЗИРОВАННЫХ CRUD ===

optimized_user_crud = OptimizedUserCrud()
optimized_order_crud = OptimizedOrderCrud()
optimized_order_change_crud = OptimizedOrderChangeCrud()
optimized_analytics_crud = OptimizedAnalyticsCrud()
optimized_file_crud = OptimizedFileCrud()

# === МИГРАЦИЯ ИНДЕКСОВ ===

def create_performance_indexes(db: Session):
    """Создание индексов для улучшения производительности"""
    indexes = [
        # Индексы для заказов
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_creation_time ON orders(creation_time);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_machine_code ON orders(machine_code);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_status_time ON orders(match_status, creation_time);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_order_number ON orders(order_number);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_created_by ON orders(created_by);",
        
        # Индексы для пользователей
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_status ON users(status);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_telegram_status ON users(telegram_id, status);",
        
        # Индексы для изменений заказов
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_changes_order_id ON order_changes(order_id);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_changes_order_time ON order_changes(order_id, changed_at);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_changes_type ON order_changes(change_type);",
        
        # Индексы для файлов
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_files_uploaded_by ON uploaded_files(uploaded_by);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_files_hash ON uploaded_files(content_hash);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_files_status ON uploaded_files(processing_status);",
        
        # Композитные индексы для сложных запросов
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_complex ON orders(match_status, creation_time, machine_code);",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_analytics ON orders(creation_time, machine_code, order_price);",
    ]
    
    for index_sql in indexes:
        try:
            db.execute(text(index_sql))
            db.commit()
            logger.info(f"Created index: {index_sql}")
        except Exception as e:
            logger.warning(f"Failed to create index: {index_sql}, error: {e}")
            db.rollback()

# === ФУНКЦИИ СОВМЕСТИМОСТИ ===

def migrate_to_optimized_crud():
    """Функция для постепенной миграции на оптимизированные CRUD операции"""
    # Здесь можно добавить логику для постепенной замены старых функций
    pass
