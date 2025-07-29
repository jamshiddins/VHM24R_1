# 🚀 Настройка переменных окружения в Railway

## 📋 Обязательные переменные для Railway

Зайдите в ваш проект Railway и добавьте следующие переменные окружения:

### 1. 🤖 Telegram Bot
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_TELEGRAM_ID=your_admin_telegram_id_here
TELEGRAM_WEBHOOK_URL=https://vhm24r1-production.up.railway.app/webhook/telegram
```

### 2. 🌐 URL настройки
```
FRONTEND_URL=https://vhm24r1-production.up.railway.app
WEBAPP_URL=https://vhm24r1-production.up.railway.app
BACKEND_URL=https://vhm24r1-production.up.railway.app/api/v1
```

### 3. 🔐 Безопасность
```
SECRET_KEY=wxz+NbznFmO8g9eYJ5fkCOFrdrBLlJQtrbnOF5Y5V8c
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24
```

### 4. 🗄️ База данных (автоматически)
Railway автоматически добавит:
```
DATABASE_URL=postgresql://...
```

### 5. 📁 DigitalOcean Spaces
```
DO_SPACES_KEY=DO0092QW37F9Q2HEVKVU
DO_SPACES_SECRET=dop_v1_1a20413d8dd3f7827a72efa19b2cbb766850258ddf44044c5546fe2e0a244de9
DO_SPACES_ENDPOINT=https://vhm24r1-files.fra1.digitaloceanspaces.com
DO_SPACES_BUCKET=vhm24r1-files
DO_SPACES_REGION=fra1
```

### 6. 🔧 Настройки приложения
```
APP_NAME=VHM24R
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
```

### 7. 🛡️ CORS и безопасность
```
CORS_ORIGINS=https://vhm24r1-production.up.railway.app
ALLOWED_HOSTS=vhm24r1-production.up.railway.app
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

## 🎯 Как добавить переменные в Railway:

### Способ 1: Через веб-интерфейс
1. Откройте ваш проект в Railway
2. Перейдите в раздел "Variables"
3. Нажмите "New Variable"
4. Добавьте каждую переменную по очереди

### Способ 2: Через Railway CLI
```bash
# Установите Railway CLI
npm install -g @railway/cli

# Войдите в аккаунт
railway login

# Перейдите в проект
railway link

# Добавьте переменные
railway variables set TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
railway variables set ADMIN_TELEGRAM_ID=your_admin_telegram_id_here
railway variables set FRONTEND_URL=https://vhm24r1-production.up.railway.app
# ... и так далее для всех переменных
```

## 🔄 После добавления переменных:

1. **Перезапустите деплой:**
   - В Railway нажмите "Redeploy"
   - Или сделайте новый commit в Git

2. **Проверьте логи:**
   - Откройте раздел "Deployments"
   - Проверьте логи запуска

3. **Тестирование:**
   - Откройте `https://vhm24r1-production.up.railway.app/health`
   - Должен показать статус всех сервисов

## ⚠️ Важные замечания:

- **DATABASE_URL** - Railway добавит автоматически при подключении PostgreSQL
- **REDIS_URL** - Railway добавит автоматически при подключении Redis (опционально)
- Все URL должны использовать ваш реальный домен Railway
- В продакшене установите `DEBUG=False`

## 🚀 Готово!

После добавления всех переменных система будет готова к работе:
- Telegram бот будет работать с вашим ID как админом
- WebApp будет доступен по адресу `/webapp`
- Все компоненты будут правильно интегрированы

---
**Ваш админский Telegram ID:** `42283329`  
**Домен:** `https://vhm24r1-production.up.railway.app`
