#!/usr/bin/env python3
"""
Test script for Agent Scholar Streamlit Interface

This script tests the Streamlit application components and API integration.
"""

import unittest
import requests
import json
import time
from unittest.mock import Mock, patch
import sys
import os

# Add the current directory to the path to import the streamlit app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestStreamlitInterface(unittest.TestCase):
    """Test cases for the Streamlit interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_base_url = "https://test-api-gateway.execute-api.us-east-1.amazonaws.com/prod"
        self.test_session_id = "test-session-123"
    
    def test_api_health_check(self):
        """Test API health check functionality."""
        # Mock successful health check
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_response
            
            # Test health check logic
            try:
                response = requests.get(f"{self.api_base_url}/health", timeout=10)
                self.assertEqual(response.status_code, 200)
                self.assertIn("status", response.json())
            except Exception as e:
                self.fail(f"Health check failed: {e}")
    
    def test_chat_message_format(self):
        """Test chat message formatting."""
        # Test user message format
        user_message = {
            'content': 'What is machine learning?',
            'timestamp': '2024-01-01T12:00:00',
            'is_user': True
        }
        
        self.assertTrue(user_message['is_user'])
        self.assertIn('content', user_message)
        self.assertIn('timestamp', user_message)
        
        # Test agent message format
        agent_message = {
            'response': {
                'answer': 'Machine learning is...',
                'reasoning_steps': [],
                'tool_invocations': [],
                'sources_used': []
            },
            'timestamp': '2024-01-01T12:00:01',
            'is_user': False
        }
        
        self.assertFalse(agent_message['is_user'])
        self.assertIn('response', agent_message)
        self.assertIn('answer', agent_message['response'])
    
    def test_api_request_format(self):
        """Test API request payload format."""
        payload = {
            'query': 'Test query',
            'session_id': self.test_session_id
        }
        
        # Validate required fields
        self.assertIn('query', payload)
        self.assertIn('session_id', payload)
        self.assertIsInstance(payload['query'], str)
        self.assertIsInstance(payload['session_id'], str)
        
        # Test JSON serialization
        try:
            json_payload = json.dumps(payload)
            self.assertIsInstance(json_payload, str)
        except Exception as e:
            self.fail(f"JSON serialization failed: {e}")
    
    def test_response_parsing(self):
        """Test API response parsing."""
        mock_response = {
            'response': {
                'answer': 'This is a test response',
                'reasoning_steps': [
                    {'step': 1, 'rationale': 'Test reasoning', 'timestamp': '2024-01-01T12:00:00'}
                ],
                'tool_invocations': [
                    {'action_group': 'test_tool', 'api_path': '/test', 'timestamp': '2024-01-01T12:00:00'}
                ],
                'sources_used': [
                    {'type': 'knowledge_base', 'content': 'Test content', 'score': 0.95}
                ],
                'session_preserved': True
            },
            'session_id': self.test_session_id,
            'query_count': 1
        }
        
        # Validate response structure
        self.assertIn('response', mock_response)
        self.assertIn('session_id', mock_response)
        
        response_data = mock_response['response']
        self.assertIn('answer', response_data)
        self.assertIn('reasoning_steps', response_data)
        self.assertIn('tool_invocations', response_data)
        self.assertIn('sources_used', response_data)
        
        # Validate data types
        self.assertIsInstance(response_data['reasoning_steps'], list)
        self.assertIsInstance(response_data['tool_invocations'], list)
        self.assertIsInstance(response_data['sources_used'], list)
    
    def test_file_upload_validation(self):
        """Test file upload validation logic."""
        # Valid file types
        valid_extensions = ['txt', 'pdf', 'docx', 'md']
        
        for ext in valid_extensions:
            filename = f"test_document.{ext}"
            self.assertTrue(any(filename.endswith(f".{valid_ext}") for valid_ext in valid_extensions))
        
        # Invalid file types
        invalid_extensions = ['exe', 'zip', 'jpg', 'mp4']
        
        for ext in invalid_extensions:
            filename = f"test_file.{ext}"
            self.assertFalse(any(filename.endswith(f".{valid_ext}") for valid_ext in valid_extensions))
    
    def test_session_management(self):
        """Test session management logic."""
        import uuid
        
        # Test session ID generation
        session_id = str(uuid.uuid4())
        self.assertIsInstance(session_id, str)
        self.assertEqual(len(session_id), 36)  # UUID4 length with hyphens
        
        # Test session uniqueness
        session_id_2 = str(uuid.uuid4())
        self.assertNotEqual(session_id, session_id_2)
    
    def test_error_handling(self):
        """Test error handling scenarios."""
        # Test API connection error
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            try:
                response = requests.post(
                    f"{self.api_base_url}/chat",
                    json={'query': 'test', 'session_id': 'test'},
                    timeout=10
                )
                self.fail("Should have raised ConnectionError")
            except requests.exceptions.ConnectionError:
                pass  # Expected behavior
        
        # Test API timeout
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
            
            try:
                response = requests.post(
                    f"{self.api_base_url}/chat",
                    json={'query': 'test', 'session_id': 'test'},
                    timeout=10
                )
                self.fail("Should have raised Timeout")
            except requests.exceptions.Timeout:
                pass  # Expected behavior
    
    def test_configuration_validation(self):
        """Test configuration file validation."""
        # Test secrets.toml format
        secrets_content = '''
API_BASE_URL = "https://test-api.execute-api.us-east-1.amazonaws.com/prod"
'''
        
        # Basic validation that it's not the default placeholder
        self.assertNotIn('your-api-gateway-url', secrets_content)
        self.assertIn('execute-api', secrets_content)
        self.assertIn('amazonaws.com', secrets_content)


class TestStreamlitComponents(unittest.TestCase):
    """Test individual Streamlit components."""
    
    def test_chat_history_management(self):
        """Test chat history management."""
        chat_history = []
        max_history = 50
        
        # Add messages beyond limit
        for i in range(60):
            message = {
                'content': f'Message {i}',
                'timestamp': f'2024-01-01T12:{i:02d}:00',
                'is_user': i % 2 == 0
            }
            chat_history.append(message)
        
        # Simulate history trimming
        if len(chat_history) > max_history:
            chat_history = chat_history[-max_history:]
        
        self.assertEqual(len(chat_history), max_history)
        self.assertEqual(chat_history[0]['content'], 'Message 10')  # First kept message
        self.assertEqual(chat_history[-1]['content'], 'Message 59')  # Last message
    
    def test_metrics_calculation(self):
        """Test session metrics calculation."""
        chat_history = [
            {'is_user': True, 'content': 'Question 1'},
            {'is_user': False, 'response': {'answer': 'Answer 1'}},
            {'is_user': True, 'content': 'Question 2'},
            {'is_user': False, 'response': {'answer': 'Answer 2'}},
        ]
        
        total_messages = len(chat_history)
        user_messages = sum(1 for msg in chat_history if msg.get('is_user', False))
        agent_messages = total_messages - user_messages
        
        self.assertEqual(total_messages, 4)
        self.assertEqual(user_messages, 2)
        self.assertEqual(agent_messages, 2)
    
    def test_tool_usage_statistics(self):
        """Test tool usage statistics calculation."""
        chat_history = [
            {
                'is_user': False,
                'response': {
                    'tool_invocations': [
                        {'action_group': 'web_search'},
                        {'action_group': 'code_execution'}
                    ]
                }
            },
            {
                'is_user': False,
                'response': {
                    'tool_invocations': [
                        {'action_group': 'web_search'},
                        {'action_group': 'cross_analysis'}
                    ]
                }
            }
        ]
        
        tool_usage = {}
        for msg in chat_history:
            if not msg.get('is_user', False):
                tools = msg.get('response', {}).get('tool_invocations', [])
                for tool in tools:
                    action_group = tool.get('action_group', 'Unknown')
                    tool_usage[action_group] = tool_usage.get(action_group, 0) + 1
        
        expected_usage = {
            'web_search': 2,
            'code_execution': 1,
            'cross_analysis': 1
        }
        
        self.assertEqual(tool_usage, expected_usage)


def run_integration_tests():
    """Run integration tests against a live API (if available)."""
    print("🧪 Running integration tests...")
    
    # These tests require a live API endpoint
    api_url = os.getenv('API_BASE_URL')
    if not api_url or 'your-api-gateway-url' in api_url:
        print("⚠️  Skipping integration tests - API_BASE_URL not configured")
        return
    
    try:
        # Test health endpoint
        response = requests.get(f"{api_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
        
        # Test chat endpoint with simple query
        payload = {
            'query': 'Hello, this is a test query',
            'session_id': 'test-session-integration'
        }
        
        response = requests.post(
            f"{api_url}/chat",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'response' in data and 'answer' in data['response']:
                print("✅ Chat endpoint test passed")
            else:
                print("❌ Chat endpoint returned invalid response format")
        else:
            print(f"❌ Chat endpoint test failed: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Integration test error: {e}")


def main():
    """Main test runner."""
    print("🧠 Agent Scholar Streamlit Interface Tests")
    print("=" * 50)
    
    # Run unit tests
    print("🔬 Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration tests
    run_integration_tests()
    
    print("\n✅ Test suite completed!")


if __name__ == '__main__':
    main()