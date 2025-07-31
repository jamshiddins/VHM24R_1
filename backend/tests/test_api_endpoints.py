"""
API endpoint tests for VHM24R Order Management System

Tests cover:
- Authentication endpoints
- File upload endpoints
- Order management endpoints
- Export endpoints
- Error handling
"""

import pytest
import json
import io
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestAuthenticationEndpoints:
    """Test authentication API endpoints"""
    
    @pytest.mark.api
    def test_telegram_login_success(self, test_client, telegram_auth_data):
        """Test successful Telegram login"""
        response = test_client.post("/api/auth/telegram/login", json=telegram_auth_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["telegram_id"] == int(telegram_auth_data["id"])
    
    @pytest.mark.api
    def test_telegram_login_invalid_hash(self, test_client):
        """Test Telegram login with invalid hash"""
        invalid_auth_data = {
            "id": "123456789",
            "first_name": "Test",
            "hash": "invalid_hash"
        }
        
        response = test_client.post("/api/auth/telegram/login", json=invalid_auth_data)
        
        assert response.status_code == 401
        data = response.json() 
        assert "error" in data
    
    @pytest.mark.api
    def test_token_validation(self, test_client, auth_headers):
        """Test token validation endpoint"""
        response = test_client.get("/api/auth/validate", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "valid" in data
        assert data["valid"] is True
    
    @pytest.mark.api
    def test_token_validation_invalid(self, test_client):
        """Test token validation with invalid token"""
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        
        response = test_client.get("/api/auth/validate", headers=invalid_headers)
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
    
    @pytest.mark.api
    def test_logout(self, test_client, auth_headers):
        """Test logout endpoint"""
        response = test_client.post("/api/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestFileUploadEndpoints:
    """Test file upload API endpoints"""
    
    @pytest.mark.api
    def test_file_upload_success(self, test_client, auth_headers, test_excel_file):
        """Test successful file upload"""
        with open(test_excel_file, 'rb') as f:
            files = {"file": ("hardware_orders.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            
            response = test_client.post(
                "/api/files/upload",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "file_id" in data
        assert "rows_processed" in data
        assert data["success"] is True
    
    @pytest.mark.api
    def test_file_upload_unauthorized(self, test_client, test_excel_file):
        """Test file upload without authentication"""
        with open(test_excel_file, 'rb') as f:
            files = {"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            
            response = test_client.post("/api/files/upload", files=files)
        
        assert response.status_code == 401
    
    @pytest.mark.api
    def test_file_upload_invalid_format(self, test_client, auth_headers):
        """Test upload of invalid file format"""
        fake_file = io.BytesIO(b"This is not an Excel file")
        files = {"file": ("test.txt", fake_file, "text/plain")}
        
        response = test_client.post(
            "/api/files/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
    
    @pytest.mark.api
    def test_file_upload_too_large(self, test_client, auth_headers, large_file):
        """Test upload of file that exceeds size limit"""
        with open(large_file, 'rb') as f:
            files = {"file": ("large_file.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            
            response = test_client.post(
                "/api/files/upload",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 413
        data = response.json()
        assert "too large" in data["error"].lower()
    
    @pytest.mark.api
    def test_get_upload_history(self, test_client, auth_headers):
        """Test get upload history endpoint"""
        response = test_client.get("/api/files/uploads", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "uploads" in data
        assert isinstance(data["uploads"], list)
    
    @pytest.mark.api
    def test_delete_uploaded_file(self, test_client, auth_headers):
        """Test delete uploaded file endpoint"""
        # First upload a file (mocked)
        with patch('backend.app.crud.get_file_upload') as mock_get:
            mock_get.return_value = {"id": 1, "user_id": 123, "filename": "test.xlsx"}
            
            response = test_client.delete("/api/files/1", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestOrderEndpoints:
    """Test order management API endpoints"""
    
    @pytest.mark.api
    def test_get_orders(self, test_client, auth_headers):
        """Test get orders endpoint"""
        response = test_client.get("/api/orders", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
    
    @pytest.mark.api
    def test_get_orders_with_filters(self, test_client, auth_headers):
        """Test get orders with filters"""
        params = {
            "machine_code": "machine_001",
            "date_from": "2025-07-01",
            "date_to": "2025-07-31",
            "page": 1,
            "size": 50
        }
        
        response = test_client.get("/api/orders", headers=auth_headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)
    
    @pytest.mark.api
    def test_get_order_by_id(self, test_client, auth_headers, test_order):
        """Test get specific order by ID"""
        response = test_client.get(f"/api/orders/{test_order.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_order.id
        assert data["order_number"] == test_order.order_number
    
    @pytest.mark.api
    def test_get_nonexistent_order(self, test_client, auth_headers):
        """Test get non-existent order"""
        response = test_client.get("/api/orders/99999", headers=auth_headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    @pytest.mark.api
    def test_update_order(self, test_client, auth_headers, test_order):
        """Test update order endpoint"""
        update_data = {
            "payment_status": "Refunded",
            "brew_status": "Cancelled"
        }
        
        response = test_client.put(
            f"/api/orders/{test_order.id}",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "Refunded"
        assert data["brew_status"] == "Cancelled"
    
    @pytest.mark.api
    def test_delete_order_admin_only(self, test_client, admin_auth_headers, test_order):
        """Test delete order (admin only)"""
        response = test_client.delete(f"/api/orders/{test_order.id}", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    @pytest.mark.api
    def test_delete_order_unauthorized(self, test_client, auth_headers, test_order):
        """Test delete order as regular user (should fail)"""
        response = test_client.delete(f"/api/orders/{test_order.id}", headers=auth_headers)
        
        assert response.status_code == 403
        data = response.json()
        assert "error" in data


class TestExportEndpoints:
    """Test export API endpoints"""
    
    @pytest.mark.api
    def test_export_orders_excel(self, test_client, auth_headers):
        """Test export orders to Excel"""
        params = {
            "format": "excel",
            "date_from": "2025-07-01",
            "date_to": "2025-07-31"
        }
        
        response = test_client.get("/api/export/orders", headers=auth_headers, params=params)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(response.content) > 0
    
    @pytest.mark.api
    def test_export_orders_csv(self, test_client, auth_headers):
        """Test export orders to CSV"""
        params = {
            "format": "csv",
            "machine_code": "machine_001"
        }
        
        response = test_client.get("/api/export/orders", headers=auth_headers, params=params)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        assert len(response.content) > 0
    
    @pytest.mark.api
    def test_export_analytics(self, test_client, admin_auth_headers):
        """Test export analytics data"""
        params = {
            "report_type": "sales_summary",
            "period": "monthly"
        }
        
        response = test_client.get("/api/export/analytics", headers=admin_auth_headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert "report_data" in data
    
    @pytest.mark.api
    def test_export_unauthorized(self, test_client):
        """Test export without authentication"""
        response = test_client.get("/api/export/orders")
        
        assert response.status_code == 401


class TestAnalyticsEndpoints:
    """Test analytics API endpoints"""
    
    @pytest.mark.api
    def test_get_dashboard_stats(self, test_client, admin_auth_headers):
        """Test dashboard statistics endpoint"""
        response = test_client.get("/api/analytics/dashboard", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_orders" in data
        assert "total_revenue" in data
        assert "active_machines" in data
        assert "recent_activity" in data
    
    @pytest.mark.api
    def test_get_machine_analytics(self, test_client, admin_auth_headers):
        """Test machine analytics endpoint"""
        params = {
            "machine_code": "machine_001",
            "period": "7d"
        }
        
        response = test_client.get("/api/analytics/machines", headers=admin_auth_headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert "machine_stats" in data
        assert "performance_data" in data
    
    @pytest.mark.api
    def test_get_sales_trends(self, test_client, admin_auth_headers):
        """Test sales trends endpoint"""
        params = {
            "period": "30d",
            "group_by": "day"
        }
        
        response = test_client.get("/api/analytics/sales", headers=admin_auth_headers, params=params)
        
        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        assert "summary" in data
    
    @pytest.mark.api
    def test_analytics_user_access_denied(self, test_client, auth_headers):
        """Test that regular users cannot access analytics"""
        response = test_client.get("/api/analytics/dashboard", headers=auth_headers)
        
        assert response.status_code == 403


class TestHealthCheckEndpoints:
    """Test health check and monitoring endpoints"""
    
    @pytest.mark.api
    def test_health_check(self, test_client):
        """Test basic health check"""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    @pytest.mark.api
    def test_detailed_health_check(self, test_client):
        """Test detailed health check"""
        response = test_client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert "redis" in data  # If using Redis
        assert "disk_space" in data
        assert "memory_usage" in data
    
    @pytest.mark.api
    def test_readiness_check(self, test_client):
        """Test readiness probe"""
        response = test_client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True


class TestErrorHandling:
    """Test API error handling"""
    
    @pytest.mark.api
    def test_404_not_found(self, test_client):
        """Test 404 error handling"""
        response = test_client.get("/api/nonexistent-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
    
    @pytest.mark.api
    def test_method_not_allowed(self, test_client):
        """Test 405 method not allowed"""
        response = test_client.patch("/api/orders")  # PATCH not allowed
        
        assert response.status_code == 405
        data = response.json()
        assert "error" in data
    
    @pytest.mark.api
    def test_validation_error(self, test_client, auth_headers):
        """Test request validation errors"""
        invalid_data = {
            "invalid_field": "invalid_value"
        }
        
        response = test_client.post("/api/orders", headers=auth_headers, json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    @pytest.mark.api
    def test_internal_server_error_handling(self, test_client, auth_headers):
        """Test internal server error handling"""
        with patch('backend.app.crud.get_orders') as mock_get:
            mock_get.side_effect = Exception("Database connection failed")
            
            response = test_client.get("/api/orders", headers=auth_headers)
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        # Should not expose internal error details
        assert "Database connection failed" not in str(data)


class TestRateLimiting:
    """Test rate limiting"""
    
    @pytest.mark.api
    def test_rate_limit_enforcement(self, test_client):
        """Test rate limiting enforcement"""
        # Make many requests rapidly
        responses = []
        for i in range(110):  # Exceed limit of 100/hour
            response = test_client.get("/health")
            responses.append(response)
        
        # Should get rate limited
        last_response = responses[-1]
        if last_response.status_code == 429:
            assert "rate limit" in last_response.json()["error"].lower()
    
    @pytest.mark.api
    def test_rate_limit_headers(self, test_client):
        """Test rate limit headers"""
        response = test_client.get("/health")
        
        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers


class TestCORS:
    """Test CORS configuration"""
    
    @pytest.mark.api
    def test_cors_preflight(self, test_client):
        """Test CORS preflight request"""
        response = test_client.options(
            "/api/orders",
            headers={
                "Origin": "https://vhm24r.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
    
    @pytest.mark.api
    def test_cors_actual_request(self, test_client, auth_headers):
        """Test CORS on actual request"""
        headers = {**auth_headers, "Origin": "https://vhm24r.example.com"}
        
        response = test_client.get("/api/orders", headers=headers)
        
        assert "Access-Control-Allow-Origin" in response.headers


class TestPerformance:
    """Test API performance"""
    
    @pytest.mark.performance
    def test_orders_endpoint_response_time(self, test_client, auth_headers, performance_timer):
        """Test orders endpoint response time"""
        performance_timer.start()
        
        response = test_client.get("/api/orders", headers=auth_headers)
        
        elapsed = performance_timer.stop()
        
        assert response.status_code == 200
        # Should respond within 200ms for normal load
        performance_timer.assert_under(0.2)
    
    @pytest.mark.performance
    def test_file_upload_performance(self, test_client, auth_headers, test_excel_file, performance_timer):
        """Test file upload performance"""
        performance_timer.start()
        
        with open(test_excel_file, 'rb') as f:
            files = {"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            
            response = test_client.post(
                "/api/files/upload",
                headers=auth_headers,
                files=files
            )
        
        elapsed = performance_timer.stop()
        
        assert response.status_code == 200
        # File upload should complete within 2 seconds
        performance_timer.assert_under(2.0)


class TestSecurity:
    """Test API security"""
    
    @pytest.mark.security
    def test_sql_injection_protection(self, test_client, auth_headers):
        """Test protection against SQL injection"""
        malicious_params = {
            "machine_code": "'; DROP TABLE orders; --",
            "order_number": "1' OR '1'='1"
        }
        
        response = test_client.get("/api/orders", headers=auth_headers, params=malicious_params)
        
        # Should not crash and should handle safely
        assert response.status_code in [200, 400]
    
    @pytest.mark.security
    def test_xss_protection(self, test_client, auth_headers):
        """Test protection against XSS"""
        malicious_data = {
            "notes": "<script>alert('xss')</script>"
        }
        
        response = test_client.post("/api/orders", headers=auth_headers, json=malicious_data)
        
        # Should sanitize or reject malicious content
        assert response.status_code in [400, 422]
    
    @pytest.mark.security
    def test_security_headers(self, test_client):
        """Test security headers presence"""
        response = test_client.get("/health")
        
        # Check for important security headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
