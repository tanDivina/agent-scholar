"""
Integration tests for API Gateway and Lambda orchestrator.

These tests validate the complete API workflow including session management,
agent invocation, and error handling.
"""

import json
import pytest
import requests
import uuid
import time
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch

# Test configuration
API_BASE_URL = "https://your-api-gateway-url.execute-api.region.amazonaws.com/prod"
TEST_TIMEOUT = 60


class TestApiGatewayIntegration:
    """Integration tests for API Gateway endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.session_id = str(uuid.uuid4())
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        response = requests.get(f"{API_BASE_URL}/health", headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert data['service'] == 'agent-scholar-orchestrator'
    
    def test_chat_endpoint_simple_query(self):
        """Test chat endpoint with a simple query."""
        payload = {
            'query': 'What is machine learning?',
            'session_id': self.session_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload,
            timeout=TEST_TIMEOUT
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert 'response' in data
        assert 'session_id' in data
        assert data['session_id'] == self.session_id
        
        agent_response = data['response']
        assert 'answer' in agent_response
        assert 'reasoning_steps' in agent_response
        assert 'sources_used' in agent_response
        assert 'session_preserved' in agent_response
        
        # Validate answer is not empty
        assert len(agent_response['answer'].strip()) > 0
    
    def test_chat_endpoint_complex_query(self):
        """Test chat endpoint with a complex multi-step query."""
        payload = {
            'query': 'Compare different machine learning algorithms and create a visualization showing their performance characteristics.',
            'session_id': self.session_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload,
            timeout=TEST_TIMEOUT
        )
        
        assert response.status_code == 200
        data = response.json()
        
        agent_response = data['response']
        
        # Should have reasoning steps for complex query
        assert len(agent_response['reasoning_steps']) > 0
        
        # Should have tool invocations
        assert 'tool_invocations' in agent_response
        
        # Answer should be comprehensive
        assert len(agent_response['answer']) > 100
    
    def test_session_management(self):
        """Test session creation and retrieval."""
        # First query to create session
        payload1 = {
            'query': 'Tell me about neural networks.',
            'session_id': self.session_id,
            'user_id': 'test_user'
        }
        
        response1 = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload1,
            timeout=TEST_TIMEOUT
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1['query_count'] == 1
        
        # Second query in same session
        payload2 = {
            'query': 'What are the different types?',
            'session_id': self.session_id
        }
        
        response2 = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload2,
            timeout=TEST_TIMEOUT
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2['query_count'] == 2
        
        # Retrieve session information
        response3 = requests.get(
            f"{API_BASE_URL}/session/{self.session_id}",
            headers=self.headers
        )
        
        assert response3.status_code == 200
        session_data = response3.json()
        assert session_data['session_id'] == self.session_id
        assert session_data['query_count'] == 2
        assert 'created_at' in session_data
        assert 'last_accessed' in session_data
    
    def test_context_preservation(self):
        """Test that context is preserved across queries in a session."""
        # First query about a specific topic
        payload1 = {
            'query': 'Explain convolutional neural networks.',
            'session_id': self.session_id
        }
        
        response1 = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload1,
            timeout=TEST_TIMEOUT
        )
        
        assert response1.status_code == 200
        
        # Follow-up query that relies on context
        payload2 = {
            'query': 'What are their main advantages?',
            'session_id': self.session_id
        }
        
        response2 = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload2,
            timeout=TEST_TIMEOUT
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        # The response should understand the context (CNNs)
        answer = data2['response']['answer'].lower()
        assert any(term in answer for term in ['cnn', 'convolutional', 'neural network'])
    
    def test_error_handling_missing_query(self):
        """Test error handling for missing query parameter."""
        payload = {
            'session_id': self.session_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert 'required' in data['error'].lower()
    
    def test_error_handling_empty_query(self):
        """Test error handling for empty query."""
        payload = {
            'query': '',
            'session_id': self.session_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
    
    def test_error_handling_invalid_json(self):
        """Test error handling for invalid JSON."""
        response = requests.post(
            f"{API_BASE_URL}/chat",
            headers=self.headers,
            data="invalid json"
        )
        
        assert response.status_code == 500
        data = response.json()
        assert 'error' in data
    
    def test_cors_headers(self):
        """Test that CORS headers are properly set."""
        response = requests.options(f"{API_BASE_URL}/chat", headers=self.headers)
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_session_not_found(self):
        """Test handling of non-existent session."""
        non_existent_session = str(uuid.uuid4())
        
        response = requests.get(
            f"{API_BASE_URL}/session/{non_existent_session}",
            headers=self.headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()


class TestOrchestratorUnit:
    """Unit tests for orchestrator Lambda function."""
    
    @patch('src.lambda.orchestrator.orchestrator.bedrock_agent_runtime')
    def test_invoke_bedrock_agent_success(self, mock_bedrock):
        """Test successful Bedrock agent invocation."""
        from src.lambda.orchestrator.orchestrator import invoke_bedrock_agent, SessionContext
        from datetime import datetime
        
        # Mock Bedrock response
        mock_response = {
            'completion': [
                {
                    'chunk': {
                        'bytes': b'This is a test response.'
                    }
                }
            ]
        }
        mock_bedrock.invoke_agent.return_value = mock_response
        
        # Create test session context
        session_context = SessionContext(
            session_id='test-session',
            user_id='test-user',
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            query_count=0,
            conversation_history=[],
            context_summary=""
        )
        
        # Set environment variables
        import os
        os.environ['AGENT_ID'] = 'test-agent-id'
        os.environ['AGENT_ALIAS_ID'] = 'test-alias-id'
        
        # Test the function
        result = invoke_bedrock_agent('Test query', session_context)
        
        assert 'answer' in result
        assert result['answer'] == 'This is a test response.'
        assert result['session_preserved'] is True
        
        # Verify Bedrock was called correctly
        mock_bedrock.invoke_agent.assert_called_once_with(
            agentId='test-agent-id',
            agentAliasId='test-alias-id',
            sessionId='test-session',
            inputText='Test query'
        )
    
    @patch('src.lambda.orchestrator.orchestrator.bedrock_agent_runtime')
    def test_invoke_bedrock_agent_error(self, mock_bedrock):
        """Test Bedrock agent invocation error handling."""
        from src.lambda.orchestrator.orchestrator import invoke_bedrock_agent, SessionContext
        from datetime import datetime
        
        # Mock Bedrock error
        mock_bedrock.invoke_agent.side_effect = Exception("Bedrock error")
        
        # Create test session context
        session_context = SessionContext(
            session_id='test-session',
            user_id='test-user',
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            query_count=0,
            conversation_history=[],
            context_summary=""
        )
        
        # Set environment variables
        import os
        os.environ['AGENT_ID'] = 'test-agent-id'
        os.environ['AGENT_ALIAS_ID'] = 'test-alias-id'
        
        # Test the function
        result = invoke_bedrock_agent('Test query', session_context)
        
        assert 'error' in result
        assert result['session_preserved'] is False
        assert 'apologize' in result['answer'].lower()
    
    def test_context_summary_generation(self):
        """Test conversation context summary generation."""
        from src.lambda.orchestrator.orchestrator import generate_context_summary
        
        conversation_history = [
            {
                'query': 'What is machine learning?',
                'response': 'Machine learning is...',
                'tools_used': ['knowledge_base']
            },
            {
                'query': 'How does neural network training work?',
                'response': 'Neural network training...',
                'tools_used': ['knowledge_base', 'code_execution']
            }
        ]
        
        summary = generate_context_summary(conversation_history)
        
        assert len(summary) > 0
        assert 'machine' in summary.lower() or 'neural' in summary.lower()
        assert 'knowledge_base' in summary
    
    def test_query_enhancement_with_context(self):
        """Test query enhancement with conversation context."""
        from src.lambda.orchestrator.orchestrator import enhance_query_with_context, SessionContext
        from datetime import datetime
        
        session_context = SessionContext(
            session_id='test-session',
            user_id='test-user',
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            query_count=1,
            conversation_history=[],
            context_summary="Recent topics: machine learning; Tools used: knowledge_base"
        )
        
        original_query = "What are the advantages?"
        enhanced_query = enhance_query_with_context(original_query, session_context)
        
        assert len(enhanced_query) > len(original_query)
        assert 'machine learning' in enhanced_query
        assert original_query in enhanced_query


if __name__ == '__main__':
    # Run integration tests
    pytest.main([__file__, '-v'])