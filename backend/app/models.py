from sqlalchemy import Column, Integer, String, Text, DECIMAL, TIMESTAMP, Boolean, ForeignKey, BIGINT, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from .database import Base

# =====================================================
# ПОЛЬЗОВАТЕЛИ И АУТЕНТИФИКАЦИЯ
# =====================================================

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
    # Временно отключены до добавления в БД:
    # last_active = Column(TIMESTAMP)
    # is_deactivated = Column(Boolean, default=False)
    # deactivated_at = Column(TIMESTAMP)
    # deactivated_by = Column(Integer, ForeignKey('users.id'))
    
    # Computed properties for backward compatibility
    @property
    def is_approved(self):
        return str(self.status) == 'approved'
    
    @property
    def is_admin(self):
        return str(self.role) == 'admin'
    
    @property
    def is_active_user(self):
        return str(self.status) == 'approved'
        # Временно упрощено до добавления поля is_deactivated в БД
        # return (str(self.status) == 'approved' and 
        #         not bool(self.is_deactivated))

class TelegramSession(Base):
    __tablename__ = "telegram_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BIGINT, index=True, nullable=False)
    session_token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

# =====================================================
# 1. HARDWARE_ORDERS - Основной источник заказов (HW.xlsx)
# =====================================================

class HardwareOrder(Base):
    __tablename__ = "hardware_orders"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основные поля заказа (всегда копируются в unified_orders)
    order_number = Column(String(255), unique=True, nullable=False, index=True)
    address = Column(Text)
    machine_code = Column(String(50), index=True)
    
    # Информация о товаре
    goods_name = Column(String(255))
    taste_name = Column(String(255))
    order_type = Column(String(100), default='Normal order')
    
    # Платеж и статусы
    order_resource = Column(String(100))
    payment_status = Column(String(50), default='Paid', index=True)
    brew_status = Column(String(50), index=True)
    order_price = Column(DECIMAL(12,2))
    
    # Временные метки (полный цикл заказа)
    creation_time = Column(TIMESTAMP, index=True)
    paying_time = Column(TIMESTAMP)
    brewing_time = Column(TIMESTAMP)
    delivery_time = Column(TIMESTAMP)
    refund_time = Column(TIMESTAMP)
    
    # Дополнительные поля
    reason = Column(Text)
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 2. SALES_REPORTS - Дополняет заказы из HWH (report.xlsx)
# =====================================================

class SalesReport(Base):
    __tablename__ = "sales_reports"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основные идентификаторы
    report_id = Column(Integer)
    order_number = Column(String(255), index=True)
    goods_id = Column(Integer)
    
    # Информация о времени (Excel формат)
    time_value = Column(DECIMAL(20,10))
    formatted_time = Column(TIMESTAMP, index=True)
    
    # Товар и цена
    goods_name = Column(String(255), index=True)
    order_price = Column(DECIMAL(12,2))
    
    # Коды и идентификаторы (дополняют HWH)
    ikpu_code = Column(String(50))
    barcode = Column(String(100), default='Нет данных')
    marking = Column(String(100), default='Нет данных')
    
    # Платеж и ресурсы
    order_resource = Column(String(100))
    payment_type = Column(String(100), index=True)
    
    # Машина и категория
    machine_category = Column(String(255))
    machine_code = Column(String(50), index=True)
    
    # Бонусы и пользователь
    accrued_bonus = Column(DECIMAL(10,2), default=0)
    username = Column(String(255), default='Не определен')
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 3. FISCAL_RECEIPTS - Фискальные чеки (fiscal_bills.xlsx)
# =====================================================

