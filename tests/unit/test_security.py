"""
Unit tests for security and authentication functionality.
Tests JWT management, API key validation, rate limiting, and input validation.
"""
import pytest
import json
import time
import jwt
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import security modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'shared'))

from security import (
    SecurityConfig, JWTManager, APIKeyManager, RateLimiter, InputValidator,
    SecurityMiddleware, SecurityLevel, AuthenticationMethod, SecurityError,
    AuthenticationError, AuthorizationError, RateLimitError, InputValidationError,
    security_middleware, SecurityAuditor
)

class TestSecurityConfig:
    """Test security configuration management."""
    
    @patch('security.ssm')
    def test_security_config_initialization(self, mock_ssm):
        """Test SecurityConfig initialization with mocked AWS services."""
        # Mock SSM responses
        mock_ssm.get_parameter.side_effect = [
            {'Parameter': {'Value': 'test-jwt-secret'}},
            {'Parameter': {'Value': 'test-api-key-hash'}},
            {'Parameter': {'Value': 'test-kms-key-id'}},
            {'Parameter': {'Value': 'test-user-pool-id'}},
            {'Parameter': {'Value': 'test-client-id'}}
        ]
        
        config = SecurityConfig()
        
        assert config.jwt_secret == 'test-jwt-secret'
        assert config.api_key_hash == 'test-api-key-hash'
        assert config.encryption_key_id == 'test-kms-key-id'
        assert config.cognito_user_pool_id == 'test-user-pool-id'
        assert config.cognito_client_id == 'test-client-id'
        
        # Verify rate limits are configured
        assert 'default' in config.rate_limits
        assert 'authenticated' in config.rate_limits
        assert 'premium' in config.rate_limits
        
        # Verify password policy
        assert config.password_policy['min_length'] == 12
        assert config.password_policy['require_uppercase'] is True

    @patch('security.ssm')
    def test_security_config_missing_parameters(self, mock_ssm):
        """Test SecurityConfig handles missing parameters gracefully."""
        # Mock SSM to raise ClientError
        from botocore.exceptions import ClientError
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}}, 'GetParameter'
        )
        
        config = SecurityConfig()
        
        # Should handle missing parameters gracefully
        assert config.jwt_secret is None
        assert config.api_key_hash is None

