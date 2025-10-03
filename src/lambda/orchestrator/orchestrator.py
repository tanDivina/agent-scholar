"""
API Orchestrator Lambda Function for Agent Scholar

This Lambda function handles API Gateway requests and orchestrates
communication with the Bedrock Agent. It provides session management,
context preservation, and comprehensive error handling.
"""

import json
import logging
import os
import boto3
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

# Import error handling utilities
import sys
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.error_handler import (
    error_handler_decorator,
    ErrorHandler,
    ValidationError,
    ExternalAPIError,
    ProcessingError,
    TimeoutError,
    validate_required_fields,
    validate_field_types,
    handle_external_api_call,
    default_circuit_breaker,
    default_retry_handler
)
from shared.health_check import create_health_check_handler

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

# Session management
SESSION_TABLE_NAME = os.getenv('SESSION_TABLE_NAME', 'agent-scholar-sessions')
SESSION_TIMEOUT_HOURS = 24

@dataclass
class SessionContext:
    """Session context for maintaining conversation state."""
    session_id: str
    user_id: Optional[str]
    created_at: datetime
    last_accessed: datetime
    query_count: int
    conversation_history: List[Dict[str, Any]]
    context_summary: str

@error_handler_decorator('orchestrator', 'agent-scholar-orchestrator')
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for API Gateway requests.
    
    Args:
        event: API Gateway event
        context: Lambda context object
        
    Returns:
        API Gateway response
    """
    try:
        logger.info(f"Received API request: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', 'UNKNOWN')}")
        
        # Handle different HTTP methods
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/chat')
        
        if http_method == 'OPTIONS':
            return create_api_response(200, {})
        
        if path == '/health':
            return handle_health_check()
        
        if path == '/chat' and http_method == 'POST':
            return handle_chat_request(event)
        
        if path.startswith('/session') and http_method == 'GET':
            return handle_session_request(event)
        
        return create_api_response(404, {'error': 'Endpoint not found'})
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return create_api_response(500, {'error': f'Internal server error: {str(e)}'})

def handle_health_check() -> Dict[str, Any]:
    """Handle health check requests."""
    return create_api_response(200, {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'agent-scholar-orchestrator'
    })

def handle_chat_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle chat requests with session management."""
    # Parse the request body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON in request body")
    
    # Validate required fields
    validate_required_fields(body, ['query'])
    validate_field_types(body, {'query': str})
    
    query = body.get('query', '').strip()
    session_id = body.get('session_id', str(uuid.uuid4()))
    user_id = body.get('user_id')
    
    if not query:
        raise ValidationError("Query cannot be empty")
    
    if len(query) > 10000:  # Reasonable limit
        raise ValidationError("Query too long (max 10000 characters)")
    
    logger.info(f"Processing query for session: {session_id}")
    
    # Send custom metric
    send_custom_metric('ChatRequests', 1)
    
    # Manage session context
    session_context = get_or_create_session(session_id, user_id)
    
    # Invoke Bedrock Agent with context
    agent_response = invoke_bedrock_agent(query, session_context)
    
    # Update session with new interaction
    update_session_context(session_context, query, agent_response)
    
    # Send success metric
    send_custom_metric('ChatRequestsSuccessful', 1)
    
    return create_api_response(200, {
        'response': agent_response,
        'session_id': session_id,
        'query_count': session_context.query_count + 1
    })

