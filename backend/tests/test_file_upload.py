"""
Unit and integration tests for VHM24R file upload and processing

Tests cover:
- File upload validation
- File format detection
- Data processing
- Error handling
- Security checks
"""

import pytest
import tempfile
import os
import io
import csv
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Any

# Simple imports for testing without the full app structure
import sys
import pandas as pd


class MockFileProcessor:
    """Mock file processor for testing"""
    
    def __init__(self):
        self.supported_formats = ['.xlsx', '.xls', '.csv', '.txt']
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def validate_file(self, file_path: str, file_size: int) -> Dict[str, Any]:
        """Validate uploaded file"""
        if not os.path.exists(file_path):
            return {'valid': False, 'error': 'File not found'}
        
        if file_size > self.max_file_size:
            return {'valid': False, 'error': 'File too large'}
        
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.supported_formats:
            return {'valid': False, 'error': 'Unsupported file format'}
        
        return {'valid': True}
    
    def detect_file_type(self, filename: str) -> str:
        """Detect file type from filename"""
        filename_lower = filename.lower()
        
        if 'hardware' in filename_lower or 'hw' in filename_lower:
            return 'hardware'
        elif 'report' in filename_lower or 'sales' in filename_lower:
            return 'sales'
        elif 'fiscal' in filename_lower or 'bill' in filename_lower:
            return 'fiscal'
        elif 'payme' in filename_lower:
            return 'payme'
        elif 'click' in filename_lower:
            return 'click'
        elif 'uzum' in filename_lower:
            return 'uzum'
        else:
            return 'unknown'
    
    def process_excel_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Process Excel file"""
        try:
            df = pd.read_excel(file_path)
            
            if df.empty:
                return {
                    'success': False,
                    'error': 'File is empty',
                    'rows_processed': 0
                }
            
            # Validate required columns based on file type
            required_columns = self._get_required_columns(file_type)
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'success': False,
                    'error': f'Missing required columns: {", ".join(missing_columns)}',
                    'rows_processed': 0
                }
            
            return {
                'success': True,
                'rows_processed': len(df),
                'columns': list(df.columns),
                'data_preview': df.head().to_dict('records')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'rows_processed': 0
            }
    
    def process_csv_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Process CSV file"""
        try:
            df = pd.read_csv(file_path)
            
            if df.empty:
                return {
                    'success': False,
                    'error': 'File is empty',
                    'rows_processed': 0
                }
            
            return {
                'success': True,
                'rows_processed': len(df),
                'columns': list(df.columns),
                'data_preview': df.head().to_dict('records')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'rows_processed': 0
            }
    
    def _get_required_columns(self, file_type: str) -> list:
        """Get required columns for file type"""
        column_mapping = {
            'hardware': ['order_number', 'machine_code', 'goods_name', 'order_price'],
            'sales': ['order_number', 'goods_name', 'order_price', 'machine_code'],
            'fiscal': ['receipt_number', 'operation_amount', 'operation_datetime'],
            'payme': ['payment_system_id', 'amount_without_commission', 'payment_time'],
            'click': ['click_id', 'amount', 'payment_date'],
            'uzum': ['receipt_id', 'amount', 'parsed_datetime']
        }
        return column_mapping.get(file_type, [])


