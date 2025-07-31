"""
Pytest configuration and fixtures for VHM24R testing

Provides database setup, authentication fixtures, and test utilities
for comprehensive testing of the VHM24R Order Management System.
"""

import pytest
import asyncio
import os
import tempfile
from typing import Generator, AsyncGenerator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Clear Prometheus registry to avoid conflicts in tests
from prometheus_client import REGISTRY
REGISTRY._collector_to_names.clear()
REGISTRY._names_to_collectors.clear()

# Import application components
from ..app.main import app
from ..app.database import Base, get_db
from ..app import models, crud
from ..app.services.auth.jwt_auth import jwt_service
from ..app.services.auth.telegram_auth import telegram_auth_service  
from ..app.services.file_processor import EnhancedFileProcessor
from ..app.utils.logger import get_logger

# Test constants
TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_JWT_SECRET = "test_secret_key_for_testing_only"
TEST_TELEGRAM_BOT_TOKEN = "test_bot_token"
TEST_USER_DATA = {
    'telegram_id': 123456789,
    'username': 'test_user',
    'first_name': 'Test',
    'last_name': 'User',
    'status': 'approved',
    'role': 'user'
}
TEST_ORDER_DATA = {
    'order_number': 'test_order_001',
    'machine_code': 'test_machine_001', 
    'goods_name': 'Test Coffee',
    'order_price': 15000,
    'creation_time': '2025-07-31 10:00:00',
    'payment_status': 'Paid',
    'brew_status': 'Delivered'
}
TEST_FILE_DATA = {
    'filename': 'test_file.xlsx',
    'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

logger = get_logger(__name__)


# ===============================
# DATABASE FIXTURES
# ===============================

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}  # SQLite specific
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_engine):
    """Create test database session with proper cleanup after each test"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=test_engine
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        # Cleanup all data to avoid UNIQUE constraint issues
        session.rollback()
        
        # Clear all tables
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture(scope="function")
def override_get_db(test_db_session):
    """Override database dependency for testing"""
    def _override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = _override_get_db
    yield test_db_session
    app.dependency_overrides.clear()


# ===============================
# CLIENT FIXTURES
# ===============================

@pytest.fixture(scope="function")
def test_client(override_get_db):
    """Create FastAPI test client"""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
async def async_test_client(override_get_db):
    """Create async test client for async endpoints"""
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ===============================
# AUTHENTICATION FIXTURES
# ===============================

@pytest.fixture(scope="function")
def test_user(test_db_session):
    """Create test user in database"""
    user = crud.create_user(test_db_session, TEST_USER_DATA)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_admin_user(test_db_session):
    """Create test admin user"""
    admin_data = TEST_USER_DATA.copy()
    admin_data.update({
        "telegram_id": 987654321,
        "username": "test_admin",
        "role": "admin"
    })
    user = crud.create_user(test_db_session, admin_data)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user):
    """Generate authentication headers with valid JWT token"""
    user_data = {
        'user_id': test_user.id,
        'username': test_user.username,
        'role': test_user.role,
        'status': test_user.status,
        'telegram_id': test_user.telegram_id
    }
    
    # Mock JWT service to use test secret
    with patch.object(jwt_service, 'secret_key', TEST_JWT_SECRET):
        token = jwt_service.create_access_token(user_data)
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_auth_headers(test_admin_user):
    """Generate admin authentication headers"""
    user_data = {
        'user_id': test_admin_user.id,
        'username': test_admin_user.username,
        'role': test_admin_user.role,
        'status': test_admin_user.status,
        'telegram_id': test_admin_user.telegram_id
    }
    
    with patch.object(jwt_service, 'secret_key', TEST_JWT_SECRET):
        token = jwt_service.create_access_token(user_data)
    
    return {"Authorization": f"Bearer {token}"}


# ===============================
# TELEGRAM FIXTURES
# ===============================

@pytest.fixture(scope="function")
def mock_telegram_bot():
    """Mock Telegram bot for testing"""
    with patch('backend.app.telegram_bot.bot') as mock_bot:
        mock_bot.send_message = MagicMock()
        mock_bot.get_me = MagicMock()
        mock_bot.get_me.return_value = MagicMock(username="test_bot")
        yield mock_bot


@pytest.fixture(scope="function")
def telegram_auth_data():
    """Generate valid Telegram auth data"""
    import time
    import hashlib
    import hmac
    
    auth_data = {
        'id': str(TEST_USER_DATA['telegram_id']),
        'first_name': TEST_USER_DATA['first_name'],
        'last_name': TEST_USER_DATA['last_name'],
        'username': TEST_USER_DATA['username'],
        'auth_date': str(int(time.time()))
    }
    
    # Generate valid hash for testing
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(auth_data.items())])
    secret_key = hashlib.sha256(TEST_TELEGRAM_BOT_TOKEN.encode()).digest()
    auth_data['hash'] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return auth_data


# ===============================
# FILE PROCESSING FIXTURES
# ===============================

@pytest.fixture(scope="function")
def test_excel_file():
    """Create temporary Excel file for testing"""
    import pandas as pd
    
    # Create test data
    test_data = {
        'order_number': ['test_order_001', 'test_order_002', 'test_order_003'],
        'machine_code': ['machine_001', 'machine_002', 'machine_001'],
        'goods_name': ['Coffee', 'Tea', 'Hot Chocolate'],
        'order_price': [15000, 12000, 18000],
        'creation_time': [
            '2025-07-31 10:00:00',
            '2025-07-31 11:00:00', 
            '2025-07-31 12:00:00'
        ],
        'payment_status': ['Paid', 'Paid', 'Refunded'],
        'brew_status': ['Delivered', 'Delivered', 'Not delivered']
    }
    
    df = pd.DataFrame(test_data)
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        df.to_excel(tmp_file.name, index=False)
        yield tmp_file.name
    
    # Cleanup
    os.unlink(tmp_file.name)


@pytest.fixture(scope="function") 
def test_csv_file():
    """Create temporary CSV file for testing"""
    import csv
    
    test_data = [
        ['order_number', 'machine_code', 'goods_name', 'order_price'],
        ['csv_order_001', 'machine_001', 'Coffee', '15000'],
        ['csv_order_002', 'machine_002', 'Tea', '12000']
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as tmp_file:
        writer = csv.writer(tmp_file)
        writer.writerows(test_data)
        tmp_file_path = tmp_file.name
    
    yield tmp_file_path
    
    # Cleanup
    os.unlink(tmp_file_path)


@pytest.fixture(scope="function")
def mock_file_processor():
    """Mock file processor for testing"""
    processor = MagicMock(spec=EnhancedFileProcessor)
    processor.process_file.return_value = {
        'success': True,
        'rows_processed': 10,
        'rows_imported': 9,
        'errors': 1
    }
    return processor


# ===============================
# ORDER DATA FIXTURES
# ===============================

@pytest.fixture(scope="function")
def test_order(test_db_session):
    """Create test order in database"""
    order_data = TEST_ORDER_DATA.copy()
    order = crud.create_order(test_db_session, order_data)
    test_db_session.commit()
    test_db_session.refresh(order)
    return order


@pytest.fixture(scope="function")
def test_orders_batch(test_db_session):
    """Create batch of test orders"""
    orders = []
    
    for i in range(5):
        order_data = TEST_ORDER_DATA.copy()
        order_data.update({
            'order_number': f'batch_order_{i:03d}',
            'machine_code': f'machine_{i % 2 + 1:03d}',
            'order_price': 15000 + (i * 1000)
        })
        
        order = crud.create_order(test_db_session, order_data)
        orders.append(order)
    
    test_db_session.commit()
    
    for order in orders:
        test_db_session.refresh(order)
    
    return orders


# ===============================
# ENVIRONMENT FIXTURES
# ===============================

@pytest.fixture(scope="function")
def mock_env_vars():
    """Mock environment variables for testing"""
    test_env = {
        'JWT_SECRET_KEY': TEST_JWT_SECRET,
        'TELEGRAM_BOT_TOKEN': TEST_TELEGRAM_BOT_TOKEN,
        'DATABASE_URL': TEST_DATABASE_URL,
        'TESTING': 'true'
    }
    
    with patch.dict(os.environ, test_env):
        yield test_env


# ===============================
# ASYNC EVENT LOOP
# ===============================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===============================
# UTILITY FIXTURES
# ===============================

@pytest.fixture(scope="function")
def captured_logs():
    """Capture logs during testing"""
    import logging
    from io import StringIO
    
    log_capture_string = StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    
    # Get logger and add handler
    logger = logging.getLogger('backend')
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)
    
    yield log_capture_string
    
    # Cleanup
    logger.removeHandler(ch)


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis for caching tests"""
    from unittest.mock import MagicMock
    
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    
    with patch('redis.from_url', return_value=mock_redis):
        yield mock_redis