class TestJWTManager:
    """Test JWT token management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = 'test-secret-key'
        self.jwt_manager = JWTManager(self.secret_key)
    
    def test_generate_token(self):
        """Test JWT token generation."""
        user_id = 'test-user-123'
        roles = ['user', 'researcher']
        permissions = ['read', 'write']
        
        token = self.jwt_manager.generate_token(user_id, roles, permissions)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify payload
        payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
        assert payload['user_id'] == user_id
        assert payload['roles'] == roles
        assert payload['permissions'] == permissions
        assert 'iat' in payload
        assert 'exp' in payload
        assert 'iss' in payload
        assert 'jti' in payload
    
    def test_verify_valid_token(self):
        """Test verification of valid JWT token."""
        user_id = 'test-user-123'
        roles = ['user']
        permissions = ['read']
        
        token = self.jwt_manager.generate_token(user_id, roles, permissions)
        payload = self.jwt_manager.verify_token(token)
        
        assert payload['user_id'] == user_id
        assert payload['roles'] == roles
        assert payload['permissions'] == permissions
    
    def test_verify_expired_token(self):
        """Test verification of expired JWT token."""
        # Create token with very short expiry
        self.jwt_manager.token_expiry = timedelta(seconds=-1)  # Already expired
        
        user_id = 'test-user-123'
        token = self.jwt_manager.generate_token(user_id)
        
        with pytest.raises(AuthenticationError, match="Token has expired"):
            self.jwt_manager.verify_token(token)
    
    def test_verify_invalid_token(self):
        """Test verification of invalid JWT token."""
        invalid_token = 'invalid.jwt.token'
        
        with pytest.raises(AuthenticationError, match="Invalid token"):
            self.jwt_manager.verify_token(invalid_token)
    
    def test_refresh_token(self):
        """Test JWT token refresh."""
        user_id = 'test-user-123'
        roles = ['user']
        permissions = ['read']
        
        original_token = self.jwt_manager.generate_token(user_id, roles, permissions)
        time.sleep(1)  # Ensure different timestamps
        
        refreshed_token = self.jwt_manager.refresh_token(original_token)
        
        assert refreshed_token != original_token
        
        # Verify refreshed token has same user data
        payload = self.jwt_manager.verify_token(refreshed_token)
        assert payload['user_id'] == user_id
        assert payload['roles'] == roles
        assert payload['permissions'] == permissions
    
    def test_refresh_old_token(self):
        """Test refresh of very old token fails."""
        # Mock old token
        old_payload = {
            'user_id': 'test-user',
            'roles': [],
            'permissions': [],
            'iat': datetime.utcnow() - timedelta(days=8),  # 8 days old
            'exp': datetime.utcnow() - timedelta(days=7),
            'iss': 'agent-scholar',
            'jti': 'test-jti'
        }
        
        old_token = jwt.encode(old_payload, self.secret_key, algorithm='HS256')
        
        with pytest.raises(AuthenticationError, match="Token too old for refresh"):
            self.jwt_manager.refresh_token(old_token)

class TestAPIKeyManager:
    """Test API key management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.secret_hash = 'test-secret-hash'
        self.api_key_manager = APIKeyManager(self.secret_hash)
    
    def test_generate_api_key(self):
        """Test API key generation."""
        api_key = self.api_key_manager.generate_api_key()
        
        assert isinstance(api_key, str)
        assert api_key.startswith('as_')
        assert len(api_key) > 10
    
    def test_generate_api_key_custom_prefix(self):
        """Test API key generation with custom prefix."""
        prefix = 'custom'
        api_key = self.api_key_manager.generate_api_key(prefix)
        
        assert api_key.startswith(f'{prefix}_')
    
    def test_hash_api_key(self):
        """Test API key hashing."""
        api_key = 'test-api-key'
        hash1 = self.api_key_manager.hash_api_key(api_key)
        hash2 = self.api_key_manager.hash_api_key(api_key)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex digest length
        assert hash1 == hash2  # Same input should produce same hash
    
    def test_verify_api_key_valid(self):
        """Test verification of valid API key."""
        api_key = 'test-api-key'
        stored_hash = self.api_key_manager.hash_api_key(api_key)
        
        assert self.api_key_manager.verify_api_key(api_key, stored_hash) is True
    
    def test_verify_api_key_invalid(self):
        """Test verification of invalid API key."""
        api_key = 'test-api-key'
        wrong_key = 'wrong-api-key'
        stored_hash = self.api_key_manager.hash_api_key(api_key)
        
        assert self.api_key_manager.verify_api_key(wrong_key, stored_hash) is False

