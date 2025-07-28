"""
Константы приложения VHM24R
"""

# Временные константы (в секундах)
SECONDS_IN_DAY = 86400
SECONDS_IN_HOUR = 3600
SECONDS_IN_MINUTE = 60

# JWT настройки
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30
SESSION_CLEANUP_INTERVAL_SECONDS = 300  # 5 минут

# Размеры файлов (в байтах)
MAX_FILE_SIZE = 104857600  # 100MB
CHUNK_SIZE = 8192  # 8KB для чтения файлов

# Пагинация
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000

# Статусы пользователей
class UserStatus:
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"

# Роли пользователей
class UserRole:
    USER = "user"
    ADMIN = "admin"

# Статусы обработки файлов
class ProcessingStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Типы изменений заказов
class ChangeType:
    NEW = "new"
    UPDATE = "update"
    CORRECTION = "correction"
    AUTO_MATCH = "auto-match"

# Статусы платежей
class PaymentStatus:
    PAID = "Paid"
    PENDING = "Pending"
    FAILED = "Failed"
    REFUNDED = "Refunded"

# Типы файлов
class FileType:
    HARDWARE = "hardware"
    SALES = "sales"
    FISCAL = "fiscal"
    PAYME = "payme"
    CLICK = "click"
    UZUM = "uzum"

# HTTP статус коды
class HTTPStatus:
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500

# Алгоритмы шифрования
HASH_ALGORITHM = "HS256"
HMAC_ALGORITHM = "sha256"

# Настройки Redis
REDIS_KEY_PREFIX = "vhm24r:"
REDIS_SESSION_TTL = SECONDS_IN_DAY
REDIS_CACHE_TTL = SECONDS_IN_HOUR

# Настройки WebSocket
WS_HEARTBEAT_INTERVAL = 30  # секунд
WS_MAX_CONNECTIONS = 1000

# Настройки экспорта
EXPORT_FORMATS = ["csv", "xlsx", "xls", "json", "pdf"]
EXPORT_TIMEOUT = 300  # 5 минут

# Настройки Telegram
TELEGRAM_AUTH_TIMEOUT = SECONDS_IN_DAY
TELEGRAM_SESSION_TIMEOUT = 1800  # 30 минут

# Настройки базы данных
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 30
DB_POOL_TIMEOUT = 30

# Настройки логирования
LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_DAYS = 30
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Настройки мониторинга
HEALTH_CHECK_TIMEOUT = 5  # секунд
METRICS_UPDATE_INTERVAL = 60  # секунд

# Регулярные выражения
PHONE_REGEX = r"^\+?[1-9]\d{1,14}$"
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
ORDER_NUMBER_REGEX = r"^[A-Z0-9]{6,20}$"

# Сообщения об ошибках
class ErrorMessages:
    INVALID_CREDENTIALS = "Неверные учетные данные"
    ACCESS_DENIED = "Доступ запрещен"
    USER_NOT_FOUND = "Пользователь не найден"
    USER_NOT_APPROVED = "Пользователь не одобрен"
    FILE_TOO_LARGE = "Файл слишком большой"
    INVALID_FILE_FORMAT = "Неподдерживаемый формат файла"
    PROCESSING_ERROR = "Ошибка обработки"
    DATABASE_ERROR = "Ошибка базы данных"
    TELEGRAM_AUTH_FAILED = "Ошибка аутентификации Telegram"
    SESSION_EXPIRED = "Сессия истекла"
    RATE_LIMIT_EXCEEDED = "Превышен лимит запросов"

# Успешные сообщения
class SuccessMessages:
    USER_CREATED = "Пользователь создан успешно"
    USER_APPROVED = "Пользователь одобрен"
    FILE_UPLOADED = "Файл загружен успешно"
    FILE_PROCESSED = "Файл обработан успешно"
    DATA_EXPORTED = "Данные экспортированы"
    ORDER_UPDATED = "Заказ обновлен"
    SETTINGS_SAVED = "Настройки сохранены"

# Настройки окружения
class Environment:
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
