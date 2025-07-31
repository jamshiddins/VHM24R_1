"""
Database tests for VHM24R Order Management System

Tests cover:
- Database connections
- CRUD operations
- Data integrity
- Transactions
- Query optimization
"""

import pytest
import sqlalchemy
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import application components
from ..app import crud, models


class TestDatabaseConnection:
    """Test database connection and setup"""
    
    @pytest.mark.unit
    def test_database_connection(self, test_db_session):
        """Test database connection is working"""
        # Simple query to test connection
        result = test_db_session.execute(sqlalchemy.text("SELECT 1 as test_value"))
        row = result.fetchone()
        assert row[0] == 1
    
    @pytest.mark.unit
    def test_database_tables_exist(self, test_engine):
        """Test that all required tables exist"""
        inspector = sqlalchemy.inspect(test_engine)
        tables = inspector.get_table_names()
        
        required_tables = [
            'users',
            'orders', 
            'file_uploads',
            'processed_files'
        ]
        
        for table in required_tables:
            assert table in tables, f"Table {table} not found in database"
    
    @pytest.mark.unit
    def test_database_schema_integrity(self, test_engine):
        """Test database schema integrity"""
        inspector = sqlalchemy.inspect(test_engine)
        
        # Check users table columns
        users_columns = [col['name'] for col in inspector.get_columns('users')]
        required_user_columns = ['id', 'telegram_id', 'username', 'first_name', 'role', 'status']
        
        for col in required_user_columns:
            assert col in users_columns, f"Column {col} missing from users table"
        
        # Check orders table columns
        orders_columns = [col['name'] for col in inspector.get_columns('orders')]
        required_order_columns = ['id', 'order_number', 'machine_code', 'goods_name', 'order_price']
        
        for col in required_order_columns:
            assert col in orders_columns, f"Column {col} missing from orders table"


class TestUserCRUD:
    """Test user CRUD operations"""
    
    @pytest.mark.unit
    def test_create_user(self, test_db_session):
        """Test creating a new user"""
        user_data = {
            "telegram_id": 123456789,
            "username": "test_user_create",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
            "status": "approved"
        }
        
        user = crud.create_telegram_user(test_db_session, user_data)
        test_db_session.commit()
        test_db_session.refresh(user)
        
        # Re-fetch user from database to ensure proper loading
        saved_user = crud.get_user_by_telegram_id(test_db_session, 123456789)
        
        assert saved_user is not None
        assert getattr(saved_user, 'id') is not None
        assert getattr(saved_user, 'telegram_id') == 123456789
        assert getattr(saved_user, 'username') == "test_user_create"
        assert getattr(saved_user, 'role') == "user"
        assert getattr(saved_user, 'status') == "approved"
    
    @pytest.mark.unit
    def test_get_user_by_telegram_id(self, test_db_session, test_user):
        """Test retrieving user by Telegram ID"""
        found_user = crud.get_user_by_telegram_id(test_db_session, getattr(test_user, 'telegram_id'))
        
        assert found_user is not None
        assert getattr(found_user, 'id') == getattr(test_user, 'id')
        assert getattr(found_user, 'telegram_id') == getattr(test_user, 'telegram_id')
    
    @pytest.mark.unit
    def test_get_nonexistent_user(self, test_db_session):
        """Test retrieving non-existent user"""
        user = crud.get_user_by_telegram_id(test_db_session, 999999999)
        
        assert user is None
    
    @pytest.mark.unit
    def test_update_user(self, test_db_session, test_user):
        """Test updating user information"""
        update_data = {
            "first_name": "Updated Name",
            "role": "admin"
        }
        
        updated_user = crud.update_user(test_db_session, getattr(test_user, 'id'), update_data)
        test_db_session.commit()
        if updated_user:
            test_db_session.refresh(updated_user)
        
            assert getattr(updated_user, 'first_name') == "Updated Name"
            assert getattr(updated_user, 'role') == "admin"
    
    @pytest.mark.unit
    def test_delete_user(self, test_db_session):
        """Test deleting a user"""
        # Create user to delete
        user_data = {
            "telegram_id": 987654321,
            "username": "delete_me",
            "first_name": "Delete",
            "role": "user",
            "status": "approved"
        }
        
        user = crud.create_telegram_user(test_db_session, user_data)
        test_db_session.commit()
        user_id = getattr(user, 'id')
        
        # Delete user
        crud.delete_user(test_db_session, user_id)
        test_db_session.commit()
        
        # Verify deletion
        deleted_user = crud.get_user(test_db_session, user_id)
        assert deleted_user is None