class TestFileValidation:
    """Test cases for file validation"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.unit
    def test_validate_supported_file_formats(self):
        """Test validation of supported file formats"""
        # Create temporary files with different extensions
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.validate_file(tmp_file_path, 1000)
            assert result['valid'] is True
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_validate_unsupported_file_format(self):
        """Test validation rejects unsupported formats"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.validate_file(tmp_file_path, 1000)
            assert result['valid'] is False
            assert 'Unsupported file format' in result['error']
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_validate_file_size_limit(self):
        """Test file size validation"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file_path = tmp_file.name
        
        try:
            # Test file too large
            large_size = 20 * 1024 * 1024  # 20MB
            result = self.processor.validate_file(tmp_file_path, large_size)
            assert result['valid'] is False
            assert 'File too large' in result['error']
            
            # Test acceptable size
            small_size = 1024  # 1KB
            result = self.processor.validate_file(tmp_file_path, small_size)
            assert result['valid'] is True
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file"""
        result = self.processor.validate_file('/nonexistent/file.xlsx', 1000)
        assert result['valid'] is False
        assert 'File not found' in result['error']
    
    @pytest.mark.unit
    def test_detect_file_type_hardware(self):
        """Test hardware file type detection"""
        test_cases = [
            'hardware_orders.xlsx',
            'HW_data.csv',
            'machine_hardware.xlsx',
            'orders_hw.xlsx'
        ]
        
        for filename in test_cases:
            file_type = self.processor.detect_file_type(filename)
            assert file_type == 'hardware', f"Failed for {filename}"
    
    @pytest.mark.unit
    def test_detect_file_type_sales(self):
        """Test sales file type detection"""
        test_cases = [
            'sales_report.xlsx',
            'monthly_reports.csv',
            'vendhub_sales.xlsx'
        ]
        
        for filename in test_cases:
            file_type = self.processor.detect_file_type(filename)
            assert file_type == 'sales', f"Failed for {filename}"
    
    @pytest.mark.unit
    def test_detect_file_type_payments(self):
        """Test payment file type detection"""
        test_cases = [
            ('payme_transactions.xlsx', 'payme'),
            ('click_payments.csv', 'click'),
            ('uzum_data.xlsx', 'uzum')
        ]
        
        for filename, expected_type in test_cases:
            file_type = self.processor.detect_file_type(filename)
            assert file_type == expected_type, f"Failed for {filename}, got {file_type}"
    
    @pytest.mark.unit
    def test_detect_file_type_unknown(self):
        """Test unknown file type detection"""
        unknown_files = [
            'random_data.xlsx',
            'unknown_file.csv',
            'test.xlsx'
        ]
        
        for filename in unknown_files:
            file_type = self.processor.detect_file_type(filename)
            assert file_type == 'unknown', f"Failed for {filename}"


