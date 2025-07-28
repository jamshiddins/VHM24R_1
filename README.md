# VHM24R - Система управления заказами

VHM24R - это современная система управления заказами с поддержкой обработки файлов различных форматов, интеграцией с Telegram ботом и возможностями экспорта данных.

## 🚀 Особенности

### 📁 Поддержка файлов
- **12 форматов загрузки**: CSV, XLS, XLSX, PDF, DOC, DOCX, JSON, XML, ZIP, RAR, TXT, TSV
- **5 форматов экспорта**: CSV, XLSX, XLS, JSON, PDF
- **Максимальный размер файла**: 100MB
- **Автоматическое определение кодировки**

### 🤖 Telegram Bot
- **Визуальные меню** вместо текстовых команд
- **Персональные ссылки** для каждого пользователя
- **Уведомления в реальном времени**
- **Административные функции**
- **WebApp интеграция**

### 🔐 Безопасность
- **JWT аутентификация** через Telegram
- **Уникальные персональные ссылки**
- **Система одобрения пользователей**
- **Единственный администратор**: @Jamshiddin

### 📊 Отслеживание изменений
- 🟩 **Новые записи**
- 🟧 **Обновленные записи**
- 🟦 **Заполненные поля**
- 🔸 **Измененные значения**

### ⚡ Производительность
- **WebSocket** для обновлений в реальном времени
- **Асинхронная обработка** файлов
- **Прогресс-бар** обработки
- **Кэширование** результатов

## 🏗️ Архитектура

```
VHM24R/
├── backend/                 # FastAPI приложение
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # Основное приложение
│   │   ├── database.py     # Подключение к БД
│   │   ├── models.py       # SQLAlchemy модели
│   │   ├── schemas.py      # Pydantic схемы
│   │   ├── crud.py         # CRUD операции
│   │   ├── auth.py         # Аутентификация
│   │   ├── telegram_bot.py # Telegram бот
│   │   └── services/
│   │       ├── file_processor.py  # Обработка файлов
│   │       └── export_service.py  # Экспорт данных
│   ├── migrations/         # Alembic миграции
│   ├── requirements.txt    # Python зависимости
│   ├── .env               # Переменные окружения
│   ├── Dockerfile         # Docker конфигурация
│   └── alembic.ini        # Alembic настройки
├── frontend/              # Vue.js приложение
│   ├── src/
│   │   ├── components/    # Vue компоненты
│   │   └── services/      # API сервисы
│   └── public/
├── railway.toml           # Railway.app конфигурация
└── README.md             # Документация
```

## 🛠️ Технологический стек

### Backend
- **FastAPI** - современный веб-фреймворк
- **PostgreSQL** - основная база данных
- **SQLAlchemy** - ORM для работы с БД
- **Alembic** - миграции базы данных
- **Redis** - кэширование и очереди
- **Celery** - асинхронные задачи

### Обработка файлов
- **pandas** - анализ данных
- **openpyxl** - Excel файлы
- **pdfplumber** - PDF документы
- **python-docx** - Word документы
- **reportlab** - генерация PDF

### Telegram
- **python-telegram-bot** - Telegram Bot API
- **WebApp** - интеграция с веб-приложением

### Развертывание
- **Railway.app** - хостинг приложения
- **DigitalOcean Spaces** - файловое хранилище
- **Docker** - контейнеризация

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/vhm24r.git
cd vhm24r
```

### 2. Настройка backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. Настройка переменных окружения
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими настройками
```

### 4. Настройка базы данных
```bash
# Создайте PostgreSQL базу данных
createdb vhm24r_db

# Выполните миграции
alembic upgrade head
```

### 5. Запуск приложения
```bash
uvicorn app.main:app --reload
```

### 6. Настройка Telegram бота
1. Создайте бота через @BotFather
2. Получите токен бота
3. Обновите `TELEGRAM_BOT_TOKEN` в .env
4. Запустите бота: `/start`

## 🌐 Развертывание на Railway.app

