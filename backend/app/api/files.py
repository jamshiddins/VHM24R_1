from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..services.file_processor import EnhancedFileProcessor
from .. import crud
import hashlib
from datetime import datetime

router = APIRouter()
file_processor = EnhancedFileProcessor()

@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Загрузка файлов для обработки"""
    user_status = getattr(current_user, 'status', '')
    if user_status != "approved":
        raise HTTPException(status_code=403, detail="User not approved")
    
    # Создаём сессию обработки
    user_id = getattr(current_user, 'id', 0)
    session = crud.create_processing_session(db, user_id, len(files))
    
    upload_results = []
    total_size = 0
    
    for file in files:
        try:
            # Читаем содержимое файла
            content = await file.read()
            total_size += len(content)
            
            # Проверяем ограничения
            if len(content) > 100 * 1024 * 1024:  # 100MB
                raise ValueError(f"Файл {file.filename} слишком большой")
            
            # Вычисляем хеш содержимого
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Проверяем схожесть с существующими файлами
            similarity, similar_file_id = await detect_file_similarity(content_hash, db)
            
            # Проверяем имя файла
            if not file.filename:
                raise ValueError("Имя файла не указано")
            
            # Сохраняем в облачное хранилище
            storage_path = await file_processor.save_to_storage(file.filename, content)
            
            # Валидируем файл
            validation_result = file_processor.validate_file(content, file.filename)
            
            if not validation_result['valid']:
                upload_results.append({
                    "filename": file.filename,
                    "error": f"Validation failed: {', '.join(validation_result['errors'])}"
                })
                continue
            
            # Создаём запись в БД
            db_file = crud.create_uploaded_file(db, {
                'filename': f"{session.session_id}_{file.filename}",
                'original_name': file.filename,
                'content_hash': content_hash,
                'file_size': len(content),
                'file_type': validation_result['file_type'],
                'storage_path': storage_path,
                'similarity_percent': similarity,
                'similar_file_id': similar_file_id,
                'uploaded_by': user_id
            })
            
            upload_results.append({
                "file_id": db_file.id,
                "filename": file.filename,
                "size": len(content),
                "type": validation_result['file_type'],
                "similarity": similarity,
                "similar_file_id": similar_file_id,
                "hash": content_hash,
                "validation": validation_result
            })
            
        except Exception as e:
            upload_results.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    # Запускаем асинхронную обработку файлов
    background_tasks.add_task(
        process_uploaded_files_async, 
        str(session.session_id), 
        user_id
    )
    
    return {
        "session_id": str(session.session_id),
        "files": upload_results,
        "total_size": total_size,
        "processing_started": True
    }

async def detect_file_similarity(content_hash: str, db: Session):
    """Проверка схожести файлов"""
    existing_file = crud.get_file_by_hash(db, content_hash)
    if existing_file:
        return 100.0, existing_file.id
    return 0.0, None

async def process_uploaded_files_async(session_id: str, user_id: int):
    """Асинхронная обработка файлов"""
    # Заглушка для обработки файлов
    # В реальной реализации здесь будет полная логика обработки
    pass

@router.get("/")
async def get_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка загруженных файлов"""
    user_id = getattr(current_user, 'id', 0)
    files = crud.get_uploaded_files(db, user_id)
    return {"files": files}
