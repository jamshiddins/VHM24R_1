import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
import pandas as pd
import asyncio
import json
from datetime import datetime, timedelta
import os
from pathlib import Path

# Sentry для error tracking
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# Инициализация Sentry
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "production"),
        release=os.getenv("APP_VERSION", "1.0.1"),
    )
    print("✅ Sentry initialized for error tracking")
else:
    print("⚠️ SENTRY_DSN not found, error tracking disabled")

from .database import get_db, engine, init_db
from .models import User, UploadedFile, Order, OrderChange, TelegramSession
from .schemas import *
from .auth import get_current_user, get_current_admin_user
from .services.unified_auth import unified_auth_service
from . import crud

# Импорты для логирования и обработки ошибок
from .utils.logger import get_logger, setup_logging
from .utils.exceptions import (
    VHMException, 
    AuthenticationError, 
    FileProcessingError, 
    DatabaseError
)
from .middleware.error_handler import add_error_handling_middleware

# Настройка логирования
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="VHM24R Order Management System",
    description="Система загрузки, сверки и анализа заказов VHM24R",
    version="1.0.1"
)

# Добавляем middleware для обработки ошибок
add_error_handling_middleware(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Задача очистки истекших сессий
async def cleanup_expired_sessions():
    """Периодическая очистка истекших сессий"""
    while True:
        await dynamic_auth_service.cleanup_expired_sessions()
        await asyncio.sleep(300)  # Каждые 5 минут

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("VHM24R application startup initiated", version="1.0.1")
    
    try:
        init_db()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise
    
    # Запускаем задачу очистки сессий
    try:
        asyncio.create_task(cleanup_expired_sessions())
        logger.info("Session cleanup task started")
    except Exception as e:
        logger.error("Failed to start session cleanup task", error=str(e))
    
    # Запускаем Telegram бота в фоне
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if telegram_token:
            from .telegram_bot import EnhancedTelegramBot
            bot = EnhancedTelegramBot(telegram_token)
            # Запускаем бота в отдельном потоке с исправленным event loop
            import threading
            bot_thread = threading.Thread(target=bot.start_bot, daemon=True)
            bot_thread.start()
            logger.info("Telegram Bot started successfully in background thread")
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not found, skipping bot initialization")
    except Exception as e:
        logger.error("Failed to start Telegram bot", error=str(e))
    
    logger.info("VHM24R application startup completed successfully")

security = HTTPBearer()

# Инициализация компонентов
from .telegram_auth import TelegramAuth
from .services.file_processor import EnhancedFileProcessor
from .services.export_service import ExportService
from .services.dynamic_auth import DynamicAuthService

telegram_auth = TelegramAuth()
file_processor = EnhancedFileProcessor()
export_service = ExportService()
dynamic_auth_service = DynamicAuthService()

# WebSocket connections
active_connections: List[WebSocket] = []

@app.websocket("/ws/session")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Обработка сообщений от клиента если нужно
    except:
        active_connections.remove(websocket)

async def broadcast_update(message: dict):
    """Отправка обновлений всем подключенным клиентам"""
    for connection in active_connections[:]:
        try:
            await connection.send_text(json.dumps(message))
        except:
            active_connections.remove(connection)

# Пути к файлам
project_root = Path(__file__).parent.parent.parent
frontend_path = project_root / "frontend"
templates_path = Path(__file__).parent.parent / "templates"

# Подключение статических файлов (только если frontend существует)
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# Подключение шаблонов
templates = Jinja2Templates(directory=str(templates_path))

# === ОСНОВНЫЕ ЭНДПОИНТЫ ===

@app.get("/")
async def root():
    """Главная страница - возвращает frontend"""
    frontend_file = frontend_path / "index.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file), media_type="text/html")
    return {"message": "VHM24R API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Проверка состояния системы"""
    services = {}
    overall_status = "healthy"
    
    # Проверка базы данных PostgreSQL
    try:
        # Простой запрос для проверки подключения
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        services["database"] = "connected"
    except Exception as e:
        services["database"] = f"error: {str(e)}"
        overall_status = "unhealthy"
    
    # Проверка Redis
    try:
        import redis
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            r = redis.from_url(redis_url)
            if r:
                r.ping()
                services["redis"] = "connected"
            else:
                services["redis"] = "connection failed"
        else:
            services["redis"] = "not configured"
    except ImportError:
        services["redis"] = "redis library not installed"
    except Exception as e:
        services["redis"] = f"error: {str(e)}"
        # Не делаем систему unhealthy из-за Redis
    
    # Проверка файлового хранилища
    try:
        # Проверяем наличие переменных DigitalOcean Spaces
        do_key = os.getenv("DO_SPACES_KEY")
        do_secret = os.getenv("DO_SPACES_SECRET")
        if do_key and do_secret:
            services["file_storage"] = "configured"
        else:
            services["file_storage"] = "not configured"
    except Exception as e:
        services["file_storage"] = f"error: {str(e)}"
    
    # Проверка Telegram бота
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if telegram_token:
            services["telegram_bot"] = "configured"
        else:
            services["telegram_bot"] = "not configured"
    except Exception as e:
        services["telegram_bot"] = f"error: {str(e)}"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": services
    }

# Подключаем роутеры API
from .api import auth, auth_v2, orders, analytics, files, export

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(auth_v2.router, tags=["Authentication v2.0"])  # Префикс уже в роутере
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(export.router, prefix="/api/v1/export", tags=["export"])

# === АУТЕНТИФИКАЦИЯ ===

@app.post("/api/v1/auth/telegram")
async def telegram_login(auth_data: TelegramAuthData, db: Session = Depends(get_db)):
    """Авторизация через Telegram"""
    try:
        # Используем unified_auth_service для аутентификации
        response = unified_auth_service.authenticate_telegram_user(auth_data, db)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/session/{session_token}")
async def session_auth_page(session_token: str):
    """Страница аутентификации по токену сессии (упрощенная)"""
    from fastapi.responses import HTMLResponse
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VHM24R - Вход в систему</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <div class="text-center mb-6">
            <h1 class="text-2xl font-bold text-gray-800">🚀 VHM24R</h1>
            <p class="text-gray-600">Автоматический вход в систему</p>
        </div>
        
        <div id="loading" class="text-center">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p class="text-gray-600">Выполняется вход...</p>
        </div>
        
        <div id="success" class="hidden text-center">
            <div class="text-green-500 text-6xl mb-4">✅</div>
            <h2 class="text-xl font-bold text-green-600 mb-2">Вход выполнен!</h2>
            <p class="text-gray-600 mb-4">Перенаправление в систему...</p>
        </div>
        
        <div id="error" class="hidden text-center">
            <div class="text-red-500 text-6xl mb-4">❌</div>
            <h2 class="text-xl font-bold text-red-600 mb-2">Ошибка входа</h2>
            <p class="text-gray-600 mb-4">Ссылка недействительна или истек срок действия</p>
            <a href="https://t.me/VHM24R_bot" class="bg-blue-500 text-white px-4 py-2 rounded inline-block">Получить новую ссылку</a>
        </div>
    </div>

    <script>
        async function authenticateWithSession() {{
            const sessionToken = '{session_token}';
            
            try {{
                const response = await fetch('/api/v1/auth/session', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        session_token: sessionToken
                    }})
                }});
                
                if (response.ok) {{
                    const data = await response.json();
                    
                    // Сохраняем токен с правильным ключом для frontend
                    localStorage.setItem('auth_token', data.access_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    
                    // Показываем успех
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('success').classList.remove('hidden');
                    
                    // Определяем куда перенаправить пользователя с токеном
                    const redirectUrl = `/webapp?token=${{data.access_token}}`;
                    
                    // Перенаправляем через 1.5 секунды
                    setTimeout(() => {{
                        window.location.href = redirectUrl;
                    }}, 1500);
                }} else {{
                    showError();
                }}
            }} catch (error) {{
                console.error('Auth error:', error);
                showError();
            }}
        }}
        
        function showError() {{
            document.getElementById('loading').classList.add('hidden');
            document.getElementById('error').classList.remove('hidden');
        }}
        
        // Автоматически запускаем аутентификацию при загрузке страницы
        window.onload = authenticateWithSession;
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/auth/dynamic/{session_token}")
async def dynamic_auth_page(session_token: str):
    """Страница динамической аутентификации"""
    from fastapi.responses import HTMLResponse
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VHM24R - Безопасный вход</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <div class="text-center mb-6">
            <h1 class="text-2xl font-bold text-gray-800">🔐 VHM24R</h1>
            <p class="text-gray-600">Безопасный вход в систему</p>
        </div>
        
        <form id="authForm">
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Пароль из Telegram
                </label>
                <input 
                    type="password" 
                    id="password" 
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Введите пароль"
                    required
                >
            </div>
            
            <button 
                type="submit"
                class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
                Войти в систему
            </button>
        </form>
        
        <div class="mt-4 text-center">
            <p class="text-xs text-gray-500">
                Ссылка действует 30 минут и используется один раз
            </p>
        </div>
    </div>

    <script>
        document.getElementById('authForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const sessionToken = '{session_token}';
            
            try {{
                const response = await fetch('/api/v1/auth/dynamic', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        session_token: sessionToken,
                        password: password
                    }})
                }});
                
                if (response.ok) {{
                    const data = await response.json();
                    localStorage.setItem('token', data.access_token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    window.location.href = '/';
                }} else {{
                    alert('Неверный пароль или истек срок действия ссылки');
                }}
            }} catch (error) {{
                alert('Ошибка подключения к серверу');
            }}
        }});
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html_content)

