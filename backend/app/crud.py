from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import secrets

from . import models, schemas

# CRUD операции для пользователей
class UserCRUD:
    @staticmethod
    def get_user(db: Session, user_id: int) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.id == user_id).first()
    
    @staticmethod
    def get_user_by_telegram_id(db: Session, telegram_id: str) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    
    @staticmethod
    def get_user_by_personal_link(db: Session, personal_link: str) -> Optional[models.User]:
        return db.query(models.User).filter(models.User.personal_link == personal_link).first()
    
    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
        return db.query(models.User).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_pending_users(db: Session) -> List[models.User]:
        return db.query(models.User).filter(models.User.is_approved == False).all()
    
    @staticmethod
    def create_user(db: Session, user: schemas.UserCreate) -> models.User:
        # Генерируем уникальную персональную ссылку
        personal_link = f"vhm24r_{secrets.token_urlsafe(16)}"
        
        db_user = models.User(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            personal_link=personal_link,
            is_admin=(user.telegram_id == "Jamshiddin")  # Админ по умолчанию
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if db_user:
            update_data = user_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_user, field, value)
            db_user.last_active = datetime.now()
            db.commit()
            db.refresh(db_user)
        return db_user
    
    @staticmethod
    def approve_user(db: Session, user_id: int) -> Optional[models.User]:
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if db_user:
            db_user.is_approved = True
            db.commit()
            db.refresh(db_user)
        return db_user
    
    @staticmethod
    def get_user_stats(db: Session, user_id: int) -> Dict[str, int]:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return {}
        
        total_orders = db.query(models.Order).filter(models.Order.user_id == user_id).count()
        completed_orders = db.query(models.Order).filter(
            and_(models.Order.user_id == user_id, models.Order.status == "completed")
        ).count()
        total_files = db.query(models.UploadedFile).filter(models.UploadedFile.user_id == user_id).count()
        
        return {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "total_files_uploaded": total_files
        }