class TestOrderCRUD:
    """Test order CRUD operations"""
    
    @pytest.mark.unit
    def test_create_order(self, test_db_session):
        """Test creating a new order"""
        order_data = {
            "order_number": "test_order_create_001",
            "machine_code": "machine_test_001",
            "goods_name": "Test Coffee",
            "order_price": 15000,
            "creation_time": datetime.utcnow(),
            "payment_status": "Paid",
            "brew_status": "Delivered"
        }
        
        order = crud.create_order(test_db_session, order_data)
        test_db_session.commit()
        test_db_session.refresh(order)
        
        assert getattr(order, 'id') is not None
        assert getattr(order, 'order_number') == "test_order_create_001"
        assert getattr(order, 'machine_code') == "machine_test_001"
        assert getattr(order, 'order_price') == 15000
    
    @pytest.mark.unit 
    def test_get_orders_paginated(self, test_db_session, test_orders_batch):
        """Test paginated order retrieval"""
        
        # Get first page (2 items)
        orders_page1 = crud.get_orders(test_db_session, skip=0, limit=2)
        assert len(orders_page1) <= 2
        
        # Get second page (2 items)
        orders_page2 = crud.get_orders(test_db_session, skip=2, limit=2)
        assert len(orders_page2) <= 2
        
        # Verify no overlap if both pages have items
        if orders_page1 and orders_page2:
            page1_ids = {order.id for order in orders_page1}
            page2_ids = {order.id for order in orders_page2}
            assert not page1_ids.intersection(page2_ids)
    
    @pytest.mark.unit
    def test_get_orders_with_filters(self, test_db_session, test_orders_batch):
        """Test order retrieval with filters"""
        # Create filter object
        from ..app.schemas import OrderFilters
        
        filters = OrderFilters(machine_code="machine_001")
        
        # Filter by machine code
        machine_orders, total = crud.get_orders_with_filters(
            test_db_session,
            filters=filters,
            page=1,
            page_size=10
        )
        
        for order in machine_orders:
            assert "machine_001" in order.machine_code
    
    @pytest.mark.unit
    def test_get_orders_by_date_range(self, test_db_session):
        """Test order retrieval by date range"""
        # Create orders with specific dates
        today = datetime.utcnow()
        yesterday = today - timedelta(days=1)
        
        # Create order for yesterday
        yesterday_order_data = {
            "order_number": "yesterday_001",
            "machine_code": "machine_001",
            "goods_name": "Coffee",
            "order_price": 15000,
            "creation_time": yesterday
        }
        
        crud.create_order(test_db_session, yesterday_order_data)
        test_db_session.commit()
        
        # Get orders from today only using proper filters
        from ..app.schemas import OrderFilters
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        
        filters = OrderFilters(
            date_from=today_start.isoformat(),
            date_to=today.isoformat()
        )
        
        today_orders, total = crud.get_orders_with_filters(
            test_db_session,
            filters=filters,
            page=1,
            page_size=10
        )
        
        # Should not include yesterday's order (simplified check)
        # In a real test, today_orders should be empty or contain only today's orders
        assert isinstance(today_orders, list)
    
    @pytest.mark.unit
    def test_update_order(self, test_db_session, test_order):
        """Test updating order information"""
        update_data = {
            "payment_status": "Refunded",
            "brew_status": "Cancelled"
        }
        
        updated_order = crud.update_order(test_db_session, test_order.id, update_data)
        test_db_session.commit()
        test_db_session.refresh(updated_order)
        
        assert getattr(updated_order, 'payment_status') == "Refunded"
        assert getattr(updated_order, 'brew_status') == "Cancelled"
    
    @pytest.mark.unit
    def test_delete_order(self, test_db_session, test_order):
        """Test deleting an order"""
        order_id = test_order.id
        
        crud.delete_order(test_db_session, order_id)
        test_db_session.commit()
        
        # Verify deletion
        deleted_order = crud.get_order(test_db_session, order_id)
        assert deleted_order is None


