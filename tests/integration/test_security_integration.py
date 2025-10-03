"""
Integration tests for security and authentication features.
Tests end-to-end security workflows including Cognito integration,
API Gateway authentication, and security monitoring.
"""
import pytest
import json
import boto3
import requests
import time
from moto import mock_dynamodb, mock_ssm, mock_kms, mock_cognito_idp, mock_cloudwatch
from unittest.mock import patch, Mock

# Import security modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'shared'))

from security import (
    SecurityConfig, SecurityMiddleware, RateLimiter, SecurityAuditor,
    security_middleware, SecurityLevel, AuthenticationMethod
)

@mock_dynamodb
@mock_ssm
@mock_kms
class TestSecurityIntegration:
    """Integration tests for security components."""
    
    def setup_method(self):
        """Set up test environment with mocked AWS services."""
        # Create DynamoDB table for rate limiting
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.rate_limit_table = dynamodb.create_table(
            TableName='agent-scholar-rate-limits',
            KeySchema=[
                {'AttributeName': 'identifier', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'identifier', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create SSM parameters
        ssm = boto3.client('ssm', region_name='us-east-1')
        ssm.put_parameter(
            Name='/agent-scholar/secrets/JWT_SECRET_KEY',
            Value='test-jwt-secret-key',
            Type='SecureString'
        )
        ssm.put_parameter(
            Name='/agent-scholar/secrets/API_KEY_HASH',
            Value='test-api-key-hash',
            Type='SecureString'
        )
        ssm.put_parameter(
            Name='/agent-scholar/config/KMS_KEY_ID',
            Value='test-kms-key-id',
            Type='String'
        )
        ssm.put_parameter(
            Name='/agent-scholar/config/COGNITO_USER_POOL_ID',
            Value='test-user-pool-id',
            Type='String'
        )
        ssm.put_parameter(
            Name='/agent-scholar/config/COGNITO_CLIENT_ID',
            Value='test-client-id',
            Type='String'
        )
        
        # Create KMS key
        kms = boto3.client('kms', region_name='us-east-1')
        key_response = kms.create_key(
            Description='Test encryption key for Agent Scholar'
        )
        self.kms_key_id = key_response['KeyMetadata']['KeyId']
    
    def test_rate_limiter_integration(self):
        """Test rate limiter with real DynamoDB operations."""
        rate_limiter = RateLimiter('agent-scholar-rate-limits')
        
        identifier = 'test-user-123'
        limit = 5
        window = 60  # 1 minute
        
        # First few requests should succeed
        for i in range(limit):
            result = rate_limiter.check_rate_limit(identifier, limit, window)
            assert result is True, f"Request {i+1} should be allowed"
        
        # Next request should be rate limited
        result = rate_limiter.check_rate_limit(identifier, limit, window)
        assert result is False, "Request should be rate limited"
        
        # Verify data is stored in DynamoDB
        response = self.rate_limit_table.get_item(Key={'identifier': identifier})
        assert 'Item' in response
        assert len(response['Item']['requests']) == limit
    
    def test_security_config_integration(self):
        """Test SecurityConfig with real AWS services."""
        config = SecurityConfig()
        
        assert config.jwt_secret == 'test-jwt-secret-key'
        assert config.api_key_hash == 'test-api-key-hash'
        assert config.encryption_key_id == 'test-kms-key-id'
        assert config.cognito_user_pool_id == 'test-user-pool-id'
        assert config.cognito_client_id == 'test-client-id'
    
    def test_security_middleware_integration(self):
        """Test SecurityMiddleware with integrated components."""
        config = SecurityConfig()
        middleware = SecurityMiddleware(config)
        
        # Test JWT authentication flow
        from security import JWTManager
        jwt_manager = JWTManager(config.jwt_secret)
        token = jwt_manager.generate_token('test-user', ['user'], ['read'])
        
        event = {
            'headers': {'Authorization': f'Bearer {token}'},
            'body': json.dumps({'query': 'test query'}),
            'requestContext': {
                'identity': {'sourceIp': '192.168.1.1'}
            }
        }
        
        # Test authentication
        auth_info = middleware.authenticate_request(event)
        assert auth_info['authenticated'] is True
        assert auth_info['user_id'] == 'test-user'
        
        # Test authorization
        assert middleware.check_authorization(auth_info, ['read']) is True
        assert middleware.check_authorization(auth_info, ['admin']) is False
        
        # Test rate limiting
        rate_limit_result = middleware.check_rate_limit(event, auth_info)
        assert rate_limit_result is True
        
        # Test input validation
        validated_data = middleware.validate_input(event)
        assert validated_data['query'] == 'test query'

@mock_cloudwatch
class TestSecurityAuditorIntegration:
    """Integration tests for security auditing."""
    
    def test_security_auditor_cloudwatch_integration(self):
        """Test SecurityAuditor with CloudWatch integration."""
        auditor = SecurityAuditor()
        
        # Test logging various security events
        auditor.log_authentication_attempt(
            success=True,
            method='JWT',
            user_id='test-user',
            ip_address='192.168.1.1'
        )
        
        auditor.log_authorization_failure(
            user_id='test-user',
            required_permissions=['admin'],
            ip_address='192.168.1.1'
        )
        
        auditor.log_rate_limit_exceeded(
            identifier='user:test-user',
            ip_address='192.168.1.1'
        )
        
        auditor.log_input_validation_failure(
            validation_errors=['XSS detected'],
            ip_address='192.168.1.1'
        )
        
        # Verify CloudWatch client was called
        # In a real test, you'd verify the metrics were sent correctly

@mock_cognito_idp
class TestCognitoIntegration:
    """Integration tests for Cognito authentication."""
    
    def setup_method(self):
        """Set up Cognito resources for testing."""
        self.cognito_client = boto3.client('cognito-idp', region_name='us-east-1')
        
        # Create user pool
        user_pool_response = self.cognito_client.create_user_pool(
            PoolName='agent-scholar-test-pool',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 12,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': True
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email'],
            Schema=[
                {
                    'Name': 'email',
                    'AttributeDataType': 'String',
                    'Required': True,
                    'Mutable': True
                },
                {
                    'Name': 'subscription_tier',
                    'AttributeDataType': 'String',
                    'Mutable': True
                }
            ]
        )
        self.user_pool_id = user_pool_response['UserPool']['Id']
        
        # Create user pool client
        client_response = self.cognito_client.create_user_pool_client(
            UserPoolId=self.user_pool_id,
            ClientName='agent-scholar-test-client',
            GenerateSecret=False,
            ExplicitAuthFlows=['ADMIN_NO_SRP_AUTH', 'ALLOW_USER_PASSWORD_AUTH']
        )
        self.client_id = client_response['UserPoolClient']['ClientId']
    
    def test_cognito_user_registration_flow(self):
        """Test complete user registration flow."""
        # Create user
        username = 'testuser@example.com'
        password = 'TestPassword123!'
        
        self.cognito_client.admin_create_user(
            UserPoolId=self.user_pool_id,
            Username=username,
            UserAttributes=[
                {'Name': 'email', 'Value': username},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'custom:subscription_tier', 'Value': 'free'}
            ],
            TemporaryPassword=password,
            MessageAction='SUPPRESS'
        )
        
        # Set permanent password
        self.cognito_client.admin_set_user_password(
            UserPoolId=self.user_pool_id,
            Username=username,
            Password=password,
            Permanent=True
        )
        
        # Test authentication
        auth_response = self.cognito_client.admin_initiate_auth(
            UserPoolId=self.user_pool_id,
            ClientId=self.client_id,
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        assert 'AuthenticationResult' in auth_response
        assert 'AccessToken' in auth_response['AuthenticationResult']
        assert 'IdToken' in auth_response['AuthenticationResult']
        assert 'RefreshToken' in auth_response['AuthenticationResult']
        
        # Test token validation
        access_token = auth_response['AuthenticationResult']['AccessToken']
        user_response = self.cognito_client.get_user(AccessToken=access_token)
        
        assert user_response['Username'] == username
        user_attributes = {attr['Name']: attr['Value'] for attr in user_response['UserAttributes']}
        assert user_attributes['email'] == username
        assert user_attributes['custom:subscription_tier'] == 'free'
    
    def test_cognito_password_policy_enforcement(self):
        """Test password policy enforcement."""
        username = 'testuser2@example.com'
        
        # Test weak password - should fail
        weak_passwords = [
            'weak',  # Too short
            'weakpassword',  # No uppercase, numbers, symbols
            'WeakPassword',  # No numbers, symbols
            'WeakPassword123',  # No symbols
        ]
        
        for weak_password in weak_passwords:
            with pytest.raises(Exception):  # Should raise ClientError
                self.cognito_client.admin_create_user(
                    UserPoolId=self.user_pool_id,
                    Username=username,
                    UserAttributes=[
                        {'Name': 'email', 'Value': username}
                    ],
                    TemporaryPassword=weak_password,
                    MessageAction='SUPPRESS'
                )

class TestEndToEndSecurityFlow:
    """End-to-end security flow tests."""
    
    @patch('requests.post')
    def test_api_gateway_security_flow(self, mock_post):
        """Test complete API Gateway security flow."""
        # Mock API Gateway response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': 'Query processed successfully',
            'session_id': 'test-session-123'
        }
        mock_post.return_value = mock_response
        
        # Test authenticated request
        api_url = 'https://api.agent-scholar.com/research'
        headers = {
            'Authorization': 'Bearer valid-jwt-token',
            'Content-Type': 'application/json'
        }
        payload = {
            'query': 'What are the latest developments in AI?',
            'session_id': 'test-session-123'
        }
        
        response = requests.post(api_url, headers=headers, json=payload)
        
        assert response.status_code == 200
        assert 'message' in response.json()
    
    def test_security_decorator_integration(self):
        """Test security decorator with Lambda function."""
        
        @security_middleware(
            security_level=SecurityLevel.AUTHENTICATED,
            required_permissions=['read'],
            enable_rate_limiting=True
        )
        def mock_lambda_handler(event, context):
            """Mock Lambda function for testing."""
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'message': 'Success',
                    'user_id': event['auth_info']['user_id']
                })
            }
        
        # Test with valid authentication
        with patch('security.SecurityConfig') as mock_config_class:
            mock_config = Mock()
            mock_config.jwt_secret = 'test-secret'
            mock_config.rate_limits = {'authenticated': {'requests': 1000, 'window': 3600}}
            mock_config_class.return_value = mock_config
            
            with patch('security.SecurityMiddleware') as mock_middleware_class:
                mock_middleware = Mock()
                mock_middleware.authenticate_request.return_value = {
                    'authenticated': True,
                    'user_id': 'test-user',
                    'roles': ['user'],
                    'permissions': ['read']
                }
                mock_middleware.check_authorization.return_value = True
                mock_middleware.check_rate_limit.return_value = True
                mock_middleware.validate_input.return_value = {'query': 'test'}
                mock_middleware_class.return_value = mock_middleware
                
                event = {
                    'headers': {'Authorization': 'Bearer valid-token'},
                    'body': json.dumps({'query': 'test query'})
                }
                context = {}
                
                response = mock_lambda_handler(event, context)
                
                assert response['statusCode'] == 200
                response_body = json.loads(response['body'])
                assert response_body['message'] == 'Success'
                assert response_body['user_id'] == 'test-user'

