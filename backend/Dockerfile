FROM python:3.12-alpine

# Обновляем пакеты и устанавливаем системные зависимости
RUN apk update && apk upgrade && apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    postgresql-dev \
    linux-headers \
    libmagic \
    unrar \
    curl \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Создаем пользователя без привилегий
RUN addgroup -S appuser && adduser -S appuser -G appuser

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Обновляем pip и устанавливаем Python зависимости
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Копируем frontend из родительской директории
COPY ../frontend ./frontend

# Создаем необходимые директории и устанавливаем права доступа
RUN mkdir -p uploads temp exports logs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Переключаемся на пользователя без привилегий
USER appuser

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
