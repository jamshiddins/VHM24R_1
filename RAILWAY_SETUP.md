# 🚀 Настройка Railway для VHM24R

## ✅ Код загружен в GitHub!

**Репозиторий**: https://github.com/jamshiddins/VHM24R_1.git  
**Ветка**: main  
**Railway Project ID**: 1daf7bb3-ad76-4a0c-9376-fc9b076aa6e7  

## 🔧 Настройка Railway (пошагово):

### 1. Подключение репозитория
1. Войдите на [railway.app](https://railway.app)
2. Откройте проект `1daf7bb3-ad76-4a0c-9376-fc9b076aa6e7`
3. Создайте новый сервис → "GitHub Repo"
4. Выберите `jamshiddins/VHM24R_1`
5. Выберите ветку `main`

### 2. Добавление баз данных
В том же проекте:
- Добавьте **PostgreSQL** (New Service → Database → PostgreSQL)
- Добавьте **Redis** (New Service → Database → Redis)

### 3. Переменные окружения для backend сервиса

Скопируйте эти переменные в Railway:

```env
# Основные настройки
APP_NAME=VHM24R
DEBUG=False
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# Безопасность
SECRET_KEY=wxz+NbznFmO8g9eYJ5fkCOFrdrBLlJQtrbnOF5Y5V8c
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=24

# Telegram Bot
TELEGRAM_BOT_TOKEN=8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk
ADMIN_TELEGRAM_ID=Jamshiddin

# DigitalOcean Spaces
DO_SPACES_KEY=DO0092QW37F9Q2HEVKVU
DO_SPACES_SECRET=dop_v1_1a20413d8dd3f7827a72efa19b2cbb766850258ddf44044c5546fe2e0a244de9
DO_SPACES_ENDPOINT=https://vhm24r1-files.fra1.digitaloceanspaces.com
DO_SPACES_BUCKET=vhm24r1-files
DO_SPACES_REGION=fra1

# Производительность
WORKERS=2
MAX_CONNECTIONS=1000

# Файлы
MAX_FILE_SIZE=104857600
SUPPORTED_UPLOAD_FORMATS=csv,xls,xlsx,pdf,doc,docx,json,xml,zip,rar,txt,tsv
SUPPORTED_EXPORT_FORMATS=csv,xlsx,xls,json,pdf

# Безопасность для продакшена
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

**Важно**: Railway автоматически создаст `DATABASE_URL` и `REDIS_URL`

### 4. После получения домена

После деплоя Railway покажет домен (например: `vhm24r-production-abc123.railway.app`)

Добавьте эти переменные с вашим реальным доменом:

```env
# URLs (замените YOUR_DOMAIN на реальный домен)
WEBAPP_URL=https://YOUR_DOMAIN.railway.app
FRONTEND_URL=https://YOUR_DOMAIN.railway.app
BACKEND_URL=https://YOUR_DOMAIN.railway.app/api/v1
TELEGRAM_WEBHOOK_URL=https://YOUR_DOMAIN.railway.app/webhook/telegram
CORS_ORIGINS=https://YOUR_DOMAIN.railway.app
ALLOWED_HOSTS=localhost,127.0.0.1,YOUR_DOMAIN.railway.app
```

### 5. Выполнение миграций

```bash
# Установка Railway CLI
npm install -g @railway/cli

# Подключение к проекту
railway login
railway link 1daf7bb3-ad76-4a0c-9376-fc9b076aa6e7

# Выполнение миграций
railway run alembic upgrade head
```

### 6. Настройка Telegram Webhook

```bash
# Замените YOUR_DOMAIN на реальный домен Railway
curl -X POST "https://api.telegram.org/bot8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://YOUR_DOMAIN.railway.app/webhook/telegram"}'
```

### 7. Настройка бота через @BotFather

```
/setdescription
VHM24R - Система управления заказами

/setabouttext
Современная система обработки файлов и управления заказами

/setcommands
start - Запуск системы
help - Помощь

/setmenubutton
text: Открыть VHM24R
url: https://YOUR_DOMAIN.railway.app
```

## 🧪 Проверка работы

### API Endpoints:
- **Health**: `https://YOUR_DOMAIN.railway.app/health`
- **Docs**: `https://YOUR_DOMAIN.railway.app/docs`
- **Frontend**: `https://YOUR_DOMAIN.railway.app/`

### Telegram Bot:
1. Отправьте `/start` боту @vhm24rbot
2. Проверьте меню WebApp
3. Попробуйте загрузить тестовый файл

## 📊 Мониторинг

```bash
# Просмотр логов
railway logs

# Статус сервисов
railway status

# Переменные окружения
railway variables
```

## 💰 Стоимость

- **Railway**: $10-20/месяц
- **DigitalOcean Spaces**: $5/месяц
- **Общая стоимость**: $15-25/месяц

## 🆘 Поддержка

Если что-то не работает:

1. **Проверьте логи**: `railway logs`
2. **Проверьте переменные**: Railway Dashboard → Settings → Variables
3. **Проверьте webhook**: 
   ```bash
   curl "https://api.telegram.org/bot8475088876:AAGCh21e0ohqPkX4M6Efe_Pra4pzQEznWmk/getWebhookInfo"
   ```

## 🎉 Готово!

После выполнения всех шагов у вас будет:

✅ Работающий Telegram бот @vhm24rbot  
✅ Web-интерфейс для загрузки файлов  
✅ Система обработки 12 форматов файлов  
✅ Экспорт в 5 форматов  
✅ Персональные ссылки для пользователей  
✅ Система одобрения пользователей  
✅ Отслеживание изменений с цветовой кодировкой  
✅ WebSocket обновления в реальном времени  
✅ Полная аналитика и мониторинг  

**Ваша система VHM24R готова к работе! 🚀**

---

*Для получения помощи обращайтесь к @Jamshiddin*