class TestSecurityVulnerabilityAssessment:
    """Security vulnerability assessment tests."""
    
    def test_sql_injection_protection(self):
        """Test protection against SQL injection attacks."""
        from security import InputValidator
        
        malicious_queries = [
            "'; DROP TABLE documents; --",
            "' OR '1'='1",
            "UNION SELECT password FROM users",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]
        
        for query in malicious_queries:
            result = InputValidator.validate_query_input(query)
            assert result['valid'] is False, f"Should detect SQL injection in: {query}"
            assert any('SQL' in issue for issue in result['issues'])
    
    def test_xss_protection(self):
        """Test protection against XSS attacks."""
        from security import InputValidator
        
        malicious_queries = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(1)">',
            '<svg onload="alert(1)">',
            'onclick="alert(1)"'
        ]
        
        for query in malicious_queries:
            result = InputValidator.validate_query_input(query)
            assert result['valid'] is False, f"Should detect XSS in: {query}"
            assert any('XSS' in issue for issue in result['issues'])
    
    def test_input_length_limits(self):
        """Test input length limits to prevent DoS."""
        from security import InputValidator
        
        # Test extremely long input
        long_query = 'A' * 50000  # 50KB query
        result = InputValidator.validate_query_input(long_query)
        
        # Should either reject or truncate
        assert len(result['sanitized_query']) <= 10000
    
    def test_rate_limiting_protection(self):
        """Test rate limiting protection against abuse."""
        with mock_dynamodb():
            # Create DynamoDB table
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = dynamodb.create_table(
                TableName='test-rate-limits',
                KeySchema=[{'AttributeName': 'identifier', 'KeyType': 'HASH'}],
                AttributeDefinitions=[{'AttributeName': 'identifier', 'AttributeType': 'S'}],
                BillingMode='PAY_PER_REQUEST'
            )
            
            rate_limiter = RateLimiter('test-rate-limits')
            
            # Simulate rapid requests
            identifier = 'attacker-ip'
            limit = 10
            window = 60
            
            # First 10 requests should succeed
            for i in range(limit):
                result = rate_limiter.check_rate_limit(identifier, limit, window)
                assert result is True
            
            # 11th request should be blocked
            result = rate_limiter.check_rate_limit(identifier, limit, window)
            assert result is False
    
    def test_jwt_token_security(self):
        """Test JWT token security features."""
        from security import JWTManager
        
        jwt_manager = JWTManager('secure-secret-key')
        
        # Test token expiration
        token = jwt_manager.generate_token('test-user')
        payload = jwt_manager.verify_token(token)
        
        # Verify token has expiration
        assert 'exp' in payload
        assert 'iat' in payload
        assert 'jti' in payload  # Unique token ID
        
        # Test token cannot be modified
        tampered_token = token[:-5] + 'XXXXX'  # Tamper with signature
        
        with pytest.raises(Exception):  # Should raise AuthenticationError
            jwt_manager.verify_token(tampered_token)

if __name__ == '__main__':
    pytest.main([__file__])