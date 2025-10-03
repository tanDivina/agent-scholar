"""
Web Search Action Group Lambda Function for Agent Scholar

This Lambda function provides web search capabilities to complement the knowledge base
with current information and recent developments.
"""

import json
import logging
import os
import requests
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import sys
sys.path.append('/opt/python')

# Try to import shared utilities, fall back to local implementations if not available
try:
    from shared.utils import create_bedrock_response, safe_json_loads, safe_json_dumps
except ImportError:
    # Fallback implementations for testing
    def create_bedrock_response(response_text: str) -> Dict[str, Any]:
        """Create standardized response for Bedrock Agent action groups."""
        return {
            'response': {
                'actionResponse': {
                    'actionResponseBody': {
                        'TEXT': {
                            'body': response_text
                        }
                    }
                }
            }
        }
    
    def safe_json_loads(json_str: str, default: Any = None) -> Any:
        """Safely parse JSON string with fallback."""
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return default
    
    def safe_json_dumps(obj: Any, default: str = "{}") -> str:
        """Safely serialize object to JSON with fallback."""
        try:
            return json.dumps(obj, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return default

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class WebSearchProvider:
    """Base class for web search providers"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.rate_limit_delay = 0.1  # Default delay between requests
        self.last_request_time = 0
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Perform search - to be implemented by subclasses"""
        raise NotImplementedError
    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()

class SerpApiProvider(WebSearchProvider):
    """SERP API provider for web search"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://serpapi.com/search"
        self.rate_limit_delay = 0.2  # SERP API rate limit
    
    def search(self, query: str, max_results: int = 10, date_range: str = None, 
               location: str = "United States", **kwargs) -> List[Dict[str, Any]]:
        """
        Search using SERP API
        
        Args:
            query: Search query
            max_results: Maximum number of results
            date_range: Date range filter (y1, m1, w1, d1)
            location: Search location
            
        Returns:
            List of search results
        """
        try:
            self._rate_limit()
            
            params = {
                'q': query,
                'api_key': self.api_key,
                'engine': 'google',
                'num': min(max_results, 20),  # SERP API max is 20
                'location': location,
                'hl': 'en',
                'gl': 'us'
            }
            
            # Add date range filter if specified
            if date_range:
                date_filter = self._convert_date_range(date_range)
                if date_filter:
                    params['tbs'] = date_filter
            
            logger.info(f"SERP API request: {query} (max_results: {max_results})")
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract organic results
            organic_results = data.get('organic_results', [])
            
            results = []
            for result in organic_results[:max_results]:
                processed_result = {
                    'title': result.get('title', ''),
                    'url': result.get('link', ''),
                    'snippet': result.get('snippet', ''),
                    'date': result.get('date', ''),
                    'source': 'SERP API',
                    'position': result.get('position', 0)
                }
                results.append(processed_result)
            
            logger.info(f"SERP API returned {len(results)} results")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SERP API request failed: {str(e)}")
            raise Exception(f"SERP API error: {str(e)}")
        except Exception as e:
            logger.error(f"SERP API processing failed: {str(e)}")
            raise Exception(f"SERP API processing error: {str(e)}")
    
    def _convert_date_range(self, date_range: str) -> Optional[str]:
        """Convert date range to SERP API format"""
        date_filters = {
            'd1': 'qdr:d',    # Past day
            'w1': 'qdr:w',    # Past week
            'm1': 'qdr:m',    # Past month
            'y1': 'qdr:y',    # Past year
        }
        return date_filters.get(date_range)

class GoogleCustomSearchProvider(WebSearchProvider):
    """Google Custom Search API provider"""
    
    def __init__(self, api_key: str, search_engine_id: str):
        super().__init__(api_key)
        self.search_engine_id = search_engine_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.rate_limit_delay = 0.1  # Google Custom Search rate limit
    
    def search(self, query: str, max_results: int = 10, date_range: str = None, 
               **kwargs) -> List[Dict[str, Any]]:
        """
        Search using Google Custom Search API
        
        Args:
            query: Search query
            max_results: Maximum number of results
            date_range: Date range filter
            
        Returns:
            List of search results
        """
        try:
            results = []
            
            # Google Custom Search returns max 10 results per request
            # Make multiple requests if needed
            for start_index in range(1, min(max_results + 1, 101), 10):
                self._rate_limit()
                
                params = {
                    'key': self.api_key,
                    'cx': self.search_engine_id,
                    'q': query,
                    'start': start_index,
                    'num': min(10, max_results - len(results))
                }
                
                # Add date range filter if specified
                if date_range:
                    date_filter = self._convert_date_range(date_range)
                    if date_filter:
                        params['dateRestrict'] = date_filter
                
                logger.info(f"Google Custom Search request: {query} (start: {start_index})")
                
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                items = data.get('items', [])
                if not items:
                    break
                
                for item in items:
                    processed_result = {
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'date': item.get('pagemap', {}).get('metatags', [{}])[0].get('article:published_time', ''),
                        'source': 'Google Custom Search',
                        'position': len(results) + 1
                    }
                    results.append(processed_result)
                
                if len(results) >= max_results:
                    break
            
            logger.info(f"Google Custom Search returned {len(results)} results")
            return results[:max_results]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Custom Search request failed: {str(e)}")
            raise Exception(f"Google Custom Search error: {str(e)}")
        except Exception as e:
            logger.error(f"Google Custom Search processing failed: {str(e)}")
            raise Exception(f"Google Custom Search processing error: {str(e)}")
    
    def _convert_date_range(self, date_range: str) -> Optional[str]:
        """Convert date range to Google Custom Search format"""
        date_filters = {
            'd1': 'd1',    # Past day
            'w1': 'w1',    # Past week
            'm1': 'm1',    # Past month
            'y1': 'y1',    # Past year
        }
        return date_filters.get(date_range)

class WebSearchManager:
    """Manages multiple web search providers with fallback"""
    
    def __init__(self):
        self.providers = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available search providers"""
        # Try to load API keys from Parameter Store first, then environment variables
        serp_api_key = self._get_api_key('SERP_API_KEY', 'SERP_API_KEY_PARAM')
        google_api_key = self._get_api_key('GOOGLE_API_KEY', 'GOOGLE_API_KEY_PARAM')
        google_search_engine_id = self._get_api_key('GOOGLE_SEARCH_ENGINE_ID', 'GOOGLE_SEARCH_ENGINE_ID_PARAM')
        
        # SERP API provider
        if serp_api_key:
            try:
                provider = SerpApiProvider(serp_api_key)
                self.providers.append(provider)
                logger.info("SERP API provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize SERP API provider: {e}")
        
        # Google Custom Search provider
        if google_api_key and google_search_engine_id:
            try:
                provider = GoogleCustomSearchProvider(google_api_key, google_search_engine_id)
                self.providers.append(provider)
                logger.info("Google Custom Search provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Custom Search provider: {e}")
        
        if not self.providers:
            logger.warning("No web search providers available")
    
    def _get_api_key(self, env_var_name: str, param_name_env: str) -> Optional[str]:
        """
        Get API key from environment variable or Parameter Store.
        
        Args:
            env_var_name: Environment variable name for direct API key
            param_name_env: Environment variable name containing Parameter Store path
            
        Returns:
            API key if found, None otherwise
        """
        # First try direct environment variable
        api_key = os.getenv(env_var_name)
        if api_key:
            return api_key
        
        # Then try Parameter Store
        param_path = os.getenv(param_name_env)
        if param_path:
            try:
                import boto3
                ssm_client = boto3.client('ssm')
                response = ssm_client.get_parameter(
                    Name=param_path,
                    WithDecryption=True
                )
                return response['Parameter']['Value']
            except Exception as e:
                logger.warning(f"Failed to get parameter {param_path}: {e}")
        
        return None
    
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search using available providers with fallback
        
        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        if not self.providers:
            raise Exception("No web search providers available")
        
        last_error = None
        
        for provider in self.providers:
            try:
                results = provider.search(query, max_results, **kwargs)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                last_error = e
                continue
        
        # If all providers failed, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All search providers failed to return results")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for web search action group.
    
    Args:
        event: Lambda event containing the search parameters
        context: Lambda context object
        
    Returns:
        Formatted response for Bedrock Agent
    """
    try:
        logger.info(f"Received web search event")
        
        # Extract parameters from the event
        # Handle both direct parameters and Bedrock Agent format
        if 'parameters' in event:
            # Bedrock Agent format
            parameters = event.get('parameters', [])
            param_dict = {param['name']: param['value'] for param in parameters}
        else:
            # Direct invocation format
            param_dict = event
        
        query = param_dict.get('query', '')
        max_results = int(param_dict.get('max_results', 10))
        date_range = param_dict.get('date_range', 'y1')
        location = param_dict.get('location', 'United States')
        
        if not query:
            return create_bedrock_response("Search query is required")
        
        logger.info(f"Searching for: '{query}' (max_results: {max_results}, date_range: {date_range})")
        
        # Perform web search
        search_manager = WebSearchManager()
        search_results = search_manager.search(
            query=query,
            max_results=max_results,
            date_range=date_range,
            location=location
        )
        
        # Process and rank results
        processed_results = process_search_results(search_results, query)
        
        # Format response
        response_text = format_search_results(processed_results, query)
        
        return create_bedrock_response(response_text)
        
    except Exception as e:
        logger.error(f"Error in web search: {str(e)}")
        return create_bedrock_response(f"Web search failed: {str(e)}")

def process_search_results(results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Process and enhance search results.
    
    Args:
        results: Raw search results
        query: Original search query
        
    Returns:
        Processed and ranked results
    """
    if not results:
        return []
    
    processed_results = []
    
    for result in results:
        # Clean and enhance the result
        processed_result = {
            'title': clean_text(result.get('title', '')),
            'url': result.get('url', ''),
            'snippet': clean_text(result.get('snippet', '')),
            'date': format_date(result.get('date', '')),
            'source': result.get('source', 'Web Search'),
            'position': result.get('position', 0),
            'relevance_score': calculate_relevance_score(result, query)
        }
        
        # Only include results with meaningful content
        if processed_result['title'] and processed_result['snippet']:
            processed_results.append(processed_result)
    
    # Sort by relevance score (descending)
    processed_results.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    return processed_results

def calculate_relevance_score(result: Dict[str, Any], query: str) -> float:
    """
    Calculate relevance score for a search result.
    
    Args:
        result: Search result dictionary
        query: Original search query
        
    Returns:
        Relevance score (0.0 to 1.0)
    """
    score = 0.0
    query_terms = query.lower().split()
    
    title = result.get('title', '').lower()
    snippet = result.get('snippet', '').lower()
    
    # Title relevance (weighted higher)
    title_matches = sum(1 for term in query_terms if term in title)
    title_score = (title_matches / len(query_terms)) * 0.6
    
    # Snippet relevance
    snippet_matches = sum(1 for term in query_terms if term in snippet)
    snippet_score = (snippet_matches / len(query_terms)) * 0.4
    
    # Position bonus (earlier results get higher scores)
    position = result.get('position', 10)
    position_bonus = max(0, (10 - position) / 10) * 0.1
    
    score = title_score + snippet_score + position_bonus
    
    return min(1.0, score)

def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove common HTML entities
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    return text.strip()

def format_date(date_str: str) -> str:
    """Format date string for display."""
    if not date_str:
        return "Unknown"
    
    try:
        # Try to parse and format common date formats
        if 'T' in date_str:  # ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        elif '-' in date_str:  # YYYY-MM-DD format
            return date_str.split('T')[0]  # Remove time part if present
        else:
            return date_str
    except:
        return date_str

def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """
    Format search results for agent consumption.
    
    Args:
        results: List of search result dictionaries
        query: Original search query
        
    Returns:
        Formatted string representation of results
    """
    if not results:
        return f"No current web search results found for query: '{query}'. The knowledge base may contain relevant information on this topic."
    
    # Create summary header
    summary = f"Found {len(results)} current web search results for '{query}':\n\n"
    
    formatted_results = [summary]
    
    for i, result in enumerate(results, 1):
        relevance_indicator = "🔥" if result.get('relevance_score', 0) > 0.7 else "📄"
        
        formatted_result = f"""{relevance_indicator} **Result {i}: {result['title']}**
   📅 Date: {result.get('date', 'Unknown')}
   🔗 URL: {result['url']}
   📝 Summary: {result['snippet']}
   ⭐ Relevance: {result.get('relevance_score', 0):.2f}
"""
        formatted_results.append(formatted_result)
    
    # Add analysis note
    analysis_note = f"""
📊 **Search Analysis:**
- Total results: {len(results)}
- High relevance results: {sum(1 for r in results if r.get('relevance_score', 0) > 0.7)}
- Sources: {', '.join(set(r.get('source', 'Unknown') for r in results))}

💡 **Usage Note:** These are current web results that complement the knowledge base. Cross-reference with existing documents for comprehensive analysis.
"""
    
    formatted_results.append(analysis_note)
    
    return "\n".join(formatted_results)

def detect_conflicts_with_knowledge_base(search_results: List[Dict[str, Any]], 
                                       knowledge_base_results: List[Dict[str, Any]] = None) -> str:
    """
    Detect potential conflicts between web search results and knowledge base.
    
    Args:
        search_results: Current web search results
        knowledge_base_results: Results from knowledge base (if available)
        
    Returns:
        Conflict analysis text
    """
    if not knowledge_base_results:
        return "Note: Cross-reference these current findings with your knowledge base for comprehensive analysis."
    
    # This would implement conflict detection logic
    # For now, return a placeholder
    return "Conflict analysis between current web results and knowledge base would be performed here."

def summarize_search_trends(results: List[Dict[str, Any]]) -> str:
    """
    Analyze search results for trends and patterns.
    
    Args:
        results: Search results to analyze
        
    Returns:
        Trend analysis summary
    """
    if not results:
        return ""
    
    # Analyze dates to identify recent trends
    recent_results = []
    older_results = []
    
    current_date = datetime.now()
    thirty_days_ago = current_date - timedelta(days=30)
    
    for result in results:
        date_str = result.get('date', '')
        try:
            if date_str and date_str != 'Unknown':
                result_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if result_date > thirty_days_ago:
                    recent_results.append(result)
                else:
                    older_results.append(result)
        except:
            older_results.append(result)
    
    trend_summary = []
    
    if recent_results:
        trend_summary.append(f"📈 {len(recent_results)} recent results (last 30 days)")
    
    if older_results:
        trend_summary.append(f"📚 {len(older_results)} older results")
    
    return " | ".join(trend_summary) if trend_summary else ""

# Additional utility functions for web search enhancement

def extract_key_entities(text: str) -> List[str]:
    """
    Extract key entities from search results.
    Simple implementation - could be enhanced with NLP libraries.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of potential key entities
    """
    # Simple keyword extraction based on capitalization and common patterns
    import re
    
    # Find capitalized words (potential proper nouns)
    entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    
    # Find years
    years = re.findall(r'\b(19|20)\d{2}\b', text)
    entities.extend(years)
    
    # Remove duplicates and common words
    common_words = {'The', 'This', 'That', 'These', 'Those', 'And', 'But', 'Or', 'For', 'With'}
    entities = [e for e in set(entities) if e not in common_words]
    
    return entities[:10]  # Return top 10 entities

def validate_search_parameters(query: str, max_results: int, date_range: str) -> Dict[str, Any]:
    """
    Validate search parameters and provide suggestions.
    
    Args:
        query: Search query
        max_results: Maximum results requested
        date_range: Date range filter
        
    Returns:
        Validation result with suggestions
    """
    validation = {
        'valid': True,
        'warnings': [],
        'suggestions': []
    }
    
    # Validate query
    if not query or len(query.strip()) < 3:
        validation['valid'] = False
        validation['warnings'].append("Query too short - minimum 3 characters required")
    
    if len(query) > 200:
        validation['warnings'].append("Very long query - consider shortening for better results")
    
    # Validate max_results
    if max_results < 1:
        validation['valid'] = False
        validation['warnings'].append("max_results must be at least 1")
    elif max_results > 50:
        validation['warnings'].append("Large result sets may be slow - consider reducing max_results")
    
    # Validate date_range
    valid_ranges = ['d1', 'w1', 'm1', 'y1']
    if date_range and date_range not in valid_ranges:
        validation['warnings'].append(f"Invalid date_range '{date_range}' - valid options: {valid_ranges}")
    
    # Provide suggestions
    if 'AI' in query.upper() or 'artificial intelligence' in query.lower():
        validation['suggestions'].append("Consider searching for recent AI developments or specific AI technologies")
    
    return validation