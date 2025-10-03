"""
Comprehensive Error Handling and Monitoring Utilities for Agent Scholar

This module provides centralized error handling, logging, and monitoring
capabilities for all Lambda functions in the Agent Scholar system.
"""

import json
import logging
import traceback
import time
import boto3
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from functools import wraps
from enum import Enum
import os

# Initialize CloudWatch client
cloudwatch = boto3.client('cloudwatch')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class ErrorSeverity(Enum):
    """Error severity levels for monitoring and alerting."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ErrorCategory(Enum):
    """Error categories for classification and handling."""
    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    EXTERNAL_API = "EXTERNAL_API"
    DATABASE = "DATABASE"
    PROCESSING = "PROCESSING"
    TIMEOUT = "TIMEOUT"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"

class AgentScholarError(Exception):
    """Base exception class for Agent Scholar specific errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.utcnow().isoformat()

class ValidationError(AgentScholarError):
    """Error for data validation failures."""
    
    def __init__(self, message: str, field: str = None, **kwargs):
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            details={"field": field} if field else {},
            **kwargs
        )

class ExternalAPIError(AgentScholarError):
    """Error for external API failures."""
    
    def __init__(self, message: str, api_name: str = None, status_code: int = None, **kwargs):
        super().__init__(
            message,
            error_code="EXTERNAL_API_ERROR",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.EXTERNAL_API,
            details={"api_name": api_name, "status_code": status_code},
            **kwargs
        )

class ProcessingError(AgentScholarError):
    """Error for processing failures."""
    
    def __init__(self, message: str, operation: str = None, **kwargs):
        super().__init__(
            message,
            error_code="PROCESSING_ERROR",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.PROCESSING,
            details={"operation": operation} if operation else {},
            **kwargs
        )

class TimeoutError(AgentScholarError):
    """Error for timeout scenarios."""
    
    def __init__(self, message: str, timeout_duration: float = None, **kwargs):
        super().__init__(
            message,
            error_code="TIMEOUT_ERROR",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.TIMEOUT,
            details={"timeout_duration": timeout_duration} if timeout_duration else {},
            **kwargs
        )

class ErrorHandler:
    """Centralized error handling and monitoring class."""
    
    def __init__(self, service_name: str, function_name: str = None):
        self.service_name = service_name
        self.function_name = function_name or os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        self.logger = logging.getLogger(f"{service_name}.{self.function_name}")
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle and log errors with appropriate monitoring metrics.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            request_id: Request identifier for tracing
            
        Returns:
            Formatted error response
        """
        context = context or {}
        request_id = request_id or context.get('aws_request_id', 'unknown')
        
        # Determine error details
        if isinstance(error, AgentScholarError):
            error_details = {
                'error_code': error.error_code,
                'severity': error.severity.value,
                'category': error.category.value,
                'recoverable': error.recoverable,
                'details': error.details,
                'timestamp': error.timestamp
            }
        else:
            error_details = {
                'error_code': 'UNEXPECTED_ERROR',
                'severity': ErrorSeverity.HIGH.value,
                'category': ErrorCategory.UNKNOWN.value,
                'recoverable': False,
                'details': {},
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Log the error
        self._log_error(error, error_details, context, request_id)
        
        # Send metrics to CloudWatch
        self._send_error_metrics(error_details)
        
        # Create response
        response = {
            'error': True,
            'message': str(error),
            'error_code': error_details['error_code'],
            'severity': error_details['severity'],
            'recoverable': error_details['recoverable'],
            'request_id': request_id,
            'timestamp': error_details['timestamp']
        }
        
        # Add details for debugging (exclude in production if needed)
        if os.getenv('ENVIRONMENT') != 'production':
            response['details'] = error_details['details']
            response['traceback'] = traceback.format_exc()
        
        return response
    
    def _log_error(
        self,
        error: Exception,
        error_details: Dict[str, Any],
        context: Dict[str, Any],
        request_id: str
    ):
        """Log error with structured logging."""
        log_entry = {
            'level': 'ERROR',
            'service': self.service_name,
            'function': self.function_name,
            'request_id': request_id,
            'error_message': str(error),
            'error_type': type(error).__name__,
            'error_details': error_details,
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        self.logger.error(json.dumps(log_entry, default=str))
    
    def _send_error_metrics(self, error_details: Dict[str, Any]):
        """Send error metrics to CloudWatch."""
        try:
            # Send general error metric
            cloudwatch.put_metric_data(
                Namespace='AgentScholar',
                MetricData=[
                    {
                        'MetricName': 'Errors',
                        'Dimensions': [
                            {
                                'Name': 'Service',
                                'Value': self.service_name
                            },
                            {
                                'Name': 'Function',
                                'Value': self.function_name
                            },
                            {
                                'Name': 'ErrorCode',
                                'Value': error_details['error_code']
                            }
                        ],
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.utcnow()
                    }
                ]
            )
            
            # Send severity-specific metric
            cloudwatch.put_metric_data(
                Namespace='AgentScholar',
                MetricData=[
                    {
                        'MetricName': f"Errors{error_details['severity']}",
                        'Dimensions': [
                            {
                                'Name': 'Service',
                                'Value': self.service_name
                            },
                            {
                                'Name': 'Function',
                                'Value': self.function_name
                            }
                        ],
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.utcnow()
                    }
                ]
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to send error metrics: {str(e)}")

def error_handler_decorator(service_name: str, function_name: str = None):
    """
    Decorator for automatic error handling in Lambda functions.
    
    Args:
        service_name: Name of the service
        function_name: Name of the function (optional)
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            handler = ErrorHandler(service_name, function_name)
            start_time = time.time()
            
            try:
                # Log function start
                handler.logger.info(json.dumps({
                    'level': 'INFO',
                    'message': f'Function {func.__name__} started',
                    'service': service_name,
                    'function': function_name or func.__name__,
                    'request_id': getattr(context, 'aws_request_id', 'unknown'),
                    'event': event
                }, default=str))
                
                # Execute function
                result = func(event, context)
                
                # Log success and send metrics
                duration = time.time() - start_time
                handler._send_success_metrics(duration)
                
                handler.logger.info(json.dumps({
                    'level': 'INFO',
                    'message': f'Function {func.__name__} completed successfully',
                    'service': service_name,
                    'function': function_name or func.__name__,
                    'request_id': getattr(context, 'aws_request_id', 'unknown'),
                    'duration': duration
                }, default=str))
                
                return result
                
            except Exception as e:
                # Handle error
                error_response = handler.handle_error(
                    e,
                    context={
                        'function_name': func.__name__,
                        'event': event,
                        'aws_request_id': getattr(context, 'aws_request_id', 'unknown')
                    },
                    request_id=getattr(context, 'aws_request_id', 'unknown')
                )
                
                # Return error response with appropriate status code
                if isinstance(e, ValidationError):
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps(error_response)
                    }
                elif isinstance(e, (ExternalAPIError, TimeoutError)):
                    return {
                        'statusCode': 503,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps(error_response)
                    }
                else:
                    return {
                        'statusCode': 500,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps(error_response)
                    }
        
        return wrapper
    return decorator

