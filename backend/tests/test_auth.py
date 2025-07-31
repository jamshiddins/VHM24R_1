"""
Unit and integration tests for VHM24R authentication system

Tests cover:
- JWT authentication
- Telegram authentication  
- Token validation
- User management
- Security edge cases
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# We'll use relative imports since we're in the tests directory
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.auth import (
    BaseAuthService,
    AuthResult,
    AuthStatus,
    AuthCredentials,
    JWTService,
    JWTCredentials,
    TelegramAuthService,
    TelegramCredentials,
    SessionAuthService,
    jwt_service,
    telegram_auth_service
)
from app.utils.exceptions import AuthenticationError, ValidationError


class TestJWTService:
    """Test cases for JWT authentication service"""
    
    def setup_method(self):
        """Setup test environment"""
        self.jwt_service = JWTService()
        # Use test secret key
        self.jwt_service.secret_key = "test-jwt-secret-key-for-testing"
        self.jwt_service.access_token_lifetime = 3600  # 1 hour
        self.jwt_service.refresh_token_lifetime = 86400  # 1 day
    
    @pytest.mark.unit
    def test_create_access_token(self):
        """Test JWT access token creation"""
        user_data = {
            'user_id': 123,
            'username': 'test_user',
            'role': 'user',
            'status': 'active'
        }
        
        token = self.jwt_service.create_access_token(user_data)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
        
        # Verify token can be decoded
        payload = self.jwt_service._decode_token(token)
        assert payload is not None
        assert payload.get('user_id') == 123
        assert payload.get('username') == 'test_user'
        assert payload.get('type') == 'access'
    
    @pytest.mark.unit
    def test_create_refresh_token(self):
        """Test JWT refresh token creation"""
        user_data = {
            'user_id': 123,
            'username': 'test_user',
            'role': 'user'
        }
        
        token = self.jwt_service.create_refresh_token(user_data)
        
        assert isinstance(token, str)
        payload = self.jwt_service._decode_token(token)
        assert payload is not None
        assert payload.get('user_id') == 123
        assert payload.get('type') == 'refresh'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful JWT authentication"""
        user_data = {
            'user_id': 123,
            'username': 'test_user',
            'role': 'admin',
            'status': 'active'
        }
        
        credentials = JWTCredentials(user_data)
        result = await self.jwt_service.authenticate(credentials)
        
        assert result.is_success
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.user_info is not None
        assert result.user_info['id'] == 123
        assert result.user_info['role'] == 'admin'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self):
        """Test authentication with invalid credentials"""
        # Missing required user_id
        invalid_data = {'username': 'test_user'}
        credentials = JWTCredentials(invalid_data)
        
        result = await self.jwt_service.authenticate(credentials)
        
        assert not result.is_success
        assert result.status == AuthStatus.FAILED
        assert result.error_message is not None
        assert "Invalid credentials" in result.error_message
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_token_success(self):
        """Test successful token validation"""
        user_data = {'user_id': 123, 'username': 'test_user'}
        token = self.jwt_service.create_access_token(user_data)
        
        result = await self.jwt_service.validate_token(token)
        
        assert result.is_success
        assert result.user_info is not None
        assert result.user_info['id'] == 123
        assert result.user_info['username'] == 'test_user'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_token_expired(self):
        """Test validation of expired token"""
        # Create token that expires immediately
        user_data = {'user_id': 123}
        self.jwt_service.access_token_lifetime = -1  # Expired
        
        token = self.jwt_service.create_access_token(user_data)
        time.sleep(0.1)  # Ensure token is expired
        
        result = await self.jwt_service.validate_token(token)
        
        assert not result.is_success
        assert result.status == AuthStatus.EXPIRED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_token_invalid(self):
        """Test validation of invalid token"""
        invalid_token = "invalid.jwt.token"
        
        result = await self.jwt_service.validate_token(invalid_token)
        
        assert not result.is_success
        assert result.status == AuthStatus.FAILED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh"""
        user_data = {'user_id': 123, 'username': 'test_user'}
        refresh_token = self.jwt_service.create_refresh_token(user_data)
        
        result = await self.jwt_service.refresh_token(refresh_token)
        
        assert result.is_success
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.user_info is not None
        assert result.user_info['id'] == 123
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_invalid_type(self):
        """Test refresh with access token (wrong type)"""
        user_data = {'user_id': 123}
        access_token = self.jwt_service.create_access_token(user_data)
        
        result = await self.jwt_service.refresh_token(access_token)
        
        assert not result.is_success
        assert result.error_message is not None
        assert "Invalid refresh token" in result.error_message
    
    @pytest.mark.unit
    def test_extract_user_id(self):
        """Test user ID extraction from token"""
        user_data = {'user_id': 456, 'username': 'test'}
        token = self.jwt_service.create_access_token(user_data)
        
        user_id = self.jwt_service.extract_user_id(token)
        
        assert user_id == 456
    
    @pytest.mark.unit
    def test_extract_user_id_invalid_token(self):
        """Test user ID extraction from invalid token"""
        invalid_token = "invalid.token"
        
        user_id = self.jwt_service.extract_user_id(invalid_token)
        
        assert user_id is None
    
    @pytest.mark.unit
    def test_is_token_valid_format(self):
        """Test token format validation"""
        user_data = {'user_id': 123}
        valid_token = self.jwt_service.create_access_token(user_data)
        invalid_token = "not.a.jwt"
        
        assert self.jwt_service.is_token_valid_format(valid_token)
        assert not self.jwt_service.is_token_valid_format(invalid_token)
    
    @pytest.mark.unit
    def test_get_token_expiry(self):
        """Test token expiry extraction"""
        user_data = {'user_id': 123}
        token = self.jwt_service.create_access_token(user_data)
        
        expiry = self.jwt_service.get_token_expiry(token)
        
        assert isinstance(expiry, datetime)
        assert expiry > datetime.utcnow()


class TestTelegramAuthService:
    """Test cases for Telegram authentication service"""
    
    def setup_method(self):
        """Setup test environment"""
        self.telegram_service = TelegramAuthService()
        self.telegram_service.bot_token = "test-telegram-bot-token"
    
    @pytest.mark.unit
    def test_verify_telegram_auth_success(self):
        """Test successful Telegram auth verification"""
        import hashlib
        import hmac
        
        # Create valid auth data
        auth_data = {
            'id': '123456789',
            'first_name': 'Test',
            'username': 'test_user',
            'auth_date': str(int(time.time()))
        }
        
        # Generate valid hash
        data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(auth_data.items())])
        bot_token = self.telegram_service.bot_token
        assert bot_token is not None
        secret_key = hashlib.sha256(bot_token.encode()).digest()
        auth_data['hash'] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        result = self.telegram_service._verify_telegram_auth(auth_data)
        
        assert result is True
    
    @pytest.mark.unit
    def test_verify_telegram_auth_invalid_hash(self):
        """Test Telegram auth with invalid hash"""
        auth_data = {
            'id': '123456789',
            'first_name': 'Test',
            'hash': 'invalid_hash'
        }
        
        result = self.telegram_service._verify_telegram_auth(auth_data)
        
        assert result is False
    
    @pytest.mark.unit
    def test_verify_telegram_auth_missing_hash(self):
        """Test Telegram auth with missing hash"""
        auth_data = {
            'id': '123456789',
            'first_name': 'Test'
        }
        
        result = self.telegram_service._verify_telegram_auth(auth_data)
        
        assert result is False
    
    @pytest.mark.unit
    def test_verify_telegram_auth_no_bot_token(self):
        """Test Telegram auth when bot token is not configured"""
        self.telegram_service.bot_token = None
        
        auth_data = {
            'id': '123456789',
            'hash': 'some_hash'
        }
        
        result = self.telegram_service._verify_telegram_auth(auth_data)
        
        assert result is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self):
        """Test Telegram authentication with invalid credentials"""
        # Missing required fields
        invalid_data = {'id': '123'}
        credentials = TelegramCredentials(invalid_data)
        
        result = await self.telegram_service.authenticate(credentials)
        
        assert not result.is_success
        assert result.status == AuthStatus.FAILED
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_token_delegates_to_jwt(self):
        """Test that token validation is delegated to JWT service"""
        token = "test.jwt.token"
        
        with patch.object(self.telegram_service.jwt_service, 'validate_token') as mock_validate:
            mock_validate.return_value = AuthResult(status=AuthStatus.SUCCESS)
            
            result = await self.telegram_service.validate_token(token)
            
            mock_validate.assert_called_once_with(token)
            assert result.status == AuthStatus.SUCCESS
    
    @pytest.mark.unit
    def test_create_access_token_backward_compatibility(self):
        """Test backward compatibility method"""
        user_id = 123
        
        with patch.object(self.telegram_service.jwt_service, 'create_access_token') as mock_create:
            mock_create.return_value = "test.jwt.token"
            
            token = self.telegram_service.create_access_token(user_id)
            
            mock_create.assert_called_once_with({'user_id': user_id})
            assert token == "test.jwt.token"
    
    @pytest.mark.unit
    def test_verify_token_backward_compatibility(self):
        """Test backward compatibility token verification"""
        token = "test.jwt.token"
        
        with patch.object(self.telegram_service.jwt_service, '_decode_token') as mock_decode:
            mock_decode.return_value = {'user_id': 123, 'username': 'test'}
            
            result = self.telegram_service.verify_token(token)
            
            mock_decode.assert_called_once_with(token)
            assert result is not None
            assert result.get('user_id') == 123
    
    @pytest.mark.unit
    def test_verify_token_invalid(self):
        """Test backward compatibility with invalid token"""
        token = "invalid.token"
        
        with patch.object(self.telegram_service.jwt_service, '_decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")
            
            result = self.telegram_service.verify_token(token)
            
            assert result is None


class TestSessionAuthService:
    """Test cases for session authentication service"""
    
    def setup_method(self):
        """Setup test environment"""
        self.session_service = SessionAuthService()
        self.session_service.session_lifetime = 3600  # 1 hour for testing
    
    @pytest.mark.unit
    def test_create_session(self):
        """Test session creation"""
        user_info = {'id': 123, 'username': 'test_user'}
        
        session_token = self.session_service.create_session(user_info)
        
        assert isinstance(session_token, str)
        assert len(session_token) == 64  # SHA256 hex length
        
        # Verify session exists
        session_info = self.session_service.get_session(session_token)
        assert session_info is not None
        assert 'user_info' in session_info
        user_info_data = session_info.get('user_info')
        assert user_info_data is not None
        assert isinstance(user_info_data, dict)
        assert user_info_data.get('id') == 123
    
    @pytest.mark.unit
    def test_create_session_with_custom_expiry(self):
        """Test session creation with custom expiry"""
        user_info = {'id': 123, 'username': 'test_user'}
        custom_expiry = 7200  # 2 hours
        
        session_token = self.session_service.create_session(
            user_info, 
            expires_in=custom_expiry
        )
        
        session_info = self.session_service.get_session(session_token)
        assert session_info is not None
        assert isinstance(session_info, dict)
        assert 'expires_at' in session_info
        expected_expiry = datetime.utcnow() + timedelta(seconds=custom_expiry)
        
        # Allow 1 second tolerance for timing
        expires_at_value = session_info.get('expires_at')
        assert expires_at_value is not None, "expires_at should not be None"
        assert isinstance(expires_at_value, datetime), f"expires_at should be datetime, got {type(expires_at_value)}"
        
        # Calculate time difference safely
        if isinstance(expires_at_value, datetime) and isinstance(expected_expiry, datetime):
            time_diff = abs((expires_at_value - expected_expiry).total_seconds())
            assert time_diff < 1, f"Time difference too large: {time_diff}"
    
    @pytest.mark.unit
    def test_get_session_nonexistent(self):
        """Test getting non-existent session"""
        fake_token = "nonexistent_session_token"
        
        session_info = self.session_service.get_session(fake_token)
        
        assert session_info is None
    
    @pytest.mark.unit
    def test_invalidate_session(self):
        """Test session invalidation"""
        user_info = {'id': 123, 'username': 'test_user'}
        session_token = self.session_service.create_session(user_info)
        
        # Session should exist
        assert self.session_service.get_session(session_token) is not None
        
        # Invalidate session
        result = self.session_service.invalidate_session(session_token)
        
        assert result is True
        assert self.session_service.get_session(session_token) is None
    
    @pytest.mark.unit
    def test_invalidate_nonexistent_session(self):
        """Test invalidating non-existent session"""
        fake_token = "nonexistent_session_token"
        
        result = self.session_service.invalidate_session(fake_token)
        
        assert result is False
    
    @pytest.mark.unit
    def test_update_session(self):
        """Test session update"""
        user_info = {'id': 123, 'username': 'test_user'}
        session_token = self.session_service.create_session(user_info)
        
        # Update user info
        new_user_info = {'role': 'admin'}
        result = self.session_service.update_session(
            session_token, 
            user_info=new_user_info
        )
        
        assert result is True
        
        # Verify update
        session_info = self.session_service.get_session(session_token)
        assert session_info is not None
        user_info_data = session_info.get('user_info')
        assert user_info_data is not None
        assert isinstance(user_info_data, dict)
        assert user_info_data.get('role') == 'admin'
        assert user_info_data.get('id') == 123  # Original data preserved
    
    @pytest.mark.unit
    def test_update_session_extend_expiry(self):
        """Test session update with expiry extension"""
        user_info = {'id': 123, 'username': 'test_user'}
        session_token = self.session_service.create_session(user_info)
        
        original_session = self.session_service.get_session(session_token)
        assert original_session is not None
        assert 'expires_at' in original_session
        original_expiry = original_session.get('expires_at')
        assert original_expiry is not None
        
        time.sleep(0.1)  # Small delay
        
        # Update with expiry extension
        result = self.session_service.update_session(
            session_token,
            extend_expiry=True
        )
        
        assert result is True
        
        updated_session = self.session_service.get_session(session_token)
        assert updated_session is not None
        assert 'expires_at' in updated_session
        updated_expiry = updated_session.get('expires_at')
        assert updated_expiry is not None
        assert updated_expiry > original_expiry
    
    @pytest.mark.unit
    def test_get_user_sessions(self):
        """Test getting all sessions for a user"""
        user_id = 123
        user_info = {'id': user_id, 'username': 'test_user'}
        
        # Create multiple sessions for the same user
        tokens = []
        for i in range(3):
            token = self.session_service.create_session(user_info)
            tokens.append(token)
        
        # Create session for different user
        other_user_info = {'id': 456, 'username': 'other_user'}
        self.session_service.create_session(other_user_info)
        
        user_sessions = self.session_service.get_user_sessions(user_id)
        
        assert len(user_sessions) == 3
        for session in user_sessions:
            assert 'session_token' in session
            assert 'created_at' in session
            assert 'expires_at' in session
    
    @pytest.mark.unit
    def test_invalidate_user_sessions(self):
        """Test invalidating all sessions for a user"""
        user_id = 123
        user_info = {'id': user_id, 'username': 'test_user'}
        
        # Create multiple sessions
        tokens = []
        for i in range(3):
            token = self.session_service.create_session(user_info)
            tokens.append(token)
        
        # Invalidate all sessions except one
        exclude_token = tokens[0]
        invalidated_count = self.session_service.invalidate_user_sessions(
            user_id, 
            exclude_token=exclude_token
        )
        
        assert invalidated_count == 2
        
        # Verify excluded token still exists
        assert self.session_service.get_session(exclude_token) is not None
        
        # Verify other tokens are gone
        for token in tokens[1:]:
            assert self.session_service.get_session(token) is None
    
    @pytest.mark.unit
    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions"""
        user_info = {'id': 123, 'username': 'test_user'}
        
        # Create session with very short lifetime
        self.session_service.session_lifetime = 1  # 1 second
        session_token = self.session_service.create_session(user_info)
        
        # Session should exist initially
        assert self.session_service.get_session(session_token) is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Cleanup expired sessions
        cleaned_count = self.session_service.cleanup_expired_sessions()
        
        assert cleaned_count == 1
        assert self.session_service.get_session(session_token) is None
    
    @pytest.mark.unit
    def test_get_sessions_stats(self):
        """Test session statistics"""
        user_info = {'id': 123, 'username': 'test_user'}
        
        # Create some sessions
        for i in range(3):
            self.session_service.create_session(user_info)
        
        stats = self.session_service.get_sessions_stats()
        
        assert 'total_sessions' in stats
        assert 'active_sessions' in stats
        assert 'expired_sessions' in stats
        assert 'last_cleanup' in stats
        assert stats['total_sessions'] == 3
        assert stats['active_sessions'] == 3


