"""
Shared utilities package for Agent Scholar

This package contains common models, utilities, and functions
used across all Lambda functions and components.
"""

from .models import (
    Document,
    DocumentChunk,
    ResearchQuery,
    QueryIntent,
    AgentResponse,
    ReasoningStep,
    Source,
    ToolInvocation,
    validate_document,
    validate_query
)

from .utils import (
    setup_logging,
    generate_id,
    hash_content,
    chunk_text,
    extract_text_from_file,
    format_timestamp,
    safe_json_loads,
    safe_json_dumps,
    get_aws_client,
    handle_aws_error,
    validate_environment_variables,
    create_bedrock_response,
    measure_execution_time
)

__all__ = [
    # Models
    'Document',
    'DocumentChunk',
    'ResearchQuery',
    'QueryIntent',
    'AgentResponse',
    'ReasoningStep',
    'Source',
    'ToolInvocation',
    'validate_document',
    'validate_query',
    
    # Utilities
    'setup_logging',
    'generate_id',
    'hash_content',
    'chunk_text',
    'extract_text_from_file',
    'format_timestamp',
    'safe_json_loads',
    'safe_json_dumps',
    'get_aws_client',
    'handle_aws_error',
    'validate_environment_variables',
    'create_bedrock_response',
    'measure_execution_time'
]