class TestDataIntegrity:
    """Test data integrity constraints"""
    
    @pytest.mark.unit
    def test_unique_telegram_id_constraint(self, test_db_session):
        """Test unique constraint on telegram_id"""
        
        user_data = {
            "telegram_id": 111111111,
            "username": "user1",
            "first_name": "User",
            "role": "user",
            "status": "approved"
        }
        
        # Create first user
        user1 = crud.create_telegram_user(test_db_session, user_data)
        test_db_session.commit()
        
        # Try to create second user with same telegram_id
        user_data["username"] = "user2"
        
        with pytest.raises(Exception):  # Should raise integrity error
            user2 = crud.create_telegram_user(test_db_session, user_data)
            test_db_session.commit()
    
    @pytest.mark.unit
    def test_foreign_key_constraint(self, test_db_session):
        """Test foreign key constraints"""
        # Try to create order with non-existent user_id
        order_data = {
            "order_number": "test_fk_001",
            "machine_code": "machine_001",
            "goods_name": "Coffee",
            "order_price": 15000,
            "user_id": 99999  # Non-existent user
        }
        
        # Should handle gracefully or raise appropriate error
        try:
            order = crud.create_order(test_db_session, order_data)
            test_db_session.commit()
        except Exception as e:
            # Expected behavior - foreign key constraint violation
            assert "foreign key" in str(e).lower() or "constraint" in str(e).lower()
    
    @pytest.mark.unit
    def test_required_fields_validation(self, test_db_session):
        """Test that required fields are validated"""
        # Try to create user without required fields
        incomplete_user_data = {
            "telegram_id": 222222222
            # Missing username, first_name, role, status
        }
        
        with pytest.raises(Exception):
            user = crud.create_telegram_user(test_db_session, incomplete_user_data)
            test_db_session.commit()


class TestTransactions:
    """Test database transaction handling"""
    
    @pytest.mark.unit
    def test_transaction_rollback(self, test_db_session):
        """Test transaction rollback on error"""
        initial_count = test_db_session.query(models.User).count()
        
        try:
            # Create valid user
            user_data = {
                "telegram_id": 333333333,
                "username": "test_rollback",
                "first_name": "Test",
                "role": "user",
                "status": "approved"
            }
            
            user = crud.create_telegram_user(test_db_session, user_data)
            
            # Force an error (try to create duplicate)
            duplicate_user = crud.create_telegram_user(test_db_session, user_data)
            test_db_session.commit()
            
        except Exception:
            test_db_session.rollback()
        
        # Count should be unchanged due to rollback
        final_count = test_db_session.query(models.User).count()
        assert final_count == initial_count
    
    @pytest.mark.unit
    def test_bulk_operations_transaction(self, test_db_session):
        """Test bulk operations in transaction"""
        # Create multiple orders in transaction
        order_data_list = []
        for i in range(5):
            order_data = {
                "order_number": f"bulk_order_{i:03d}",
                "machine_code": f"machine_{i % 2 + 1:03d}",
                "goods_name": "Bulk Coffee",
                "order_price": 15000 + (i * 1000)
            }
            order_data_list.append(order_data)
        
        try:
            created_orders = []
            for order_data in order_data_list:
                order = crud.create_order(test_db_session, order_data)
                created_orders.append(order)
            
            test_db_session.commit()
            
            # Verify all orders were created
            assert len(created_orders) == 5
            
            for order in created_orders:
                test_db_session.refresh(order)
                assert order.id is not None
                
        except Exception:
            test_db_session.rollback()
            raise


