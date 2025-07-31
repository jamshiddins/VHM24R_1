"""
Безопасные CRUD операции с защитой от SQL Injection
"""
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
import uuid
import re

from ..models import (
    User, File, UnifiedOrder, OrderChange, ProcessingSession, UserToken,
    HardwareOrder, SalesReport, FiscalReceipt, PaymePayment, ClickPayment, UzumPayment,
    # Алиасы для обратной совместимости
    UploadedFile, Order
)
from ..schemas import UserCreate, UploadedFileCreate, OrderFilters
from ..utils.logger import get_logger, db_logger
from ..utils.exceptions import DatabaseError, ValidationError, SecurityError, handle_database_error

logger = get_logger(__name__)

class SecureCrud:
    """Безопасные CRUD операции с защитой от SQL Injection"""
    
    @staticmethod
    def _validate_search_query(search: str) -> str:
        """Валидация поискового запроса"""
        if not search:
            return ""
        
        # Удаляем потенциально опасные символы
        # Разрешаем только буквы, цифры, пробелы, дефисы и точки
        cleaned_search = re.sub(r'[^\w\s\-\.]', '', search)
        
        # Ограничиваем длину
        if len(cleaned_search) > 100:
            cleaned_search = cleaned_search[:100]
        
        # Проверяем на SQL ключевые слова
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'EXEC', 'EXECUTE',
            'UNION', 'SELECT', 'FROM', 'WHERE', 'OR', 'AND',
            'TRUNCATE', 'ALTER', 'CREATE', 'SCHEMA', 'DATABASE'
        ]
        
        search_upper = cleaned_search.upper()
        for keyword in dangerous_keywords:
            if keyword in search_upper:
                logger.warning(f"Попытка SQL инъекции обнаружена: {keyword} в запросе: {search}")
                raise SecurityError(f"Недопустимые символы в поисковом запросе")
        
        return cleaned_search.strip()
    
    @staticmethod
    def _validate_order_field(field_name: str) -> str:
        """Валидация имени поля для сортировки"""
        allowed_fields = [
            'id', 'order_number', 'machine_code', 'order_price', 
            'payment_type', 'match_status', 'creation_time', 'updated_at',
            'created_at', 'uploaded_at', 'filename', 'file_size'
        ]
        
        if field_name not in allowed_fields:
            raise ValidationError(f"Недопустимое поле для сортировки: {field_name}")
        
        return field_name

    def get_orders_with_search_secure(self, db: Session, search: str, page: int = 1, 
                                     page_size: int = 50) -> Tuple[List[Order], int]:
        """Безопасный поиск заказов с защитой от SQL Injection"""
        try:
            # Валидируем поисковый запрос
            safe_search = self._validate_search_query(search)
            
            if not safe_search:
                # Возвращаем все заказы если поиск пустой
                query = db.query(Order)
            else:
                # Используем безопасные ORM методы вместо raw SQL
                query = db.query(Order).filter(
                    or_(
                        Order.order_number.ilike(f"%{safe_search}%"),
                        Order.machine_code.ilike(f"%{safe_search}%")
                    )
                )
                
                db_logger.log_query("SELECT", "orders", {
                    "search": safe_search,
                    "page": page,
                    "page_size": page_size
                })
            
            # Подсчитываем общее количество
            total = query.count()
            
            # Применяем пагинацию
            orders = query.order_by(desc(Order.creation_time))\
                         .offset((page - 1) * page_size)\
                         .limit(page_size)\
                         .all()
            
            logger.info(f"Безопасный поиск заказов: найдено {len(orders)} из {total}")
            return orders, total
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in secure search", error=str(e))
            raise handle_database_error("get_orders_with_search_secure", "orders", e)
    
    def get_orders_with_filters_secure(self, db: Session, filters: OrderFilters, 
                                      page: int, page_size: int) -> Tuple[List[Order], int]:
        """Безопасное получение заказов с фильтрами"""
        try:
            db_logger.log_query("SELECT", "orders", filters.dict() if filters else None)
            
            # Используем joinedload для оптимизации N+1 запросов
            query = db.query(Order).options(
                joinedload(Order.changes),
                selectinload(Order.uploaded_files)
            )
            
            # Применяем фильтры безопасно через ORM
            if filters.order_number:
                safe_order_number = self._validate_search_query(filters.order_number)
                query = query.filter(Order.order_number.ilike(f'%{safe_order_number}%'))
            
            if filters.machine_code:
                # Точное совпадение для machine_code
                query = query.filter(Order.machine_code == filters.machine_code)
            
            if filters.payment_type:
                # Точное совпадение для payment_type
                query = query.filter(Order.payment_type == filters.payment_type)
            
            if filters.match_status:
                # Точное совпадение для match_status
                query = query.filter(Order.match_status == filters.match_status)
            
            # Валидация и применение фильтров по дате
            if filters.date_from:
                try:
                    date_from = datetime.fromisoformat(filters.date_from.replace('Z', '+00:00'))
                    query = query.filter(Order.creation_time >= date_from)
                except ValueError as e:
                    logger.warning(f"Invalid date_from format: {filters.date_from}", error=str(e))
                    raise ValidationError(f"Некорректный формат даты 'с': {filters.date_from}")
            
            if filters.date_to:
                try:
                    date_to = datetime.fromisoformat(filters.date_to.replace('Z', '+00:00'))
                    query = query.filter(Order.creation_time <= date_to)
                except ValueError as e:
                    logger.warning(f"Invalid date_to format: {filters.date_to}", error=str(e))
                    raise ValidationError(f"Некорректный формат даты 'до': {filters.date_to}")
            
            # Фильтр по типу изменений через подзапрос
            if filters.change_type:
                # Валидируем тип изменения
                allowed_change_types = ['new', 'updated', 'filled', 'changed']
                if filters.change_type not in allowed_change_types:
                    raise ValidationError(f"Недопустимый тип изменения: {filters.change_type}")
                
                subquery = db.query(OrderChange.order_id).filter(
                    OrderChange.change_type == filters.change_type
                ).distinct().subquery()
                
                query = query.filter(Order.id.in_(
                    db.query(subquery.c.order_id)
                ))
            
            # Подсчитываем общее количество
            total = query.count()
            
            # Применяем пагинацию с валидацией
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 1000:  # Ограничиваем размер страницы
                page_size = 50
            
            orders = query.order_by(desc(Order.creation_time))\
                         .offset((page - 1) * page_size)\
                         .limit(page_size)\
                         .all()
            
            logger.info(f"Получено {len(orders)} заказов из {total} с фильтрами", 
                       page=page, page_size=page_size)
            
            return orders, total
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_orders_with_filters_secure", error=str(e))
            raise handle_database_error("get_orders_with_filters_secure", "orders", e)
    
    def get_analytics_data_secure(self, db: Session, date_from: Optional[str], 
                                 date_to: Optional[str], group_by: str) -> Dict:
        """Безопасное получение аналитических данных"""
        try:
            db_logger.log_query("SELECT", "orders", {
                "date_from": date_from, 
                "date_to": date_to, 
                "group_by": group_by
            })
            
            # Валидируем group_by параметр
            allowed_group_by = ['day', 'week', 'month', 'year']
            if group_by not in allowed_group_by:
                raise ValidationError(f"Недопустимый параметр группировки: {group_by}")
            
            query = db.query(Order)
            
            # Применяем фильтры дат с валидацией
            if date_from:
                try:
                    date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                    query = query.filter(Order.creation_time >= date_from_dt)
                except ValueError as e:
                    logger.warning(f"Invalid date_from format in analytics: {date_from}", error=str(e))
                    raise ValidationError(f"Некорректный формат даты 'с' для аналитики: {date_from}")
            
            if date_to:
                try:
                    date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    query = query.filter(Order.creation_time <= date_to_dt)
                except ValueError as e:
                    logger.warning(f"Invalid date_to format in analytics: {date_to}", error=str(e))
                    raise ValidationError(f"Некорректный формат даты 'до' для аналитики: {date_to}")
            
            # Общая статистика - используем ORM агрегации
            total_orders = query.count()
            total_revenue = query.with_entities(func.sum(Order.order_price)).scalar() or 0
            
            # Статистика по типам оплаты - безопасная группировка
            payment_stats = db.query(
                Order.payment_type,
                func.count(Order.id).label('count'),
                func.sum(Order.order_price).label('total')
            ).filter(
                Order.creation_time >= (date_from_dt if date_from else datetime.min),
                Order.creation_time <= (date_to_dt if date_to else datetime.max)
            ).group_by(Order.payment_type).all()
            
            # Статистика по автоматам - ограничиваем топ-10
            machine_stats = db.query(
                Order.machine_code,
                func.count(Order.id).label('count'),
                func.sum(Order.order_price).label('total')
            ).filter(
                Order.creation_time >= (date_from_dt if date_from else datetime.min),
                Order.creation_time <= (date_to_dt if date_to else datetime.max)
            ).group_by(Order.machine_code).order_by(desc('count')).limit(10).all()
            
            # Временные тренды - безопасная группировка по дате
            time_stats = db.query(
                func.date(Order.creation_time).label('period'),
                func.count(Order.id).label('count'),
                func.sum(Order.order_price).label('total')
            ).filter(
                Order.creation_time >= (date_from_dt if date_from else datetime.min),
                Order.creation_time <= (date_to_dt if date_to else datetime.max)
            ).group_by(func.date(Order.creation_time)).order_by('period').all()
            
            logger.info(f"Аналитические данные сгенерированы: {total_orders} заказов, выручка: {total_revenue}")
            
            return {
                'summary': {
                    'total_orders': total_orders,
                    'total_revenue': float(total_revenue),
                    'avg_order_value': float(total_revenue / total_orders) if total_orders > 0 else 0
                },
                'payment_types': [
                    {
                        'type': stat.payment_type or 'Unknown',
                        'count': stat.count,
                        'total': float(stat.total or 0)
                    }
                    for stat in payment_stats
                ],
                'top_machines': [
                    {
                        'machine_code': stat.machine_code or 'Unknown',
                        'count': stat.count,
                        'total': float(stat.total or 0)
                    }
                    for stat in machine_stats
                ],
                'time_series': [
                    {
                        'period': stat.period.isoformat() if stat.period else None,
                        'count': stat.count,
                        'total': float(stat.total or 0)
                    }
                    for stat in time_stats
                ]
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_analytics_data_secure", error=str(e))
            raise handle_database_error("get_analytics_data_secure", "orders", e)
    
    def create_order_secure(self, db: Session, order_data: Dict[str, Any], 
                           user_id: Optional[int] = None, file_id: Optional[int] = None) -> Order:
        """Безопасное создание заказа с валидацией"""
        try:
            # Валидируем обязательные поля
            required_fields = ['order_number', 'machine_code']
            for field in required_fields:
                if field not in order_data or not order_data[field]:
                    raise ValidationError(f"Обязательное поле '{field}' отсутствует")
            
            # Валидируем номер заказа
            order_number = str(order_data['order_number']).strip()
            if not re.match(r'^[A-Za-z0-9\-_]{1,50}$', order_number):
                raise ValidationError("Номер заказа содержит недопустимые символы")
            
            # Валидируем код машины
            machine_code = str(order_data['machine_code']).strip()
            if not re.match(r'^[A-Za-z0-9\-_]{1,20}$', machine_code):
                raise ValidationError("Код машины содержит недопустимые символы")
            
            # Проверяем уникальность номера заказа
            existing_order = db.query(Order).filter(Order.order_number == order_number).first()
            if existing_order:
                raise ValidationError(f"Заказ с номером {order_number} уже существует")
            
            # Подготавливаем данные заказа
            clean_order_data = {
                'order_number': order_number,
                'machine_code': machine_code,
                'order_price': float(order_data.get('order_price', 0)),
                'payment_type': order_data.get('payment_type', 'unknown'),
                'payment_status': order_data.get('payment_status', 'pending'),
                'match_status': order_data.get('match_status', 'new'),
                'creation_time': datetime.utcnow()
            }
            
            if user_id is not None:
                clean_order_data['created_by'] = user_id
            if file_id is not None:
                clean_order_data['source_file_id'] = file_id
            
            # Создаем заказ
            order = Order(**clean_order_data)
            db.add(order)
            db.commit()
            db.refresh(order)
            
            logger.info(f"Заказ создан безопасно: {order_number}, ID: {order.id}")
            return order
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in create_order_secure", error=str(e))
            raise handle_database_error("create_order_secure", "orders", e)
    
    def update_order_secure(self, db: Session, order_id: int, 
                           order_data: Dict[str, Any]) -> Optional[Order]:
        """Безопасное обновление заказа"""
        try:
            # Валидируем ID заказа
            if not isinstance(order_id, int) or order_id <= 0:
                raise ValidationError("Некорректный ID заказа")
            
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                return None
            
            # Валидируем и применяем изменения
            allowed_fields = [
                'machine_code', 'order_price', 'payment_type', 
                'payment_status', 'match_status', 'metadata'
            ]
            
            for key, value in order_data.items():
                if key in allowed_fields and value is not None:
                    if key == 'machine_code':
                        # Валидируем код машины
                        if not re.match(r'^[A-Za-z0-9\-_]{1,20}$', str(value)):
                            raise ValidationError("Код машины содержит недопустимые символы")
                    elif key == 'order_price':
                        # Валидируем цену
                        try:
                            value = float(value)
                            if value < 0:
                                raise ValidationError("Цена заказа не может быть отрицательной")
                        except (ValueError, TypeError):
                            raise ValidationError("Некорректное значение цены")
                    
                    setattr(order, key, value)
            
            setattr(order, 'updated_at', datetime.utcnow())
            db.commit()
            db.refresh(order)
            
            logger.info(f"Заказ обновлен безопасно: ID {order_id}")
            return order
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in update_order_secure", error=str(e))
            raise handle_database_error("update_order_secure", "orders", e)

# Глобальный экземпляр безопасного CRUD
secure_crud = SecureCrud()

# Функции-обертки для использования в других модулях
def get_orders_with_search_secure(db: Session, search: str, page: int = 1, 
                                 page_size: int = 50) -> Tuple[List[Order], int]:
    """Безопасный поиск заказов"""
    return secure_crud.get_orders_with_search_secure(db, search, page, page_size)

def get_orders_with_filters_secure(db: Session, filters: OrderFilters, 
                                  page: int, page_size: int) -> Tuple[List[Order], int]:
    """Безопасное получение заказов с фильтрами"""
    return secure_crud.get_orders_with_filters_secure(db, filters, page, page_size)

def get_analytics_data_secure(db: Session, date_from: Optional[str], 
                             date_to: Optional[str], group_by: str) -> Dict:
    """Безопасное получение аналитики"""
    return secure_crud.get_analytics_data_secure(db, date_from, date_to, group_by)

def create_order_secure(db: Session, order_data: Dict[str, Any], 
                       user_id: Optional[int] = None, file_id: Optional[int] = None) -> Order:
    """Безопасное создание заказа"""
    return secure_crud.create_order_secure(db, order_data, user_id, file_id)

def update_order_secure(db: Session, order_id: int, order_data: Dict[str, Any]) -> Optional[Order]:
    """Безопасное обновление заказа"""
    return secure_crud.update_order_secure(db, order_id, order_data)
