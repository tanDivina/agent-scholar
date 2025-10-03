"""
Integration tests for Lambda functions
"""

import pytest
import json
import sys
import os
import importlib.util
from unittest.mock import Mock, patch

class TestWebSearchLambda:
    """Integration tests for web search Lambda function."""
    
    def test_lambda_handler_valid_request(self):
        """Test web search Lambda with valid request."""
        # Import Lambda function dynamically to avoid keyword conflicts
        spec = importlib.util.spec_from_file_location(
            "web_search", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'web-search', 'web_search.py')
        )
        web_search_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web_search_module)
        lambda_handler = web_search_module.lambda_handler
        
        event = {
            'parameters': [
                {'name': 'query', 'value': 'artificial intelligence'},
                {'name': 'max_results', 'value': '5'}
            ]
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']
        assert 'actionResponseBody' in response['response']['actionResponse']
        assert 'TEXT' in response['response']['actionResponse']['actionResponseBody']
    
    def test_lambda_handler_missing_query(self):
        """Test web search Lambda with missing query parameter."""
        # Import Lambda function dynamically
        spec = importlib.util.spec_from_file_location(
            "web_search", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'web-search', 'web_search.py')
        )
        web_search_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web_search_module)
        lambda_handler = web_search_module.lambda_handler
        
        event = {'parameters': []}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return error response
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Error' in body

class TestCodeExecutionLambda:
    """Integration tests for code execution Lambda function."""
    
    def test_lambda_handler_valid_request(self):
        """Test code execution Lambda with valid request."""
        # Import Lambda function dynamically
        spec = importlib.util.spec_from_file_location(
            "code_executor", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'code-execution', 'code_executor.py')
        )
        code_executor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(code_executor_module)
        lambda_handler = code_executor_module.lambda_handler
        
        event = {
            'parameters': [
                {'name': 'code', 'value': 'print("Hello, World!")'},
                {'name': 'timeout', 'value': '30'}
            ]
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']
    
    def test_lambda_handler_missing_code(self):
        """Test code execution Lambda with missing code parameter."""
        # Import Lambda function dynamically
        spec = importlib.util.spec_from_file_location(
            "code_executor", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'code-execution', 'code_executor.py')
        )
        code_executor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(code_executor_module)
        lambda_handler = code_executor_module.lambda_handler
        
        event = {'parameters': []}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return error response
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Error' in body

class TestAnalysisLambda:
    """Integration tests for analysis Lambda function."""
    
    def test_lambda_handler_valid_request(self):
        """Test analysis Lambda with valid request."""
        # Import Lambda function dynamically
        spec = importlib.util.spec_from_file_location(
            "analysis_engine", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'analysis', 'analysis_engine.py')
        )
        analysis_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analysis_module)
        lambda_handler = analysis_module.lambda_handler
        
        event = {
            'parameters': [
                {'name': 'analysis_type', 'value': 'themes'},
                {'name': 'query_context', 'value': 'machine learning'}
            ]
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']

class TestOrchestratorLambda:
    """Integration tests for orchestrator Lambda function."""
    
    def test_lambda_handler_valid_request(self):
        """Test orchestrator Lambda with valid request."""
        # Import Lambda function dynamically
        spec = importlib.util.spec_from_file_location(
            "orchestrator", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'orchestrator', 'orchestrator.py')
        )
        orchestrator_module = importlib.util.module_from_spec(spec)
        
        # Mock Bedrock before loading the module
        with patch('boto3.client') as mock_boto3:
            mock_bedrock = Mock()
            mock_bedrock.invoke_agent.return_value = {
                'completion': [
                    {'chunk': {'bytes': b'Test response from agent'}}
                ]
            }
            mock_boto3.return_value = mock_bedrock
            
            spec.loader.exec_module(orchestrator_module)
            lambda_handler = orchestrator_module.lambda_handler
        
        event = {
            'body': json.dumps({
                'query': 'What is artificial intelligence?',
                'session_id': 'test-session-123'
            })
        }
        context = Mock()
        
        # Mock environment variables
        with patch.dict('os.environ', {
            'AGENT_ID': 'test-agent-id',
            'AGENT_ALIAS_ID': 'test-alias-id'
        }):
            response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'response' in body
        assert 'session_id' in body
    
    def test_lambda_handler_missing_query(self):
        """Test orchestrator Lambda with missing query."""
        # Import Lambda function dynamically with mocked boto3
        spec = importlib.util.spec_from_file_location(
            "orchestrator", 
            os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'orchestrator', 'orchestrator.py')
        )
        orchestrator_module = importlib.util.module_from_spec(spec)
        
        # Mock boto3 before loading the module
        with patch('boto3.client') as mock_boto3:
            mock_bedrock = Mock()
            mock_boto3.return_value = mock_bedrock
            
            spec.loader.exec_module(orchestrator_module)
            lambda_handler = orchestrator_module.lambda_handler
        
        event = {
            'body': json.dumps({})
        }
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body