class TestInputValidator:
    """Test input validation and sanitization."""
    
    def test_validate_email_valid(self):
        """Test validation of valid email addresses."""
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org'
        ]
        
        for email in valid_emails:
            assert InputValidator.validate_email(email) is True
    
    def test_validate_email_invalid(self):
        """Test validation of invalid email addresses."""
        invalid_emails = [
            'invalid-email',
            '@example.com',
            'user@',
            'user@.com',
            'user space@example.com'
        ]
        
        for email in invalid_emails:
            assert InputValidator.validate_email(email) is False
    
    def test_validate_string_length(self):
        """Test string length validation."""
        assert InputValidator.validate_string_length('test', 1, 10) is True
        assert InputValidator.validate_string_length('', 1, 10) is False
        assert InputValidator.validate_string_length('a' * 11, 1, 10) is False
    
    def test_validate_safe_string(self):
        """Test safe string validation."""
        safe_strings = [
            'hello world',
            'test123',
            'file-name_v2.txt'
        ]
        
        for string in safe_strings:
            assert InputValidator.validate_safe_string(string) is True
        
        unsafe_strings = [
            'hello<script>',
            'test@#$%',
            'file/path'
        ]
        
        for string in unsafe_strings:
            assert InputValidator.validate_safe_string(string) is False
    
    def test_detect_sql_injection(self):
        """Test SQL injection detection."""
        safe_queries = [
            'search for machine learning',
            'find documents about AI',
            'python programming tutorial'
        ]
        
        for query in safe_queries:
            assert InputValidator.detect_sql_injection(query) is False
        
        malicious_queries = [
            "'; DROP TABLE users; --",
            'SELECT * FROM documents',
            'UNION SELECT password FROM users'
        ]
        
        for query in malicious_queries:
            assert InputValidator.detect_sql_injection(query) is True
    
    def test_detect_xss(self):
        """Test XSS detection."""
        safe_queries = [
            'search for machine learning',
            'find documents about AI'
        ]
        
        for query in safe_queries:
            assert InputValidator.detect_xss(query) is False
        
        malicious_queries = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            'onclick="alert(1)"'
        ]
        
        for query in malicious_queries:
            assert InputValidator.detect_xss(query) is True
    
    def test_sanitize_input(self):
        """Test input sanitization."""
        malicious_input = '<script>alert("xss")</script>Hello World<img onerror="alert(1)">'
        sanitized = InputValidator.sanitize_input(malicious_input)
        
        assert '<script>' not in sanitized
        assert 'alert' not in sanitized
        assert 'Hello World' in sanitized
    
    def test_validate_query_input_valid(self):
        """Test comprehensive query validation for valid input."""
        valid_query = 'What are the latest developments in machine learning?'
        result = InputValidator.validate_query_input(valid_query)
        
        assert result['valid'] is True
        assert len(result['issues']) == 0
        assert result['sanitized_query'] == valid_query
    
    def test_validate_query_input_invalid(self):
        """Test comprehensive query validation for invalid input."""
        invalid_query = '<script>alert("xss")</script>SELECT * FROM users'
        result = InputValidator.validate_query_input(invalid_query)
        
        assert result['valid'] is False
        assert len(result['issues']) > 0
        assert 'XSS' in str(result['issues']) or 'SQL' in str(result['issues'])
    
    def test_validate_query_input_empty(self):
        """Test validation of empty query."""
        result = InputValidator.validate_query_input('')
        
        assert result['valid'] is False
        assert any('empty' in issue.lower() for issue in result['issues'])

class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @patch('security.boto3')
    def setup_method(self, mock_boto3):
        """Set up test fixtures with mocked DynamoDB."""
        self.mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = self.mock_table
        self.rate_limiter = RateLimiter('test-table')
    
    def test_check_rate_limit_first_request(self):
        """Test rate limiting for first request."""
        # Mock DynamoDB response for new identifier
        self.mock_table.get_item.return_value = {}
        
        result = self.rate_limiter.check_rate_limit('test-user', 100, 3600)
        
        assert result is True
        self.mock_table.put_item.assert_called_once()
    
    def test_check_rate_limit_within_limit(self):
        """Test rate limiting when within limits."""
        # Mock DynamoDB response with existing requests
        current_time = int(time.time())
        self.mock_table.get_item.return_value = {
            'Item': {
                'identifier': 'test-user',
                'requests': [current_time - 1800]  # 30 minutes ago
            }
        }
        
        result = self.rate_limiter.check_rate_limit('test-user', 100, 3600)
        
        assert result is True
        self.mock_table.update_item.assert_called_once()
    
    def test_check_rate_limit_exceeded(self):
        """Test rate limiting when limit is exceeded."""
        # Mock DynamoDB response with many recent requests
        current_time = int(time.time())
        recent_requests = [current_time - i for i in range(100)]  # 100 recent requests
        
        self.mock_table.get_item.return_value = {
            'Item': {
                'identifier': 'test-user',
                'requests': recent_requests
            }
        }
        
        result = self.rate_limiter.check_rate_limit('test-user', 50, 3600)
        
        assert result is False
    
    def test_check_rate_limit_old_requests_filtered(self):
        """Test that old requests are filtered out."""
        current_time = int(time.time())
        old_requests = [current_time - 7200]  # 2 hours ago
        
        self.mock_table.get_item.return_value = {
            'Item': {
                'identifier': 'test-user',
                'requests': old_requests
            }
        }
        
        result = self.rate_limiter.check_rate_limit('test-user', 100, 3600)
        
        assert result is True