class FiscalReceipt(Base):
    __tablename__ = "fiscal_receipts"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основные идентификаторы чека
    receipt_number = Column(String(50), nullable=False, index=True)
    fiscal_module = Column(String(100), index=True)
    recipe_number = Column(String(50))
    
    # Информация об операции
    operation_type = Column(String(50), default='Продажа')
    cashier = Column(String(255))
    trade_point = Column(String(255), index=True)
    
    # Суммы операции (для сравнения с order_price)
    operation_amount = Column(DECIMAL(12,2), nullable=False)
    cash_amount = Column(DECIMAL(12,2), default=0, index=True)
    card_amount = Column(DECIMAL(12,2), default=0)
    
    # Покупатель
    customer_info = Column(Text)
    
    # Временная метка (для сравнения ±5 сек)
    operation_datetime = Column(TIMESTAMP, nullable=False, index=True)
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 4. PAYME_PAYMENTS - Платежи через Payme (Payme.xlsx)
# =====================================================

class PaymePayment(Base):
    __tablename__ = "payme_payments"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Номер в отчете
    report_number = Column(Integer)
    
    # Основная информация
    provider_name = Column(String(100))
    cashbox_name = Column(String(255), index=True)
    payment_state = Column(String(50))
    
    # Временные метки (для сравнения ±5 сек)
    payment_time = Column(TIMESTAMP, index=True)
    cancel_time = Column(TIMESTAMP)
    processing_time = Column(TIMESTAMP)
    bank_time = Column(TIMESTAMP)
    
    # Процессинг и состояние
    state = Column(String(50))
    processing_name = Column(String(100), index=True)
    
    # ePos данные
    epos_merchant_id = Column(String(50))
    epos_terminal_id = Column(String(50))
    
    # Платежная информация (для сравнения с order_price)
    card_number = Column(String(50))
    amount_without_commission = Column(DECIMAL(12,2), index=True)
    client_commission = Column(DECIMAL(12,2))
    
    # Идентификаторы платежа
    payment_system_id = Column(String(255), index=True)
    provider_payment_id = Column(String(255))
    rrn = Column(String(50))
    
    # Дополнительные идентификаторы
    cashbox_identifier = Column(String(255))
    cash_register_id = Column(String(255))
    
    # Банковские данные
    bank_receipt_date = Column(Date)
    fiscal_sign = Column(String(50))
    fiscal_receipt_id = Column(String(50))
    
    # Дополнительная информация
    external_id = Column(String(255))
    payment_description = Column(Text)
    order_number = Column(String(50), index=True)
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 5. CLICK_PAYMENTS - Платежи через Click (Click.xlsx)
# =====================================================

class ClickPayment(Base):
    __tablename__ = "click_payments"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основные идентификаторы
    click_id = Column(String(50), unique=True, nullable=False, index=True)
    billing_id = Column(String(50), index=True)
    identifier = Column(String(50))
    
    # Информация о платеже
    service_name = Column(String(100))
    client_info = Column(String(100))
    payment_method = Column(String(100))
    amount = Column(DECIMAL(12,2), nullable=False, index=True)
    
    # Статус и касса
    payment_status = Column(String(50), index=True)
    cashbox = Column(String(100))
    
    # Временная метка (для сравнения ±5 сек)
    payment_date = Column(TIMESTAMP, nullable=False, index=True)
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 6. UZUM_PAYMENTS - Платежи через Uzum (uzum.xlsx)
# =====================================================