def handle_session_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle session management requests."""
    try:
        path_params = event.get('pathParameters', {})
        session_id = path_params.get('sessionId')
        
        if not session_id:
            return create_api_response(400, {'error': 'Session ID is required'})
        
        session_context = get_session_context(session_id)
        if not session_context:
            return create_api_response(404, {'error': 'Session not found'})
        
        return create_api_response(200, {
            'session_id': session_context.session_id,
            'created_at': session_context.created_at.isoformat(),
            'last_accessed': session_context.last_accessed.isoformat(),
            'query_count': session_context.query_count,
            'conversation_summary': session_context.context_summary
        })
        
    except Exception as e:
        logger.error(f"Error handling session request: {str(e)}", exc_info=True)
        return create_api_response(500, {'error': f'Session management error: {str(e)}'})

def invoke_bedrock_agent(query: str, session_context: SessionContext) -> Dict[str, Any]:
    """
    Invoke the Bedrock Agent with the user query and session context.
    
    Args:
        query: User's research query
        session_context: Session context for conversation continuity
        
    Returns:
        Agent response dictionary
    """
    agent_id = os.getenv('AGENT_ID')
    agent_alias_id = os.getenv('AGENT_ALIAS_ID')
    
    if not agent_id or not agent_alias_id:
        raise ProcessingError("Agent ID and Alias ID must be configured in environment variables")
    
    logger.info(f"Invoking agent {agent_id} with alias {agent_alias_id} for session {session_context.session_id}")
    
    # Send custom metric
    send_custom_metric('AgentInvocations', 1)
    
    # Enhance query with context if available
    enhanced_query = enhance_query_with_context(query, session_context)
    
    def bedrock_api_call():
        """Bedrock API call wrapped for error handling."""
        try:
            return bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_context.session_id,
                inputText=enhanced_query
            )
        except Exception as e:
            if 'ThrottlingException' in str(e):
                raise ExternalAPIError(f"Bedrock Agent throttled: {str(e)}", api_name="bedrock_agent")
            elif 'ValidationException' in str(e):
                raise ValidationError(f"Invalid request to Bedrock Agent: {str(e)}")
            else:
                raise ExternalAPIError(f"Bedrock Agent API error: {str(e)}", api_name="bedrock_agent")
    
    # Use circuit breaker and retry for Bedrock calls
    try:
        response = handle_external_api_call(
            bedrock_api_call,
            "bedrock_agent",
            circuit_breaker=default_circuit_breaker,
            retry_handler=default_retry_handler,
            timeout=120.0
        )
        
        # Process the streaming response
        agent_response = process_agent_response(response)
        
        # Send success metric
        send_custom_metric('AgentInvocationsSuccessful', 1)
        
        return agent_response
        
    except Exception as e:
        # Send failure metric
        send_custom_metric('AgentInvocationFailures', 1)
        
        # Return graceful error response
        return {
            'answer': 'I apologize, but I encountered an error processing your request. Please try again or rephrase your question.',
            'reasoning_steps': [],
            'sources_used': [],
            'tool_invocations': [],
            'session_preserved': False,
            'error': str(e),
            'error_type': 'agent_invocation_error'
        }

def process_agent_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the streaming response from Bedrock Agent.
    
    Args:
        response: Raw response from Bedrock Agent
        
    Returns:
        Processed response dictionary
    """
    try:
        # Extract the completion from the streaming response
        completion = ""
        reasoning_steps = []
        sources_used = []
        tool_invocations = []
        
        # Process the event stream
        event_stream = response.get('completion', [])
        
        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    completion += chunk['bytes'].decode('utf-8')
            elif 'trace' in event:
                # Extract reasoning information from trace
                trace = event['trace']
                
                # Process orchestration trace
                if 'orchestrationTrace' in trace:
                    orchestration = trace['orchestrationTrace']
                    if 'rationale' in orchestration:
                        reasoning_steps.append({
                            'step': len(reasoning_steps) + 1,
                            'rationale': orchestration['rationale']['text'],
                            'timestamp': datetime.utcnow().isoformat()
                        })
                
                # Process knowledge base trace
                if 'knowledgeBaseTrace' in trace:
                    kb_trace = trace['knowledgeBaseTrace']
                    if 'retrievalResults' in kb_trace:
                        for result in kb_trace['retrievalResults']:
                            if 'content' in result:
                                sources_used.append({
                                    'type': 'knowledge_base',
                                    'content': result['content']['text'][:200] + '...',
                                    'score': result.get('score', 0),
                                    'metadata': result.get('metadata', {})
                                })
                
                # Process action group invocations
                if 'actionGroupInvocationTrace' in trace:
                    action_trace = trace['actionGroupInvocationTrace']
                    tool_invocations.append({
                        'action_group': action_trace.get('actionGroupName', 'unknown'),
                        'api_path': action_trace.get('apiPath', ''),
                        'input': action_trace.get('input', {}),
                        'timestamp': datetime.utcnow().isoformat()
                    })
        
        return {
            'answer': completion.strip(),
            'reasoning_steps': reasoning_steps,
            'sources_used': sources_used,
            'tool_invocations': tool_invocations,
            'session_preserved': True,
            'response_time': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing agent response: {str(e)}", exc_info=True)
        return {
            'answer': 'I apologize, but I encountered an error processing the response. Please try again.',
            'reasoning_steps': [],
            'sources_used': [],
            'tool_invocations': [],
            'session_preserved': False,
            'error': str(e),
            'error_type': 'response_processing_error'
        }

def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> SessionContext:
    """
    Get existing session or create a new one.
    
    Args:
        session_id: Session identifier
        user_id: Optional user identifier
        
    Returns:
        SessionContext object
    """
    try:
        # Try to get existing session
        session_context = get_session_context(session_id)
        
        if session_context:
            # Update last accessed time
            session_context.last_accessed = datetime.utcnow()
            return session_context
        
        # Create new session
        now = datetime.utcnow()
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_accessed=now,
            query_count=0,
            conversation_history=[],
            context_summary=""
        )
        
        # Store in DynamoDB if table exists
        try:
            table = dynamodb.Table(SESSION_TABLE_NAME)
            table.put_item(Item={
                'session_id': session_id,
                'user_id': user_id or 'anonymous',
                'created_at': now.isoformat(),
                'last_accessed': now.isoformat(),
                'query_count': 0,
                'conversation_history': [],
                'context_summary': "",
                'ttl': int((now + timedelta(hours=SESSION_TIMEOUT_HOURS)).timestamp())
            })
        except Exception as e:
            logger.warning(f"Could not store session in DynamoDB: {str(e)}")
        
        return session_context
        
    except Exception as e:
        logger.error(f"Error managing session: {str(e)}", exc_info=True)
        # Return minimal session context
        now = datetime.utcnow()
        return SessionContext(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_accessed=now,
            query_count=0,
            conversation_history=[],
            context_summary=""
        )

