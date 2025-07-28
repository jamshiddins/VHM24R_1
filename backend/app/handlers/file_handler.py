"""
Обработчик файлов для VHM24R
Отвечает за загрузку и обработку файлов
"""

from fastapi import HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import hashlib
import os
from datetime import datetime

from ..constants import (
    MAX_FILE_SIZE,
    ProcessingStatus,
    ErrorMessages,
    SuccessMessages,
    HTTPStatus
)
from .. import crud, models
from ..services.file_processor import EnhancedFileProcessor

class FileHandler:
    """Обработчик файлов"""
    
    def __init__(self):
        self.file_processor = EnhancedFileProcessor()
    
    def _calculate_content_hash(self, content: bytes) -> str:
        """Расчёт хеша содержимого файла"""
        return hashlib.sha256(content).hexdigest()
    
    def _detect_file_similarity(self, content_hash: str, db: Session) -> tuple:
        """Проверка схожести файла с уже загруженными"""
        # Ищем файлы с таким же хешем
        existing_file = db.query(models.File).filter(
            models.File.content_hash == content_hash
        ).first()
        
        if existing_file:
            return 100.0, existing_file.id
        
        # Упрощённая версия - возвращаем 0% схожести для разных хешей
        return 0.0, None
    
    def _validate_file(self, file: UploadFile, content: bytes) -> None:
        """Валидация загружаемого файла"""
        # Проверка размера файла
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=ErrorMessages.FILE_TOO_LARGE
            )
        
        # Проверка типа файла (базовая)
        allowed_extensions = {
            '.csv', '.xls', '.xlsx', '.pdf', '.doc', '.docx', 
            '.json', '.xml', '.zip', '.rar', '.txt', '.tsv'
        }
        
        filename = file.filename or ""
        file_extension = os.path.splitext(filename.lower())[1]
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=ErrorMessages.INVALID_FILE_FORMAT
            )
    
    async def upload_files(
        self, 
        files: List[UploadFile], 
        current_user: models.User, 
        db: Session,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Загрузка файлов для обработки"""
        
        upload_results = []
        
        for file in files:
            try:
                # Читаем содержимое
                content = await file.read()
                
                # Валидируем файл
                self._validate_file(file, content)
                
                # Вычисляем хеш
                content_hash = self._calculate_content_hash(content)
                
                # Проверяем схожесть
                similarity, similar_file_id = self._detect_file_similarity(content_hash, db)
                
                # Создаём запись в БД
                file_data = {
                    "filename": file.filename or "unknown",
                    "original_name": file.filename or "unknown",
                    "content_hash": content_hash,
                    "file_size": len(content),
                    "file_type": file.content_type or "application/octet-stream",
                    "storage_path": f"uploads/{file.filename}",
                    "uploaded_by": current_user.id,
                    "processing_status": ProcessingStatus.PENDING
                }
                
                db_file = crud.create_uploaded_file(db, file_data)
                
                # Убеждаемся, что объект сохранен и имеет ID
                if db_file:
                    db.commit()
                    db.refresh(db_file)
                
                # Сохраняем файл на диск (если нужно)
                storage_path = f"uploads/{file.filename}"
                os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                
                with open(storage_path, "wb") as f:
                    f.write(content)
                
                # Добавляем задачу на обработку в фоне
                if db_file and similarity < 90.0:  # Обрабатываем только если файл не дубликат
                    # Получаем фактическое значение ID из базы данных
                    actual_file_id = getattr(db_file, 'id', None)
                    actual_user_id = getattr(current_user, 'id', None)
                    if actual_file_id is not None and actual_user_id is not None:
                        background_tasks.add_task(
                            self._process_file_background,
                            actual_file_id,
                            storage_path,
                            actual_user_id
                        )
                
                upload_results.append({
                    "file_id": db_file.id if db_file else 0,
                    "filename": file.filename,
                    "size": len(content),
                    "similarity": similarity,
                    "similar_file_id": similar_file_id,
                    "hash": content_hash,
                    "status": "uploaded"
                })
                
            except HTTPException:
                raise
            except Exception as e:
                upload_results.append({
                    "filename": file.filename,
                    "error": str(e),
                    "status": "error"
                })
        
        return {
            "files": upload_results,
            "message": SuccessMessages.FILE_UPLOADED
        }
    
    async def _process_file_background(self, file_id: int, file_path: str, user_id: int):
        """Фоновая обработка файла"""
        from ..database import SessionLocal
        
        db = SessionLocal()
        try:
            # Обновляем статус на "обработка"
            crud.update_file_processing_status(db, file_id, ProcessingStatus.PROCESSING)
            
            # Обрабатываем файл
            result = await self.file_processor.process_file(file_path, file_id, user_id)
            
            # Обновляем статистику файла
            crud.update_file_stats(
                db, 
                file_id, 
                result.get('total_rows', 0),
                result.get('processed_rows', 0),
                result.get('processed_rows', 0)  # используем processed_rows как updated_rows
            )
            
            # Обновляем статус на "завершено"
            crud.update_file_processing_status(db, file_id, ProcessingStatus.COMPLETED)
            
        except Exception as e:
            # Обновляем статус на "ошибка"
            crud.update_file_processing_status(
                db, 
                file_id, 
                ProcessingStatus.FAILED, 
                error_message=str(e)
            )
        finally:
            db.close()
    
    def get_user_files(self, user_id: int, db: Session) -> List[Dict[str, Any]]:
        """Получение списка файлов пользователя"""
        files = crud.get_uploaded_files(db, user_id)
        
        return [{
            "id": file.id,
            "filename": file.filename,
            "original_name": file.original_name,
            "file_size": file.file_size,
            "file_type": file.file_type,
            "processing_status": file.processing_status,
            "records_count": file.records_count,
            "processed_records": file.processed_records,
            "matched_records": file.matched_records,
            "error_records": file.error_records,
            "uploaded_at": file.uploaded_at,
            "processing_started_at": file.processing_started_at,
            "processing_finished_at": file.processing_finished_at,
            "error_message": file.error_message
        } for file in files]
    
    def get_file_details(self, file_id: int, user_id: int, db: Session) -> Dict[str, Any]:
        """Получение детальной информации о файле"""
        file = crud.get_uploaded_file_by_id(db, file_id)
        
        if not file:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Файл не найден"
            )
        
        # Проверяем права доступа
        if getattr(file, 'uploaded_by', None) != user_id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=ErrorMessages.ACCESS_DENIED
            )
        
        return {
            "id": file.id,
            "filename": file.filename,
            "original_name": file.original_name,
            "file_size": file.file_size,
            "file_type": file.file_type,
            "content_hash": file.content_hash,
            "processing_status": file.processing_status,
            "records_count": file.records_count,
            "processed_records": file.processed_records,
            "matched_records": file.matched_records,
            "error_records": file.error_records,
            "similarity_percent": file.similarity_percent,
            "duplicate_of_id": file.duplicate_of_id,
            "uploaded_at": file.uploaded_at,
            "processing_started_at": file.processing_started_at,
            "processing_finished_at": file.processing_finished_at,
            "error_message": file.error_message,
            "detected_encoding": file.detected_encoding,
            "detected_delimiter": file.detected_delimiter,
            "sheet_names": file.sheet_names,
            "processed_sheet": file.processed_sheet
        }

# Создаем глобальный экземпляр обработчика
file_handler = FileHandler()
