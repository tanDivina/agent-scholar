"""
Authentication and authorization Lambda function for Agent Scholar.
Handles user authentication, token validation, and session management.
"""
import json
import logging
import os
from typing import Dict, Any, Optional

# Import security modules
import sys
sys.path.append('/opt/python')  # Lambda layer path
from security import (
    security_middleware, SecurityLevel, SecurityAuditor,
    JWTManager, SecurityConfig, AuthenticationError
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize security components
security_auditor = SecurityAuditor()

@security_middleware(
    security_level=SecurityLevel.PUBLIC,
    enable_rate_limiting=True
)
def login_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle user login requests.
    Validates credentials and returns JWT token.
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        email = body.get('email')
        password = body.get('password')
        
        if not email or not password:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Email and password are required'
                })
            }
        
        # Get source IP for logging
        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        
        # Validate credentials (in production, use Cognito or database)
        if validate_user_credentials(email, password):
            # Generate JWT token
            config = SecurityConfig()
            jwt_manager = JWTManager(config.jwt_secret)
            
            # Get user roles and permissions (from database in production)
            user_roles, user_permissions = get_user_roles_and_permissions(email)
            
            token = jwt_manager.generate_token(
                user_id=email,
                roles=user_roles,
                permissions=user_permissions
            )
            
            # Log successful authentication
            security_auditor.log_authentication_attempt(
                success=True,
                method='password',
                user_id=email,
                ip_address=source_ip
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'token': token,
                    'user_id': email,
                    'roles': user_roles,
                    'permissions': user_permissions,
                    'expires_in': 86400  # 24 hours
                })
            }
        else:
            # Log failed authentication
            security_auditor.log_authentication_attempt(
                success=False,
                method='password',
                user_id=email,
                ip_address=source_ip
            )
            
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid credentials'
                })
            }
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }

@security_middleware(
    security_level=SecurityLevel.AUTHENTICATED,
    enable_rate_limiting=True
)
def refresh_token_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle token refresh requests.
    Validates existing token and returns new token.
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        refresh_token = body.get('refresh_token')
        
        if not refresh_token:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Refresh token is required'
                })
            }
        
        # Refresh token
        config = SecurityConfig()
        jwt_manager = JWTManager(config.jwt_secret)
        
        try:
            new_token = jwt_manager.refresh_token(refresh_token)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'token': new_token,
                    'expires_in': 86400  # 24 hours
                })
            }
        except AuthenticationError as e:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': str(e)
                })
            }
            
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }

@security_middleware(
    security_level=SecurityLevel.AUTHENTICATED,
    required_permissions=['read'],
    enable_rate_limiting=True
)
def user_profile_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle user profile requests.
    Returns user information for authenticated users.
    """
    try:
        # Get user info from auth context
        auth_info = event.get('auth_info', {})
        user_id = auth_info.get('user_id')
        
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'User not authenticated'
                })
            }
        
        # Get user profile (from database in production)
        user_profile = get_user_profile(user_id)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'user_id': user_id,
                'profile': user_profile,
                'roles': auth_info.get('roles', []),
                'permissions': auth_info.get('permissions', [])
            })
        }
        
    except Exception as e:
        logger.error(f"User profile error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }

@security_middleware(
    security_level=SecurityLevel.AUTHENTICATED,
    required_permissions=['admin'],
    enable_rate_limiting=True
)
def admin_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle admin requests.
    Only accessible to users with admin permissions.
    """
    try:
        # Get user info from auth context
        auth_info = event.get('auth_info', {})
        user_id = auth_info.get('user_id')
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')
        
        if action == 'get_users':
            # Return list of users (mock data)
            users = get_all_users()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'users': users,
                    'admin_user': user_id
                })
            }
        elif action == 'get_security_metrics':
            # Return security metrics
            metrics = get_security_metrics()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'metrics': metrics,
                    'admin_user': user_id
                })
            }
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid action'
                })
            }
        
    except Exception as e:
        logger.error(f"Admin handler error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }

def validate_user_credentials(email: str, password: str) -> bool:
    """
    Validate user credentials.
    In production, this would check against Cognito or a database.
    """
    # Mock validation - in production, use proper authentication
    test_users = {
        'admin@example.com': 'AdminPassword123!',
        'user@example.com': 'UserPassword123!',
        'researcher@example.com': 'ResearchPassword123!'
    }
    
    return test_users.get(email) == password

def get_user_roles_and_permissions(email: str) -> tuple:
    """
    Get user roles and permissions.
    In production, this would query a database or Cognito.
    """
    # Mock roles and permissions
    user_data = {
        'admin@example.com': (['admin', 'user'], ['read', 'write', 'admin', 'delete']),
        'user@example.com': (['user'], ['read', 'write']),
        'researcher@example.com': (['researcher', 'user'], ['read', 'write', 'analyze'])
    }
    
    return user_data.get(email, ([], []))

def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Get user profile information.
    In production, this would query a database.
    """
    # Mock profile data
    profiles = {
        'admin@example.com': {
            'name': 'Admin User',
            'subscription_tier': 'premium',
            'api_quota': 10000,
            'created_at': '2024-01-01T00:00:00Z'
        },
        'user@example.com': {
            'name': 'Regular User',
            'subscription_tier': 'free',
            'api_quota': 100,
            'created_at': '2024-01-15T00:00:00Z'
        },
        'researcher@example.com': {
            'name': 'Research User',
            'subscription_tier': 'professional',
            'api_quota': 1000,
            'created_at': '2024-01-10T00:00:00Z'
        }
    }
    
    return profiles.get(user_id, {
        'name': 'Unknown User',
        'subscription_tier': 'free',
        'api_quota': 100,
        'created_at': '2024-01-01T00:00:00Z'
    })

def get_all_users() -> list:
    """
    Get all users (admin function).
    In production, this would query a database.
    """
    return [
        {
            'user_id': 'admin@example.com',
            'name': 'Admin User',
            'subscription_tier': 'premium',
            'status': 'active'
        },
        {
            'user_id': 'user@example.com',
            'name': 'Regular User',
            'subscription_tier': 'free',
            'status': 'active'
        },
        {
            'user_id': 'researcher@example.com',
            'name': 'Research User',
            'subscription_tier': 'professional',
            'status': 'active'
        }
    ]

def get_security_metrics() -> Dict[str, Any]:
    """
    Get security metrics (admin function).
    In production, this would query CloudWatch or a monitoring system.
    """
    return {
        'total_users': 3,
        'active_sessions': 2,
        'failed_login_attempts_24h': 5,
        'rate_limit_violations_24h': 12,
        'security_events_24h': {
            'authentication_attempts': 45,
            'authorization_failures': 3,
            'input_validation_failures': 8
        },
        'top_blocked_ips': [
            {'ip': '192.168.1.100', 'violations': 15},
            {'ip': '10.0.0.50', 'violations': 8}
        ]
    }

# Lambda entry points
def login(event, context):
    """Lambda entry point for login."""
    return login_handler(event, context)

def refresh_token(event, context):
    """Lambda entry point for token refresh."""
    return refresh_token_handler(event, context)

def user_profile(event, context):
    """Lambda entry point for user profile."""
    return user_profile_handler(event, context)

def admin(event, context):
    """Lambda entry point for admin functions."""
    return admin_handler(event, context)