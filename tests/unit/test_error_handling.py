"""
Unit tests for error handling and monitoring utilities.

Tests the comprehensive error handling, logging, and monitoring
capabilities of the Agent Scholar system.
"""

import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from shared.error_handler import (
    AgentScholarError,
    ValidationError,
    ExternalAPIError,
    ProcessingError,
    TimeoutError,
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    error_handler_decorator,
    CircuitBreaker,
    RetryHandler,
    validate_required_fields,
    validate_field_types,
    handle_external_api_call
)

from shared.health_check import (
    HealthChecker,
    HealthStatus,
    HealthCheckResult,
    StandardHealthChecks,
    SystemHealthMonitor
)

from shared.logging_config import (
    AgentScholarLogger,
    StructuredFormatter,
    setup_logging
)

class TestAgentScholarErrors(unittest.TestCase):
    """Test custom exception classes."""
    
    def test_agent_scholar_error_creation(self):
        """Test basic AgentScholarError creation."""
        error = AgentScholarError(
            "Test error message",
            error_code="TEST_ERROR",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.PROCESSING,
            details={'key': 'value'},
            recoverable=False
        )
        
        self.assertEqual(str(error), "Test error message")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.severity, ErrorSeverity.HIGH)
        self.assertEqual(error.category, ErrorCategory.PROCESSING)
        self.assertEqual(error.details, {'key': 'value'})
        self.assertFalse(error.recoverable)
        self.assertIsInstance(error.timestamp, str)
    
    def test_validation_error(self):
        """Test ValidationError specific functionality."""
        error = ValidationError("Invalid field", field="test_field")
        
        self.assertEqual(error.error_code, "VALIDATION_ERROR")
        self.assertEqual(error.severity, ErrorSeverity.LOW)
        self.assertEqual(error.category, ErrorCategory.VALIDATION)
        self.assertEqual(error.details['field'], "test_field")
    
    def test_external_api_error(self):
        """Test ExternalAPIError specific functionality."""
        error = ExternalAPIError("API failed", api_name="test_api", status_code=500)
        
        self.assertEqual(error.error_code, "EXTERNAL_API_ERROR")
        self.assertEqual(error.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(error.category, ErrorCategory.EXTERNAL_API)
        self.assertEqual(error.details['api_name'], "test_api")
        self.assertEqual(error.details['status_code'], 500)
    
    def test_processing_error(self):
        """Test ProcessingError specific functionality."""
        error = ProcessingError("Processing failed", operation="test_operation")
        
        self.assertEqual(error.error_code, "PROCESSING_ERROR")
        self.assertEqual(error.severity, ErrorSeverity.MEDIUM)
        self.assertEqual(error.category, ErrorCategory.PROCESSING)
        self.assertEqual(error.details['operation'], "test_operation")
    
    def test_timeout_error(self):
        """Test TimeoutError specific functionality."""
        error = TimeoutError("Operation timed out", timeout_duration=30.0)
        
        self.assertEqual(error.error_code, "TIMEOUT_ERROR")
        self.assertEqual(error.severity, ErrorSeverity.HIGH)
        self.assertEqual(error.category, ErrorCategory.TIMEOUT)
        self.assertEqual(error.details['timeout_duration'], 30.0)

class TestErrorHandler(unittest.TestCase):
    """Test ErrorHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler("test_service", "test_function")
    
    @patch('shared.error_handler.cloudwatch')
    def test_handle_agent_scholar_error(self, mock_cloudwatch):
        """Test handling of AgentScholarError."""
        error = ValidationError("Test validation error", field="test_field")
        context = {'test_key': 'test_value'}
        request_id = 'test-request-123'
        
        result = self.error_handler.handle_error(error, context, request_id)
        
        self.assertTrue(result['error'])
        self.assertEqual(result['error_code'], 'VALIDATION_ERROR')
        self.assertEqual(result['severity'], 'LOW')
        self.assertTrue(result['recoverable'])
        self.assertEqual(result['request_id'], request_id)
        
        # Verify CloudWatch metric was sent
        mock_cloudwatch.put_metric_data.assert_called()
    
    @patch('shared.error_handler.cloudwatch')
    def test_handle_unexpected_error(self, mock_cloudwatch):
        """Test handling of unexpected errors."""
        error = ValueError("Unexpected error")
        
        result = self.error_handler.handle_error(error)
        
        self.assertTrue(result['error'])
        self.assertEqual(result['error_code'], 'UNEXPECTED_ERROR')
        self.assertEqual(result['severity'], 'HIGH')
        self.assertFalse(result['recoverable'])
        
        # Verify CloudWatch metric was sent
        mock_cloudwatch.put_metric_data.assert_called()
    
    @patch('shared.error_handler.cloudwatch')
    def test_cloudwatch_metric_failure(self, mock_cloudwatch):
        """Test graceful handling of CloudWatch metric failures."""
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        
        error = ValidationError("Test error")
        result = self.error_handler.handle_error(error)
        
        # Should still return error response even if metrics fail
        self.assertTrue(result['error'])
        self.assertEqual(result['error_code'], 'VALIDATION_ERROR')

class TestErrorHandlerDecorator(unittest.TestCase):
    """Test error handler decorator."""
    
    @patch('shared.error_handler.cloudwatch')
    def test_successful_function_execution(self, mock_cloudwatch):
        """Test decorator with successful function execution."""
        @error_handler_decorator('test_service', 'test_function')
        def test_function(event, context):
            return {'statusCode': 200, 'body': 'success'}
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-123'
        
        result = test_function({'test': 'event'}, mock_context)
        
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['body'], 'success')
    
    @patch('shared.error_handler.cloudwatch')
    def test_validation_error_handling(self, mock_cloudwatch):
        """Test decorator handling ValidationError."""
        @error_handler_decorator('test_service', 'test_function')
        def test_function(event, context):
            raise ValidationError("Invalid input")
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-123'
        
        result = test_function({'test': 'event'}, mock_context)
        
        self.assertEqual(result['statusCode'], 400)
        body = json.loads(result['body'])
        self.assertTrue(body['error'])
        self.assertEqual(body['error_code'], 'VALIDATION_ERROR')
    
    @patch('shared.error_handler.cloudwatch')
    def test_external_api_error_handling(self, mock_cloudwatch):
        """Test decorator handling ExternalAPIError."""
        @error_handler_decorator('test_service', 'test_function')
        def test_function(event, context):
            raise ExternalAPIError("API failed")
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-123'
        
        result = test_function({'test': 'event'}, mock_context)
        
        self.assertEqual(result['statusCode'], 503)
        body = json.loads(result['body'])
        self.assertTrue(body['error'])
        self.assertEqual(body['error_code'], 'EXTERNAL_API_ERROR')
    
    @patch('shared.error_handler.cloudwatch')
    def test_unexpected_error_handling(self, mock_cloudwatch):
        """Test decorator handling unexpected errors."""
        @error_handler_decorator('test_service', 'test_function')
        def test_function(event, context):
            raise ValueError("Unexpected error")
        
        mock_context = Mock()
        mock_context.aws_request_id = 'test-request-123'
        
        result = test_function({'test': 'event'}, mock_context)
        
        self.assertEqual(result['statusCode'], 500)
        body = json.loads(result['body'])
        self.assertTrue(body['error'])
        self.assertEqual(body['error_code'], 'UNEXPECTED_ERROR')

class TestCircuitBreaker(unittest.TestCase):
    """Test CircuitBreaker implementation."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        circuit_breaker = CircuitBreaker(failure_threshold=3)
        
        def successful_function():
            return "success"
        
        result = circuit_breaker.call(successful_function)
        self.assertEqual(result, "success")
        self.assertEqual(circuit_breaker.state, 'CLOSED')
        self.assertEqual(circuit_breaker.failure_count, 0)
    
    def test_circuit_breaker_open_state(self):
        """Test circuit breaker opening after failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2)
        
        def failing_function():
            raise Exception("Function failed")
        
        # First failure
        with self.assertRaises(Exception):
            circuit_breaker.call(failing_function)
        self.assertEqual(circuit_breaker.failure_count, 1)
        self.assertEqual(circuit_breaker.state, 'CLOSED')
        
        # Second failure - should open circuit
        with self.assertRaises(Exception):
            circuit_breaker.call(failing_function)
        self.assertEqual(circuit_breaker.failure_count, 2)
        self.assertEqual(circuit_breaker.state, 'OPEN')
        
        # Third call should be rejected
        with self.assertRaises(ExternalAPIError):
            circuit_breaker.call(failing_function)
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def failing_function():
            raise Exception("Function failed")
        
        def successful_function():
            return "success"
        
        # Trigger failure to open circuit
        with self.assertRaises(Exception):
            circuit_breaker.call(failing_function)
        self.assertEqual(circuit_breaker.state, 'OPEN')
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Should allow call and reset on success
        result = circuit_breaker.call(successful_function)
        self.assertEqual(result, "success")
        self.assertEqual(circuit_breaker.state, 'CLOSED')
        self.assertEqual(circuit_breaker.failure_count, 0)

class TestRetryHandler(unittest.TestCase):
    """Test RetryHandler implementation."""
    
    def test_successful_retry(self):
        """Test successful execution without retries."""
        retry_handler = RetryHandler(max_retries=3)
        
        def successful_function():
            return "success"
        
        result = retry_handler.retry(successful_function)
        self.assertEqual(result, "success")
    
    def test_retry_with_recoverable_error(self):
        """Test retry with recoverable error."""
        retry_handler = RetryHandler(max_retries=2, base_delay=0.01)
        call_count = 0
        
        def failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ExternalAPIError("Temporary failure")
            return "success"
        
        result = retry_handler.retry(failing_then_succeeding_function)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_retry_exhaustion(self):
        """Test retry exhaustion with persistent failures."""
        retry_handler = RetryHandler(max_retries=2, base_delay=0.01)
        
        def always_failing_function():
            raise ExternalAPIError("Persistent failure")
        
        with self.assertRaises(ExternalAPIError):
            retry_handler.retry(always_failing_function)
    
    def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        retry_handler = RetryHandler(max_retries=3, retryable_exceptions=[ExternalAPIError])
        
        def function_with_validation_error():
            raise ValidationError("Invalid input")
        
        with self.assertRaises(ValidationError):
            retry_handler.retry(function_with_validation_error)

class TestValidationUtilities(unittest.TestCase):
    """Test validation utility functions."""
    
    def test_validate_required_fields_success(self):
        """Test successful required field validation."""
        data = {'field1': 'value1', 'field2': 'value2'}
        required_fields = ['field1', 'field2']
        
        # Should not raise exception
        validate_required_fields(data, required_fields)
    
    def test_validate_required_fields_missing(self):
        """Test required field validation with missing fields."""
        data = {'field1': 'value1'}
        required_fields = ['field1', 'field2', 'field3']
        
        with self.assertRaises(ValidationError) as context:
            validate_required_fields(data, required_fields)
        
        error = context.exception
        self.assertIn('field2', error.details['missing_fields'])
        self.assertIn('field3', error.details['missing_fields'])
    
    def test_validate_field_types_success(self):
        """Test successful field type validation."""
        data = {'string_field': 'value', 'int_field': 42, 'bool_field': True}
        field_types = {'string_field': str, 'int_field': int, 'bool_field': bool}
        
        # Should not raise exception
        validate_field_types(data, field_types)
    
    def test_validate_field_types_invalid(self):
        """Test field type validation with invalid types."""
        data = {'string_field': 42, 'int_field': 'not_int'}
        field_types = {'string_field': str, 'int_field': int}
        
        with self.assertRaises(ValidationError) as context:
            validate_field_types(data, field_types)
        
        error = context.exception
        self.assertEqual(len(error.details['type_errors']), 2)

class TestHealthChecker(unittest.TestCase):
    """Test HealthChecker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.health_checker = HealthChecker()
    
    def test_register_and_run_check(self):
        """Test registering and running a health check."""
        def test_check():
            return {'status': 'healthy'}
        
        self.health_checker.register_check('test_component', test_check)
        
        # Run checks synchronously for testing
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.health_checker.run_all_checks())
        loop.close()
        
        self.assertIn('test_component', results)
        result = results['test_component']
        self.assertEqual(result.component, 'test_component')
        self.assertEqual(result.status, HealthStatus.HEALTHY)
    
    def test_health_check_failure(self):
        """Test health check failure handling."""
        def failing_check():
            raise Exception("Health check failed")
        
        self.health_checker.register_check('failing_component', failing_check)
        
        # Run checks synchronously for testing
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.health_checker.run_all_checks())
        loop.close()
        
        self.assertIn('failing_component', results)
        result = results['failing_component']
        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn('Health check failed', result.message)
    
    def test_overall_status_calculation(self):
        """Test overall status calculation."""
        results = {
            'healthy1': HealthCheckResult('healthy1', HealthStatus.HEALTHY, 0.1, 'OK', {}, ''),
            'healthy2': HealthCheckResult('healthy2', HealthStatus.HEALTHY, 0.2, 'OK', {}, ''),
            'degraded': HealthCheckResult('degraded', HealthStatus.DEGRADED, 5.0, 'Slow', {}, ''),
        }
        
        overall_status = self.health_checker.get_overall_status(results)
        self.assertEqual(overall_status, HealthStatus.DEGRADED)
        
        # Test with unhealthy component
        results['unhealthy'] = HealthCheckResult('unhealthy', HealthStatus.UNHEALTHY, 0.0, 'Failed', {}, '')
        overall_status = self.health_checker.get_overall_status(results)
        self.assertEqual(overall_status, HealthStatus.UNHEALTHY)

