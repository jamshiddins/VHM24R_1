# 🚀 VHM24R Enterprise Deployment Guide

## 📋 Обзор

Данное руководство описывает развертывание полной enterprise-версии системы VHM24R с использованием:
- **Kong API Gateway** для управления API
- **ELK Stack** для централизованного логирования
- **Prometheus + Grafana** для мониторинга
- **Docker Compose** для оркестрации контейнеров

## 🏗️ Архитектура Enterprise-системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx LB      │────│  Kong Gateway   │────│   FastAPI       │
│   Port: 80/443  │    │   Port: 8000    │    │   Port: 8080    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   Vue.js App    │
                       │   Port: 3000    │
                       └─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  PostgreSQL     │    │     Redis       │    │ DigitalOcean    │
│  Port: 5432     │    │   Port: 6379    │    │    Spaces       │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Elasticsearch   │    │    Logstash     │    │     Kibana      │
│  Port: 9200     │    │   Port: 5044    │    │   Port: 5601    │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │     Grafana     │
│  Port: 9090     │    │   Port: 3001    │
└─────────────────┘    └─────────────────┘
```

## 🔧 Предварительные требования

### Системные требования
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Docker Desktop
- **CPU**: 8+ cores (рекомендуется)
- **RAM**: 16+ GB (минимум 8 GB)
- **Storage**: 100+ GB SSD
- **Network**: 1+ Gbps

### Программное обеспечение
```bash
# Docker и Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Git
sudo apt update && sudo apt install -y git

# Утилиты
sudo apt install -y curl wget htop
```

## 📁 Структура проекта

```
VHM24R_1/
├── backend/                    # FastAPI приложение
├── frontend/                   # Vue.js приложение
├── kong/                       # Kong API Gateway конфигурация
│   └── kong.yml
├── elk/                        # ELK Stack конфигурация
│   ├── elasticsearch/
│   │   └── elasticsearch.yml
│   ├── logstash/
│   │   └── logstash.conf
│   ├── kibana/
│   │   └── kibana.yml
│   └── filebeat/
│       └── filebeat.yml
├── monitoring/                 # Prometheus & Grafana
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── provisioning/
├── nginx/                      # Nginx конфигурация
│   ├── nginx.conf
│   └── ssl/
├── docs/                       # Документация
│   └── ARCHITECTURE.md
├── docker-compose.enterprise.yml
└── .env.enterprise
```

## 🚀 Пошаговое развертывание

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/jamshiddins/VHM24R_1.git
cd VHM24R_1
```

### Шаг 2: Настройка переменных окружения

```bash
# Создаем файл переменных окружения
cp .env.example .env.enterprise

# Редактируем переменные
nano .env.enterprise
```

**Содержимое .env.enterprise:**
```env
# Database
DATABASE_URL=postgresql://vhm24r_user:your_secure_password@postgres:5432/vhm24r
POSTGRES_DB=vhm24r
POSTGRES_USER=vhm24r_user
POSTGRES_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://:your_redis_password@redis:6379/0
REDIS_PASSWORD=your_redis_password

# JWT
JWT_SECRET_KEY=your_super_secret_jwt_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# DigitalOcean Spaces
DO_SPACES_KEY=your_do_spaces_key
DO_SPACES_SECRET=your_do_spaces_secret
DO_SPACES_ENDPOINT=https://fra1.digitaloceanspaces.com
DO_SPACES_REGION=fra1
DO_SPACES_BUCKET=vhm24r-files

# Application
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=production
LOG_LEVEL=INFO

# Monitoring
GRAFANA_PASSWORD=your_grafana_admin_password

# Kong
KONG_ADMIN_TOKEN=your_kong_admin_token
```

### Шаг 3: Создание дополнительных конфигураций

#### Filebeat конфигурация
```bash
mkdir -p elk/filebeat
```

<details>
<summary>elk/filebeat/filebeat.yml</summary>