class TestAuthCredentials:
    """Test cases for AuthCredentials base class"""
    
    @pytest.mark.unit
    def test_auth_credentials_creation(self):
        """Test AuthCredentials creation"""
        data = {'user_id': 123, 'username': 'test'}
        credentials = AuthCredentials('test_auth', data)
        
        assert credentials.auth_type == 'test_auth'
        assert credentials.data == data
        assert credentials.get('user_id') == 123
        assert credentials.get('nonexistent', 'default') == 'default'
    
    @pytest.mark.unit
    def test_auth_credentials_validation(self):
        """Test AuthCredentials validation"""
        # Valid credentials
        valid_data = {'user_id': 123}
        valid_credentials = AuthCredentials('test', valid_data)
        assert valid_credentials.validate() is True
        
        # Invalid credentials (empty data)
        invalid_credentials = AuthCredentials('test', {})
        assert invalid_credentials.validate() is False


class TestAuthResult:
    """Test cases for AuthResult class"""
    
    @pytest.mark.unit
    def test_auth_result_success(self):
        """Test successful AuthResult"""
        result = AuthResult(
            status=AuthStatus.SUCCESS,
            access_token="test_token",
            user_info={'id': 123, 'username': 'test'}
        )
        
        assert result.is_success
        assert not result.is_expired
        assert result.access_token == "test_token"
        assert result.user_info is not None
        assert result.user_info['id'] == 123
    
    @pytest.mark.unit
    def test_auth_result_expired(self):
        """Test expired AuthResult"""
        past_time = datetime.utcnow() - timedelta(hours=1)
        result = AuthResult(
            status=AuthStatus.SUCCESS,
            expires_at=past_time
        )
        
        assert result.is_expired
    
    @pytest.mark.unit
    def test_auth_result_to_dict(self):
        """Test AuthResult to dictionary conversion"""
        future_time = datetime.utcnow() + timedelta(hours=1)
        result = AuthResult(
            status=AuthStatus.SUCCESS,
            access_token="test_token",
            refresh_token="refresh_token",
            user_info={'id': 123},
            expires_at=future_time,
            additional_data={'custom': 'data'}
        )
        
        data = result.to_dict()
        
        assert data['status'] == 'success'
        assert data['success'] is True
        assert data['access_token'] == 'test_token'
        assert data['token_type'] == 'bearer'
        assert data['refresh_token'] == 'refresh_token'
        assert data['user'] == {'id': 123}
        assert 'expires_at' in data
        assert 'expires_in' in data
        assert data['custom'] == 'data'
    
    @pytest.mark.unit
    def test_auth_result_error_to_dict(self):
        """Test error AuthResult to dictionary conversion"""
        result = AuthResult(
            status=AuthStatus.FAILED,
            error_message="Authentication failed"
        )
        
        data = result.to_dict()
        
        assert data['status'] == 'failed'
        assert data['success'] is False
        assert data['error'] == 'Authentication failed'


