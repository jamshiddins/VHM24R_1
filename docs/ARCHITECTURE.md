# VHM24R - Архитектура системы

## 🏗️ Общая архитектура

```mermaid
graph TB
    subgraph "External Services"
        TG[Telegram Bot API]
        DO[DigitalOcean Spaces]
        RAILWAY[Railway Platform]
    end

    subgraph "Load Balancer & Gateway"
        NGINX[Nginx Load Balancer]
        KONG[Kong API Gateway]
    end

    subgraph "Frontend Layer"
        WEB[Vue.js Frontend]
        WEBAPP[Telegram WebApp]
    end

    subgraph "Backend Services"
        API[FastAPI Backend]
        AUTH[Authentication Service]
        FILE[File Processing Service]
        EXPORT[Export Service]
        TELEGRAM[Telegram Bot Service]
    end

    subgraph "Data Layer"
        POSTGRES[(PostgreSQL Database)]
        REDIS[(Redis Cache)]
    end

    subgraph "Monitoring & Logging"
        ELK[ELK Stack]
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana]
        FILEBEAT[Filebeat]
    end

    subgraph "Message Queue"
        WEBSOCKET[WebSocket Connections]
    end

    %% External connections
    TG --> TELEGRAM
    DO --> FILE
    RAILWAY --> API

    %% Load balancing
    NGINX --> KONG
    KONG --> API
    KONG --> WEB

    %% Frontend connections
    WEB --> API
    WEBAPP --> API

    %% Backend connections
    API --> AUTH
    API --> FILE
    API --> EXPORT
    API --> TELEGRAM
    API --> WEBSOCKET

    %% Data connections
    API --> POSTGRES
    API --> REDIS
    AUTH --> POSTGRES
    FILE --> POSTGRES
    EXPORT --> POSTGRES
    TELEGRAM --> POSTGRES

    %% Monitoring connections
    API --> ELK
    KONG --> ELK
    FILEBEAT --> ELK
    PROMETHEUS --> API
    GRAFANA --> PROMETHEUS

    %% Styling
    classDef external fill:#ff9999
    classDef gateway fill:#99ccff
    classDef frontend fill:#99ff99
    classDef backend fill:#ffcc99
    classDef data fill:#cc99ff
    classDef monitoring fill:#ffff99

    class TG,DO,RAILWAY external
    class NGINX,KONG gateway
    class WEB,WEBAPP frontend
    class API,AUTH,FILE,EXPORT,TELEGRAM backend
    class POSTGRES,REDIS data
    class ELK,PROMETHEUS,GRAFANA,FILEBEAT monitoring
```

## 🔄 Поток данных

```mermaid
sequenceDiagram
    participant U as User
    participant N as Nginx
    participant K as Kong Gateway
    participant A as FastAPI
    participant P as PostgreSQL
    participant R as Redis
    participant F as File Processor
    participant T as Telegram Bot
    participant E as ELK Stack

    U->>N: HTTP Request
    N->>K: Forward Request
    K->>K: Rate Limiting & Auth
    K->>A: Authenticated Request
    
    A->>R: Check Cache
    alt Cache Hit
        R->>A: Return Cached Data
    else Cache Miss
        A->>P: Query Database
        P->>A: Return Data
        A->>R: Update Cache
    end
    
    A->>F: Process File (if needed)
    F->>P: Store Results
    F->>T: Send Notification
    T->>U: Telegram Message
    
    A->>E: Log Request
    A->>K: Response
    K->>N: Forward Response
    N->>U: HTTP Response
```

## 🏛️ Микросервисная архитектура

