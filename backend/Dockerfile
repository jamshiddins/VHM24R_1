FROM python:3.13.1-slim-bookworm

# Обновляем пакеты и устанавливаем системные зависимости
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libmagic1 \
    unrar \
    curl \
    ca-certificates \
    && apt-get dist-upgrade -y \
    && apt-get autoremove -y \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Создаем пользователя без привилегий
RUN groupadd -r appuser && useradd -r -g appuser appuser

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