# CRUD операции для заказов
class OrderCRUD:
    @staticmethod
    def get_order(db: Session, order_id: int) -> Optional[models.Order]:
        return db.query(models.Order).filter(models.Order.id == order_id).first()
    
    @staticmethod
    def get_order_by_number(db: Session, order_number: str) -> Optional[models.Order]:
        return db.query(models.Order).filter(models.Order.order_number == order_number).first()
    
    @staticmethod
    def get_orders(db: Session, skip: int = 0, limit: int = 100, user_id: Optional[int] = None) -> List[models.Order]:
        query = db.query(models.Order)
        if user_id:
            query = query.filter(models.Order.user_id == user_id)
        return query.order_by(desc(models.Order.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def create_order(db: Session, order: schemas.OrderCreate, user_id: int) -> models.Order:
        # Генерируем уникальный номер заказа
        order_number = f"VHM{datetime.now().strftime('%Y%m%d')}{secrets.token_hex(4).upper()}"
        
        db_order = models.Order(
            order_number=order_number,
            user_id=user_id,
            original_filename=order.original_filename,
            file_path=order.file_path,
            file_size=order.file_size,
            file_format=order.file_format
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        return db_order
    
    @staticmethod
    def update_order(db: Session, order_id: int, order_update: schemas.OrderUpdate) -> Optional[models.Order]:
        db_order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if db_order:
            update_data = order_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_order, field, value)
            
            # Если статус изменился на completed, устанавливаем время завершения
            if order_update.status == schemas.OrderStatus.COMPLETED:
                db_order.completed_at = datetime.now()
            
            db_order.updated_at = datetime.now()
            db.commit()
            db.refresh(db_order)
        return db_order
    
    @staticmethod
    def get_orders_by_status(db: Session, status: str, limit: int = 100) -> List[models.Order]:
        return db.query(models.Order).filter(models.Order.status == status).limit(limit).all()

# CRUD операции для изменений заказов
class OrderChangeCRUD:
    @staticmethod
    def get_changes_by_order(db: Session, order_id: int) -> List[models.OrderChange]:
        return db.query(models.OrderChange).filter(models.OrderChange.order_id == order_id).all()
    
    @staticmethod
    def create_change(db: Session, change: schemas.OrderChangeCreate) -> models.OrderChange:
        db_change = models.OrderChange(**change.dict())
        db.add(db_change)
        db.commit()
        db.refresh(db_change)
        return db_change
    
    @staticmethod
    def create_changes_batch(db: Session, changes: List[schemas.OrderChangeCreate]) -> List[models.OrderChange]:
        db_changes = [models.OrderChange(**change.dict()) for change in changes]
        db.add_all(db_changes)
        db.commit()
        for change in db_changes:
            db.refresh(change)
        return db_changes
    
    @staticmethod
    def get_changes_by_type(db: Session, order_id: int, change_type: str) -> List[models.OrderChange]:
        return db.query(models.OrderChange).filter(
            and_(models.OrderChange.order_id == order_id, models.OrderChange.change_type == change_type)
        ).all()

# CRUD операции для загруженных файлов
class UploadedFileCRUD:
    @staticmethod
    def get_file(db: Session, file_id: int) -> Optional[models.UploadedFile]:
        return db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    
    @staticmethod
    def get_files_by_user(db: Session, user_id: int) -> List[models.UploadedFile]:
        return db.query(models.UploadedFile).filter(models.UploadedFile.user_id == user_id).all()
    
    @staticmethod
    def get_files_by_order(db: Session, order_id: int) -> List[models.UploadedFile]:
        return db.query(models.UploadedFile).filter(models.UploadedFile.order_id == order_id).all()
    
    @staticmethod
    def create_file(db: Session, file: schemas.UploadedFileCreate) -> models.UploadedFile:
        db_file = models.UploadedFile(**file.dict())
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    
    @staticmethod
    def update_file(db: Session, file_id: int, file_update: schemas.UploadedFileUpdate) -> Optional[models.UploadedFile]:
        db_file = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
        if db_file:
            update_data = file_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_file, field, value)
            db.commit()
            db.refresh(db_file)
        return db_file

# CRUD операции для Telegram сессий
class TelegramSessionCRUD:
    @staticmethod
    def get_session(db: Session, session_token: str) -> Optional[models.TelegramSession]:
        return db.query(models.TelegramSession).filter(
            and_(
                models.TelegramSession.session_token == session_token,
                models.TelegramSession.is_active == True,
                models.TelegramSession.expires_at > datetime.now()
            )
        ).first()
    
    @staticmethod
    def create_session(db: Session, session: schemas.TelegramSessionCreate) -> models.TelegramSession:
        # Деактивируем старые сессии пользователя
        db.query(models.TelegramSession).filter(
            models.TelegramSession.telegram_id == session.telegram_id
        ).update({"is_active": False})
        
        db_session = models.TelegramSession(**session.dict())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session
    
    @staticmethod
    def deactivate_session(db: Session, session_token: str) -> bool:
        result = db.query(models.TelegramSession).filter(
            models.TelegramSession.session_token == session_token
        ).update({"is_active": False})
        db.commit()
        return result > 0
    
    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        result = db.query(models.TelegramSession).filter(
            models.TelegramSession.expires_at < datetime.now()
        ).update({"is_active": False})
        db.commit()
        return result

# CRUD операции для аналитики
class AnalyticsCRUD:
    @staticmethod
    def create_event(db: Session, event: schemas.AnalyticsCreate) -> models.Analytics:
        db_event = models.Analytics(**event.dict())
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    
    @staticmethod
    def get_events(db: Session, skip: int = 0, limit: int = 100, event_type: Optional[str] = None) -> List[models.Analytics]:
        query = db.query(models.Analytics)
        if event_type:
            query = query.filter(models.Analytics.event_type == event_type)
        return query.order_by(desc(models.Analytics.created_at)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_analytics_summary(db: Session, days: int = 30) -> Dict[str, Any]:
        start_date = datetime.now() - timedelta(days=days)
        
        # Общая статистика
        total_users = db.query(models.User).count()
        active_users = db.query(models.User).filter(
            models.User.last_active >= start_date
        ).count()
        
        total_orders = db.query(models.Order).count()
        completed_orders = db.query(models.Order).filter(
            models.Order.status == "completed"
        ).count()
        
        total_files = db.query(models.UploadedFile).count()
        
        # Популярные форматы файлов
        popular_formats = db.query(
            models.Order.file_format,
            func.count(models.Order.file_format).label('count')
        ).group_by(models.Order.file_format).all()
        
        # Среднее время обработки
        avg_processing_time = db.query(
            func.avg(
                func.extract('epoch', models.Order.completed_at - models.Order.created_at)
            )
        ).filter(models.Order.completed_at.isnot(None)).scalar()
        
        # Ежедневная статистика
        daily_stats = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_orders = db.query(models.Order).filter(
                and_(models.Order.created_at >= day_start, models.Order.created_at < day_end)
            ).count()
            
            daily_stats.append({
                "date": day.strftime("%Y-%m-%d"),
                "orders": day_orders
            })
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "total_files_processed": total_files,
            "average_processing_time": avg_processing_time,
            "popular_file_formats": {format_name: count for format_name, count in popular_formats},
            "daily_stats": daily_stats
        }

# CRUD операции для системных настроек
class SystemSettingsCRUD:
    @staticmethod
    def get_setting(db: Session, key: str) -> Optional[models.SystemSettings]:
        return db.query(models.SystemSettings).filter(models.SystemSettings.key == key).first()
    
    @staticmethod
    def get_all_settings(db: Session) -> List[models.SystemSettings]:
        return db.query(models.SystemSettings).all()
    
    @staticmethod
    def create_setting(db: Session, setting: schemas.SystemSettingsCreate) -> models.SystemSettings:
        db_setting = models.SystemSettings(**setting.dict())
        db.add(db_setting)
        db.commit()
        db.refresh(db_setting)
        return db_setting
    
    @staticmethod
    def update_setting(db: Session, key: str, setting_update: schemas.SystemSettingsUpdate) -> Optional[models.SystemSettings]:
        db_setting = db.query(models.SystemSettings).filter(models.SystemSettings.key == key).first()
        if db_setting:
            update_data = setting_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_setting, field, value)
            db_setting.updated_at = datetime.now()
            db.commit()
            db.refresh(db_setting)
        return db_setting
    
    @staticmethod
    def delete_setting(db: Session, key: str) -> bool:
        result = db.query(models.SystemSettings).filter(models.SystemSettings.key == key).delete()
        db.commit()
        return result > 0

# Экспорт всех CRUD классов
user_crud = UserCRUD()
order_crud = OrderCRUD()
order_change_crud = OrderChangeCRUD()
uploaded_file_crud = UploadedFileCRUD()
telegram_session_crud = TelegramSessionCRUD()
analytics_crud = AnalyticsCRUD()
system_settings_crud = SystemSettingsCRUD()