```mermaid
graph LR
    subgraph "API Gateway Layer"
        KONG[Kong Gateway<br/>- Rate Limiting<br/>- Authentication<br/>- Load Balancing<br/>- Monitoring]
    end

    subgraph "Application Services"
        AUTH_SVC[Authentication Service<br/>- JWT Management<br/>- Telegram Auth<br/>- Dynamic Auth<br/>- Session Management]
        
        FILE_SVC[File Processing Service<br/>- 12 Format Support<br/>- Async Processing<br/>- Validation<br/>- Storage Management]
        
        ORDER_SVC[Order Management Service<br/>- CRUD Operations<br/>- Change Tracking<br/>- Analytics<br/>- Reporting]
        
        EXPORT_SVC[Export Service<br/>- 5 Format Export<br/>- Async Generation<br/>- Download Management]
        
        TELEGRAM_SVC[Telegram Bot Service<br/>- Bot Management<br/>- Webhook Handling<br/>- Notifications<br/>- Admin Interface]
    end

    subgraph "Data Services"
        POSTGRES_SVC[(PostgreSQL<br/>- Primary Database<br/>- ACID Compliance<br/>- Relationships)]
        
        REDIS_SVC[(Redis<br/>- Session Storage<br/>- Caching<br/>- Rate Limiting)]
        
        SPACES_SVC[DigitalOcean Spaces<br/>- File Storage<br/>- CDN<br/>- Backup]
    end

    subgraph "Monitoring Services"
        LOG_SVC[Logging Service<br/>- ELK Stack<br/>- Log Aggregation<br/>- Search & Analysis]
        
        METRICS_SVC[Metrics Service<br/>- Prometheus<br/>- Grafana<br/>- Alerting]
    end

    KONG --> AUTH_SVC
    KONG --> FILE_SVC
    KONG --> ORDER_SVC
    KONG --> EXPORT_SVC
    KONG --> TELEGRAM_SVC

    AUTH_SVC --> POSTGRES_SVC
    AUTH_SVC --> REDIS_SVC
    FILE_SVC --> POSTGRES_SVC
    FILE_SVC --> SPACES_SVC
    ORDER_SVC --> POSTGRES_SVC
    EXPORT_SVC --> POSTGRES_SVC
    TELEGRAM_SVC --> POSTGRES_SVC

    AUTH_SVC --> LOG_SVC
    FILE_SVC --> LOG_SVC
    ORDER_SVC --> LOG_SVC
    EXPORT_SVC --> LOG_SVC
    TELEGRAM_SVC --> LOG_SVC

    AUTH_SVC --> METRICS_SVC
    FILE_SVC --> METRICS_SVC
    ORDER_SVC --> METRICS_SVC
    EXPORT_SVC --> METRICS_SVC
    TELEGRAM_SVC --> METRICS_SVC
```

## 🔐 Безопасность

```mermaid
graph TD
    subgraph "Security Layers"
        subgraph "Network Security"
            FIREWALL[Firewall Rules]
            SSL[SSL/TLS Encryption]
            VPN[VPN Access]
        end

        subgraph "API Security"
            RATE_LIMIT[Rate Limiting]
            CORS[CORS Policy]
            JWT_AUTH[JWT Authentication]
            API_KEY[API Key Management]
        end

        subgraph "Application Security"
            INPUT_VAL[Input Validation]
            SQL_INJ[SQL Injection Prevention]
            XSS_PROT[XSS Protection]
            CSRF_PROT[CSRF Protection]
        end

        subgraph "Data Security"
            ENCRYPTION[Data Encryption]
            BACKUP[Secure Backups]
            ACCESS_CTRL[Access Control]
            AUDIT_LOG[Audit Logging]
        end
    end

    FIREWALL --> SSL
    SSL --> RATE_LIMIT
    RATE_LIMIT --> JWT_AUTH
    JWT_AUTH --> INPUT_VAL
    INPUT_VAL --> ENCRYPTION
    ENCRYPTION --> AUDIT_LOG
```

## 📊 Мониторинг и логирование

```mermaid
graph TB
    subgraph "Application Logs"
        APP_LOGS[Application Logs<br/>- FastAPI<br/>- Telegram Bot<br/>- File Processor]
        ACCESS_LOGS[Access Logs<br/>- Kong Gateway<br/>- Nginx<br/>- API Requests]
        ERROR_LOGS[Error Logs<br/>- Exceptions<br/>- Stack Traces<br/>- Debug Info]
    end

    subgraph "Log Collection"
        FILEBEAT[Filebeat<br/>- Log Shipping<br/>- Multi-line Support<br/>- Filtering]
    end

    subgraph "Log Processing"
        LOGSTASH[Logstash<br/>- Parsing<br/>- Enrichment<br/>- Transformation]
    end

    subgraph "Storage & Search"
        ELASTICSEARCH[Elasticsearch<br/>- Indexing<br/>- Search<br/>- Aggregation]
    end

    subgraph "Visualization"
        KIBANA[Kibana<br/>- Dashboards<br/>- Alerts<br/>- Reports]
    end

    subgraph "Metrics"
        PROMETHEUS[Prometheus<br/>- Metrics Collection<br/>- Time Series DB<br/>- Alerting]
        GRAFANA[Grafana<br/>- Visualization<br/>- Dashboards<br/>- Notifications]
    end

    APP_LOGS --> FILEBEAT
    ACCESS_LOGS --> FILEBEAT
    ERROR_LOGS --> FILEBEAT
    
    FILEBEAT --> LOGSTASH
    LOGSTASH --> ELASTICSEARCH
    ELASTICSEARCH --> KIBANA
    
    APP_LOGS --> PROMETHEUS
    PROMETHEUS --> GRAFANA
```