### 1. Подготовка к развертыванию
```bash
# Убедитесь, что все файлы готовы
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Создание проекта на Railway
1. Зайдите на [railway.app](https://railway.app)
2. Создайте новый проект
3. Подключите GitHub репозиторий
4. Railway автоматически обнаружит `railway.toml`

### 3. Настройка сервисов
Railway автоматически создаст:
- **PostgreSQL** база данных
- **Redis** для кэширования
- **Backend** сервис
- **Frontend** сервис (если есть)

### 4. Настройка переменных окружения
В Railway панели установите:
```
TELEGRAM_BOT_TOKEN=your-bot-token
DO_SPACES_KEY=your-spaces-key
DO_SPACES_SECRET=your-spaces-secret
SECRET_KEY=your-secret-key
```

### 5. Настройка домена
1. В Railway панели перейдите в Settings
2. Добавьте custom domain или используйте railway.app домен
3. Обновите `WEBAPP_URL` в переменных окружения

## 📋 API Документация

После запуска приложения документация доступна по адресам:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Основные эндпоинты

#### Аутентификация
```
POST /api/v1/auth/telegram - Аутентификация через Telegram
GET  /api/v1/auth/me       - Получить текущего пользователя
```

#### Управление пользователями
```
GET  /api/v1/users/pending           - Пользователи на одобрении
POST /api/v1/users/{user_id}/approve - Одобрить пользователя
```

#### Файлы и заказы
```
POST /api/v1/upload                    - Загрузить файл
GET  /api/v1/orders                    - Список заказов
GET  /api/v1/orders/{order_id}         - Детали заказа
GET  /api/v1/orders/{order_id}/changes - Изменения в заказе
```

#### Экспорт
```
POST /api/v1/export - Экспорт данных
```

#### Аналитика
```
GET /api/v1/analytics - Аналитика системы
```

## 🤖 Telegram Bot команды

### Пользовательские команды
- `/start` - Регистрация и главное меню
- `📊 Мои заказы` - Просмотр заказов
- `📈 Статистика` - Личная статистика
- `ℹ️ Информация` - О системе
- `🆘 Помощь` - Справка

### Административные команды
- `👥 Управление пользователями` - Одобрение пользователей
- `📊 Аналитика системы` - Системная аналитика

## 🔧 Конфигурация

### Основные настройки (.env)
```env
# Приложение
APP_NAME=VHM24R
DEBUG=True
SECRET_KEY=your-secret-key

# База данных
DATABASE_URL=postgresql://user:pass@localhost:5432/vhm24r_db

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
ADMIN_TELEGRAM_ID=Jamshiddin

# Файловое хранилище
DO_SPACES_KEY=your-key
DO_SPACES_SECRET=your-secret
DO_SPACES_BUCKET=vhm24r-files

# Ограничения
MAX_FILE_SIZE=104857600  # 100MB
```

## 📊 Мониторинг и логирование

### Логи
Логи сохраняются в:
- `./logs/app.log` - основные логи приложения
- `./logs/telegram.log` - логи Telegram бота
- `./logs/processing.log` - логи обработки файлов

### Метрики
- **Prometheus** метрики доступны на `/metrics`
- **Health check** доступен на `/health`

### Мониторинг производительности
```python
# Пример метрик
- vhm24r_requests_total - общее количество запросов
- vhm24r_processing_duration - время обработки файлов
- vhm24r_active_users - активные пользователи
- vhm24r_file_uploads_total - загруженные файлы
```

## 🧪 Тестирование

### Запуск тестов
```bash
# Установка тестовых зависимостей
pip install pytest pytest-asyncio httpx

# Запуск всех тестов
pytest

# Запуск с покрытием
pytest --cov=app tests/
```

### Структура тестов
```
tests/
├── test_auth.py          # Тесты аутентификации
├── test_file_processing.py # Тесты обработки файлов
├── test_export.py        # Тесты экспорта
├── test_telegram_bot.py  # Тесты Telegram бота
└── conftest.py          # Конфигурация тестов
```

## 🔒 Безопасность

### Рекомендации для продакшена
1. **Измените SECRET_KEY** на случайную строку
2. **Используйте HTTPS** для всех соединений
3. **Настройте CORS** только для нужных доменов
4. **Включите rate limiting** для API
5. **Регулярно обновляйте** зависимости

### Переменные окружения для продакшена
```env
DEBUG=False
ENVIRONMENT=production
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

## 💰 Стоимость развертывания

### Railway.app (рекомендуемый)
- **Starter Plan**: $5/месяц
- **Developer Plan**: $10/месяц
- **Team Plan**: $20/месяц

### DigitalOcean Spaces
- **Хранилище**: $5/месяц за 250GB
- **Трафик**: $0.01/GB

### Общая стоимость: $10-25/месяц

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## 📝 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Поддержка

- **Telegram**: @Jamshiddin
- **Email**: support@vhm24r.com
- **Issues**: [GitHub Issues](https://github.com/your-username/vhm24r/issues)

## 🎯 Roadmap

### v1.1 (Планируется)
- [ ] Поддержка дополнительных форматов файлов
- [ ] Улучшенная аналитика
- [ ] API для интеграции с внешними системами
- [ ] Мобильное приложение

### v1.2 (Планируется)
- [ ] Машинное обучение для анализа данных
- [ ] Автоматическая категоризация файлов
- [ ] Расширенные права доступа
- [ ] Интеграция с облачными хранилищами

## 🏆 Благодарности

- [FastAPI](https://fastapi.tiangolo.com/) - за отличный веб-фреймворк
- [python-telegram-bot](https://python-telegram-bot.org/) - за Telegram интеграцию
- [Railway.app](https://railway.app/) - за простое развертывание
- [DigitalOcean](https://digitalocean.com/) - за надежное хранилище

---

**VHM24R** - Современная система управления заказами с поддержкой множества форматов файлов и интеграцией с Telegram.
