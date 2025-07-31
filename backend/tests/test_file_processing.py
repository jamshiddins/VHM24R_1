"""
Тесты для обработки файлов
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, mock_open
from pathlib import Path
import pandas as pd
import tempfile
import os

from app.services.file_processor import EnhancedFileProcessor
from app.services.optimized_file_processor import OptimizedFileProcessor


class TestEnhancedFileProcessor:
    """Тесты для EnhancedFileProcessor"""
    
    @pytest.fixture
    def file_processor(self):
        return EnhancedFileProcessor()
    
    def test_detect_file_type_excel(self, file_processor):
        """Тест определения типа Excel файла"""
        # Тест для .xlsx
        assert file_processor.detect_file_type("test.xlsx") == "excel"
        assert file_processor.detect_file_type("test.xls") == "excel"
        assert file_processor.detect_file_type("TEST.XLSX") == "excel"
    
    def test_detect_file_type_csv(self, file_processor):
        """Тест определения типа CSV файла"""
        assert file_processor.detect_file_type("test.csv") == "csv"
        assert file_processor.detect_file_type("TEST.CSV") == "csv"
    
    def test_detect_file_type_unknown(self, file_processor):
        """Тест определения неизвестного типа файла"""
        assert file_processor.detect_file_type("test.txt") == "unknown"
        assert file_processor.detect_file_type("test.pdf") == "unknown"
    
    @pytest.mark.asyncio
    async def test_process_file_excel_success(self, file_processor):
        """Тест успешной обработки Excel файла"""
        # Создаем временный Excel файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # Создаем тестовые данные
            test_data = pd.DataFrame({
                'order_number': ['ORD001', 'ORD002'],
                'machine_code': ['MAC001', 'MAC002'],
                'order_price': [100.0, 200.0],
                'payment_status': ['paid', 'pending']
            })
            test_data.to_excel(tmp_file.name, index=False)
            
            try:
                # Мокаем зависимости
                with patch('app.services.file_processor.crud') as mock_crud:
                    mock_crud.create_order.return_value = Mock(id=1)
                    
                    result = await file_processor.process_file(tmp_file.name, 1, 1)
                    
                    assert result['status'] == 'success'
                    assert result['total_rows'] == 2
                    assert result['processed_rows'] >= 0
                    
            finally:
                os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_process_file_csv_success(self, file_processor):
        """Тест успешной обработки CSV файла"""
        # Создаем временный CSV файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("order_number,machine_code,order_price,payment_status\n")
            tmp_file.write("ORD001,MAC001,100.0,paid\n")
            tmp_file.write("ORD002,MAC002,200.0,pending\n")
            tmp_file.flush()
            
            try:
                with patch('app.services.file_processor.crud') as mock_crud:
                    mock_crud.create_order.return_value = Mock(id=1)
                    
                    result = await file_processor.process_file(tmp_file.name, 1, 1)
                    
                    assert result['status'] == 'success'
                    assert result['total_rows'] == 2
                    
            finally:
                os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_process_file_not_found(self, file_processor):
        """Тест обработки несуществующего файла"""
        result = await file_processor.process_file("nonexistent.xlsx", 1, 1)
        
        assert result['status'] == 'error'
        assert 'not found' in result['message'].lower()
    
    @pytest.mark.asyncio
    async def test_process_file_unsupported_format(self, file_processor):
        """Тест обработки неподдерживаемого формата"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(b"Some text content")
            
            try:
                result = await file_processor.process_file(tmp_file.name, 1, 1)
                
                assert result['status'] == 'error'
                assert 'unsupported' in result['message'].lower()
                
            finally:
                os.unlink(tmp_file.name)
    
    def test_validate_row_data_valid(self, file_processor):
        """Тест валидации корректных данных строки"""
        valid_row = {
            'order_number': 'ORD001',
            'machine_code': 'MAC001',
            'order_price': 100.0,
            'payment_status': 'paid'
        }
        
        is_valid, errors = file_processor.validate_row_data(valid_row)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_row_data_missing_required(self, file_processor):
        """Тест валидации данных с отсутствующими обязательными полями"""
        invalid_row = {
            'machine_code': 'MAC001',
            'order_price': 100.0
            # Отсутствует order_number
        }
        
        is_valid, errors = file_processor.validate_row_data(invalid_row)
        assert is_valid is False
        assert len(errors) > 0
        assert any('order_number' in error for error in errors)
    
    def test_validate_row_data_invalid_price(self, file_processor):
        """Тест валидации данных с некорректной ценой"""
        invalid_row = {
            'order_number': 'ORD001',
            'machine_code': 'MAC001',
            'order_price': 'invalid_price',
            'payment_status': 'paid'
        }
        
        is_valid, errors = file_processor.validate_row_data(invalid_row)
        assert is_valid is False
        assert any('price' in error.lower() for error in errors)


