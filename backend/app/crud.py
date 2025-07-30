from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, text
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from .models import (
    User, File, UnifiedOrder, OrderChange, ProcessingSession, UserToken,
    HardwareOrder, SalesReport, FiscalReceipt, PaymePayment, ClickPayment, UzumPayment,
    # Алиасы для обратной совместимости
    UploadedFile, Order
)
from .schemas import UserCreate, UploadedFileCreate, OrderFilters
import uuid

# === ПОЛЬЗОВАТЕЛИ ===

def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user_data: dict) -> User:
    # Генерируем уникальную персональную ссылку
    import secrets
    personal_link = secrets.token_urlsafe(16)
    user_data['personal_link'] = personal_link
    
    db_user = User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_personal_link(db: Session, personal_link: str) -> Optional[User]:
    return db.query(User).filter(User.personal_link == personal_link).first()

def get_pending_users(db: Session) -> List[User]:
    return db.query(User).filter(User.status == 'pending').all()

def get_all_users(db: Session) -> List[User]:
    return db.query(User).order_by(User.created_at.desc()).all()

def approve_user(db: Session, user_id: int, approved_by: int) -> Optional[User]:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # Используем setattr для избежания ошибок типизации
        setattr(user, 'status', 'approved')
        setattr(user, 'approved_at', datetime.utcnow())
        setattr(user, 'approved_by', approved_by)
        db.commit()
        db.refresh(user)
    return user

def block_user(db: Session, user_id: int) -> Optional[User]:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        setattr(user, 'status', 'blocked')
        db.commit()
        db.refresh(user)
    return user

def get_total_users_count(db: Session) -> int:
    return db.query(User).count()

def get_active_sessions_count(db: Session) -> int:
    return db.query(ProcessingSession).filter(
        ProcessingSession.status.in_(['started', 'processing'])
    ).count()

# === ФАЙЛЫ ===

def get_file_by_hash(db: Session, content_hash: str) -> Optional[UploadedFile]:
    return db.query(UploadedFile).filter(UploadedFile.content_hash == content_hash).first()

def create_uploaded_file(db: Session, file_data: dict) -> UploadedFile:
    db_file = UploadedFile(**file_data)
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def update_file_stats(db: Session, file_id: int, total_rows: int, new_rows: int, updated_rows: int):
    file_obj = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if file_obj:
        setattr(file_obj, 'processed', True)
        setattr(file_obj, 'total_rows', total_rows)
        setattr(file_obj, 'new_rows', new_rows)
        setattr(file_obj, 'updated_rows', updated_rows)
        db.commit()

def get_uploaded_files(db: Session, user_id: int) -> List[UploadedFile]:
    return db.query(UploadedFile).filter(UploadedFile.uploaded_by == user_id).order_by(desc(UploadedFile.uploaded_at)).all()

def mark_file_processed(db: Session, file_id: int):
    file_obj = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if file_obj:
        setattr(file_obj, 'processed', True)
        db.commit()

def update_file_processing_status(db: Session, file_id: int, status: str, error_message: Optional[str] = None):
    """Обновление статуса обработки файла"""
    file_obj = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if file_obj:
        setattr(file_obj, 'processing_status', status)
        if error_message:
            setattr(file_obj, 'error_message', error_message)
        if status == 'processing':
            setattr(file_obj, 'processing_started_at', datetime.utcnow())
        elif status in ['completed', 'failed']:
            setattr(file_obj, 'processing_finished_at', datetime.utcnow())
        db.commit()

def get_uploaded_file_by_id(db: Session, file_id: int) -> Optional[UploadedFile]:
    """Получение файла по ID"""
    return db.query(UploadedFile).filter(UploadedFile.id == file_id).first()

# === СЕССИИ ОБРАБОТКИ ===

