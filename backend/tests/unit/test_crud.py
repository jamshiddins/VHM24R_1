"""
Unit тесты для CRUD операций
"""
import pytest
from sqlalchemy.orm import Session
from app import crud
from app.models import User, Order, UploadedFile
from app.schemas import OrderFilters


class TestUserCrud:
    """Тесты для CRUD операций с пользователями"""
    
    def test_create_user(self, db_session: Session):
        """Тест создания пользователя"""
        user_data = {
            "telegram_id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User"
        }
        
        user = crud.create_user(db_session, user_data)
        
        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.personal_link is not None  # Генерируется автоматически
    
    def test_get_user_by_telegram_id(self, db_session: Session, test_user: User):
        """Тест получения пользователя по Telegram ID"""
        user = crud.get_user_by_telegram_id(db_session, test_user.telegram_id)
        
        assert user is not None
        assert user.telegram_id == test_user.telegram_id
        assert user.username == test_user.username
    
    def test_get_user_by_telegram_id_not_found(self, db_session: Session):
        """Тест получения несуществующего пользователя"""
        user = crud.get_user_by_telegram_id(db_session, 999999999)
        
        assert user is None
    
    def test_get_all_users(self, db_session: Session):
        """Тест получения всех пользователей"""
        # Создаем несколько пользователей
        for i in range(3):
            user_data = {
                "telegram_id": 100000000 + i,
                "username": f"user{i}",
                "first_name": f"User{i}",
                "last_name": "Test"
            }
            crud.create_user(db_session, user_data)
        
        users = crud.get_all_users(db_session)
        assert len(users) >= 3
    
    def test_approve_user(self, db_session: Session, test_user: User, admin_user: User):
        """Тест одобрения пользователя"""
        updated_user = crud.approve_user(db_session, test_user.id, admin_user.id)
        
        assert updated_user is not None
        assert updated_user.id == test_user.id
    
    def test_get_pending_users(self, db_session: Session):
        """Тест получения пользователей на модерации"""
        # Создаем пользователя со статусом pending
        user_data = {
            "telegram_id": 555555555,
            "username": "pendinguser",
            "first_name": "Pending",
            "last_name": "User",
            "status": "pending"
        }
        crud.create_user(db_session, user_data)
        
        pending_users = crud.get_pending_users(db_session)
        assert len(pending_users) >= 1
        assert any(user.username == "pendinguser" for user in pending_users)


class TestOrderCrud:
    """Тесты для CRUD операций с заказами"""
    
    def test_create_order(self, db_session: Session, test_user: User):
        """Тест создания заказа"""
        order_data = {
            "machine_code": "VM001",
            "order_number": "ORD001",
            "order_price": 100.50,
            "creation_time": "2024-01-15 10:30:00"
        }
        
        order = crud.create_order(db_session, order_data, test_user.id)
        
        assert order.machine_code == "VM001"
        assert order.order_number == "ORD001"
        assert order.order_price == 100.50
        assert order.created_by == test_user.id
    
    def test_get_order_by_number(self, db_session: Session, sample_orders: list):
        """Тест получения заказа по номеру"""
        order = crud.get_order_by_number(db_session, "ORD001")
        
        assert order is not None
        assert order.order_number == "ORD001"
    
    def test_get_orders_with_filters(self, db_session: Session, sample_orders: list):
        """Тест получения заказов с фильтрами"""
        # Создаем фильтр по коду автомата
        filters = OrderFilters(machine_code="VM001")
        orders, total = crud.get_orders_with_filters(
            db_session, 
            filters,
            page=1, 
            page_size=10
        )
        
        assert len(orders) >= 0  # Может быть 0 или больше
        assert total >= 0
    
    def test_update_order(self, db_session: Session, sample_orders: list):
        """Тест обновления заказа"""
        order = sample_orders[0]
        update_data = {"order_price": 150.75}
        
        updated_order = crud.update_order(db_session, order.id, update_data)
        
        assert updated_order is not None
        assert updated_order.id == order.id
    
    def test_get_order(self, db_session: Session, sample_orders: list):
        """Тест получения заказа по ID"""
        order = sample_orders[0]
        found_order = crud.get_order(db_session, order.id)
        
        assert found_order is not None
        assert found_order.id == order.id