# ===============================
# SECURITY TEST FIXTURES
# ===============================

@pytest.fixture(scope="function")
def malicious_file():
    """Create malicious file for security testing"""
    content = b"<?xml version='1.0'?><!DOCTYPE root [<!ENTITY test SYSTEM 'file:///etc/passwd'>]><root>&test;</root>"
    
    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as tmp_file:
        tmp_file.write(content)
        yield tmp_file.name
    
    # Cleanup
    os.unlink(tmp_file.name)


@pytest.fixture(scope="function")
def large_file():
    """Create large file for upload limit testing"""
    # Create 10MB file
    content = b"x" * (10 * 1024 * 1024)
    
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(content)
        yield tmp_file.name
    
    # Cleanup
    os.unlink(tmp_file.name)


# ===============================
# API TESTING UTILITIES
# ===============================

@pytest.fixture(scope="function")
def api_test_helpers():
    """Helper functions for API testing"""
    class APITestHelpers:
        @staticmethod
        def assert_error_response(response, status_code: int, error_message: Optional[str] = None):
            """Assert API error response format"""
            assert response.status_code == status_code
            data = response.json()
            assert 'error' in data
            if error_message:
                assert error_message in data['error']
        
        @staticmethod
        def assert_success_response(response, expected_keys: Optional[list] = None):
            """Assert API success response format"""
            assert response.status_code == 200
            data = response.json()
            if expected_keys:
                for key in expected_keys:
                    assert key in data
        
        @staticmethod
        def assert_paginated_response(response, expected_total: Optional[int] = None):
            """Assert paginated response format"""
            assert response.status_code == 200
            data = response.json()
            assert 'items' in data
            assert 'total' in data
            assert 'page' in data
            assert 'size' in data
            if expected_total is not None:
                assert data['total'] == expected_total
    
    return APITestHelpers()


