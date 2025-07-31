"""
VHM24R Test Suite

Comprehensive testing framework for VHM24R Order Management System.
Includes unit tests, integration tests, and API endpoint tests.
"""

# Test configuration constants
TEST_DATABASE_URL = "sqlite:///./test.db"
TEST_JWT_SECRET = "test-jwt-secret-key-for-testing-only"
TEST_TELEGRAM_BOT_TOKEN = "test-telegram-bot-token"

# Test data fixtures
TEST_USER_DATA = {
    "telegram_id": 123456789,
    "username": "test_user",
    "first_name": "Test",
    "last_name": "User",
    "role": "user",
    "status": "approved"
}

TEST_ORDER_DATA = {
    "order_number": "test_order_123",
    "machine_code": "test_machine_001",
    "goods_name": "Test Coffee",
    "order_price": 15000,
    "creation_time": "2025-07-31T12:00:00Z"
}

TEST_FILE_DATA = {
    "filename": "test_file.xlsx",
    "original_name": "Test Hardware Orders.xlsx",
    "file_type": "hardware"
}

__version__ = "1.0.0"