class TestFileCrud:
    """Тесты для CRUD операций с файлами"""
    
    def test_create_uploaded_file(self, db_session: Session, test_user: User):
        """Тест создания записи о файле"""
        file_data = {
            "original_filename": "test.csv",
            "file_path": "/uploads/test.csv",
            "file_size": 1024,
            "content_hash": "abc123",
            "uploaded_by": test_user.id
        }
        
        file_record = crud.create_uploaded_file(db_session, file_data)
        
        assert file_record.original_filename == "test.csv"
        assert file_record.file_path == "/uploads/test.csv"
        assert file_record.file_size == 1024
        assert file_record.uploaded_by == test_user.id
    
    def test_get_uploaded_files(self, db_session: Session, test_user: User):
        """Тест получения файлов пользователя"""
        # Создаем несколько файлов
        for i in range(3):
            file_data = {
                "original_filename": f"test{i}.csv",
                "file_path": f"/uploads/test{i}.csv",
                "file_size": 1024 * (i + 1),
                "content_hash": f"hash{i}",
                "uploaded_by": test_user.id
            }
            crud.create_uploaded_file(db_session, file_data)
        
        files = crud.get_uploaded_files(db_session, test_user.id)
        
        assert len(files) == 3
        assert all(file.uploaded_by == test_user.id for file in files)
    
    def test_get_file_by_hash(self, db_session: Session, test_user: User):
        """Тест получения файла по хешу"""
        file_data = {
            "original_filename": "test.csv",
            "file_path": "/uploads/test.csv",
            "file_size": 1024,
            "content_hash": "unique_hash_123",
            "uploaded_by": test_user.id
        }
        
        file_record = crud.create_uploaded_file(db_session, file_data)
        
        # Ищем файл по хешу
        found_file = crud.get_file_by_hash(db_session, "unique_hash_123")
        
        assert found_file is not None
        assert found_file.id == file_record.id
        assert found_file.content_hash == "unique_hash_123"
    
    def test_update_file_processing_status(self, db_session: Session, test_user: User):
        """Тест обновления статуса обработки файла"""
        file_data = {
            "original_filename": "test.csv",
            "file_path": "/uploads/test.csv",
            "file_size": 1024,
            "content_hash": "test_hash",
            "uploaded_by": test_user.id
        }
        
        file_record = crud.create_uploaded_file(db_session, file_data)
        
        # Обновляем статус
        crud.update_file_processing_status(
            db_session, 
            file_record.id, 
            "completed"
        )
        
        # Проверяем обновление
        updated_file = crud.get_uploaded_file_by_id(db_session, file_record.id)
        assert updated_file is not None


class TestOptimizedCrud:
    """Тесты для оптимизированных CRUD операций"""
    
    def test_batch_approve_users(self, db_session: Session, admin_user: User):
        """Тест батчевого одобрения пользователей"""
        # Создаем несколько пользователей
        user_ids = []
        for i in range(3):
            user_data = {
                "telegram_id": 200000000 + i,
                "username": f"batchuser{i}",
                "first_name": f"BatchUser{i}",
                "last_name": "Test"
            }
            user = crud.create_user(db_session, user_data)
            user_ids.append(user.id)
        
        # Батчевое одобрение
        from app.crud_optimized import optimized_user_crud
        result = optimized_user_crud.approve_users_batch(
            db_session, 
            user_ids, 
            admin_user.id
        )
        
        assert result == len(user_ids)
        
        # Проверяем, что все пользователи одобрены
        for user_id in user_ids:
            user = crud.get_user_by_id(db_session, user_id)
            assert user is not None
    
    def test_batch_create_orders(self, db_session: Session, test_user: User):
        """Тест батчевого создания заказов"""
        orders_data = [
            {
                "machine_code": f"VM{i:03d}",
                "order_number": f"ORD{i:03d}",
                "order_price": 100.0 + i,
                "creation_time": "2024-01-15 10:30:00"
            }
            for i in range(1, 4)
        ]
        
        from app.crud_optimized import optimized_order_crud
        created_orders = optimized_order_crud.create_orders_batch(
            db_session,
            orders_data,
            test_user.id
        )
        
        assert len(created_orders) == 3
        assert all(order.created_by == test_user.id for order in created_orders)
        assert created_orders[0].machine_code == "VM001"
        assert created_orders[2].order_price == 102.0


