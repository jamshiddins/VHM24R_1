from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums для статусов
class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ChangeType(str, Enum):
    NEW = "new"
    UPDATED = "updated"
    FILLED = "filled"
    CHANGED = "changed"

class UploadStatus(str, Enum):
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"

# Базовые схемы пользователей
class UserBase(BaseModel):
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[str] = None

class User(UserBase):
    id: int
    personal_link: str
    status: str
    role: str
    created_at: datetime
    last_active: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserWithStats(User):
    total_orders: int = 0
    completed_orders: int = 0
    total_files_uploaded: int = 0

# Схемы для заказов
class OrderBase(BaseModel):
    original_filename: str
    file_format: str

class OrderCreate(OrderBase):
    file_path: str
    file_size: int

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    total_rows: Optional[int] = None
    processed_rows: Optional[int] = None
    progress_percentage: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class Order(OrderBase):
    id: int
    order_number: str
    user_id: int
    status: OrderStatus
    file_path: str
    file_size: int
    total_rows: int
    processed_rows: int
    progress_percentage: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class OrderWithUser(Order):
    user: User

class OrderWithChanges(Order):
    changes: List['OrderChange'] = []

# Схемы для изменений заказов
class OrderChangeBase(BaseModel):
    row_number: int
    column_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_type: ChangeType

class OrderChangeCreate(OrderChangeBase):
    order_id: int

class OrderChange(OrderChangeBase):
    id: int
    order_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Схемы для загруженных файлов
class UploadedFileBase(BaseModel):
    filename: str
    original_filename: str
    file_format: str
    mime_type: Optional[str] = None

class UploadedFileCreate(UploadedFileBase):
    file_path: str
    file_size: int
    user_id: int
    order_id: Optional[int] = None

class UploadedFileUpdate(BaseModel):
    upload_status: Optional[UploadStatus] = None
    spaces_url: Optional[str] = None

class UploadedFile(UploadedFileBase):
    id: int
    user_id: int
    order_id: Optional[int] = None
    file_path: str
    file_size: int
    upload_status: UploadStatus
    spaces_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Схемы для Telegram сессий
class TelegramSessionBase(BaseModel):
    telegram_id: str
    session_token: str
    expires_at: datetime

class TelegramSessionCreate(TelegramSessionBase):
    pass

class TelegramSession(TelegramSessionBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Схемы для аутентификации
class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
    personal_link: str

# Схемы для загрузки файлов
class FileUploadResponse(BaseModel):
    order_id: int
    order_number: str
    filename: str
    file_size: int
    file_format: str
    upload_status: str
    message: str

class FileProcessingProgress(BaseModel):
    order_id: int
    order_number: str
    progress_percentage: float
    processed_rows: int
    total_rows: int
    status: OrderStatus
    current_operation: Optional[str] = None

# Схемы для экспорта
class ExportRequest(BaseModel):
    order_id: Optional[int] = None
    data_type: str = Field(..., pattern="^(orders|analytics)$")
    export_format: str = Field(..., pattern="^(csv|xlsx|xls|json|pdf)$")
    filename: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    include_changes: bool = True

class ExportRecordCreate(BaseModel):
    user_id: int
    data_type: str
    format: str
    file_path: str
    filters: Optional[Dict[str, Any]] = None

class ExportResponse(BaseModel):
    download_url: str
    filename: str
    file_size: int
    expires_at: datetime

# Схемы для фильтров заказов
class OrderFilters(BaseModel):
    order_number: Optional[str] = None
    machine_code: Optional[str] = None
    payment_type: Optional[str] = None
    match_status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    change_type: Optional[str] = None

# Схемы для загруженных файлов (расширенные)
class UploadedFileCreateExtended(BaseModel):
    filename: str
    original_name: str
    content_hash: str
    file_size: int
    file_type: str
    storage_path: str
    similarity_percent: float
    similar_file_id: Optional[int] = None
    uploaded_by: int

# Схемы для сессий обработки
class ProcessingSessionCreate(BaseModel):
    user_id: int
    total_files: int

class ProcessingSession(BaseModel):
    id: int
    session_id: str
    user_id: int
    status: str
    total_files: int
    processed_files: int
    total_rows: int
    processed_rows: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Схемы для аналитики
class AnalyticsCreate(BaseModel):
    event_type: str
    user_id: Optional[int] = None
    order_id: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class Analytics(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int] = None
    order_id: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AnalyticsSummary(BaseModel):
    total_users: int
    active_users: int
    total_orders: int
    completed_orders: int
    total_files_processed: int
    average_processing_time: Optional[float] = None
    popular_file_formats: Dict[str, int]
    daily_stats: List[Dict[str, Any]]

# Схемы для системных настроек
class SystemSettingsBase(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class SystemSettingsCreate(SystemSettingsBase):
    pass

class SystemSettingsUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None

class SystemSettings(SystemSettingsBase):
    id: int
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Схемы для WebSocket сообщений
class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

class OrderProgressMessage(WebSocketMessage):
    type: str = "order_progress"
    
class OrderCompletedMessage(WebSocketMessage):
    type: str = "order_completed"

class SystemNotificationMessage(WebSocketMessage):
    type: str = "system_notification"

# Схемы для пагинации
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100)

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

# Обновляем forward references
OrderWithChanges.model_rebuild()