@app.post("/api/v1/auth/dynamic")
async def authenticate_dynamic(auth_data: dict, db: Session = Depends(get_db)):
    """API для динамической аутентификации"""
    try:
        session_token = auth_data.get('session_token')
        password = auth_data.get('password')
        
        if not session_token or not password:
            raise HTTPException(status_code=400, detail="Missing credentials")
        
        # Проверяем сессию
        user_id = await dynamic_auth_service.validate_session(session_token, password)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid credentials or expired session")
        
        # Получаем пользователя
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Генерируем JWT токен
        access_token = telegram_auth.create_access_token(getattr(user, 'id', 0))
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "status": "approved" if str(user.status) == "approved" else "pending",
                "role": "admin" if str(user.role) == "admin" else "user"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/auth/session")
async def authenticate_session(auth_data: dict, db: Session = Depends(get_db)):
    """API для аутентификации по токену сессии"""
    try:
        session_token = auth_data.get('session_token')
        
        if not session_token:
            raise HTTPException(status_code=400, detail="Missing session token")
        
        # Импортируем SimpleDynamicAuth
        from .services.simple_dynamic_auth import SimpleDynamicAuth
        simple_auth = SimpleDynamicAuth()
        
        # Проверяем токен сессии
        user_id = await simple_auth.validate_session_token(session_token, db)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired session token")
        
        # Получаем пользователя
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Генерируем JWT токен
        access_token = telegram_auth.create_access_token(getattr(user, 'id', 0))
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "status": "approved" if str(user.status) == "approved" else "pending",
                "role": "admin" if str(user.role) == "admin" else "user"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/auth/admin")