class CircuitBreaker:
    """Circuit breaker pattern implementation for external service calls."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise ExternalAPIError(
                    "Circuit breaker is OPEN - service unavailable",
                    details={'state': self.state, 'failure_count': self.failure_count}
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class RetryHandler:
    """Retry handler with exponential backoff."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        retryable_exceptions: List[type] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.retryable_exceptions = retryable_exceptions or [ExternalAPIError, TimeoutError]
    
    def retry(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not any(isinstance(e, exc_type) for exc_type in self.retryable_exceptions):
                    raise
                
                # Don't retry on last attempt
                if attempt == self.max_retries:
                    raise
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.base_delay * (self.backoff_multiplier ** attempt),
                    self.max_delay
                )
                
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
                time.sleep(delay)
        
        # This should never be reached, but just in case
        raise last_exception

# Utility functions for common error scenarios
def validate_required_fields(data: Dict[str, Any], required_fields: List[str]):
    """Validate that required fields are present in data."""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={'missing_fields': missing_fields}
        )

def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]):
    """Validate field types in data."""
    type_errors = []
    
    for field, expected_type in field_types.items():
        if field in data and not isinstance(data[field], expected_type):
            type_errors.append({
                'field': field,
                'expected_type': expected_type.__name__,
                'actual_type': type(data[field]).__name__
            })
    
    if type_errors:
        raise ValidationError(
            f"Invalid field types: {type_errors}",
            details={'type_errors': type_errors}
        )

def handle_external_api_call(
    api_call: Callable,
    api_name: str,
    circuit_breaker: CircuitBreaker = None,
    retry_handler: RetryHandler = None,
    timeout: float = 30.0
) -> Any:
    """
    Handle external API calls with circuit breaker and retry logic.
    
    Args:
        api_call: The API call function
        api_name: Name of the API for logging
        circuit_breaker: Circuit breaker instance
        retry_handler: Retry handler instance
        timeout: Request timeout
        
    Returns:
        API response
    """
    def wrapped_call():
        try:
            if circuit_breaker:
                return circuit_breaker.call(api_call)
            else:
                return api_call()
        except Exception as e:
            raise ExternalAPIError(
                f"API call to {api_name} failed: {str(e)}",
                api_name=api_name
            )
    
    if retry_handler:
        return retry_handler.retry(wrapped_call)
    else:
        return wrapped_call()

# Global instances for common use cases
default_circuit_breaker = CircuitBreaker()
default_retry_handler = RetryHandler()