```yaml
filebeat.inputs:
- type: container
  paths:
    - '/var/lib/docker/containers/*/*.log'
  processors:
    - add_docker_metadata:
        host: "unix:///var/run/docker.sock"

- type: log
  enabled: true
  paths:
    - /var/log/vhm24r/*.log
  fields:
    service: vhm24r-backend
  fields_under_root: true

output.logstash:
  hosts: ["logstash:5044"]

logging.level: info
logging.to_files: true
logging.files:
  path: /var/log/filebeat
  name: filebeat
  keepfiles: 7
  permissions: 0644
```
</details>

#### Prometheus конфигурация
```bash
mkdir -p monitoring/prometheus
```

<details>
<summary>monitoring/prometheus/prometheus.yml</summary>

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'vhm24r-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'kong'
    static_configs:
      - targets: ['kong:8001']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'elasticsearch'
    static_configs:
      - targets: ['elasticsearch:9200']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```
</details>

#### Nginx конфигурация
```bash
mkdir -p nginx/ssl
```

<details>
<summary>nginx/nginx.conf</summary>

```nginx
events {
    worker_connections 1024;
}

http {
    upstream kong_upstream {
        server kong:8000;
    }

    upstream kibana_upstream {
        server kibana:5601;
    }

    upstream grafana_upstream {
        server grafana:3000;
    }

    # Main application
    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://kong_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # Kibana dashboard
    server {
        listen 80;
        server_name kibana.localhost;

        location / {
            proxy_pass http://kibana_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }

    # Grafana dashboard
    server {
        listen 80;
        server_name grafana.localhost;

        location / {
            proxy_pass http://grafana_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
```
</details>

### Шаг 4: Запуск системы

```bash
# Создаем необходимые директории
mkdir -p backend/logs backend/uploads backend/exports
mkdir -p elk/logstash/templates

# Устанавливаем права доступа
sudo chown -R 1000:1000 backend/logs backend/uploads backend/exports
sudo chmod -R 755 backend/logs backend/uploads backend/exports

# Запускаем систему
docker-compose -f docker-compose.enterprise.yml --env-file .env.enterprise up -d
```

### Шаг 5: Проверка развертывания

```bash
# Проверяем статус контейнеров
docker-compose -f docker-compose.enterprise.yml ps

# Проверяем логи
docker-compose -f docker-compose.enterprise.yml logs -f backend
```

## 🔍 Проверка компонентов

### API Gateway (Kong)
```bash
# Проверка Kong
curl -i http://localhost:8001/status

# Проверка маршрутов
curl -i http://localhost:8000/health
```

### ELK Stack
```bash
# Elasticsearch
curl -X GET "localhost:9200/_cluster/health?pretty"

# Kibana (через браузер)
# http://localhost:5601
```

### Мониторинг
```bash
# Prometheus
# http://localhost:9090

# Grafana
# http://localhost:3001
# Логин: admin / Пароль: из .env.enterprise
```

### Приложение
```bash
# Backend API
curl -i http://localhost:8000/health

# Frontend
# http://localhost:3000
```

## 📊 Настройка мониторинга

### Kibana Dashboards

1. Откройте Kibana: http://localhost:5601
2. Перейдите в **Management** → **Index Patterns**
3. Создайте индекс-паттерны:
   - `vhm24r-logs-*`
   - `vhm24r-errors-*`
   - `vhm24r-performance-*`

### Grafana Dashboards

1. Откройте Grafana: http://localhost:3001
2. Добавьте Prometheus как источник данных: http://prometheus:9090
3. Импортируйте готовые дашборды для:
   - Kong API Gateway
   - PostgreSQL
   - Redis
   - Application metrics

## 🔧 Управление системой

### Основные команды

```bash
# Запуск системы
docker-compose -f docker-compose.enterprise.yml up -d

# Остановка системы
docker-compose -f docker-compose.enterprise.yml down

# Перезапуск отдельного сервиса
docker-compose -f docker-compose.enterprise.yml restart backend

# Просмотр логов
docker-compose -f docker-compose.enterprise.yml logs -f [service_name]

# Масштабирование сервиса
docker-compose -f docker-compose.enterprise.yml up -d --scale backend=3
```

### Обновление системы

```bash
# Получение обновлений
git pull origin main

# Пересборка образов
docker-compose -f docker-compose.enterprise.yml build --no-cache

# Обновление с минимальным downtime
docker-compose -f docker-compose.enterprise.yml up -d --force-recreate
```

## 🔒 Безопасность

### SSL/TLS настройка

```bash
# Генерация самоподписанного сертификата
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/nginx.key \
  -out nginx/ssl/nginx.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Firewall настройка

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Закрытие прямого доступа к сервисам
sudo ufw deny 5432/tcp   # PostgreSQL
sudo ufw deny 6379/tcp   # Redis
sudo ufw deny 9200/tcp   # Elasticsearch
```

## 📈 Производительность

### Оптимизация PostgreSQL

```sql
-- Настройки в postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Оптимизация Redis

```bash
# В redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## 🚨 Мониторинг и алерты

### Основные метрики для мониторинга

1. **Система**:
   - CPU utilization
   - Memory usage
   - Disk I/O
   - Network traffic

2. **Приложение**:
   - Response time
   - Request rate
   - Error rate
   - Active connections

3. **База данных**:
   - Connection count
   - Query performance
   - Lock waits
   - Replication lag

4. **Kong Gateway**:
   - Request latency
   - Upstream health
   - Rate limiting hits
   - Authentication failures

### Настройка алертов

Создайте правила алертов в Prometheus:

```yaml
# monitoring/prometheus/rules/alerts.yml
groups:
- name: vhm24r_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"

  - alert: DatabaseDown
    expr: up{job="postgres"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "PostgreSQL database is down"
```

## 🔄 Резервное копирование

### Автоматическое резервное копирование

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# PostgreSQL backup
docker exec vhm24r-postgres pg_dump -U vhm24r_user vhm24r > $BACKUP_DIR/postgres_$DATE.sql

# Redis backup
docker exec vhm24r-redis redis-cli BGSAVE
docker cp vhm24r-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Application files backup
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz backend/uploads/
tar -czf $BACKUP_DIR/exports_$DATE.tar.gz backend/exports/

# Cleanup old backups (keep 7 days)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Cron задача для резервного копирования

```bash
# Добавляем в crontab
crontab -e

# Ежедневное резервное копирование в 2:00
0 2 * * * /path/to/backup.sh
```

## 🆘 Устранение неполадок

### Общие проблемы

1. **Контейнер не запускается**:
   ```bash
   docker-compose -f docker-compose.enterprise.yml logs [service_name]
   ```

2. **Проблемы с памятью**:
   ```bash
   # Увеличиваем лимиты в docker-compose.yml
   mem_limit: 2g
   ```

3. **Проблемы с правами доступа**:
   ```bash
   sudo chown -R 1000:1000 backend/
   sudo chmod -R 755 backend/
   ```

4. **Elasticsearch не запускается**:
   ```bash
   # Увеличиваем vm.max_map_count
   sudo sysctl -w vm.max_map_count=262144
   echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
   ```

### Полезные команды диагностики

```bash
# Проверка использования ресурсов
docker stats

# Проверка сетевых подключений
docker network ls
docker network inspect vhm24r_vhm24r-network

# Проверка томов
docker volume ls
docker volume inspect vhm24r_postgres_data

# Очистка системы
docker system prune -a
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи всех сервисов
2. Убедитесь в корректности переменных окружения
3. Проверьте доступность внешних сервисов (Telegram API, DigitalOcean)
4. Обратитесь к документации компонентов
5. Создайте issue в репозитории проекта

---

**🎉 Поздравляем! Ваша enterprise-система VHM24R успешно развернута и готова к работе!**