class UzumPayment(Base):
    __tablename__ = "uzum_payments"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основная информация о сервисе
    service_name = Column(String(255), nullable=False)
    
    # Финансовая информация (для сравнения с order_price)
    amount = Column(DECIMAL(12,2), nullable=False, index=True)
    commission = Column(DECIMAL(12,2))
    
    # Карта и тип
    card_type = Column(String(50))
    card_number = Column(String(50))
    
    # Статус платежа
    status = Column(String(50), index=True)
    
    # Идентификаторы
    merchant_id = Column(String(50), index=True)
    receipt_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Временная метка (для сравнения ±5 сек)
    payment_datetime = Column(String(100))
    parsed_datetime = Column(TIMESTAMP, index=True)
    
    # Метаданные
    source_file_id = Column(Integer, ForeignKey('files.id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    version = Column(Integer, default=1)

# =====================================================
# 7. UNIFIED_ORDERS - Общая база заказов (объединенная)
# =====================================================

class UnifiedOrder(Base):
    __tablename__ = "unified_orders"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Основные поля из hardware_orders (всегда заполняются)
    order_number = Column(String(255), unique=True, nullable=False, index=True)
    address = Column(Text)
    machine_code = Column(String(50), index=True)
    goods_name = Column(String(255))
    taste_name = Column(String(255))
    order_type = Column(String(100))
    order_resource = Column(String(100))
    payment_status = Column(String(50))
    brew_status = Column(String(50))
    order_price = Column(DECIMAL(12,2), index=True)
    creation_time = Column(TIMESTAMP, index=True)
    paying_time = Column(TIMESTAMP)
    brewing_time = Column(TIMESTAMP)
    delivery_time = Column(TIMESTAMP)
    refund_time = Column(TIMESTAMP)
    reason = Column(Text)
    
    # Поля из sales_reports (префикс vhr_)
    vhr_id = Column(Integer)
    vhr_time = Column(TIMESTAMP)
    vhr_ikpu_code = Column(String(50))
    vhr_barcode = Column(String(100))
    vhr_marking = Column(String(100))
    vhr_payment_type = Column(String(100))
    vhr_username = Column(String(255))
    vhr_accrued_bonus = Column(DECIMAL(10,2))
    vhr_machine_category = Column(String(255))
    
    # Поля из fiscal_receipts (префикс fiscal_)
    fiscal_receipt_number = Column(String(50))
    fiscal_module = Column(String(100))
    fiscal_recipe_number = Column(String(50))
    fiscal_operation_type = Column(String(50))
    fiscal_cashier = Column(String(255))
    fiscal_trade_point = Column(String(255))
    fiscal_operation_amount = Column(DECIMAL(12,2))
    fiscal_cash_amount = Column(DECIMAL(12,2))
    fiscal_card_amount = Column(DECIMAL(12,2))
    fiscal_customer_info = Column(Text)
    fiscal_operation_datetime = Column(TIMESTAMP)
    
    # Поля из payme_payments (префикс payme_)
    payme_provider_name = Column(String(100))
    payme_cashbox_name = Column(String(255))
    payme_payment_state = Column(String(50))
    payme_payment_time = Column(TIMESTAMP)
    payme_processing_name = Column(String(100))
    payme_card_number = Column(String(50))
    payme_amount_without_commission = Column(DECIMAL(12,2))
    payme_client_commission = Column(DECIMAL(12,2))
    payme_payment_system_id = Column(String(255))
    payme_provider_payment_id = Column(String(255))
    payme_rrn = Column(String(50))
    payme_fiscal_receipt_id = Column(String(50))
    payme_order_number = Column(String(50))
    
    # Поля из click_payments (префикс click_)
    click_id = Column(String(50))
    click_billing_id = Column(String(50))
    click_identifier = Column(String(50))
    click_service_name = Column(String(100))
    click_client_info = Column(String(100))
    click_payment_method = Column(String(100))
    click_amount = Column(DECIMAL(12,2))
    click_payment_status = Column(String(50))
    click_cashbox = Column(String(100))
    click_payment_date = Column(TIMESTAMP)
    
    # Поля из uzum_payments (префикс uzum_)
    uzum_service_name = Column(String(255))
    uzum_amount = Column(DECIMAL(12,2))
    uzum_commission = Column(DECIMAL(12,2))
    uzum_card_type = Column(String(50))
    uzum_card_number = Column(String(50))
    uzum_status = Column(String(50))
    uzum_merchant_id = Column(String(50))
    uzum_receipt_id = Column(String(255))
    uzum_parsed_datetime = Column(TIMESTAMP)
    
    # Метаданные
    is_temporary = Column(Boolean, default=False, index=True)
    source_files = Column(Text)  # JSON строка с ID файлов-источников
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_matched_at = Column(TIMESTAMP)
    match_score = Column(Integer, default=0, index=True)  # Количество совпавших источников (1-6)

# =====================================================
# 8. FILES - Управление файлами-источниками
# =====================================================

class File(Base):
    __tablename__ = "files"
    
    # Системные поля
    id = Column(Integer, primary_key=True, index=True)
    
    # Информация о файле
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False, index=True)  # 'hardware', 'sales', 'fiscal', 'payme', 'click', 'uzum'
    content_hash = Column(String(64), nullable=False, index=True)
    file_size = Column(BIGINT)
    file_url = Column(Text)
    
    # Статистика обработки
    records_count = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    matched_records = Column(Integer, default=0)
    error_records = Column(Integer, default=0)
    
    # Информация о дубликатах
    similarity_percent = Column(DECIMAL(5,2))
    duplicate_of_id = Column(Integer, ForeignKey('files.id'))
    
    # Метаданные загрузки
    uploaded_by = Column(Integer)
    uploaded_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    processing_started_at = Column(TIMESTAMP)
    processing_finished_at = Column(TIMESTAMP)
    processing_status = Column(String(50), default='pending', index=True)  # 'pending', 'processing', 'completed', 'failed'
    error_message = Column(Text)
    
    # Дополнительная информация
    detected_encoding = Column(String(50))
    detected_delimiter = Column(String(10))
    sheet_names = Column(Text)  # JSON строка с именами листов
    processed_sheet = Column(String(255))

# =====================================================
# 9. ORDER_CHANGES - История изменений
# =====================================================

class OrderChange(Base):
    __tablename__ = "order_changes"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Идентификация записи
    table_name = Column(String(50), nullable=False)
    record_id = Column(BIGINT, nullable=False)
    order_number = Column(String(255), index=True)
    
    # Информация об изменении
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    change_type = Column(String(20), nullable=False, index=True)  # 'new', 'update', 'correction', 'auto-match'
    
    # Контекст изменения
    change_reason = Column(Text)
    confidence_score = Column(DECIMAL(3,2))
    
    # Метаданные
    changed_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    source_file_id = Column(Integer, ForeignKey('files.id'))
    changed_by = Column(Integer)
    
    # Дополнительная информация
    processing_batch_id = Column(String(36))  # UUID строка
    validation_status = Column(String(50), default='pending')  # 'pending', 'approved', 'rejected'

# =====================================================
# 10. ORDER_ERRORS - Ошибки сопоставления
# =====================================================

class OrderError(Base):
    __tablename__ = "order_errors"
    
    # Системные поля
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Информация об ошибке
    order_number = Column(String(255), index=True)
    error_type = Column(String(100), nullable=False, index=True)
    error_code = Column(String(50))
    description = Column(Text, nullable=False)
    severity = Column(String(20), default='medium', index=True)  # 'low', 'medium', 'high', 'critical'
    
    # Контекст ошибки
    source_table = Column(String(50))
    source_record_id = Column(BIGINT)
    target_table = Column(String(50))
    target_record_id = Column(BIGINT)
    
    # Данные для анализа
    conflicting_values = Column(Text)  # JSON строка
    suggested_resolution = Column(Text)
    
    # Метаданные
    error_timestamp = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    source_file_id = Column(Integer, ForeignKey('files.id'))
    processing_batch_id = Column(String(36))  # UUID строка
    
    # Статус обработки ошибки
    resolution_status = Column(String(50), default='open', index=True)  # 'open', 'investigating', 'resolved', 'ignored'
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(Integer)
    resolution_note = Column(Text)

# =====================================================
# LEGACY MODELS (для обратной совместимости)
# =====================================================

# Алиасы для обратной совместимости
UploadedFile = File
Order = UnifiedOrder

# Дополнительные модели для совместимости
class ProcessingSession(Base):
    __tablename__ = "processing_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True)
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
