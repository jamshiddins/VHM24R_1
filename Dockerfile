FROM python:3.12-alpine

# Обновляем систему и устанавливаем PostgreSQL зависимости
RUN apk update && apk upgrade && \
    apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Создаем непривилегированного пользователя
RUN addgroup -S appuser && adduser -S appuser -G appuser

WORKDIR /app

# Копируйте только backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend/

# Изменяем владельца файлов на непривилегированного пользователя
RUN chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