class TestSecurityMiddleware:
    """Test security middleware functionality."""
    
    @patch('security.SecurityConfig')
    def setup_method(self, mock_config_class):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.jwt_secret = 'test-secret'
        self.mock_config.api_key_hash = 'test-hash'
        self.mock_config.cognito_user_pool_id = 'test-pool'
        self.mock_config.rate_limits = {
            'default': {'requests': 100, 'window': 3600},
            'authenticated': {'requests': 1000, 'window': 3600}
        }
        mock_config_class.return_value = self.mock_config
        
        self.middleware = SecurityMiddleware(self.mock_config)
    
    def test_authenticate_request_jwt(self):
        """Test JWT authentication."""
        # Create a valid JWT token
        jwt_manager = JWTManager('test-secret')
        token = jwt_manager.generate_token('test-user', ['user'], ['read'])
        
        event = {
            'headers': {
                'Authorization': f'Bearer {token}'
            }
        }
        
        auth_info = self.middleware.authenticate_request(event)
        
        assert auth_info['authenticated'] is True
        assert auth_info['method'] == AuthenticationMethod.JWT_TOKEN
        assert auth_info['user_id'] == 'test-user'
        assert auth_info['roles'] == ['user']
        assert auth_info['permissions'] == ['read']
    
    def test_authenticate_request_api_key(self):
        """Test API key authentication."""
        event = {
            'headers': {
                'X-API-Key': 'valid-api-key-12345'
            }
        }
        
        auth_info = self.middleware.authenticate_request(event)
        
        assert auth_info['authenticated'] is True
        assert auth_info['method'] == AuthenticationMethod.API_KEY
        assert auth_info['user_id'] == 'api_user'
    
    def test_authenticate_request_no_auth(self):
        """Test request with no authentication."""
        event = {'headers': {}}
        
        auth_info = self.middleware.authenticate_request(event)
        
        assert auth_info['authenticated'] is False
        assert auth_info['method'] is None
        assert auth_info['user_id'] == 'anonymous'
    
    def test_check_authorization_success(self):
        """Test successful authorization check."""
        auth_info = {
            'authenticated': True,
            'permissions': ['read', 'write']
        }
        
        result = self.middleware.check_authorization(auth_info, ['read'])
        assert result is True
    
    def test_check_authorization_failure(self):
        """Test failed authorization check."""
        auth_info = {
            'authenticated': True,
            'permissions': ['read']
        }
        
        result = self.middleware.check_authorization(auth_info, ['write'])
        assert result is False
    
    def test_validate_input_valid_json(self):
        """Test input validation with valid JSON."""
        event = {
            'body': json.dumps({
                'query': 'What is machine learning?',
                'session_id': '12345678-1234-1234-1234-123456789012'
            })
        }
        
        validated_data = self.middleware.validate_input(event)
        
        assert validated_data['query'] == 'What is machine learning?'
        assert validated_data['session_id'] == '12345678-1234-1234-1234-123456789012'
    
    def test_validate_input_invalid_json(self):
        """Test input validation with invalid JSON."""
        event = {'body': 'invalid json'}
        
        with pytest.raises(InputValidationError, match="Invalid JSON"):
            self.middleware.validate_input(event)
    
    def test_validate_input_malicious_query(self):
        """Test input validation with malicious query."""
        event = {
            'body': json.dumps({
                'query': '<script>alert("xss")</script>SELECT * FROM users'
            })
        }
        
        with pytest.raises(InputValidationError, match="Query validation failed"):
            self.middleware.validate_input(event)