def create_processing_session(db: Session, user_id: int, files_count: int) -> ProcessingSession:
    session = ProcessingSession(
        session_id=str(uuid.uuid4()),
        total_files=files_count,
        created_by=user_id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_processing_session(db: Session, session_id: str) -> Optional[ProcessingSession]:
    return db.query(ProcessingSession).filter(ProcessingSession.session_id == session_id).first()

def update_processing_session(db: Session, session_id: str, status: str):
    session = db.query(ProcessingSession).filter(ProcessingSession.session_id == session_id).first()
    if session:
        setattr(session, 'status', status)
        db.commit()

def complete_processing_session(db: Session, session_id: str, total_rows: int, processed_rows: int, new_orders: int = 0, updated_orders: int = 0, errors: Optional[List[str]] = None):
    session = db.query(ProcessingSession).filter(ProcessingSession.session_id == session_id).first()
    if session:
        setattr(session, 'status', 'completed')
        setattr(session, 'total_rows', total_rows)
        setattr(session, 'processed_rows', processed_rows)
        setattr(session, 'completed_at', datetime.utcnow())
        if errors:
            setattr(session, 'errors', '\n'.join(errors))
        db.commit()

def fail_processing_session(db: Session, session_id: str, error: str):
    session = db.query(ProcessingSession).filter(ProcessingSession.session_id == session_id).first()
    if session:
        setattr(session, 'status', 'failed')
        setattr(session, 'errors', error)
        setattr(session, 'completed_at', datetime.utcnow())
        db.commit()

def get_session_files(db: Session, session_id: int) -> List[UploadedFile]:
    """Получение файлов для сессии обработки"""
    # Получаем сессию
    session = db.query(ProcessingSession).filter(ProcessingSession.id == session_id).first()
    if not session:
        return []
    
    # Получаем файлы, загруженные этим пользователем в период сессии
    created_by = getattr(session, 'created_by', 0)
    started_at = getattr(session, 'started_at', None)
    
    if not created_by or not started_at:
        return []
    
    # Возвращаем файлы, загруженные пользователем после начала сессии
    return db.query(UploadedFile).filter(
        UploadedFile.uploaded_by == created_by,
        UploadedFile.uploaded_at >= started_at
    ).order_by(UploadedFile.uploaded_at.desc()).all()

def update_session_stats(db: Session, session_id: int, total_size: int, files_count: int):
    # Обновляем статистику сессии
    pass

# === ЗАКАЗЫ ===

def get_order_by_number(db: Session, order_number: str) -> Optional[Order]:
    return db.query(Order).filter(Order.order_number == order_number).first()

def create_order(db: Session, order_data: Dict[str, Any], user_id: Optional[int] = None, file_id: Optional[int] = None) -> Order:
    if user_id is not None:
        order_data['created_by'] = user_id
    if file_id is not None:
        order_data['source_file_id'] = file_id
    
    order = Order(**order_data)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def update_order(db: Session, order_id: int, order_data: Dict[str, Any], file_id: Optional[int] = None) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        # Обновляем только непустые поля
        for key, value in order_data.items():
            if value is not None and hasattr(order, key):
                setattr(order, key, value)
        
        if file_id is not None:
            setattr(order, 'source_file_id', file_id)
        setattr(order, 'updated_at', datetime.utcnow())
        
        db.commit()
        db.refresh(order)
    return order

def get_orders_with_filters(db: Session, filters: OrderFilters, page: int, page_size: int) -> Tuple[List[Order], int]:
    query = db.query(Order)
    
    # Применяем фильтры
    if filters.order_number:
        query = query.filter(Order.order_number.ilike(f'%{filters.order_number}%'))
    
    if filters.machine_code:
        query = query.filter(Order.machine_code == filters.machine_code)
    
    if filters.payment_type:
        query = query.filter(Order.payment_type == filters.payment_type)
    
    if filters.match_status:
        query = query.filter(Order.match_status == filters.match_status)
    
    if filters.date_from:
        try:
            date_from = datetime.fromisoformat(filters.date_from)
            query = query.filter(Order.creation_time >= date_from)
        except:
            pass
    
    if filters.date_to:
        try:
            date_to = datetime.fromisoformat(filters.date_to)
            query = query.filter(Order.creation_time <= date_to)
        except:
            pass
    
    # Фильтр по типу изменений
    if filters.change_type:
        subquery = db.query(OrderChange.order_id).filter(
            OrderChange.change_type == filters.change_type
        ).distinct()
        query = query.filter(Order.id.in_(subquery))
    
    # Подсчитываем общее количество
    total = query.count()
    
    # Применяем пагинацию
    orders = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return orders, total

def get_order(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()

def get_order_changes(db: Session, order_id: int) -> List[OrderChange]:
    return db.query(OrderChange).filter(OrderChange.order_id == order_id).order_by(OrderChange.changed_at).all()

def create_order_change(db: Session, change_data: Dict[str, Any]) -> OrderChange:
    change = OrderChange(**change_data)
    db.add(change)
    db.commit()
    db.refresh(change)
    return change

def get_order_versions(db: Session, order_number: str) -> List[Dict]:
    """Получение всех версий заказа"""
    order = db.query(Order).filter(Order.order_number == order_number).first()
    if not order:
        return []
    
    changes = db.query(OrderChange).filter(OrderChange.order_id == order.id).order_by(OrderChange.version).all()
    
    # Строим версии заказа
    versions = []
    current_version = {}
    
    for change in changes:
        change_version = getattr(change, 'version', None)
        if change_version not in [v.get('version') for v in versions]:
            # Новая версия
            if current_version:
                versions.append(current_version.copy())
            current_version = {'version': change_version, 'changed_at': change.changed_at}
        
        if getattr(change, 'change_type', None) == 'new':
            # Начальная версия
            current_version.update({
                'order_number': order.order_number,
                'machine_code': order.machine_code,
                'order_price': order.order_price
            })
        else:
            current_version[str(change.field_name)] = change.new_value
    
    if current_version:
        versions.append(current_version)
    
    return versions

# === АНАЛИТИКА ===

def get_analytics_data(db: Session, date_from: Optional[str], date_to: Optional[str], group_by: str) -> Dict:
    query = db.query(Order)
    
    # Применяем фильтры дат
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(Order.creation_time >= date_from_dt)
        except:
            pass
    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            query = query.filter(Order.creation_time <= date_to_dt)
        except:
            pass
    
    # Общая статистика
    total_orders = query.count()
    total_revenue = query.with_entities(func.sum(Order.order_price)).scalar() or 0
    
    # Статистика по типам оплаты
    payment_stats = db.query(
        Order.payment_type,
        func.count(Order.id).label('count'),
        func.sum(Order.order_price).label('total')
    ).group_by(Order.payment_type).all()
    
    # Статистика по автоматам
    machine_stats = db.query(
        Order.machine_code,
        func.count(Order.id).label('count'),
        func.sum(Order.order_price).label('total')
    ).group_by(Order.machine_code).limit(10).all()
    
    # Временные тренды
    time_stats = db.query(
        func.date(Order.creation_time).label('period'),
        func.count(Order.id).label('count'),
        func.sum(Order.order_price).label('total')
    ).group_by(func.date(Order.creation_time)).order_by(func.date(Order.creation_time)).all()
    
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

# === ТОКЕНЫ ПОЛЬЗОВАТЕЛЕЙ ===

def save_user_unique_token(db: Session, user_id: int, unique_token: str):
    """Сохранение уникального токена пользователя"""
    # Удаляем старые токены
    db.query(UserToken).filter(UserToken.user_id == user_id).delete()
    
    # Создаем новый токен
    token = UserToken(
        user_id=user_id,
        unique_token=unique_token,
        is_active=True
    )
    db.add(token)
    db.commit()

def get_user_by_token(db: Session, unique_token: str) -> Optional[User]:
    """Получение пользователя по уникальному токену"""
    token = db.query(UserToken).filter(
        UserToken.unique_token == unique_token,
        UserToken.is_active.is_(True)
    ).first()
    
    if token:
        return db.query(User).filter(User.id == token.user_id).first()
    return None

def deactivate_user_token(db: Session, unique_token: str):
    """Деактивация токена пользователя"""
    token = db.query(UserToken).filter(UserToken.unique_token == unique_token).first()
    if token:
        setattr(token, 'is_active', False)
        db.commit()

# === CRUD ОПЕРАЦИИ ДЛЯ ЗАКАЗОВ ===

class OrderCrud:
    """CRUD операции для заказов"""
    
    def get_order(self, db: Session, order_id: int) -> Optional[Order]:
        return db.query(Order).filter(Order.id == order_id).first()
    
    def update_order(self, db: Session, order_id: int, order_update: dict) -> Optional[Order]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            for key, value in order_update.items():
                if hasattr(order, key) and value is not None:
                    setattr(order, key, value)
            setattr(order, 'updated_at', datetime.utcnow())
            db.commit()
            db.refresh(order)
        return order

class OrderChangeCrud:
    """CRUD операции для изменений заказов"""
    
    def create_changes_batch(self, db: Session, changes: List[dict]):
        """Создание изменений батчом"""
        for change_data in changes:
            change = OrderChange(**change_data)
            db.add(change)
        db.commit()
    
    def get_changes_by_order(self, db: Session, order_id: int) -> List[OrderChange]:
        return db.query(OrderChange).filter(OrderChange.order_id == order_id).all()

class AnalyticsCrud:
    """CRUD операции для аналитики"""
    
    def create_event(self, db: Session, event_data: dict):
        """Создание события аналитики"""
        # Заглушка для аналитических событий
        # В реальном приложении здесь будет создание записи в таблице аналитики
        pass

# === СЕССИИ TELEGRAM ===

def get_session_by_token(db: Session, session_token: str):
    """Получение сессии по токену"""
    from .models import TelegramSession
    return db.query(TelegramSession).filter(TelegramSession.session_token == session_token).first()

def deactivate_session(db: Session, session_token: str):
    """Деактивация конкретной сессии"""
    from .models import TelegramSession
    session = db.query(TelegramSession).filter(TelegramSession.session_token == session_token).first()
    if session:
        setattr(session, 'is_active', False)
        db.commit()

def deactivate_user_sessions(db: Session, user_id: int):
    """Деактивация всех сессий пользователя"""
    from .models import TelegramSession
    sessions = db.query(TelegramSession).filter(TelegramSession.telegram_id == user_id).all()
    for session in sessions:
        setattr(session, 'is_active', False)
    db.commit()

def get_user_sessions(db: Session, user_id: int):
    """Получение всех сессий пользователя"""
    from .models import TelegramSession
    return db.query(TelegramSession).filter(TelegramSession.telegram_id == user_id).all()

def get_active_sessions(db: Session, user_id: int):
    """Получение активных сессий пользователя"""
    from .models import TelegramSession
    return db.query(TelegramSession).filter(
        TelegramSession.telegram_id == user_id,
        TelegramSession.is_active.is_(True),
        TelegramSession.expires_at > datetime.utcnow()
    ).all()

def cleanup_expired_sessions(db: Session):
    """Очистка истекших сессий"""
    from .models import TelegramSession
    expired_sessions = db.query(TelegramSession).filter(
        TelegramSession.expires_at < datetime.utcnow()
    ).all()
    
    for session in expired_sessions:
        setattr(session, 'is_active', False)
    
    db.commit()
    return len(expired_sessions)

# Глобальные экземпляры CRUD
order_crud = OrderCrud()
order_change_crud = OrderChangeCrud()
analytics_crud = AnalyticsCrud()