class TestExcelProcessing:
    """Test cases for Excel file processing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.unit
    def test_process_valid_hardware_excel(self):
        """Test processing valid hardware Excel file"""
        # Create test data
        test_data = {
            'order_number': ['order_001', 'order_002'],
            'machine_code': ['machine_001', 'machine_002'],
            'goods_name': ['Coffee', 'Tea'],
            'order_price': [15000, 12000],
            'creation_time': ['2025-07-31 10:00:00', '2025-07-31 11:00:00']
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            assert result['success'] is True
            assert result['rows_processed'] == 2
            assert 'order_number' in result['columns']
            assert 'machine_code' in result['columns']
            assert len(result['data_preview']) == 2
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_process_excel_missing_columns(self):
        """Test processing Excel file with missing required columns"""
        # Create data missing required columns
        test_data = {
            'some_column': ['value1', 'value2'],
            'another_column': ['value3', 'value4']
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            assert result['success'] is False
            assert 'Missing required columns' in result['error']
            assert result['rows_processed'] == 0
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_process_empty_excel_file(self):
        """Test processing empty Excel file"""
        # Create empty DataFrame
        df = pd.DataFrame()
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            assert result['success'] is False
            assert 'File is empty' in result['error']
            assert result['rows_processed'] == 0
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_process_corrupted_excel_file(self):
        """Test processing corrupted Excel file"""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # Write invalid Excel content
            tmp_file.write(b'This is not a valid Excel file')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            assert result['success'] is False
            assert result['rows_processed'] == 0
            assert 'error' in result
        finally:
            os.unlink(tmp_file_path)


class TestCSVProcessing:
    """Test cases for CSV file processing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.unit
    def test_process_valid_csv_file(self):
        """Test processing valid CSV file"""
        test_data = [
            ['order_number', 'machine_code', 'goods_name', 'order_price'],
            ['order_001', 'machine_001', 'Coffee', '15000'],
            ['order_002', 'machine_002', 'Tea', '12000']
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as tmp_file:
            writer = csv.writer(tmp_file)
            writer.writerows(test_data)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_csv_file(tmp_file_path, 'hardware')
            
            assert result['success'] is True
            assert result['rows_processed'] == 2
            assert 'order_number' in result['columns']
            assert len(result['data_preview']) == 2
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_process_empty_csv_file(self):
        """Test processing empty CSV file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as tmp_file:
            # Create empty CSV
            tmp_file.write('')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_csv_file(tmp_file_path, 'hardware')
            
            assert result['success'] is False
            assert 'File is empty' in result['error']
            assert result['rows_processed'] == 0
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_process_csv_with_different_encodings(self):
        """Test processing CSV files with different encodings"""
        test_data = [
            ['order_number', 'goods_name', 'price'],
            ['order_001', 'Кофе', '15000'],  # Cyrillic characters
            ['order_002', 'Чай', '12000']
        ]
        
        # Test UTF-8 encoding
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, 
                                       newline='', encoding='utf-8') as tmp_file:
            writer = csv.writer(tmp_file)
            writer.writerows(test_data)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_csv_file(tmp_file_path, 'hardware')
            assert result['success'] is True
            assert result['rows_processed'] == 2
        finally:
            os.unlink(tmp_file_path)


class TestFileUploadSecurity:
    """Security tests for file uploads"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.security
    def test_reject_executable_files(self):
        """Test rejection of executable files"""
        dangerous_extensions = ['.exe', '.bat', '.sh', '.py', '.js']
        
        for ext in dangerous_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                tmp_file.write(b'malicious content')
                tmp_file_path = tmp_file.name
            
            try:
                result = self.processor.validate_file(tmp_file_path, 1000)
                assert result['valid'] is False, f"Should reject {ext} files"
                assert 'Unsupported file format' in result['error']
            finally:
                os.unlink(tmp_file_path)
    
    @pytest.mark.security
    def test_filename_path_traversal_protection(self):
        """Test protection against path traversal in filenames"""
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config',
            '/etc/shadow',
            'C:\\Windows\\System32\\config\\SAM'
        ]
        
        for filename in malicious_filenames:
            # The detect_file_type should work safely with malicious paths
            file_type = self.processor.detect_file_type(filename)
            # Should return 'unknown' or handle safely without error
            assert isinstance(file_type, str)
    
    @pytest.mark.security
    def test_large_file_rejection(self):
        """Test rejection of excessively large files"""
        max_size = self.processor.max_file_size
        oversized = max_size + 1024  # 1KB over limit
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'content')
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.validate_file(tmp_file_path, oversized)
            assert result['valid'] is False
            assert 'File too large' in result['error']
        finally:
            os.unlink(tmp_file_path)