class TestStandardHealthChecks(unittest.TestCase):
    """Test standard health check functions."""
    
    @patch('requests.get')
    def test_api_gateway_health_success(self, mock_get):
        """Test successful API Gateway health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.5
        mock_get.return_value = mock_response
        
        result = StandardHealthChecks.api_gateway_health('https://api.example.com')
        
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['response_time'], 0.5)
    
    @patch('requests.get')
    def test_api_gateway_health_failure(self, mock_get):
        """Test failed API Gateway health check."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = StandardHealthChecks.api_gateway_health('https://api.example.com')
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['status_code'], 500)
    
    @patch('boto3.client')
    def test_lambda_function_health_success(self, mock_boto3):
        """Test successful Lambda function health check."""
        mock_lambda = Mock()
        mock_lambda.get_function.return_value = {
            'Configuration': {
                'State': 'Active',
                'LastUpdateStatus': 'Successful',
                'Runtime': 'python3.9',
                'MemorySize': 512
            }
        }
        mock_boto3.return_value = mock_lambda
        
        result = StandardHealthChecks.lambda_function_health('test-function')
        
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['state'], 'Active')
        self.assertEqual(result['last_update_status'], 'Successful')

class TestLoggingConfiguration(unittest.TestCase):
    """Test logging configuration."""
    
    def test_structured_formatter(self):
        """Test structured log formatter."""
        formatter = StructuredFormatter('test_service', 'test_function')
        
        # Create a log record
        import logging
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        self.assertEqual(log_data['level'], 'INFO')
        self.assertEqual(log_data['service'], 'test_service')
        self.assertEqual(log_data['function'], 'test_function')
        self.assertEqual(log_data['message'], 'Test message')
        self.assertEqual(log_data['line'], 42)
    
    def test_agent_scholar_logger(self):
        """Test AgentScholarLogger functionality."""
        logger = AgentScholarLogger('test_service', 'test_function')
        
        # Test that logger is properly configured
        self.assertEqual(logger.service_name, 'test_service')
        self.assertEqual(logger.function_name, 'test_function')
        self.assertIsNotNone(logger.logger)
    
    def test_setup_logging(self):
        """Test logging setup function."""
        logger = setup_logging('test_service', 'test_function', 'DEBUG')
        
        self.assertIsInstance(logger, AgentScholarLogger)
        self.assertEqual(logger.service_name, 'test_service')
        self.assertEqual(logger.function_name, 'test_function')

if __name__ == '__main__':
    unittest.main()