def get_session_context(session_id: str) -> Optional[SessionContext]:
    """
    Retrieve session context from storage.
    
    Args:
        session_id: Session identifier
        
    Returns:
        SessionContext object or None if not found
    """
    try:
        table = dynamodb.Table(SESSION_TABLE_NAME)
        response = table.get_item(Key={'session_id': session_id})
        
        if 'Item' not in response:
            return None
        
        item = response['Item']
        return SessionContext(
            session_id=item['session_id'],
            user_id=item.get('user_id'),
            created_at=datetime.fromisoformat(item['created_at']),
            last_accessed=datetime.fromisoformat(item['last_accessed']),
            query_count=item.get('query_count', 0),
            conversation_history=item.get('conversation_history', []),
            context_summary=item.get('context_summary', "")
        )
        
    except Exception as e:
        logger.warning(f"Could not retrieve session from DynamoDB: {str(e)}")
        return None

def update_session_context(session_context: SessionContext, query: str, response: Dict[str, Any]) -> None:
    """
    Update session context with new interaction.
    
    Args:
        session_context: Current session context
        query: User query
        response: Agent response
    """
    try:
        # Update session data
        session_context.query_count += 1
        session_context.last_accessed = datetime.utcnow()
        
        # Add to conversation history (keep last 10 interactions)
        interaction = {
            'query': query,
            'response': response.get('answer', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'tools_used': [inv.get('action_group', '') for inv in response.get('tool_invocations', [])]
        }
        
        session_context.conversation_history.append(interaction)
        if len(session_context.conversation_history) > 10:
            session_context.conversation_history = session_context.conversation_history[-10:]
        
        # Update context summary
        session_context.context_summary = generate_context_summary(session_context.conversation_history)
        
        # Store updated session
        try:
            table = dynamodb.Table(SESSION_TABLE_NAME)
            table.update_item(
                Key={'session_id': session_context.session_id},
                UpdateExpression='SET last_accessed = :la, query_count = :qc, conversation_history = :ch, context_summary = :cs, #ttl = :ttl',
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':la': session_context.last_accessed.isoformat(),
                    ':qc': session_context.query_count,
                    ':ch': session_context.conversation_history,
                    ':cs': session_context.context_summary,
                    ':ttl': int((session_context.last_accessed + timedelta(hours=SESSION_TIMEOUT_HOURS)).timestamp())
                }
            )
        except Exception as e:
            logger.warning(f"Could not update session in DynamoDB: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error updating session context: {str(e)}", exc_info=True)