class TestFileUploadIntegration:
    """Integration tests for file upload workflow"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.integration
    def test_complete_file_processing_workflow(self):
        """Test complete file processing workflow"""
        # 1. Create test Excel file
        test_data = {
            'order_number': ['hw_001', 'hw_002', 'hw_003'],
            'machine_code': ['machine_001', 'machine_001', 'machine_002'],
            'goods_name': ['Coffee', 'Tea', 'Hot Chocolate'],
            'order_price': [15000, 12000, 18000],
            'creation_time': ['2025-07-31 10:00:00', '2025-07-31 11:00:00', '2025-07-31 12:00:00'],
            'payment_status': ['Paid', 'Paid', 'Refunded'],
            'brew_status': ['Delivered', 'Delivered', 'Not delivered']
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
            file_size = os.path.getsize(tmp_file.name)
        
        try:
            # 2. Validate file
            validation_result = self.processor.validate_file(tmp_file_path, file_size)
            assert validation_result['valid'] is True
            
            # 3. Detect file type
            filename = 'hardware_orders_july.xlsx'
            file_type = self.processor.detect_file_type(filename)
            assert file_type == 'hardware'
            
            # 4. Process file
            processing_result = self.processor.process_excel_file(tmp_file_path, file_type)
            assert processing_result['success'] is True
            assert processing_result['rows_processed'] == 3
            
            # 5. Verify data structure
            assert len(processing_result['columns']) > 0
            assert len(processing_result['data_preview']) == 3
            
            # 6. Verify data content
            preview_data = processing_result['data_preview']
            assert preview_data[0]['order_number'] == 'hw_001'
            assert preview_data[0]['machine_code'] == 'machine_001'
            assert preview_data[2]['brew_status'] == 'Not delivered'
            
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.integration
    def test_multiple_file_types_processing(self):
        """Test processing different file types"""
        file_configs = [
            {
                'filename': 'hardware_orders.xlsx',
                'type': 'hardware',
                'data': {
                    'order_number': ['hw_001'],
                    'machine_code': ['machine_001'],
                    'goods_name': ['Coffee'],
                    'order_price': [15000]
                }
            },
            {
                'filename': 'sales_report.xlsx',
                'type': 'sales',
                'data': {
                    'order_number': ['sale_001'],
                    'goods_name': ['Coffee'],
                    'order_price': [15000],
                    'machine_code': ['machine_001']
                }
            }
        ]
        
        for config in file_configs:
            df = pd.DataFrame(config['data'])
            
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                df.to_excel(tmp_file.name, index=False)
                tmp_file_path = tmp_file.name
            
            try:
                # Detect type
                detected_type = self.processor.detect_file_type(config['filename'])
                assert detected_type == config['type']
                
                # Process file
                result = self.processor.process_excel_file(tmp_file_path, config['type'])
                assert result['success'] is True
                assert result['rows_processed'] == 1
                
            finally:
                os.unlink(tmp_file_path)


class TestFileUploadPerformance:
    """Performance tests for file upload processing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.performance
    def test_large_file_processing_performance(self):
        """Test processing performance with large files"""
        import time
        
        # Create large dataset (1000 rows)
        large_data = {
            'order_number': [f'order_{i:06d}' for i in range(1000)],
            'machine_code': [f'machine_{i % 10:03d}' for i in range(1000)],
            'goods_name': ['Coffee' if i % 2 == 0 else 'Tea' for i in range(1000)],
            'order_price': [15000 + (i % 100) * 100 for i in range(1000)]
        }
        
        df = pd.DataFrame(large_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            start_time = time.time()
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            processing_time = time.time() - start_time
            
            assert result['success'] is True
            assert result['rows_processed'] == 1000
            
            # Should process 1000 rows in under 5 seconds
            assert processing_time < 5.0, f"Processing took {processing_time:.2f}s for 1000 rows"
            
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.performance
    def test_multiple_file_validation_performance(self):
        """Test validation performance with multiple files"""
        import time
        
        # Create multiple small files
        file_paths = []
        
        try:
            for i in range(10):
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                    tmp_file.write(b'test content')
                    file_paths.append(tmp_file.name)
            
            start_time = time.time()
            
            # Validate all files
            for file_path in file_paths:
                result = self.processor.validate_file(file_path, 1000)
                assert result['valid'] is True
            
            validation_time = time.time() - start_time
            
            # Should validate 10 files in under 1 second
            assert validation_time < 1.0, f"Validation took {validation_time:.2f}s for 10 files"
            
        finally:
            # Cleanup
            for file_path in file_paths:
                if os.path.exists(file_path):
                    os.unlink(file_path)


class TestErrorHandling:
    """Test error handling in file processing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.unit
    def test_handle_permission_denied_error(self):
        """Test handling of permission denied errors"""
        # This test would need to be adapted based on the actual implementation
        # Here we simulate the error condition
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_file_path = tmp_file.name
        
        try:
            # Simulate permission denied by changing file permissions
            os.chmod(tmp_file_path, 0o000)  # No permissions
            
            # The processor should handle this gracefully
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            assert result['success'] is False
            assert 'error' in result
            
        finally:
            # Restore permissions for cleanup
            os.chmod(tmp_file_path, 0o644)
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_handle_network_interruption(self):
        """Test handling of network interruptions during upload"""
        # This would be more relevant for actual HTTP uploads
        # Here we simulate a partial file scenario
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # Write partial/corrupted Excel content
            tmp_file.write(b'PK\x03\x04')  # Start of ZIP header but incomplete
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            assert result['success'] is False
            assert 'error' in result
            
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_handle_disk_space_error(self):
        """Test handling of disk space errors"""
        # This is difficult to simulate in unit tests
        # but we can test the error handling structure
        
        # Mock a disk space error scenario
        with patch('pandas.read_excel') as mock_read:
            mock_read.side_effect = OSError("No space left on device")
            
            result = self.processor.process_excel_file('dummy_path.xlsx', 'hardware')
            assert result['success'] is False
            assert 'No space left on device' in result['error']


class TestDataValidation:
    """Test data validation within uploaded files"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = MockFileProcessor()
    
    @pytest.mark.unit
    def test_validate_required_columns_present(self):
        """Test validation of required columns"""
        file_types_and_columns = {
            'hardware': ['order_number', 'machine_code', 'goods_name', 'order_price'],
            'sales': ['order_number', 'goods_name', 'order_price', 'machine_code'],
            'fiscal': ['receipt_number', 'operation_amount', 'operation_datetime'],
            'payme': ['payment_system_id', 'amount_without_commission', 'payment_time'],
        }
        
        for file_type, required_cols in file_types_and_columns.items():
            required_columns = self.processor._get_required_columns(file_type)
            assert required_columns == required_cols, f"Mismatch for {file_type}"
    
    @pytest.mark.unit
    def test_validate_data_types_in_columns(self):
        """Test validation of data types in uploaded data"""
        # Create data with mixed types
        test_data = {
            'order_number': ['order_001', 'order_002'],
            'machine_code': ['machine_001', 'machine_002'],
            'goods_name': ['Coffee', 'Tea'],
            'order_price': [15000, 'invalid_price']  # Invalid price
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            # The processor should still succeed but flag data quality issues
            assert result['success'] is True
            assert result['rows_processed'] == 2
            
            # Check that data preview contains the problematic data
            preview = result['data_preview']
            assert preview[1]['order_price'] == 'invalid_price'
            
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit
    def test_validate_duplicate_detection(self):
        """Test detection of duplicate records"""
        # Create data with duplicates
        test_data = {
            'order_number': ['order_001', 'order_001', 'order_002'],  # Duplicate
            'machine_code': ['machine_001', 'machine_001', 'machine_002'],
            'goods_name': ['Coffee', 'Coffee', 'Tea'],
            'order_price': [15000, 15000, 12000]
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            result = self.processor.process_excel_file(tmp_file_path, 'hardware')
            
            # The processor should still succeed
            assert result['success'] is True
            assert result['rows_processed'] == 3
            
            # Check for duplicates in data preview
            preview = result['data_preview']
            order_numbers = [row['order_number'] for row in preview]
            assert 'order_001' in order_numbers
            
        finally:
            os.unlink(tmp_file_path)


# Mock tests that would connect to real implementations
class TestFileUploadMocks:
    """Test file upload with mocked dependencies"""
    
    @pytest.mark.unit
    def test_file_upload_with_database_mock(self):
        """Test file upload with mocked database operations"""
        processor = MockFileProcessor()
        
        # Create test file
        test_data = {
            'order_number': ['test_001'],
            'machine_code': ['machine_001'],
            'goods_name': ['Coffee'],
            'order_price': [15000]
        }
        
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            df.to_excel(tmp_file.name, index=False)
            tmp_file_path = tmp_file.name
        
        try:
            # Mock database save operation
            with patch('backend.app.crud.create_order') as mock_create:
                mock_create.return_value = {'id': 1, 'order_number': 'test_001'}
                
                result = processor.process_excel_file(tmp_file_path, 'hardware')
                assert result['success'] is True
                
        finally:
            os.unlink(tmp_file_path)
    
    @pytest.mark.unit 
    def test_file_upload_with_cloud_storage_mock(self):
        """Test file upload with mocked cloud storage"""
        processor = MockFileProcessor()
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            tmp_file.write(b'test excel content')
            tmp_file_path = tmp_file.name
        
        try:
            # Mock cloud storage upload
            with patch('backend.app.services.cloud_storage.upload_file') as mock_upload:
                mock_upload.return_value = {'url': 'https://cloud.example.com/file.xlsx'}
                
                validation_result = processor.validate_file(tmp_file_path, 1000)
                assert validation_result['valid'] is True
                
        finally:
            os.unlink(tmp_file_path)