async def authenticate_admin(auth_data: dict, db: Session = Depends(get_db)):
    """API для административной аутентификации"""
    try:
        admin_token = auth_data.get('admin_token')
        
        if not admin_token:
            raise HTTPException(status_code=400, detail="Missing admin token")
        
        # Импортируем SimpleDynamicAuth
        from .services.simple_dynamic_auth import SimpleDynamicAuth
        simple_auth = SimpleDynamicAuth()
        
        # Проверяем админский токен
        user_id = await simple_auth.validate_admin_session(admin_token, db)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired admin token")
        
        # Получаем пользователя
        user = crud.get_user_by_telegram_id(db, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Дополнительная проверка прав администратора
        if str(user.role) != "admin":
            raise HTTPException(status_code=403, detail="Access denied: admin rights required")
        
        # Генерируем JWT токен
        access_token = telegram_auth.create_access_token(getattr(user, 'id', 0))
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "status": "approved",
                "role": "admin"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "status": "approved" if str(current_user.status) == "approved" else "pending",
        "role": "admin" if str(current_user.role) == "admin" else "user"
    }

# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (только для админов) ===

@app.get("/api/v1/users/pending")
async def get_pending_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Получение списка пользователей, ожидающих одобрения"""
    return crud.get_pending_users(db)

@app.post("/api/v1/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Одобрение пользователя"""
    user = crud.approve_user(db, user_id, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User approved successfully"}

# === ЗАГРУЗКА ФАЙЛОВ ===
# Удалено - используется роутер files.router

async def process_uploaded_files(session_id: str, db: Session):
    """Асинхронная обработка загруженных файлов"""
    try:
        session = crud.get_processing_session(db, session_id)
        if not session:
            return
        
        # Обновляем статус
        crud.update_processing_session(db, session_id, "processing")
        
        files = crud.get_session_files(db, getattr(session, 'id', 0))
        total_rows = 0
        processed_rows = 0
        
        for file_record in files:
            try:
                # Получаем путь к файлу
                file_path = getattr(file_record, 'storage_path', '')
                if not file_path or not os.path.exists(file_path):
                    print(f"Файл не найден: {file_path}")
                    continue
                
                # Обрабатываем файл
                user_id = getattr(session, 'created_by', 0)
                file_id = getattr(file_record, 'id', 0)
                
                # Создаем временный заказ для обработки файла
                temp_order_data = {
                    "order_number": f"TEMP_{session_id}_{file_id}",
                    "machine_code": "PROCESSING",
                    "order_price": 0,
                    "payment_status": "processing",
                    "match_status": "processing"
                }
                temp_order = crud.create_order(db, temp_order_data, user_id, file_id)
                temp_order_id = getattr(temp_order, 'id', 0)
                
                # Обрабатываем файл через file_processor
                result = await file_processor.process_file(file_path, temp_order_id, user_id)
                
                total_rows += result.get('total_rows', 0)
                processed_rows += result.get('processed_rows', 0)
                
                # Удаляем временный заказ
                db.delete(temp_order)
                db.commit()
                
                # Отправляем обновление прогресса
                await broadcast_update({
                    "type": "progress",
                    "session_id": session_id,
                    "processed_rows": processed_rows,
                    "total_rows": total_rows
                })
                
                # Обновляем статистику файла
                crud.update_file_stats(db, file_id, result.get('total_rows', 0), 0, 0)
                
            except Exception as e:
                print(f"Error processing file {file_record.filename}: {e}")
        
        # Завершаем сессию
        crud.complete_processing_session(db, session_id, total_rows, processed_rows)
        
        await broadcast_update({
            "type": "completed",
            "session_id": session_id,
            "total_rows": total_rows,
            "processed_rows": processed_rows
        })
        
    except Exception as e:
        crud.fail_processing_session(db, session_id, str(e))
        await broadcast_update({
            "type": "error",
            "session_id": session_id,
            "error": str(e)
        })

# === РАБОТА С ЗАКАЗАМИ ===

@app.get("/api/v1/orders")
async def get_orders(
    page: int = 1,
    page_size: int = 50,
    order_number: Optional[str] = None,
    machine_code: Optional[str] = None,
    payment_type: Optional[str] = None,
    match_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    change_type: Optional[str] = None,  # new, updated, filled, changed
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка заказов с фильтрами"""
    # Получаем заказы с фильтрами
    try:
        # Создаем фильтры
        filters = OrderFilters(
            order_number=order_number,
            machine_code=machine_code,
            payment_type=payment_type,
            match_status=match_status,
            date_from=date_from,
            date_to=date_to,
            change_type=change_type
        )
        
        orders, total = crud.get_orders_with_filters(db, filters, page, page_size)
    except Exception as e:
        # Fallback к простому запросу
        orders = []
        total = 0
    
    return {
        "orders": orders,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }

@app.get("/api/v1/orders/{order_id}/changes")
async def get_order_changes(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение истории изменений заказа"""
    order = crud.order_crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    changes = crud.order_change_crud.get_changes_by_order(db, order_id)
    return {
        "order": order,
        "changes": changes
    }

@app.get("/api/v1/orders/by-number/{order_number}")
async def get_order_versions(
    order_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех версий заказа по номеру"""
    order = crud.get_order_by_number(db, order_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Получаем все изменения для этого заказа
    changes = crud.order_change_crud.get_changes_by_order(db, getattr(order, 'id', 0))
    return {
        "order": order,
        "changes": changes
    }

# === АНАЛИТИКА ===

@app.get("/api/v1/analytics")
async def get_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "day",  # day, week, month
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение аналитических данных"""
    # Используем существующую функцию get_analytics_data
    analytics = crud.get_analytics_data(db, date_from, date_to, group_by)
    return analytics

@app.get("/api/v1/files")
async def get_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка загруженных файлов"""
    user_id = current_user.id
    files = crud.get_uploaded_files(db, user_id)
    return {"files": files}

# === ЭКСПОРТ ДАННЫХ ===

@app.post("/api/v1/export")
async def export_data(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Экспорт данных в различных форматах"""
    try:
        # Заглушка для экспорта данных
        # В реальном приложении здесь будет получение данных и их экспорт
        
        # Создаем имя файла
        filename = export_request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = f"exports/{filename}.{export_request.export_format}"
        
        # Заглушка - возвращаем базовую информацию
        return {
            "export_id": 1,
            "download_url": f"/api/v1/exports/1/download",
            "file_path": file_path,
            "created_at": datetime.now().isoformat(),
            "message": "Export functionality is not fully implemented yet"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/api/v1/exports/{export_id}/download")
async def download_export(
    export_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Скачивание экспортированного файла"""
    # Заглушка для скачивания файла
    raise HTTPException(status_code=501, detail="Download functionality is not implemented yet")

# === TELEGRAM WEBAPP ===

@app.get("/webapp")
async def telegram_webapp():
    """Telegram WebApp интерфейс"""
    webapp_file = Path(__file__).parent.parent / "templates" / "webapp.html"
    if webapp_file.exists():
        return FileResponse(str(webapp_file), media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="WebApp template not found")

# === TELEGRAM WEBHOOK ===

@app.post("/webhook/telegram")
async def telegram_webhook(update: dict, db: Session = Depends(get_db)):
    """Webhook для получения обновлений от Telegram"""
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            raise HTTPException(status_code=500, detail="Telegram bot token not configured")
        
        from .telegram_bot import EnhancedTelegramBot
        bot = EnhancedTelegramBot(telegram_token)
        # Примечание: process_update метод должен быть добавлен в EnhancedTelegramBot
        # await bot.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