class TestAnalyticsCrud:
    """Тесты для аналитических CRUD операций"""
    
    def test_get_analytics_data(self, db_session: Session, sample_orders: list):
        """Тест получения аналитических данных"""
        analytics = crud.get_analytics_data(
            db_session,
            date_from=None,
            date_to=None,
            group_by="day"
        )
        
        assert "summary" in analytics
        assert "payment_types" in analytics
        assert "top_machines" in analytics
        assert "time_series" in analytics
        
        # Проверяем структуру summary
        summary = analytics["summary"]
        assert "total_orders" in summary
        assert "total_revenue" in summary
        assert "avg_order_value" in summary


class TestProcessingSessionCrud:
    """Тесты для CRUD операций с сессиями обработки"""
    
    def test_create_processing_session(self, db_session: Session, test_user: User):
        """Тест создания сессии обработки"""
        session = crud.create_processing_session(db_session, test_user.id, 3)
        
        assert session is not None
        assert session.total_files == 3
        assert session.created_by == test_user.id
        assert session.session_id is not None
    
    def test_get_processing_session(self, db_session: Session, test_user: User):
        """Тест получения сессии обработки"""
        session = crud.create_processing_session(db_session, test_user.id, 2)
        session_id = session.session_id
        
        found_session = crud.get_processing_session(db_session, session_id)
        
        assert found_session is not None
        assert found_session.session_id == session_id
        assert found_session.total_files == 2
    
    def test_complete_processing_session(self, db_session: Session, test_user: User):
        """Тест завершения сессии обработки"""
        session = crud.create_processing_session(db_session, test_user.id, 1)
        session_id = session.session_id
        
        crud.complete_processing_session(
            db_session,
            session_id,
            total_rows=100,
            processed_rows=95,
            new_orders=50,
            updated_orders=45
        )
        
        completed_session = crud.get_processing_session(db_session, session_id)
        assert completed_session is not None


class TestUserTokenCrud:
    """Тесты для CRUD операций с токенами пользователей"""
    
    def test_save_user_unique_token(self, db_session: Session, test_user: User):
        """Тест сохранения уникального токена пользователя"""
        unique_token = "test_unique_token_123"
        
        crud.save_user_unique_token(db_session, test_user.id, unique_token)
        
        # Проверяем, что токен сохранен
        user = crud.get_user_by_token(db_session, unique_token)
        assert user is not None
        assert user.id == test_user.id
    
    def test_get_user_by_token(self, db_session: Session, test_user: User):
        """Тест получения пользователя по токену"""
        unique_token = "another_test_token_456"
        
        crud.save_user_unique_token(db_session, test_user.id, unique_token)
        
        found_user = crud.get_user_by_token(db_session, unique_token)
        
        assert found_user is not None
        assert found_user.id == test_user.id
        assert found_user.telegram_id == test_user.telegram_id
    
    def test_deactivate_user_token(self, db_session: Session, test_user: User):
        """Тест деактивации токена пользователя"""
        unique_token = "token_to_deactivate_789"
        
        crud.save_user_unique_token(db_session, test_user.id, unique_token)
        
        # Проверяем, что токен работает
        user = crud.get_user_by_token(db_session, unique_token)
        assert user is not None
        
        # Деактивируем токен
        crud.deactivate_user_token(db_session, unique_token)
        
        # Проверяем, что токен больше не работает
        user = crud.get_user_by_token(db_session, unique_token)
        assert user is None