## 🚀 Развертывание

```mermaid
graph LR
    subgraph "Development"
        DEV_CODE[Source Code]
        DEV_TEST[Unit Tests]
        DEV_BUILD[Local Build]
    end

    subgraph "CI/CD Pipeline"
        GIT[Git Repository]
        CI[GitHub Actions]
        BUILD[Docker Build]
        TEST[Integration Tests]
        DEPLOY[Auto Deploy]
    end

    subgraph "Production Environment"
        RAILWAY[Railway Platform]
        CONTAINERS[Docker Containers]
        MONITORING[Monitoring Stack]
        BACKUP[Backup System]
    end

    DEV_CODE --> GIT
    DEV_TEST --> GIT
    DEV_BUILD --> GIT
    
    GIT --> CI
    CI --> BUILD
    BUILD --> TEST
    TEST --> DEPLOY
    
    DEPLOY --> RAILWAY
    RAILWAY --> CONTAINERS
    CONTAINERS --> MONITORING
    MONITORING --> BACKUP
```

## 📈 Масштабирование

```mermaid
graph TB
    subgraph "Horizontal Scaling"
        LB[Load Balancer]
        API1[API Instance 1]
        API2[API Instance 2]
        API3[API Instance N]
        
        LB --> API1
        LB --> API2
        LB --> API3
    end

    subgraph "Database Scaling"
        MASTER[(Master DB)]
        REPLICA1[(Read Replica 1)]
        REPLICA2[(Read Replica 2)]
        
        MASTER --> REPLICA1
        MASTER --> REPLICA2
    end

    subgraph "Cache Layer"
        REDIS_CLUSTER[Redis Cluster]
        REDIS1[(Redis Node 1)]
        REDIS2[(Redis Node 2)]
        REDIS3[(Redis Node 3)]
        
        REDIS_CLUSTER --> REDIS1
        REDIS_CLUSTER --> REDIS2
        REDIS_CLUSTER --> REDIS3
    end

    API1 --> MASTER
    API2 --> REPLICA1
    API3 --> REPLICA2
    
    API1 --> REDIS_CLUSTER
    API2 --> REDIS_CLUSTER
    API3 --> REDIS_CLUSTER
```

## 🔧 Технологический стек

### Backend
- **FastAPI** - Современный веб-фреймворк для Python
- **SQLAlchemy** - ORM для работы с базой данных
- **PostgreSQL** - Реляционная база данных
- **Redis** - Кэширование и сессии
- **Celery** - Асинхронные задачи (планируется)

### Frontend
- **Vue.js 3** - Прогрессивный JavaScript фреймворк
- **Vite** - Быстрый сборщик модулей
- **Tailwind CSS** - Utility-first CSS фреймворк

### Infrastructure
- **Kong** - API Gateway
- **ELK Stack** - Логирование и мониторинг
- **Prometheus + Grafana** - Метрики и визуализация
- **Docker** - Контейнеризация
- **Railway** - Облачная платформа

### External Services
- **Telegram Bot API** - Интеграция с Telegram
- **DigitalOcean Spaces** - Объектное хранилище

## 📋 Требования к системе

### Минимальные требования
- **CPU**: 2 vCPU
- **RAM**: 4 GB
- **Storage**: 20 GB SSD
- **Network**: 100 Mbps

### Рекомендуемые требования
- **CPU**: 4 vCPU
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **Network**: 1 Gbps

### Production требования
- **CPU**: 8 vCPU
- **RAM**: 16 GB
- **Storage**: 100 GB SSD
- **Network**: 10 Gbps
- **Backup**: Ежедневное резервное копирование
- **Monitoring**: 24/7 мониторинг