def enhance_query_with_context(query: str, session_context: SessionContext) -> str:
    """
    Enhance user query with conversation context.
    
    Args:
        query: Original user query
        session_context: Session context
        
    Returns:
        Enhanced query with context
    """
    try:
        if not session_context.conversation_history or session_context.query_count == 0:
            return query
        
        # Add context summary if available
        if session_context.context_summary:
            context_prefix = f"[Previous conversation context: {session_context.context_summary}]\n\n"
            return context_prefix + query
        
        return query
        
    except Exception as e:
        logger.warning(f"Error enhancing query with context: {str(e)}")
        return query

def generate_context_summary(conversation_history: List[Dict[str, Any]]) -> str:
    """
    Generate a summary of the conversation context.
    
    Args:
        conversation_history: List of conversation interactions
        
    Returns:
        Context summary string
    """
    try:
        if not conversation_history:
            return ""
        
        # Simple context summary based on recent topics
        recent_topics = []
        tools_used = set()
        
        for interaction in conversation_history[-3:]:  # Last 3 interactions
            query = interaction.get('query', '')
            if len(query) > 10:
                # Extract key terms (simple approach)
                words = query.lower().split()
                key_words = [w for w in words if len(w) > 4 and w.isalpha()][:3]
                recent_topics.extend(key_words)
            
            tools_used.update(interaction.get('tools_used', []))
        
        summary_parts = []
        if recent_topics:
            summary_parts.append(f"Recent topics: {', '.join(set(recent_topics))}")
        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(tools_used)}")
        
        return "; ".join(summary_parts)
        
    except Exception as e:
        logger.warning(f"Error generating context summary: {str(e)}")
        return ""

def send_custom_metric(metric_name: str, value: float, unit: str = 'Count', dimensions: Dict[str, str] = None):
    """Send custom metric to CloudWatch."""
    try:
        dimensions = dimensions or {}
        dimensions.update({
            'Service': 'AgentScholar',
            'Function': 'Orchestrator'
        })
        
        cloudwatch.put_metric_data(
            Namespace='AgentScholar',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Dimensions': [
                        {'Name': key, 'Value': value} for key, value in dimensions.items()
                    ],
                    'Value': value,
                    'Unit': unit,
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to send custom metric {metric_name}: {str(e)}")

# Health check configuration
HEALTH_CHECK_CONFIG = {
    'api_gateway_url': os.getenv('API_BASE_URL', ''),
    'lambda_functions': ['agent-scholar-orchestrator'],
    'bedrock_agent': {
        'agent_id': os.getenv('AGENT_ID', ''),
        'agent_alias_id': os.getenv('AGENT_ALIAS_ID', '')
    }
}

# Create health check handler
health_check_handler = create_health_check_handler(HEALTH_CHECK_CONFIG)

def create_api_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a properly formatted API Gateway response.
    
    Args:
        status_code: HTTP status code
        body: Response body dictionary
        
    Returns:
        API Gateway response format
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body)
    }