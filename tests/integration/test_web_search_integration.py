"""
Integration tests for the Web Search Action Group Lambda function.
Tests the complete web search workflow with real or mocked APIs.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch
import sys
sys.path.append('src/lambda/web-search')
sys.path.append('src/shared')

from web_search import lambda_handler, WebSearchManager

# Test configuration
TEST_REGION = 'us-east-1'

class TestWebSearchIntegration:
    """Integration tests for web search functionality"""
    
    def test_lambda_handler_end_to_end_mock(self):
        """Test complete Lambda handler workflow with mocked search results"""
        
        # Mock search results
        mock_search_results = [
            {
                'title': 'Latest AI Developments in 2024',
                'url': 'https://example.com/ai-2024',
                'snippet': 'Recent breakthroughs in artificial intelligence including large language models and computer vision advances.',
                'date': '2024-01-15',
                'source': 'Mock Search',
                'position': 1
            },
            {
                'title': 'Machine Learning Trends',
                'url': 'https://example.com/ml-trends',
                'snippet': 'Current trends in machine learning including deep learning, reinforcement learning, and neural networks.',
                'date': '2024-01-10',
                'source': 'Mock Search',
                'position': 2
            }
        ]
        
        # Create test event
        event = {
            'parameters': [
                {'name': 'query', 'value': 'artificial intelligence 2024'},
                {'name': 'max_results', 'value': '5'},
                {'name': 'date_range', 'value': 'm1'}
            ]
        }
        
        context = Mock()
        context.function_name = 'test-web-search'
        context.aws_request_id = 'test-request-id'
        
        # Mock the WebSearchManager
        with patch('web_search.WebSearchManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.search.return_value = mock_search_results
            mock_manager_class.return_value = mock_manager
            
            # Execute Lambda handler
            response = lambda_handler(event, context)
            
            # Verify response structure
            assert 'response' in response
            assert 'actionResponse' in response['response']
            assert 'actionResponseBody' in response['response']['actionResponse']
            assert 'TEXT' in response['response']['actionResponse']['actionResponseBody']
            
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            # Verify response content
            assert 'artificial intelligence 2024' in response_body
            assert 'Latest AI Developments in 2024' in response_body
            assert 'Machine Learning Trends' in response_body
            assert 'https://example.com/ai-2024' in response_body
            assert 'Found 2 current web search results' in response_body
            
            # Verify search was called with correct parameters
            mock_manager.search.assert_called_once_with(
                query='artificial intelligence 2024',
                max_results=5,
                date_range='m1',
                location='United States'
            )
    
    def test_lambda_handler_no_results(self):
        """Test Lambda handler when no search results are found"""
        
        event = {
            'query': 'very specific query with no results',
            'max_results': 10
        }
        
        context = Mock()
        
        # Mock empty search results
        with patch('web_search.WebSearchManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.search.return_value = []
            mock_manager_class.return_value = mock_manager
            
            response = lambda_handler(event, context)
            
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            assert 'No current web search results found' in response_body
            assert 'very specific query with no results' in response_body
            assert 'knowledge base may contain relevant information' in response_body
    
    def test_search_result_processing_and_ranking(self):
        """Test search result processing and relevance ranking"""
        
        # Create test results with different relevance levels
        raw_results = [
            {
                'title': 'Cooking Recipes',  # Low relevance
                'url': 'https://example.com/cooking',
                'snippet': 'Delicious recipes for dinner',
                'date': '2024-01-01',
                'source': 'Test',
                'position': 1
            },
            {
                'title': 'Machine Learning Guide',  # High relevance
                'url': 'https://example.com/ml-guide',
                'snippet': 'Complete guide to machine learning algorithms and techniques',
                'date': '2024-01-02',
                'source': 'Test',
                'position': 2
            },
            {
                'title': 'AI and Machine Learning News',  # Very high relevance
                'url': 'https://example.com/ai-ml-news',
                'snippet': 'Latest news in artificial intelligence and machine learning research',
                'date': '2024-01-03',
                'source': 'Test',
                'position': 3
            }
        ]
        
        event = {
            'query': 'machine learning artificial intelligence',
            'max_results': 10
        }
        
        context = Mock()
        
        with patch('web_search.WebSearchManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.search.return_value = raw_results
            mock_manager_class.return_value = mock_manager
            
            response = lambda_handler(event, context)
            
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            # Verify high relevance results appear first
            ai_ml_news_pos = response_body.find('AI and Machine Learning News')
            ml_guide_pos = response_body.find('Machine Learning Guide')
            cooking_pos = response_body.find('Cooking Recipes')
            
            # AI and ML News should appear before ML Guide, which should appear before Cooking
            assert ai_ml_news_pos < ml_guide_pos
            assert ml_guide_pos < cooking_pos
    
    def test_error_handling_and_fallback(self):
        """Test error handling when search providers fail"""
        
        event = {
            'query': 'test query',
            'max_results': 5
        }
        
        context = Mock()
        
        # Mock search manager that raises an exception
        with patch('web_search.WebSearchManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.search.side_effect = Exception("All search providers failed")
            mock_manager_class.return_value = mock_manager
            
            response = lambda_handler(event, context)
            
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            assert 'Web search failed' in response_body
            assert 'All search providers failed' in response_body
    
    def test_parameter_validation_and_suggestions(self):
        """Test parameter validation and suggestion generation"""
        
        from web_search import validate_search_parameters
        
        # Test valid parameters
        validation = validate_search_parameters("machine learning", 10, "y1")
        assert validation['valid'] is True
        assert len(validation['warnings']) == 0
        
        # Test invalid parameters
        validation = validate_search_parameters("", 0, "invalid")
        assert validation['valid'] is False
        assert len(validation['warnings']) > 0
        
        # Test AI-related suggestions
        validation = validate_search_parameters("artificial intelligence trends", 10, "y1")
        assert len(validation['suggestions']) > 0
        assert any("AI" in suggestion for suggestion in validation['suggestions'])
    
    def test_date_range_filtering(self):
        """Test date range filtering functionality"""
        
        # Test different date ranges
        date_ranges = ['d1', 'w1', 'm1', 'y1']
        
        for date_range in date_ranges:
            event = {
                'query': 'test query',
                'max_results': 5,
                'date_range': date_range
            }
            
            context = Mock()
            
            with patch('web_search.WebSearchManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.search.return_value = [
                    {
                        'title': f'Result for {date_range}',
                        'url': 'https://example.com',
                        'snippet': f'Test result for date range {date_range}',
                        'date': '2024-01-01',
                        'source': 'Test',
                        'position': 1
                    }
                ]
                mock_manager_class.return_value = mock_manager
                
                response = lambda_handler(event, context)
                
                # Verify search was called with correct date range
                mock_manager.search.assert_called_with(
                    query='test query',
                    max_results=5,
                    date_range=date_range,
                    location='United States'
                )
                
                response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
                assert f'Result for {date_range}' in response_body
    
    def test_large_result_set_handling(self):
        """Test handling of large result sets"""
        
        # Create a large number of mock results
        large_result_set = []
        for i in range(25):
            large_result_set.append({
                'title': f'Result {i+1}',
                'url': f'https://example.com/result-{i+1}',
                'snippet': f'This is test result number {i+1}',
                'date': '2024-01-01',
                'source': 'Test',
                'position': i+1
            })
        
        event = {
            'query': 'test query',
            'max_results': 20  # Request 20 results
        }
        
        context = Mock()
        
        with patch('web_search.WebSearchManager') as mock_manager_class:
            mock_manager = Mock()
            mock_manager.search.return_value = large_result_set
            mock_manager_class.return_value = mock_manager
            
            response = lambda_handler(event, context)
            
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            # Should handle all results properly
            assert 'Found 25 current web search results' in response_body
            assert 'Result 1' in response_body
            assert 'Result 25' in response_body
    
    @pytest.mark.skipif(
        not os.getenv('INTEGRATION_TEST_API_KEYS'),
        reason="Integration test with real APIs requires API keys"
    )
    def test_real_api_integration(self):
        """
        Test with real search APIs (only runs if API keys are provided).
        This test is skipped by default to avoid API costs and rate limits.
        """
        
        # This test would only run if INTEGRATION_TEST_API_KEYS environment variable is set
        # and would test against real SERP API or Google Custom Search API
        
        event = {
            'query': 'machine learning 2024',
            'max_results': 3,
            'date_range': 'm1'
        }
        
        context = Mock()
        
        # This would test against real APIs
        response = lambda_handler(event, context)
        
        # Verify we get real results
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        assert 'machine learning 2024' in response_body.lower()
        assert 'http' in response_body  # Should contain real URLs
        assert 'Found' in response_body  # Should find some results

class TestWebSearchManager:
    """Test the WebSearchManager class in isolation"""
    
    def test_manager_initialization_no_providers(self):
        """Test manager initialization when no API keys are available"""
        
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            with patch('web_search.boto3.client') as mock_boto3:
                # Mock SSM client that returns no parameters
                mock_ssm = Mock()
                mock_ssm.get_parameter.side_effect = Exception("Parameter not found")
                mock_boto3.return_value = mock_ssm
                
                manager = WebSearchManager()
                
                assert len(manager.providers) == 0
                
                # Should raise exception when trying to search
                with pytest.raises(Exception) as exc_info:
                    manager.search("test query")
                
                assert "No web search providers available" in str(exc_info.value)
    
    def test_manager_provider_fallback_behavior(self):
        """Test that manager properly falls back between providers"""
        
        # Create mock providers
        failing_provider = Mock()
        failing_provider.search.side_effect = Exception("Provider 1 failed")
        failing_provider.__class__.__name__ = "FailingProvider"
        
        working_provider = Mock()
        working_provider.search.return_value = [
            {'title': 'Success', 'url': 'test.com', 'snippet': 'test', 'date': '2024-01-01', 'source': 'Test', 'position': 1}
        ]
        working_provider.__class__.__name__ = "WorkingProvider"
        
        manager = WebSearchManager()
        manager.providers = [failing_provider, working_provider]
        
        results = manager.search("test query", max_results=5)
        
        # Should get results from working provider
        assert len(results) == 1
        assert results[0]['title'] == 'Success'
        
        # Both providers should have been tried
        failing_provider.search.assert_called_once()
        working_provider.search.assert_called_once()

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])