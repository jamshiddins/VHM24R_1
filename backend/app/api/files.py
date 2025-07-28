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
            
            # Сохраняем файл локально
            import os
            uploads_dir = os.path.join(os.getcwd(), "backend", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}_{file.filename}"
            storage_path = os.path.join(uploads_dir, safe_filename)
            
            with open(storage_path, "wb") as f:
                f.write(content)
            
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
                'file_url': storage_path,
                'similarity_percent': similarity,
                'duplicate_of_id': similar_file_id,
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
    try:
        from ..database import SessionLocal
        db = SessionLocal()
        
        try:
            # Получаем сессию обработки
            session = crud.get_processing_session(db, session_id)
            if not session:
                print(f"Session {session_id} not found")
                return
            
            # Обновляем статус на "processing"
            crud.update_processing_session(db, session_id, "processing")
            
            # Получаем файлы для обработки
            files = crud.get_session_files(db, getattr(session, 'id', 0))
            
            total_rows = 0
            processed_rows = 0
            
            for file_record in files:
                try:
                    # Получаем путь к файлу
                    file_path = getattr(file_record, 'file_url', '')
                    if not file_path:
                        print(f"No file URL for file {file_record.id}")
                        continue
                    
                    # Создаем полный путь к файлу
                    import os
                    full_path = os.path.join(os.getcwd(), file_path)
                    
                    if not os.path.exists(full_path):
                        print(f"File not found: {full_path}")
                        continue
                    
                    # Получаем ID файла
                    file_id = getattr(file_record, 'id', 0)
                    
                    # Создаем временный заказ для обработки
                    temp_order_data = {
                        "order_number": f"TEMP_{session_id}_{file_id}",
                        "machine_code": "PROCESSING",
                        "order_price": 0,
                        "payment_status": "processing",
                        "created_by": user_id,
                        "source_file_id": file_id
                    }
                    
                    temp_order = crud.create_order(db, temp_order_data)
                    temp_order_id = getattr(temp_order, 'id', 0)
                    
                    # Обрабатываем файл
                    result = await file_processor.process_file(full_path, temp_order_id, user_id)
                    
                    total_rows += result.get('total_rows', 0)
                    processed_rows += result.get('processed_rows', 0)
                    
                    # Удаляем временный заказ
                    db.delete(temp_order)
                    db.commit()
                    
                    # Обновляем статистику файла
                    crud.update_file_stats(db, file_id, result.get('total_rows', 0), 0, 0)
                    
                except Exception as e:
                    print(f"Error processing file {file_record.id}: {e}")
                    continue
            
            # Завершаем сессию
            crud.complete_processing_session(db, session_id, total_rows, processed_rows)
            print(f"Processing session {session_id} completed: {processed_rows}/{total_rows} rows")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error in process_uploaded_files_async: {e}")
        try:
            from ..database import SessionLocal
            db = SessionLocal()
            crud.fail_processing_session(db, session_id, str(e))
            db.close()
        except:
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
