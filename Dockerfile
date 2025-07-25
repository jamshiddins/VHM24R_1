FROM python:3.12.8-slim-bookworm

# Устанавливаем системные зависимости и обновления безопасности
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && apt-get autoremove -y \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && find /usr/share/doc -depth -type f ! -name copyright | xargs rm || true \
    && find /usr/share/man -depth -type f | xargs rm || true

# Создаем непривилегированного пользователя с ограниченными правами
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false -M appuser

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY backend/requirements.txt .

# Обновляем pip и устанавливаем Python зависимости
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY backend/ .

# Создаем необходимые директории и устанавливаем права доступа
RUN mkdir -p uploads temp exports logs \
    && chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Устанавливаем переменные окружения для безопасности
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Открываем порт
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
