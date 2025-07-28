# Инструкция по развертыванию VHM24R

Это подробная инструкция по развертыванию системы VHM24R на Railway.app с интеграцией DigitalOcean Spaces.

## 📋 Предварительные требования

### 1. Аккаунты и сервисы
- [Railway.app](https://railway.app) аккаунт
- [DigitalOcean](https://digitalocean.com) аккаунт
- [GitHub](https://github.com) репозиторий
- Telegram Bot Token от [@BotFather](https://t.me/BotFather)

### 2. Локальные инструменты
- Git
- Node.js (для локальной разработки frontend)
- Python 3.11+ (для локальной разработки backend)

## 🚀 Пошаговое развертывание

### Шаг 1: Подготовка репозитория

1. **Создайте GitHub репозиторий**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: VHM24R project"
   git branch -M main
   git remote add origin https://github.com/your-username/vhm24r.git
   git push -u origin main
   ```

### Шаг 2: Создание Telegram бота

1. **Создайте бота через @BotFather**
   - Отправьте `/newbot` в [@BotFather](https://t.me/BotFather)
   - Выберите имя бота (например: `VHM24R Bot`)
   - Выберите username бота (например: `vhm24r_bot`)
   - Сохраните полученный токен

2. **Настройте бота**
   ```
   /setdescription - Система управления заказами VHM24R
   /setabouttext - VHM24R - современная система управления заказами
   /setuserpic - Загрузите аватар бота
   ```

### Шаг 3: Настройка DigitalOcean Spaces

1. **Создайте Spaces bucket**
   - Войдите в DigitalOcean панель
   - Перейдите в Spaces Object Storage
   - Создайте новый Space (например: `vhm24r-files`)
   - Выберите регион (рекомендуется: Frankfurt - fra1)

2. **Создайте API ключи**
   - Перейдите в API → Spaces Keys
   - Создайте новый ключ
   - Сохраните Access Key и Secret Key

3. **Настройте CORS**
   ```json
   [
     {
       "AllowedOrigins": ["*"],
       "AllowedMethods": ["GET", "POST", "PUT", "DELETE"],
       "AllowedHeaders": ["*"],
       "MaxAgeSeconds": 3000
     }
   ]
   ```

### Шаг 4: Развертывание на Railway.app

1. **Создайте проект на Railway**
   - Войдите в [Railway.app](https://railway.app)
   - Нажмите "New Project"
   - Выберите "Deploy from GitHub repo"
   - Выберите ваш репозиторий

2. **Railway автоматически обнаружит конфигурацию**
   - Railway прочитает `railway.toml`
   - Создаст сервисы для backend и frontend
   - Настроит автоматическое развертывание

### Шаг 5: Добавление баз данных

1. **Добавьте PostgreSQL**
   - В Railway проекте нажмите "New Service"
   - Выберите "Database" → "PostgreSQL"
   - Railway автоматически создаст `DATABASE_URL`

2. **Добавьте Redis**
   - Нажмите "New Service"
   - Выберите "Database" → "Redis"
   - Railway автоматически создаст `REDIS_URL`

### Шаг 6: Настройка переменных окружения

В Railway панели для backend сервиса установите:

```env
# Основные настройки
APP_NAME=VHM24R
DEBUG=False
ENVIRONMENT=production
SECRET_KEY=your-super-secret-key-generate-new-one

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
ADMIN_TELEGRAM_ID=Jamshiddin

# DigitalOcean Spaces
DO_SPACES_KEY=your-spaces-access-key
DO_SPACES_SECRET=your-spaces-secret-key
DO_SPACES_ENDPOINT=https://fra1.digitaloceanspaces.com
DO_SPACES_BUCKET=vhm24r-files
DO_SPACES_REGION=fra1

# URLs (обновите после получения домена)
WEBAPP_URL=https://your-app-name.railway.app
FRONTEND_URL=https://your-app-name.railway.app
BACKEND_URL=https://your-app-name.railway.app/api/v1
TELEGRAM_WEBHOOK_URL=https://your-app-name.railway.app/webhook/telegram

# Безопасность для продакшена
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
CORS_ORIGINS=https://your-app-name.railway.app

# Производительность
WORKERS=2
MAX_CONNECTIONS=1000
```

### Шаг 7: Настройка домена

1. **Получите Railway домен**
   - В Railway проекте перейдите в Settings
   - Скопируйте сгенерированный домен (например: `vhm24r-production.railway.app`)

2. **Обновите переменные окружения**
   - Замените `your-app-name.railway.app` на ваш реальный домен
   - Обновите все URL переменные

3. **Настройте Telegram Webhook**
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
        -H "Content-Type: application/json" \
        -d '{"url": "https://your-app-name.railway.app/webhook/telegram"}'
   ```

### Шаг 8: Выполнение миграций

1. **Подключитесь к Railway CLI**
   ```bash
   npm install -g @railway/cli
   railway login
   railway link
   ```

2. **Выполните миграции**
   ```bash
   railway run alembic upgrade head
   ```

### Шаг 9: Проверка развертывания

1. **Проверьте статус сервисов**
   - Все сервисы должны быть в статусе "Active"
   - Проверьте логи на наличие ошибок

2. **Проверьте API**
   ```bash
   curl https://your-app-name.railway.app/health
   ```

3. **Проверьте Telegram бота**
   - Отправьте `/start` вашему боту
   - Убедитесь, что бот отвечает

4. **Проверьте документацию API**
   - Откройте `https://your-app-name.railway.app/docs`

## 🔧 Настройка после развертывания

### Настройка мониторинга

1. **Настройте Sentry (опционально)**
   ```env
   SENTRY_DSN=your-sentry-dsn
   ```

2. **Настройте метрики**
   - Prometheus метрики доступны на `/metrics`
   - Health check на `/health`

### Настройка резервного копирования

1. **Настройте автоматические бэкапы PostgreSQL**
   - Railway автоматически создает бэкапы
   - Настройте дополнительные бэкапы через DigitalOcean

2. **Настройте бэкап файлов**
   - DigitalOcean Spaces автоматически реплицирует данные
   - Настройте lifecycle policies для старых файлов

## 📊 Мониторинг и логирование

### Логи Railway
```bash
# Просмотр логов в реальном времени
railway logs

# Логи конкретного сервиса
railway logs --service backend
```

### Метрики
- **CPU и память**: Railway Dashboard
- **База данных**: PostgreSQL метрики в Railway
- **API метрики**: `/metrics` endpoint
- **Пользовательская активность**: `/api/v1/analytics`

## 🚨 Устранение неполадок

### Частые проблемы

1. **Бот не отвечает**
   ```bash
   # Проверьте webhook
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   
   # Переустановите webhook
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
        -d "url=https://your-app-name.railway.app/webhook/telegram"
   ```

2. **Ошибки базы данных**
   ```bash
   # Проверьте подключение
   railway run python -c "from app.database import engine; print('DB OK')"
   
   # Выполните миграции
   railway run alembic upgrade head
   ```

3. **Проблемы с файлами**
   ```bash
   # Проверьте Spaces подключение
   railway run python -c "from app.services.file_processor import test_spaces_connection; test_spaces_connection()"
   ```

### Логи и отладка

1. **Просмотр логов приложения**
   ```bash
   railway logs --service backend
   ```

2. **Подключение к базе данных**
   ```bash
   railway connect postgresql
   ```

3. **Выполнение команд в контейнере**
   ```bash
   railway run bash
   ```

## 🔄 Обновление приложения

### Автоматическое развертывание
Railway автоматически развертывает изменения при push в main ветку:

```bash
git add .
git commit -m "Update: description of changes"
git push origin main
```

### Ручное развертывание
```bash
# Через Railway CLI
railway up

# Или через Railway Dashboard
# Нажмите "Deploy" в интерфейсе
```

### Миграции базы данных
```bash
# Создание новой миграции
railway run alembic revision --autogenerate -m "Description"

# Применение миграций
railway run alembic upgrade head
```

## 💰 Оптимизация стоимости

### Railway.app планы
- **Starter**: $5/месяц - подходит для тестирования
- **Developer**: $10/месяц - рекомендуется для продакшена
- **Team**: $20/месяц - для команд

### DigitalOcean Spaces
- **Хранилище**: $5/месяц за 250GB
- **Трафик**: $0.01/GB исходящего трафика
- **Запросы**: $0.01 за 1000 запросов

### Общая стоимость: $10-25/месяц

## 🔒 Безопасность

### Рекомендации для продакшена

1. **Обновите все секретные ключи**
   ```bash
   # Сгенерируйте новый SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Настройте HTTPS**
   - Railway автоматически предоставляет SSL сертификаты
   - Убедитесь, что `SECURE_SSL_REDIRECT=true`

3. **Ограничьте CORS**
   ```env
   CORS_ORIGINS=https://your-domain.com
   ```

4. **Настройте rate limiting**
   ```env
   API_RATE_LIMIT=100  # запросов в минуту
   ```

5. **Регулярно обновляйте зависимости**
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

## 📞 Поддержка

### Контакты
- **Telegram**: @Jamshiddin
- **Email**: support@vhm24r.com
- **GitHub Issues**: [Создать issue](https://github.com/your-username/vhm24r/issues)

### Полезные ссылки
- [Railway.app документация](https://docs.railway.app/)
- [DigitalOcean Spaces документация](https://docs.digitalocean.com/products/spaces/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [FastAPI документация](https://fastapi.tiangolo.com/)

---

**Успешного развертывания! 🚀**

После завершения развертывания ваша система VHM24R будет доступна по адресу `https://your-app-name.railway.app` с полной функциональностью обработки файлов, Telegram интеграцией и возможностями экспорта данных.