# ===============================
# PERFORMANCE TEST FIXTURES
# ===============================

@pytest.fixture(scope="function")
def performance_timer():
    """Timer for performance testing"""
    import time
    
    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            return self.elapsed()
        
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
        
        def assert_under(self, max_seconds: float):
            elapsed = self.elapsed()
            assert elapsed is not None, "Timer not started/stopped"
            assert elapsed < max_seconds, f"Operation took {elapsed:.3f}s, expected under {max_seconds}s"
    
    return PerformanceTimer()


# ===============================
# CLEANUP AND SETUP
# ===============================

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    # Set testing flag
    os.environ['TESTING'] = 'true'
    
    # Configure logging for tests
    import logging
    logging.getLogger('backend').setLevel(logging.WARNING)
    
    yield
    
    # Cleanup after test
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


# ===============================
# PYTEST CONFIGURATION
# ===============================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API endpoint test"
    )
    config.addinivalue_line(
        "markers", "auth: mark test as authentication test"
    )
    config.addinivalue_line(
        "markers", "file_upload: mark test as file upload test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test location/name
        if "test_auth" in item.nodeid:
            item.add_marker(pytest.mark.auth)
        
        if "test_api" in item.nodeid or "api" in item.nodeid:
            item.add_marker(pytest.mark.api)
        
        if "test_file" in item.nodeid or "upload" in item.nodeid:
            item.add_marker(pytest.mark.file_upload)
        
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        
        if "security" in item.nodeid:
            item.add_marker(pytest.mark.security)