class TestSecurityDecorator:
    """Test security middleware decorator."""
    
    @patch('security.SecurityConfig')
    @patch('security.SecurityMiddleware')
    def test_security_middleware_decorator_success(self, mock_middleware_class, mock_config_class):
        """Test successful request through security middleware."""
        # Mock middleware
        mock_middleware = Mock()
        mock_middleware.authenticate_request.return_value = {
            'authenticated': True,
            'user_id': 'test-user',
            'roles': ['user'],
            'permissions': ['read']
        }
        mock_middleware.check_authorization.return_value = True
        mock_middleware.check_rate_limit.return_value = True
        mock_middleware.validate_input.return_value = {'query': 'test query'}
        mock_middleware_class.return_value = mock_middleware
        
        # Create decorated function
        @security_middleware(
            security_level=SecurityLevel.AUTHENTICATED,
            required_permissions=['read']
        )
        def test_function(event, context):
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }
        
        # Test the decorated function
        event = {'headers': {}, 'body': '{}'}
        context = {}
        
        response = test_function(event, context)
        
        assert response['statusCode'] == 200
        assert 'auth_info' in event
    
    @patch('security.SecurityConfig')
    @patch('security.SecurityMiddleware')
    def test_security_middleware_decorator_auth_failure(self, mock_middleware_class, mock_config_class):
        """Test authentication failure in security middleware."""
        # Mock middleware
        mock_middleware = Mock()
        mock_middleware.authenticate_request.return_value = {
            'authenticated': False,
            'user_id': 'anonymous',
            'roles': [],
            'permissions': []
        }
        mock_middleware_class.return_value = mock_middleware
        
        # Create decorated function
        @security_middleware(security_level=SecurityLevel.AUTHENTICATED)
        def test_function(event, context):
            return {'statusCode': 200}
        
        # Test the decorated function
        response = test_function({}, {})
        
        assert response['statusCode'] == 401
        assert 'Authentication required' in response['body']
    
    @patch('security.SecurityConfig')
    @patch('security.SecurityMiddleware')
    def test_security_middleware_decorator_rate_limit(self, mock_middleware_class, mock_config_class):
        """Test rate limit exceeded in security middleware."""
        # Mock middleware
        mock_middleware = Mock()
        mock_middleware.authenticate_request.return_value = {'authenticated': True}
        mock_middleware.check_authorization.return_value = True
        mock_middleware.check_rate_limit.return_value = False
        mock_middleware_class.return_value = mock_middleware
        
        # Create decorated function
        @security_middleware()
        def test_function(event, context):
            return {'statusCode': 200}
        
        # Test the decorated function
        response = test_function({}, {})
        
        assert response['statusCode'] == 429
        assert 'Rate limit exceeded' in response['body']

class TestSecurityAuditor:
    """Test security auditing functionality."""
    
    @patch('security.boto3')
    def setup_method(self, mock_boto3):
        """Set up test fixtures."""
        self.mock_cloudwatch = Mock()
        mock_boto3.client.return_value = self.mock_cloudwatch
        self.auditor = SecurityAuditor()
    
    def test_log_security_event(self):
        """Test security event logging."""
        event_type = 'test_event'
        details = {'user_id': 'test-user', 'action': 'login'}
        severity = 'INFO'
        
        self.auditor.log_security_event(event_type, details, severity)
        
        # Verify CloudWatch metric was sent
        self.mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = self.mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'AgentScholar/Security'
        assert call_args[1]['MetricData'][0]['MetricName'] == f'SecurityEvent_{event_type}'
        assert call_args[1]['MetricData'][0]['Value'] == 1
    
    def test_log_authentication_attempt_success(self):
        """Test logging successful authentication attempt."""
        self.auditor.log_authentication_attempt(
            success=True,
            method='JWT',
            user_id='test-user',
            ip_address='192.168.1.1'
        )
        
        self.mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_log_authentication_attempt_failure(self):
        """Test logging failed authentication attempt."""
        self.auditor.log_authentication_attempt(
            success=False,
            method='JWT',
            user_id='test-user',
            ip_address='192.168.1.1'
        )
        
        self.mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_log_authorization_failure(self):
        """Test logging authorization failure."""
        self.auditor.log_authorization_failure(
            user_id='test-user',
            required_permissions=['write'],
            ip_address='192.168.1.1'
        )
        
        self.mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_log_rate_limit_exceeded(self):
        """Test logging rate limit exceeded."""
        self.auditor.log_rate_limit_exceeded(
            identifier='user:test-user',
            ip_address='192.168.1.1'
        )
        
        self.mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_log_input_validation_failure(self):
        """Test logging input validation failure."""
        validation_errors = ['XSS detected', 'SQL injection detected']
        
        self.auditor.log_input_validation_failure(
            validation_errors=validation_errors,
            ip_address='192.168.1.1'
        )
        
        self.mock_cloudwatch.put_metric_data.assert_called_once()

if __name__ == '__main__':
    pytest.main([__file__])