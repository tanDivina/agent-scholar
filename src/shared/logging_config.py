"""
Centralized Logging Configuration for Agent Scholar

This module provides structured logging configuration for all Lambda functions
and components in the Agent Scholar system.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import boto3

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def __init__(self, service_name: str, function_name: str = None):
        super().__init__()
        self.service_name = service_name
        self.function_name = function_name or os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'service': self.service_name,
            'function': self.function_name,
            'message': record.getMessage(),
            'logger': record.name,
            'module': record.module,
            'line': record.lineno
        }
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }
        
        return json.dumps(log_entry, default=str)

class AgentScholarLogger:
    """Enhanced logger for Agent Scholar components."""
    
    def __init__(self, service_name: str, function_name: str = None, log_level: str = None):
        self.service_name = service_name
        self.function_name = function_name or os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
        self.log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
        
        # Create logger
        self.logger = logging.getLogger(f"{service_name}.{self.function_name}")
        self.logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add structured handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter(service_name, self.function_name))
        self.logger.addHandler(handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
    
    def info(self, message: str, extra_fields: Dict[str, Any] = None, request_id: str = None):
        """Log info message with optional extra fields."""
        self._log(logging.INFO, message, extra_fields, request_id)
    
    def warning(self, message: str, extra_fields: Dict[str, Any] = None, request_id: str = None):
        """Log warning message with optional extra fields."""
        self._log(logging.WARNING, message, extra_fields, request_id)
    
    def error(self, message: str, extra_fields: Dict[str, Any] = None, request_id: str = None, exc_info: bool = False):
        """Log error message with optional extra fields."""
        self._log(logging.ERROR, message, extra_fields, request_id, exc_info)
    
    def debug(self, message: str, extra_fields: Dict[str, Any] = None, request_id: str = None):
        """Log debug message with optional extra fields."""
        self._log(logging.DEBUG, message, extra_fields, request_id)
    
    def _log(self, level: int, message: str, extra_fields: Dict[str, Any] = None, request_id: str = None, exc_info: bool = False):
        """Internal logging method."""
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=sys.exc_info() if exc_info else None
        )
        
        if extra_fields:
            record.extra_fields = extra_fields
        
        if request_id:
            record.request_id = request_id
        
        self.logger.handle(record)
    
    def log_function_start(self, function_name: str, event: Dict[str, Any], request_id: str = None):
        """Log function start with event details."""
        self.info(
            f"Function {function_name} started",
            extra_fields={
                'event_type': 'function_start',
                'function_name': function_name,
                'event': self._sanitize_event(event)
            },
            request_id=request_id
        )
    
    def log_function_end(self, function_name: str, duration: float, request_id: str = None):
        """Log function completion with duration."""
        self.info(
            f"Function {function_name} completed",
            extra_fields={
                'event_type': 'function_end',
                'function_name': function_name,
                'duration_ms': round(duration * 1000, 2)
            },
            request_id=request_id
        )
    
    def log_api_call(self, api_name: str, method: str, url: str, status_code: int = None, duration: float = None, request_id: str = None):
        """Log external API call."""
        extra_fields = {
            'event_type': 'api_call',
            'api_name': api_name,
            'method': method,
            'url': url
        }
        
        if status_code is not None:
            extra_fields['status_code'] = status_code
        
        if duration is not None:
            extra_fields['duration_ms'] = round(duration * 1000, 2)
        
        level = logging.INFO if status_code and 200 <= status_code < 400 else logging.WARNING
        message = f"API call to {api_name}: {method} {url}"
        
        if status_code:
            message += f" -> {status_code}"
        
        self._log(level, message, extra_fields, request_id)
    
    def log_database_operation(self, operation: str, table: str, duration: float = None, request_id: str = None):
        """Log database operation."""
        extra_fields = {
            'event_type': 'database_operation',
            'operation': operation,
            'table': table
        }
        
        if duration is not None:
            extra_fields['duration_ms'] = round(duration * 1000, 2)
        
        self.info(
            f"Database operation: {operation} on {table}",
            extra_fields=extra_fields,
            request_id=request_id
        )
    
    def log_processing_step(self, step: str, details: Dict[str, Any] = None, request_id: str = None):
        """Log processing step."""
        extra_fields = {
            'event_type': 'processing_step',
            'step': step
        }
        
        if details:
            extra_fields.update(details)
        
        self.info(
            f"Processing step: {step}",
            extra_fields=extra_fields,
            request_id=request_id
        )
    
    def _sanitize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize event data for logging (remove sensitive information)."""
        sanitized = event.copy()
        
        # Remove sensitive fields
        sensitive_fields = ['password', 'token', 'key', 'secret', 'authorization']
        
        def remove_sensitive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in list(obj.items()):
                    if any(sensitive in key.lower() for sensitive in sensitive_fields):
                        obj[key] = "[REDACTED]"
                    else:
                        remove_sensitive(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    remove_sensitive(item, f"{path}[{i}]")
        
        remove_sensitive(sanitized)
        return sanitized

class CloudWatchLogsHandler(logging.Handler):
    """Custom handler for sending logs to CloudWatch Logs."""
    
    def __init__(self, log_group: str, log_stream: str = None):
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream or f"{os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown')}-{datetime.utcnow().strftime('%Y%m%d')}"
        self.logs_client = boto3.client('logs')
        self.sequence_token = None
        
        # Create log group and stream if they don't exist
        self._ensure_log_group_exists()
        self._ensure_log_stream_exists()
    
    def emit(self, record: logging.LogRecord):
        """Emit log record to CloudWatch Logs."""
        try:
            log_event = {
                'timestamp': int(record.created * 1000),
                'message': self.format(record)
            }
            
            kwargs = {
                'logGroupName': self.log_group,
                'logStreamName': self.log_stream,
                'logEvents': [log_event]
            }
            
            if self.sequence_token:
                kwargs['sequenceToken'] = self.sequence_token
            
            response = self.logs_client.put_log_events(**kwargs)
            self.sequence_token = response.get('nextSequenceToken')
            
        except Exception as e:
            # Don't raise exceptions from logging handler
            print(f"Failed to send log to CloudWatch: {str(e)}")
    
    def _ensure_log_group_exists(self):
        """Ensure log group exists."""
        try:
            self.logs_client.create_log_group(logGroupName=self.log_group)
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            print(f"Failed to create log group: {str(e)}")
    
    def _ensure_log_stream_exists(self):
        """Ensure log stream exists."""
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group,
                logStreamName=self.log_stream
            )
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            print(f"Failed to create log stream: {str(e)}")

def setup_logging(service_name: str, function_name: str = None, log_level: str = None, enable_cloudwatch: bool = False) -> AgentScholarLogger:
    """
    Set up logging for Agent Scholar components.
    
    Args:
        service_name: Name of the service
        function_name: Name of the function (optional)
        log_level: Log level (optional, defaults to INFO)
        enable_cloudwatch: Whether to enable CloudWatch Logs handler
        
    Returns:
        Configured logger instance
    """
    logger = AgentScholarLogger(service_name, function_name, log_level)
    
    if enable_cloudwatch:
        log_group = f"/aws/lambda/{function_name or service_name}"
        cloudwatch_handler = CloudWatchLogsHandler(log_group)
        cloudwatch_handler.setFormatter(StructuredFormatter(service_name, function_name))
        logger.logger.addHandler(cloudwatch_handler)
    
    return logger

# Global logger instances for common services
orchestrator_logger = setup_logging('orchestrator')
web_search_logger = setup_logging('web_search')
code_execution_logger = setup_logging('code_execution')
cross_analysis_logger = setup_logging('cross_analysis')
document_indexing_logger = setup_logging('document_indexing')