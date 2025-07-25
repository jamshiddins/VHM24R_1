import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
import pandas as pd
import asyncio
import json
from datetime import datetime, timedelta
import os
from pathlib import Path

from .database import get_db, engine, init_db
from .models import User, UploadedFile, Order, OrderChange, ProcessingSession
from .schemas import *
from .auth import get_current_user
from .services.file_processor import EnhancedFileProcessor
from .services.export_service import ExportService
from . import crud

app = FastAPI(
    title="VHM24R Order Management System",
    description="Система загрузки, сверки и анализа заказов VHM24R",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    init_db()
    
    # Запускаем Telegram бота в фоне
    try:
        from .telegram_bot import EnhancedTelegramBot
        bot = EnhancedTelegramBot(os.getenv("TELEGRAM_BOT_TOKEN"))
        asyncio.create_task(bot.start_bot())
    except Exception as e:
        print(f"Failed to start Telegram bot: {e}")

security = HTTPBearer()

# Инициализация компонентов
from .auth import TelegramAuth, auth_service
telegram_auth = TelegramAuth()
file_processor = EnhancedFileProcessor()
export_service = ExportService()

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

# Подключение статических файлов
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# === ОСНОВНЫЕ ЭНДПОИНТЫ ===

@app.get("/")
async def root():
    """Главная страница - возвращает frontend"""
    frontend_file = frontend_path / "index.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file))
    return {"message": "VHM24R API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "database": "connected",
            "file_storage": "available",
            "telegram_bot": "running"
        }
    }

# === АУТЕНТИФИКАЦИЯ ===

@app.post("/api/v1/auth/telegram")
async def telegram_login(auth_data: TelegramAuthData, db: Session = Depends(get_db)):
    """Авторизация через Telegram"""
    try:
        # Используем auth_service для аутентификации
        response = auth_service.authenticate_telegram_user(auth_data, db)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "status": current_user.status,
        "role": current_user.role
    }

# === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (только для админов) ===

@app.get("/api/v1/users/pending")
async def get_pending_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка пользователей, ожидающих одобрения"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    return crud.get_pending_users(db)

