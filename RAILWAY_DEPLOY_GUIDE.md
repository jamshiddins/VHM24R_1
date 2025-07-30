# 🚀 РУКОВОДСТВО ПО ДЕПЛОЮ НА RAILWAY

## 📋 ПОДГОТОВКА К ДЕПЛОЮ

### 1. Обновленные переменные окружения для Railway:

```bash
# Основные настройки
DATABASE_URL=postgresql://user:password@host:port/database
FRONTEND_URL=https://vhm24r1-production.up.railway.app

# Telegram Bot
TELEGRAM_BOT_TOKEN=7435657487:AAGiKh4x41v6VupkvvB5qKdcEQCeeXewszk

# JWT и безопасность  
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Railway специфические
PORT=8000
PYTHONPATH=/app
```

### 2. Обновления в коде:

✅ **Система аутентификации v2.0**
- API эндпоинты: `/api/v2/auth/*`
- JWT токены с refresh механизмом
- Множественные методы аутентификации
- Типизированные модели данных

✅ **Telegram бот исправления**
- Исправлены localhost URL (заменены на callback кнопки)
- Обновлен токен бота
- Production-ready настройки

✅ **Конфигурация Railway**
- Обновлен railway.toml
- Dockerfile оптимизирован
- Переменные окружения настроены

## 🔄 КОМАНДЫ ДЛЯ ДЕПЛОЯ

### 1. Обновить Git:
```bash
git add .
git commit -m "feat: complete authentication system v2.0 with telegram bot fixes"
git push origin main
```

### 2. Деплой на Railway:
```bash
railway login
railway link vhm24r1-production
railway up
```

### 3. Установить переменные окружения:
```bash
railway variables set TELEGRAM_BOT_TOKEN=7435657487:AAGiKh4x41v6VupkvvB5qKdcEQCeeXewszk
railway variables set FRONTEND_URL=https://vhm24r1-production.up.railway.app
railway variables set SECRET_KEY=your-super-secret-key-here
railway variables set JWT_SECRET_KEY=your-jwt-secret-key-here
```

## 🎯 ПРОВЕРКА ПОСЛЕ ДЕПЛОЯ

### API проверки:
- `GET /api/v2/auth/health` - должен вернуть success
- `GET /docs` - Swagger документация
- Telegram бот @vendhub24bot - должен работать без ошибок

### Telegram бот функции:
- ✅ Получение ссылок через callback кнопки (вместо URL кнопок)
- ✅ Система одобрения пользователей
- ✅ Административные функции
- ✅ Уведомления админа

## 📊 МОНИТОРИНГ

После деплоя система будет доступна:
- **API**: https://vhm24r1-production.up.railway.app/api/v2/auth/health
- **WebApp**: https://vhm24r1-production.up.railway.app/
- **Telegram Bot**: @vendhub24bot

## 🔐 БЕЗОПАСНОСТЬ

- JWT токены с автоматическим обновлением
- Централизованная аутентификация
- Безопасные сессии пользователей
- Административный контроль доступа
