from sqlalchemy import Column, Integer, String, Text, DECIMAL, TIMESTAMP, Boolean, ForeignKey, BIGINT
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BIGINT, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    status = Column(String(50), default='pending')  # pending, approved, blocked
    role = Column(String(50), default='user')  # user, admin
    personal_link = Column(String(255), unique=True, index=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    approved_at = Column(TIMESTAMP)
    approved_by = Column(Integer, ForeignKey('users.id'))
    last_active = Column(TIMESTAMP)
    # Deactivation fields
    is_deactivated = Column(Boolean, default=False)
    deactivated_at = Column(TIMESTAMP)
    deactivated_by = Column(Integer, ForeignKey('users.id'))

    # Computed properties for backward compatibility
    @property
    def is_approved(self) -> bool:
        return self.status == 'approved'

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_active_user(self) -> bool:
        """
        Return ``True`` when the user is approved and not deactivated.

        This property is used throughout the system to determine whether a
        Telegram user may generate access links or interact with the
        application. A user must have an ``approved`` status and must not
        have been deactivated by an administrator.
        """
        return (self.status == 'approved' and not self.is_deactivated)

    # Relationships
    uploaded_files = relationship("UploadedFile", back_populates="uploader")
    created_orders = relationship("Order", back_populates="creator")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    original_name = Column(String(500), nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    file_size = Column(BIGINT, nullable=False)
    file_type = Column(String(50), nullable=False)
    storage_path = Column(Text, nullable=False)
    similarity_percent = Column(DECIMAL(5, 2))
    similar_file_id = Column(Integer, ForeignKey('uploaded_files.id'))
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(TIMESTAMP, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    total_rows = Column(Integer, default=0)
    new_rows = Column(Integer, default=0)
    updated_rows = Column(Integer, default=0)

    # Relationships
    uploader = relationship("User", back_populates="uploaded_files")
    similar_file = relationship("UploadedFile", remote_side=[id])
    orders = relationship("Order", back_populates="source_file")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(100), unique=True, nullable=False, index=True)
    machine_code = Column(String(100), index=True)
    address = Column(Text)
    goods_name = Column(String(255))
    taste_name = Column(String(100))
    order_type = Column(String(100))
    order_resource = Column(String(100))
    order_price = Column(DECIMAL(12, 2))
    creation_time = Column(TIMESTAMP, index=True)
    paying_time = Column(TIMESTAMP)
    brewing_time = Column(TIMESTAMP)
    delivery_time = Column(TIMESTAMP)
    refund_time = Column(TIMESTAMP)
    payment_status = Column(String(100))
    brew_status = Column(String(100))
    payment_type = Column(String(100), index=True)
    match_status = Column(String(50), default='unmatched', index=True)
    reason = Column(Text)
    # Metadata
    version = Column(Integer, default=1)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'))
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))
    # JSON for additional fields
    additional_data = Column(Text)

    # Relationships
    creator = relationship("User", back_populates="created_orders")
    source_file = relationship("UploadedFile", back_populates="orders")
    changes = relationship("OrderChange", back_populates="order", cascade="all, delete-orphan")


class OrderChange(Base):
    __tablename__ = "order_changes"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    old_value = Column(Text)
    new_value = Column(Text)
    change_type = Column(String(20), nullable=False)  # new, updated, filled, changed
    changed_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    changed_by = Column(Integer, ForeignKey('users.id'))
    source_file_id = Column(Integer, ForeignKey('uploaded_files.id'))
    version = Column(Integer, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="changes")


class ProcessingSession(Base):
    __tablename__ = "processing_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    status = Column(String(50), default='started')  # started, processing, completed, failed
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    errors = Column(Text)
    started_at = Column(TIMESTAMP, default=datetime.utcnow)
    completed_at = Column(TIMESTAMP)
    created_by = Column(Integer, ForeignKey('users.id'))


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    unique_token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User")


class TelegramSession(Base):
    __tablename__ = "telegram_sessions"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BIGINT, index=True, nullable=False)
    session_token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)