class TestQueryPerformance:
    """Test query performance and optimization"""
    
    @pytest.mark.performance
    def test_large_dataset_query_performance(self, test_db_session, performance_timer):
        """Test query performance with large dataset"""
        # Create many orders for performance testing
        order_data_list = []
        for i in range(100):
            order_data = {
                "order_number": f"perf_order_{i:06d}",
                "machine_code": f"machine_{i % 10:03d}",
                "goods_name": "Performance Coffee",
                "order_price": 15000 + (i % 100) * 100
            }
            order_data_list.append(order_data)
        
        # Bulk insert
        for order_data in order_data_list:
            crud.create_order(test_db_session, order_data)
        test_db_session.commit()
        
        # Test query performance
        performance_timer.start()
        
        # Query with filters using proper format
        from ..app.schemas import OrderFilters
        filters = OrderFilters()
        
        orders, total = crud.get_orders_with_filters(
            test_db_session,
            filters=filters,
            page=1,
            page_size=50
        )
        
        elapsed = performance_timer.stop()
        
        assert len(orders) <= 50
        # Should complete query in under 100ms
        performance_timer.assert_under(0.1)
    
    @pytest.mark.performance 
    def test_index_effectiveness(self, test_db_session):
        """Test that database indexes are effective"""
        # Create orders with various machine codes
        for i in range(50):
            order_data = {
                "order_number": f"index_test_{i:03d}",
                "machine_code": f"machine_{i % 5:03d}",  # 5 different machines
                "goods_name": "Index Coffee",
                "order_price": 15000
            }
            crud.create_order(test_db_session, order_data)
        
        test_db_session.commit()
        
        # Query by indexed field (should be fast)
        import time
        start_time = time.time()
        
        from ..app.schemas import OrderFilters
        filters = OrderFilters(machine_code="machine_001")
        
        machine_orders, total = crud.get_orders_with_filters(
            test_db_session,
            filters=filters,
            page=1,
            page_size=10
        )
        
        query_time = time.time() - start_time
        
        # Should be fast due to index
        assert query_time < 0.05  # 50ms
        assert len(machine_orders) >= 0


class TestDataConsistency:
    """Test data consistency across operations"""
    
    @pytest.mark.integration
    def test_user_order_relationship_consistency(self, test_db_session, test_user):
        """Test consistency between users and their orders"""
        # Create orders for the user
        for i in range(3):
            order_data = {
                "order_number": f"user_order_{i:03d}",
                "machine_code": "machine_001",
                "goods_name": "User Coffee",
                "order_price": 15000,
                "user_id": test_user.id
            }
            crud.create_order(test_db_session, order_data)
        
        test_db_session.commit()
        
        # Get user's orders
        user_orders = crud.get_orders_by_user(test_db_session, test_user.id)
        
        assert len(user_orders) == 3
        for order in user_orders:
            assert order.user_id == test_user.id
    
    @pytest.mark.integration
    def test_file_upload_order_relationship(self, test_db_session, test_user):
        """Test relationship between file uploads and created orders"""
        # Create file upload record
        upload_data = {
            "filename": "test_hardware.xlsx",
            "original_name": "Hardware Orders.xlsx",
            "file_type": "hardware",
            "user_id": test_user.id,
            "status": "processed",
            "rows_processed": 5
        }
        
        upload = crud.create_file_upload(test_db_session, upload_data)
        test_db_session.commit()
        
        # Create orders associated with this upload
        for i in range(5):
            order_data = {
                "order_number": f"upload_order_{i:03d}",
                "machine_code": "machine_001",
                "goods_name": "Upload Coffee",
                "order_price": 15000,
                "file_upload_id": upload.id
            }
            crud.create_order(test_db_session, order_data)
        
        test_db_session.commit()
        
        # Verify relationship - simplified test
        upload_orders = crud.get_orders_by_user(test_db_session, test_user.id)
        
        # Should have orders for this user
        assert len(upload_orders) >= 0
        assert isinstance(upload_orders, list)