# Integration tests
class TestAuthIntegration:
    """Integration tests for authentication system"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_jwt_auth_flow(self):
        """Test complete JWT authentication flow"""
        jwt_service = JWTService()
        jwt_service.secret_key = "test-secret"
        
        # 1. Create user credentials
        user_data = {
            'user_id': 123,
            'username': 'integration_test',
            'role': 'user',
            'status': 'active'
        }
        
        # 2. Authenticate and get tokens
        credentials = JWTCredentials(user_data)
        auth_result = await jwt_service.authenticate(credentials)
        
        assert auth_result.is_success
        access_token = auth_result.access_token
        refresh_token = auth_result.refresh_token
        
        # 3. Validate access token
        assert access_token is not None
        validate_result = await jwt_service.validate_token(access_token)
        assert validate_result.is_success
        assert validate_result.user_info is not None
        assert validate_result.user_info['id'] == 123
        
        # 4. Refresh tokens
        assert refresh_token is not None
        refresh_result = await jwt_service.refresh_token(refresh_token)
        assert refresh_result.is_success
        assert refresh_result.access_token != access_token  # New token
    
    @pytest.mark.integration
    def test_session_auth_integration(self):
        """Test session authentication integration"""
        session_service = SessionAuthService()
        
        # Create session
        user_info = {'id': 123, 'username': 'session_test'}
        session_token = session_service.create_session(user_info)
        
        # Test session lifecycle
        assert session_service.get_session(session_token) is not None
        
        # Update session
        session_service.update_session(session_token, {'role': 'admin'})
        updated_session = session_service.get_session(session_token)
        assert updated_session is not None
        user_info_data = updated_session.get('user_info')
        assert user_info_data is not None
        assert isinstance(user_info_data, dict)
        assert user_info_data.get('role') == 'admin'
        
        # Invalidate session
        session_service.invalidate_session(session_token)
        assert session_service.get_session(session_token) is None


# Performance tests
class TestAuthPerformance:
    """Performance tests for authentication system"""
    
    @pytest.mark.performance
    def test_jwt_token_creation_performance(self):
        """Test JWT token creation performance"""
        jwt_service = JWTService()
        jwt_service.secret_key = "test-secret"
        
        user_data = {'user_id': 123, 'username': 'perf_test'}
        
        start_time = time.time()
        
        # Create 100 tokens
        for i in range(100):
            jwt_service.create_access_token(user_data)
        
        elapsed = time.time() - start_time
        
        # Should create 100 tokens in under 1 second
        assert elapsed < 1.0, f"Token creation took {elapsed:.3f}s for 100 tokens"
    
    @pytest.mark.performance
    def test_session_cleanup_performance(self):
        """Test session cleanup performance"""
        session_service = SessionAuthService()
        session_service.session_lifetime = 1  # 1 second
        
        # Create many sessions
        user_info = {'id': 123, 'username': 'perf_test'}
        for i in range(1000):
            session_service.create_session(user_info)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Measure cleanup time
        start_time = time.time()
        cleaned_count = session_service.cleanup_expired_sessions()
        elapsed = time.time() - start_time
        
        assert cleaned_count == 1000
        # Cleanup should complete in under 0.5 seconds
        assert elapsed < 0.5, f"Cleanup took {elapsed:.3f}s for 1000 sessions"


# Security tests
class TestAuthSecurity:
    """Security tests for authentication system"""
    
    @pytest.mark.security
    def test_jwt_token_tampering_detection(self):
        """Test detection of tampered JWT tokens"""
        jwt_service = JWTService()
        jwt_service.secret_key = "test-secret"
        
        user_data = {'user_id': 123, 'username': 'security_test'}
        token = jwt_service.create_access_token(user_data)
        
        # Tamper with token (change last character)
        tampered_token = token[:-1] + ('x' if token[-1] != 'x' else 'y')
        
        # Should detect tampering
        assert not jwt_service.is_token_valid_format(tampered_token)
    
    @pytest.mark.security
    def test_session_token_uniqueness(self):
        """Test that session tokens are unique"""
        session_service = SessionAuthService()
        user_info = {'id': 123, 'username': 'security_test'}
        
        # Create many sessions and ensure all tokens are unique
        tokens = set()
        for i in range(100):
            token = session_service.create_session(user_info)
            assert token not in tokens, "Duplicate session token generated"
            tokens.add(token)
    
    @pytest.mark.security
    @pytest.mark.asyncio
    async def test_expired_token_rejection(self):
        """Test that expired tokens are properly rejected"""
        jwt_service = JWTService()
        jwt_service.secret_key = "test-secret"
        jwt_service.access_token_lifetime = 1  # 1 second
        
        user_data = {'user_id': 123, 'username': 'security_test'}
        token = jwt_service.create_access_token(user_data)
        
        # Token should be valid initially
        result = await jwt_service.validate_token(token)
        assert result.is_success
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Token should now be rejected
        result = await jwt_service.validate_token(token)
        assert not result.is_success
        assert result.status == AuthStatus.EXPIRED