class TestOptimizedFileProcessor:
    """Тесты для OptimizedFileProcessor"""
    
    @pytest.fixture
    def optimized_processor(self):
        return OptimizedFileProcessor()
    
    @pytest.mark.asyncio
    async def test_process_large_file_chunked(self, optimized_processor):
        """Тест обработки большого файла по частям"""
        # Создаем большой CSV файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("order_number,machine_code,order_price,payment_status\n")
            
            # Создаем 1000 строк для тестирования chunked обработки
            for i in range(1000):
                tmp_file.write(f"ORD{i:04d},MAC{i:04d},{i * 10}.0,paid\n")
            tmp_file.flush()
            
            try:
                with patch('app.services.optimized_file_processor.crud') as mock_crud:
                    mock_crud.bulk_create_orders.return_value = 100  # Мок для bulk операций
                    
                    result = await optimized_processor.process_file_chunked(tmp_file.name, 1, 1)
                    
                    assert result['status'] == 'success'
                    assert result['total_rows'] == 1000
                    
            finally:
                os.unlink(tmp_file.name)
    
    def test_chunk_dataframe(self, optimized_processor):
        """Тест разбиения DataFrame на части"""
        # Создаем тестовый DataFrame
        test_df = pd.DataFrame({
            'order_number': [f'ORD{i:03d}' for i in range(100)],
            'machine_code': [f'MAC{i:03d}' for i in range(100)],
            'order_price': [i * 10.0 for i in range(100)]
        })
        
        chunks = list(optimized_processor.chunk_dataframe(test_df, chunk_size=25))
        
        assert len(chunks) == 4  # 100 / 25 = 4 части
        assert len(chunks[0]) == 25
        assert len(chunks[-1]) == 25
    
    @pytest.mark.asyncio
    async def test_process_chunk_with_validation(self, optimized_processor):
        """Тест обработки части данных с валидацией"""
        chunk_data = pd.DataFrame({
            'order_number': ['ORD001', 'ORD002', ''],  # Одна пустая строка
            'machine_code': ['MAC001', 'MAC002', 'MAC003'],
            'order_price': [100.0, 200.0, 300.0],
            'payment_status': ['paid', 'pending', 'paid']
        })
        
        with patch('app.services.optimized_file_processor.crud') as mock_crud:
            mock_crud.bulk_create_orders.return_value = 2  # 2 валидные строки
            
            result = await optimized_processor.process_chunk(chunk_data, 1, 1)
            
            assert result['processed'] == 2
            assert result['errors'] == 1


class TestFileValidation:
    """Тесты для валидации файлов"""
    
    def test_file_size_validation(self):
        """Тест валидации размера файла"""
        from app.services.file_processor import validate_file_size
        
        # Создаем временный файл известного размера
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            # Записываем 1MB данных
            tmp_file.write(b'0' * (1024 * 1024))
            tmp_file.flush()
            
            try:
                # Тест с лимитом 2MB - должен пройти
                assert validate_file_size(tmp_file.name, max_size_mb=2) is True
                
                # Тест с лимитом 0.5MB - должен не пройти
                assert validate_file_size(tmp_file.name, max_size_mb=0.5) is False
                
            finally:
                os.unlink(tmp_file.name)
    
    def test_file_extension_validation(self):
        """Тест валидации расширения файла"""
        from app.services.file_processor import validate_file_extension
        
        allowed_extensions = ['.xlsx', '.xls', '.csv']
        
        assert validate_file_extension('test.xlsx', allowed_extensions) is True
        assert validate_file_extension('test.csv', allowed_extensions) is True
        assert validate_file_extension('test.txt', allowed_extensions) is False
        assert validate_file_extension('test.pdf', allowed_extensions) is False
    
    def test_file_content_validation(self):
        """Тест валидации содержимого файла"""
        from app.services.file_processor import validate_file_content
        
        # Создаем корректный CSV файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("order_number,machine_code,order_price\n")
            tmp_file.write("ORD001,MAC001,100.0\n")
            tmp_file.flush()
            
            try:
                required_columns = ['order_number', 'machine_code', 'order_price']
                is_valid, message = validate_file_content(tmp_file.name, required_columns)
                
                assert is_valid is True
                assert message == "File content is valid"
                
            finally:
                os.unlink(tmp_file.name)
    
    def test_file_content_validation_missing_columns(self):
        """Тест валидации файла с отсутствующими колонками"""
        from app.services.file_processor import validate_file_content
        
        # Создаем CSV файл с отсутствующими колонками
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("order_number,machine_code\n")  # Отсутствует order_price
            tmp_file.write("ORD001,MAC001\n")
            tmp_file.flush()
            
            try:
                required_columns = ['order_number', 'machine_code', 'order_price']
                is_valid, message = validate_file_content(tmp_file.name, required_columns)
                
                assert is_valid is False
                assert 'missing' in message.lower()
                
            finally:
                os.unlink(tmp_file.name)


class TestFileProcessingIntegration:
    """Интеграционные тесты обработки файлов"""
    
    @pytest.mark.asyncio
    async def test_full_file_processing_pipeline(self):
        """Тест полного пайплайна обработки файла"""
        processor = EnhancedFileProcessor()
        
        # Создаем тестовый файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write("order_number,machine_code,order_price,payment_status\n")
            tmp_file.write("ORD001,MAC001,100.0,paid\n")
            tmp_file.write("ORD002,MAC002,200.0,pending\n")
            tmp_file.write("ORD003,MAC003,invalid_price,paid\n")  # Невалидная строка
            tmp_file.flush()
            
            try:
                with patch('app.services.file_processor.crud') as mock_crud:
                    mock_crud.create_order.return_value = Mock(id=1)
                    
                    result = await processor.process_file(tmp_file.name, 1, 1)
                    
                    # Проверяем результат
                    assert result['status'] == 'success'
                    assert result['total_rows'] == 3
                    assert result['processed_rows'] >= 2  # Минимум 2 валидные строки
                    assert 'errors' in result
                    
            finally:
                os.unlink(tmp_file.name)
    
    def test_error_handling_corrupted_file(self):
        """Тест обработки поврежденного файла"""
        processor = EnhancedFileProcessor()
        
        # Создаем поврежденный файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'This is not a valid Excel file')
            
            try:
                # Тест должен обработать ошибку gracefully
                import asyncio
                result = asyncio.run(processor.process_file(tmp_file.name, 1, 1))
                
                assert result['status'] == 'error'
                assert 'error' in result['message'].lower()
                
            finally:
                os.unlink(tmp_file.name)


if __name__ == "__main__":
    pytest.main([__file__])