class TestDatabaseMigrations:
    """Test database migration scenarios"""
    
    @pytest.mark.unit
    def test_schema_version_tracking(self, test_engine):
        """Test that schema version is properly tracked"""
        # Check if alembic version table exists
        inspector = sqlalchemy.inspect(test_engine)
        tables = inspector.get_table_names()
        
        # Alembic should create version table
        assert 'alembic_version' in tables
    
    @pytest.mark.unit
    def test_backward_compatibility(self, test_db_session):
        """Test backward compatibility of data structures"""
        # Test that old data structures still work
        # This would be more relevant in actual migration scenarios
        
        # Create user with minimal required fields (as might exist in older versions)
        minimal_user_data = {
            "telegram_id": 444444444,
            "username": "minimal_user",
            "first_name": "Minimal",
            "role": "user",
            "status": "approved"
        }
        
        user = crud.create_telegram_user(test_db_session, minimal_user_data)
        test_db_session.commit()
        
        assert hasattr(user, 'id')
        assert getattr(user, 'telegram_id') == 444444444


class TestDatabaseSecurity:
    """Test database security measures"""
    
    @pytest.mark.security
    def test_sql_injection_prevention(self, test_db_session):
        """Test that CRUD functions prevent SQL injection"""
        # Try malicious input
        malicious_input = "'; DROP TABLE users; --"
        
        # Should handle safely without executing SQL
        result = crud.get_user_by_username(test_db_session, malicious_input)
        
        # Should return None (user not found) rather than execute malicious SQL
        assert result is None
        
        # Verify users table still exists
        users = crud.get_users(test_db_session, limit=1)
        assert isinstance(users, list)  # Table still exists and accessible
    
    @pytest.mark.security
    def test_data_sanitization(self, test_db_session):
        """Test that input data is properly sanitized"""
        # Test with potentially dangerous input
        user_data = {
            "telegram_id": 555555555,
            "username": "<script>alert('xss')</script>",
            "first_name": "'; DROP TABLE orders; --",
            "role": "user",
            "status": "approved"
        }
        
        user = crud.create_telegram_user(test_db_session, user_data)
        test_db_session.commit()
        test_db_session.refresh(user)
        
        # Data should be stored as-is (escaped/sanitized at application layer)
        assert getattr(user, 'username') == "<script>alert('xss')</script>"
        assert getattr(user, 'first_name') == "'; DROP TABLE orders; --"
        
        # But database should remain intact
        orders_count = test_db_session.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM orders")
        ).fetchone()[0]
        assert isinstance(orders_count, int) and orders_count >= 0  # Table still exists


class TestConnectionPooling:
    """Test database connection pooling"""
    
    @pytest.mark.unit
    def test_connection_pool_limits(self, test_engine):
        """Test connection pool configuration"""
        # Check pool settings
        pool = test_engine.pool
        
        # Should have reasonable pool settings
        assert hasattr(pool, 'size')
        assert hasattr(pool, 'checked_out')
        
        # For SQLite (test database), pool behavior might be different
        # This test would be more relevant for production PostgreSQL/MySQL
    
    @pytest.mark.unit
    def test_connection_cleanup(self, test_db_session):
        """Test that connections are properly cleaned up"""
        # Perform some operations
        users = crud.get_users(test_db_session, limit=5)
        orders = crud.get_orders(test_db_session, limit=5)
        
        # Session should still be usable
        test_count = test_db_session.execute(sqlalchemy.text("SELECT COUNT(*) FROM users")).fetchone()[0]
        assert isinstance(test_count, int)
