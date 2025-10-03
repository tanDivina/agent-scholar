"""
Unit tests for the Web Search Action Group Lambda function.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
sys.path.append('src/lambda/web-search')
sys.path.append('src/shared')

# Import the web search module
from web_search import (
    lambda_handler, WebSearchManager, SerpApiProvider, GoogleCustomSearchProvider,
    process_search_results, calculate_relevance_score, clean_text, format_date,
    format_search_results, extract_key_entities, validate_search_parameters
)

class TestWebSearchProviders:
    """Test web search provider classes"""
    
    def test_serp_api_provider_initialization(self):
        """Test SERP API provider initialization"""
        provider = SerpApiProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert provider.base_url == "https://serpapi.com/search"
        assert provider.rate_limit_delay == 0.2
    
    def test_google_custom_search_provider_initialization(self):
        """Test Google Custom Search provider initialization"""
        provider = GoogleCustomSearchProvider("test-api-key", "test-engine-id")
        assert provider.api_key == "test-api-key"
        assert provider.search_engine_id == "test-engine-id"
        assert provider.base_url == "https://www.googleapis.com/customsearch/v1"
    
    @patch('web_search.requests.get')
    def test_serp_api_search_success(self, mock_get):
        """Test successful SERP API search"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'organic_results': [
                {
                    'title': 'Test Result 1',
                    'link': 'https://example.com/1',
                    'snippet': 'This is a test result',
                    'date': '2024-01-01',
                    'position': 1
                },
                {
                    'title': 'Test Result 2',
                    'link': 'https://example.com/2',
                    'snippet': 'Another test result',
                    'date': '2024-01-02',
                    'position': 2
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        provider = SerpApiProvider("test-api-key")
        results = provider.search("test query", max_results=5)
        
        assert len(results) == 2
        assert results[0]['title'] == 'Test Result 1'
        assert results[0]['url'] == 'https://example.com/1'
        assert results[0]['source'] == 'SERP API'
        
        # Verify API call was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert 'q' in call_args[1]['params']
        assert call_args[1]['params']['q'] == 'test query'
    
    @patch('web_search.requests.get')
    def test_google_custom_search_success(self, mock_get):
        """Test successful Google Custom Search"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'items': [
                {
                    'title': 'Google Result 1',
                    'link': 'https://google-example.com/1',
                    'snippet': 'Google test result',
                    'pagemap': {
                        'metatags': [{'article:published_time': '2024-01-01'}]
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        provider = GoogleCustomSearchProvider("test-api-key", "test-engine-id")
        results = provider.search("test query", max_results=5)
        
        assert len(results) == 1
        assert results[0]['title'] == 'Google Result 1'
        assert results[0]['source'] == 'Google Custom Search'
    
    @patch('web_search.requests.get')
    def test_provider_api_error_handling(self, mock_get):
        """Test API error handling"""
        # Mock API error
        mock_get.side_effect = Exception("API Error")
        
        provider = SerpApiProvider("test-api-key")
        
        with pytest.raises(Exception) as exc_info:
            provider.search("test query")
        
        assert "SERP API" in str(exc_info.value) and "error" in str(exc_info.value)

class TestWebSearchManager:
    """Test the WebSearchManager class"""
    
    @patch.dict(os.environ, {'SERP_API_KEY': 'test-serp-key'})
    def test_manager_initialization_with_serp(self):
        """Test manager initialization with SERP API"""
        with patch('web_search.SerpApiProvider') as mock_provider:
            manager = WebSearchManager()
            mock_provider.assert_called_once_with('test-serp-key')
    
    @patch.dict(os.environ, {
        'GOOGLE_API_KEY': 'test-google-key',
        'GOOGLE_SEARCH_ENGINE_ID': 'test-engine-id'
    })
    def test_manager_initialization_with_google(self):
        """Test manager initialization with Google Custom Search"""
        with patch('web_search.GoogleCustomSearchProvider') as mock_provider:
            manager = WebSearchManager()
            mock_provider.assert_called_once_with('test-google-key', 'test-engine-id')
    
    def test_manager_no_providers(self):
        """Test manager with no providers available"""
        with patch.dict(os.environ, {}, clear=True):
            manager = WebSearchManager()
            assert len(manager.providers) == 0
            
            with pytest.raises(Exception) as exc_info:
                manager.search("test query")
            
            assert "No web search providers available" in str(exc_info.value)
    
    def test_manager_provider_fallback(self):
        """Test provider fallback functionality"""
        # Create mock providers
        failing_provider = Mock()
        failing_provider.search.side_effect = Exception("Provider 1 failed")
        
        working_provider = Mock()
        working_provider.search.return_value = [{'title': 'Success', 'url': 'test.com', 'snippet': 'test'}]
        
        manager = WebSearchManager()
        manager.providers = [failing_provider, working_provider]
        
        results = manager.search("test query")
        
        assert len(results) == 1
        assert results[0]['title'] == 'Success'
        
        # Verify both providers were tried
        failing_provider.search.assert_called_once()
        working_provider.search.assert_called_once()

class TestSearchResultProcessing:
    """Test search result processing functions"""
    
    def test_process_search_results(self):
        """Test search result processing"""
        raw_results = [
            {
                'title': 'Machine Learning Basics',
                'url': 'https://example.com/ml',
                'snippet': 'Learn about machine learning algorithms and techniques',
                'date': '2024-01-01',
                'source': 'Test Source',
                'position': 1
            },
            {
                'title': 'AI Research Paper',
                'url': 'https://example.com/ai',
                'snippet': 'Advanced artificial intelligence research findings',
                'date': '2024-01-02',
                'source': 'Test Source',
                'position': 2
            }
        ]
        
        processed = process_search_results(raw_results, "machine learning")
        
        assert len(processed) == 2
        assert all('relevance_score' in result for result in processed)
        assert processed[0]['relevance_score'] >= processed[1]['relevance_score']  # Should be sorted by relevance
    
    def test_calculate_relevance_score(self):
        """Test relevance score calculation"""
        result = {
            'title': 'Machine Learning Tutorial',
            'snippet': 'Learn machine learning algorithms and techniques',
            'position': 1
        }
        
        score = calculate_relevance_score(result, "machine learning")
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should have high relevance for matching terms
    
    def test_calculate_relevance_score_no_match(self):
        """Test relevance score with no matching terms"""
        result = {
            'title': 'Cooking Recipes',
            'snippet': 'Delicious food recipes for dinner',
            'position': 1
        }
        
        score = calculate_relevance_score(result, "machine learning")
        
        assert score < 0.2  # Should have low relevance
    
    def test_clean_text(self):
        """Test text cleaning function"""
        dirty_text = "  This is &amp; a test &lt;with&gt; HTML entities  "
        clean = clean_text(dirty_text)
        
        assert clean == "This is & a test <with> HTML entities"
    
    def test_clean_text_empty(self):
        """Test text cleaning with empty input"""
        assert clean_text("") == ""
        assert clean_text(None) == ""
    
    def test_format_date(self):
        """Test date formatting"""
        # ISO format
        iso_date = "2024-01-01T12:00:00Z"
        formatted = format_date(iso_date)
        assert formatted == "2024-01-01"
        
        # Simple date format
        simple_date = "2024-01-01"
        formatted = format_date(simple_date)
        assert formatted == "2024-01-01"
        
        # Empty date
        formatted = format_date("")
        assert formatted == "Unknown"

class TestResultFormatting:
    """Test result formatting functions"""
    
    def test_format_search_results(self):
        """Test search result formatting"""
        results = [
            {
                'title': 'Test Result',
                'url': 'https://example.com',
                'snippet': 'This is a test result',
                'date': '2024-01-01',
                'source': 'Test Source',
                'relevance_score': 0.8
            }
        ]
        
        formatted = format_search_results(results, "test query")
        
        assert "Test Result" in formatted
        assert "https://example.com" in formatted
        assert "test query" in formatted
        assert "Relevance: 0.80" in formatted
    
    def test_format_search_results_empty(self):
        """Test formatting with no results"""
        formatted = format_search_results([], "test query")
        
        assert "No current web search results found" in formatted
        assert "test query" in formatted
    
    def test_extract_key_entities(self):
        """Test key entity extraction"""
        text = "Apple Inc. released the iPhone in 2007. Steve Jobs was the CEO."
        entities = extract_key_entities(text)
        
        # Check that we extracted some entities
        assert len(entities) > 0
        
        # Check for expected entities (allowing for variations in extraction)
        entity_text = ' '.join(entities)
        assert "Apple" in entity_text or "Apple Inc" in entities
        assert "Steve Jobs" in entities or "Steve" in entities
        # Year extraction might be partial, so check for any numeric content
        assert any(char.isdigit() for char in entity_text)
    
    def test_validate_search_parameters_valid(self):
        """Test parameter validation with valid inputs"""
        validation = validate_search_parameters("machine learning", 10, "y1")
        
        assert validation['valid'] is True
        assert len(validation['warnings']) == 0
    
    def test_validate_search_parameters_invalid_query(self):
        """Test parameter validation with invalid query"""
        validation = validate_search_parameters("", 10, "y1")
        
        assert validation['valid'] is False
        assert any("Query too short" in warning for warning in validation['warnings'])
    
    def test_validate_search_parameters_invalid_max_results(self):
        """Test parameter validation with invalid max_results"""
        validation = validate_search_parameters("test query", 0, "y1")
        
        assert validation['valid'] is False
        assert any("max_results must be at least 1" in warning for warning in validation['warnings'])
    
    def test_validate_search_parameters_warnings(self):
        """Test parameter validation warnings"""
        validation = validate_search_parameters("test query", 100, "invalid_range")
        
        assert len(validation['warnings']) > 0
        assert any("Large result sets" in warning for warning in validation['warnings'])
        assert any("Invalid date_range" in warning for warning in validation['warnings'])

class TestLambdaHandler:
    """Test the main Lambda handler"""
    
    @patch('web_search.WebSearchManager')
    def test_lambda_handler_bedrock_format(self, mock_manager_class):
        """Test Lambda handler with Bedrock Agent event format"""
        # Mock the search manager
        mock_manager = Mock()
        mock_manager.search.return_value = [
            {
                'title': 'Test Result',
                'url': 'https://example.com',
                'snippet': 'Test snippet',
                'date': '2024-01-01',
                'source': 'Test',
                'position': 1
            }
        ]
        mock_manager_class.return_value = mock_manager
        
        # Bedrock Agent event format
        event = {
            'parameters': [
                {'name': 'query', 'value': 'machine learning'},
                {'name': 'max_results', 'value': '5'},
                {'name': 'date_range', 'value': 'y1'}
            ]
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']
        
        # Verify search was called
        mock_manager.search.assert_called_once_with(
            query='machine learning',
            max_results=5,
            date_range='y1',
            location='United States'
        )
    
    @patch('web_search.WebSearchManager')
    def test_lambda_handler_direct_format(self, mock_manager_class):
        """Test Lambda handler with direct invocation format"""
        # Mock the search manager
        mock_manager = Mock()
        mock_manager.search.return_value = []
        mock_manager_class.return_value = mock_manager
        
        # Direct invocation format
        event = {
            'query': 'artificial intelligence',
            'max_results': 10,
            'date_range': 'm1'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        
        # Verify search was called
        mock_manager.search.assert_called_once_with(
            query='artificial intelligence',
            max_results=10,
            date_range='m1',
            location='United States'
        )
    
    def test_lambda_handler_missing_query(self):
        """Test Lambda handler with missing query"""
        event = {
            'parameters': [
                {'name': 'max_results', 'value': '5'}
            ]
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return error response
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert "Search query is required" in body
    
    @patch('web_search.WebSearchManager')
    def test_lambda_handler_search_error(self, mock_manager_class):
        """Test Lambda handler with search error"""
        # Mock the search manager to raise an error
        mock_manager = Mock()
        mock_manager.search.side_effect = Exception("Search API failed")
        mock_manager_class.return_value = mock_manager
        
        event = {
            'query': 'test query',
            'max_results': 5
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        # Should return error response
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert "Web search failed" in body
        assert "Search API failed" in body

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])