@app.post("/api/v1/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Одобрение пользователя"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = crud.approve_user(db, user_id, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User approved successfully"}

# === ЗАГРУЗКА ФАЙЛОВ ===

def calculate_content_hash(content: bytes) -> str:
    """Расчёт хеша содержимого файла"""
    return hashlib.sha256(content).hexdigest()

def detect_file_similarity(content_hash: str, db: Session) -> tuple:
    """Проверка схожести файла с уже загруженными"""
    # Упрощённая версия - точное совпадение хеша
    existing_file = crud.get_file_by_hash(db, content_hash)
    if existing_file:
        return 100.0, existing_file.id
    return 0.0, None

@app.post("/api/v1/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Загрузка файлов для обработки"""
    if current_user.status != "approved":
        raise HTTPException(status_code=403, detail="User not approved")
    
    # Создаём сессию обработки
    session = crud.create_processing_session(db, current_user.id, len(files))
    
    upload_results = []
    
    for file in files:
        try:
            # Читаем содержимое
            content = await file.read()
            content_hash = calculate_content_hash(content)
            
            # Проверяем схожесть
            similarity, similar_file_id = detect_file_similarity(content_hash, db)
            
            # Сохраняем файл в облаке (DigitalOcean Spaces)
            storage_path = await file_processor.save_to_storage(file.filename, content)
            
            # Создаём запись в БД
            db_file = crud.create_uploaded_file(db, UploadedFileCreate(
                filename=f"{session.session_id}_{file.filename}",
                original_name=file.filename,
                content_hash=content_hash,
                file_size=len(content),
                file_type=file.content_type or "application/octet-stream",
                storage_path=storage_path,
                similarity_percent=similarity,
                similar_file_id=similar_file_id,
                uploaded_by=current_user.id
            ))
            
            upload_results.append({
                "file_id": db_file.id,
                "filename": file.filename,
                "size": len(content),
                "similarity": similarity,
                "similar_file_id": similar_file_id,
                "hash": content_hash
            })
            
        except Exception as e:
            upload_results.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    # Запускаем асинхронную обработку
    asyncio.create_task(process_uploaded_files(session.session_id, db))
    
    return {
        "session_id": str(session.session_id),
        "files": upload_results
    }

async def process_uploaded_files(session_id: str, db: Session):
    """Асинхронная обработка загруженных файлов"""
    try:
        session = crud.get_processing_session(db, session_id)
        if not session:
            return
        
        # Обновляем статус
        crud.update_processing_session(db, session_id, "processing")
        
        files = crud.get_session_files(db, session.id)
        total_rows = 0
        processed_rows = 0
        
        for file_record in files:
            try:
                # Загружаем файл из хранилища
                content = await file_processor.load_from_storage(file_record.storage_path)
                
                # Парсим файл
                df = await file_processor.process_file(content, file_record.original_name)
                total_rows += len(df)
                
                # Обрабатываем строки
                new_orders = 0
                updated_orders = 0
                
                for _, row in df.iterrows():
                    order_data = file_processor.normalize_row(row)
                    
                    # Проверяем существование заказа
                    existing_order = crud.get_order_by_number(db, order_data["order_number"])
                    
                    if existing_order:
                        # Обновляем существующий заказ
                        updated_order = crud.update_order(db, existing_order.id, order_data, file_record.id)
                        updated_orders += 1
                    else:
                        # Создаём новый заказ
                        new_order = crud.create_order(db, order_data, current_user.id, file_record.id)
                        new_orders += 1
                    
                    processed_rows += 1
                    
                    # Отправляем обновление прогресса
                    await broadcast_update({
                        "type": "progress",
                        "session_id": session_id,
                        "processed_rows": processed_rows,
                        "total_rows": total_rows
                    })
                
                # Обновляем статистику файла
                crud.update_file_stats(db, file_record.id, len(df), new_orders, updated_orders)
                
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
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    changes = crud.get_order_changes(db, order_id)
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
    versions = crud.get_order_versions(db, order_number)
    if not versions:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"versions": versions}

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
    analytics = crud.get_analytics_data(db, date_from, date_to, group_by)
    
    return analytics

@app.get("/api/v1/files")
async def get_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка загруженных файлов"""
    files = crud.get_uploaded_files(db, current_user.id)
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
        # Получаем данные для экспорта
        if export_request.data_type == "orders":
            data = crud.get_orders_for_export(db, export_request.filters)
        elif export_request.data_type == "analytics":
            data = crud.get_analytics_for_export(db, export_request.filters)
        else:
            raise HTTPException(status_code=400, detail="Invalid data type")
        
        # Экспортируем данные
        file_path = await export_service.export_data(
            data=data,
            format=export_request.format,
            filename=export_request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Создаем запись об экспорте
        export_record = crud.create_export_record(db, ExportRecordCreate(
            user_id=current_user.id,
            data_type=export_request.data_type,
            format=export_request.format,
            file_path=file_path,
            filters=export_request.filters
        ))
        
        return {
            "export_id": export_record.id,
            "download_url": f"/api/v1/exports/{export_record.id}/download",
            "file_path": file_path,
            "created_at": export_record.created_at
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
    export_record = crud.get_export_record(db, export_id)
    if not export_record or export_record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    
    return await export_service.get_download_response(export_record.file_path)

# === TELEGRAM WEBHOOK ===

@app.post("/webhook/telegram")
async def telegram_webhook(update: dict, db: Session = Depends(get_db)):
    """Webhook для получения обновлений от Telegram"""
    try:
        from .telegram_bot import EnhancedTelegramBot
        bot = EnhancedTelegramBot(os.getenv("TELEGRAM_BOT_TOKEN"))
        await bot.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
