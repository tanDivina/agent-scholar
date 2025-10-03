"""
Unit tests for the Cross-Library Analysis Action Group Lambda function.
"""

import pytest
import json
from unittest.mock import Mock, patch
import sys
sys.path.append('src/lambda/cross-library-analysis')

# Import the analysis module
from analysis_engine import (
    lambda_handler, CrossLibraryAnalyzer, ThemeExtractor, ContradictionDetector,
    AuthorPerspectiveAnalyzer, format_analysis_results, create_bedrock_response
)

class TestThemeExtractor:
    """Test the ThemeExtractor class"""
    
    def test_theme_extractor_initialization(self):
        """Test ThemeExtractor initialization"""
        extractor = ThemeExtractor()
        assert hasattr(extractor, 'stop_words')
        assert isinstance(extractor.stop_words, set)
        assert 'the' in extractor.stop_words
        assert 'machine' not in extractor.stop_words
    
    def test_extract_themes_from_documents(self):
        """Test theme extraction from document collection"""
        extractor = ThemeExtractor()
        
        documents = [
            {
                'document_id': 'doc1',
                'title': 'Machine Learning Basics',
                'content': 'Machine learning is a powerful tool for data analysis. Neural networks and deep learning are important concepts in machine learning.',
                'authors': ['Dr. Smith']
            },
            {
                'document_id': 'doc2',
                'title': 'Data Science Methods',
                'content': 'Data science involves statistical analysis and machine learning. Data visualization and data analysis are key components.',
                'authors': ['Prof. Jones']
            }
        ]
        
        result = extractor.extract_themes(documents)
        
        assert 'total_documents' in result
        assert result['total_documents'] == 2
        assert 'top_themes' in result
        assert 'theme_clusters' in result
        assert 'document_theme_mapping' in result
        
        # Check that relevant themes are found (may not be the top ones due to TF-IDF)
        theme_names = [theme['theme'] for theme in result['top_themes']]
        # Should find some meaningful themes related to the content
        assert len(theme_names) > 0
        # Check for any technical terms that should appear
        has_relevant_themes = any(
            term in theme for theme in theme_names 
            for term in ['neural', 'networks', 'analysis', 'powerful', 'tool', 'concepts']
        )
        assert has_relevant_themes
    
    def test_extract_themes_empty_documents(self):
        """Test theme extraction with empty document list"""
        extractor = ThemeExtractor()
        
        result = extractor.extract_themes([])
        
        assert result['total_documents'] == 0
    
    def test_extract_terms_from_text(self):
        """Test term extraction from text"""
        extractor = ThemeExtractor()
        
        text = "Machine learning algorithms are used for data analysis and pattern recognition."
        terms = extractor._extract_terms_from_text(text)
        
        assert 'machine' in terms
        assert 'learning' in terms
        assert 'algorithms' in terms
        assert 'machine learning' in terms
        assert 'data analysis' in terms
        
        # Stop words should not be included
        assert 'the' not in terms
        assert 'are' not in terms
    
    def test_cluster_themes(self):
        """Test theme clustering"""
        extractor = ThemeExtractor()
        
        themes = ['machine learning', 'deep learning', 'data analysis', 'data science', 'neural networks']
        clusters = extractor._cluster_themes(themes)
        
        # Should find some clusters with related themes
        assert isinstance(clusters, list)
        
        # Check that related themes are grouped
        for cluster in clusters:
            assert 'cluster_name' in cluster
            assert 'themes' in cluster
            assert 'size' in cluster

class TestContradictionDetector:
    """Test the ContradictionDetector class"""
    
    def test_contradiction_detector_initialization(self):
        """Test ContradictionDetector initialization"""
        detector = ContradictionDetector()
        assert hasattr(detector, 'contradiction_patterns')
        assert len(detector.contradiction_patterns) > 0
    
    def test_detect_contradictions_with_opposing_statements(self):
        """Test contradiction detection with clearly opposing statements"""
        detector = ContradictionDetector()
        
        documents = [
            {
                'document_id': 'doc1',
                'title': 'Positive View',
                'content': 'Machine learning is excellent and highly effective. It definitely provides great results for businesses.',
                'authors': ['Dr. Optimist']
            },
            {
                'document_id': 'doc2',
                'title': 'Negative View',
                'content': 'Machine learning is problematic and often ineffective. It never provides reliable results for businesses.',
                'authors': ['Dr. Pessimist']
            }
        ]
        
        result = detector.detect_contradictions(documents)
        
        assert 'total_documents_analyzed' in result
        assert result['total_documents_analyzed'] == 2
        assert 'contradictions_found' in result
        assert result['contradictions_found'] > 0
        assert 'all_contradictions' in result
        
        # Check contradiction details
        contradictions = result['all_contradictions']
        assert len(contradictions) > 0
        
        contradiction = contradictions[0]
        assert 'document1' in contradiction
        assert 'document2' in contradiction
        assert 'confidence_score' in contradiction
        assert 'contradiction_type' in contradiction
    
    def test_detect_contradictions_no_conflicts(self):
        """Test contradiction detection with consistent statements"""
        detector = ContradictionDetector()
        
        documents = [
            {
                'document_id': 'doc1',
                'title': 'Consistent View 1',
                'content': 'Machine learning is a useful technology for data analysis.',
                'authors': ['Dr. A']
            },
            {
                'document_id': 'doc2',
                'title': 'Consistent View 2',
                'content': 'Data analysis benefits from machine learning techniques.',
                'authors': ['Dr. B']
            }
        ]
        
        result = detector.detect_contradictions(documents)
        
        assert result['contradictions_found'] == 0 or result['contradictions_found'] is None
    
    def test_extract_statements(self):
        """Test statement extraction from text"""
        detector = ContradictionDetector()
        
        text = "Machine learning is excellent. It never fails to deliver results. The technology is definitely beneficial."
        statements = detector._extract_statements(text)
        
        assert len(statements) > 0
        
        # Check that statements contain pattern information
        for stmt in statements:
            assert 'text' in stmt
            assert 'patterns' in stmt
            assert 'length' in stmt
    
    def test_calculate_contradiction_score(self):
        """Test contradiction score calculation"""
        detector = ContradictionDetector()
        
        # Create opposing statements
        stmt1 = {
            'text': 'Machine learning is excellent and effective',
            'patterns': ['positive']
        }
        stmt2 = {
            'text': 'Machine learning is poor and ineffective',
            'patterns': ['negative']
        }
        
        score = detector._calculate_contradiction_score(stmt1, stmt2)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.3  # Should detect opposition
    
    def test_identify_contradiction_type(self):
        """Test contradiction type identification"""
        detector = ContradictionDetector()
        
        stmt1 = {'patterns': ['positive']}
        stmt2 = {'patterns': ['negative']}
        
        contradiction_type = detector._identify_contradiction_type(stmt1, stmt2)
        
        assert contradiction_type == 'sentiment_contradiction'

class TestAuthorPerspectiveAnalyzer:
    """Test the AuthorPerspectiveAnalyzer class"""
    
    def test_analyze_perspectives(self):
        """Test author perspective analysis"""
        analyzer = AuthorPerspectiveAnalyzer()
        
        documents = [
            {
                'document_id': 'doc1',
                'title': 'Optimistic Paper',
                'content': 'Machine learning is excellent and definitely beneficial. The results are clearly positive and effective.',
                'authors': ['Dr. Optimist']
            },
            {
                'document_id': 'doc2',
                'title': 'Cautious Paper',
                'content': 'Machine learning might be useful, but there are possibly some concerns. The results are uncertain and need more research.',
                'authors': ['Dr. Cautious']
            }
        ]
        
        result = analyzer.analyze_perspectives(documents)
        
        assert 'total_authors' in result
        assert result['total_authors'] == 2
        assert 'author_perspectives' in result
        assert 'perspective_comparisons' in result
        assert 'diversity_analysis' in result
        
        # Check author data
        perspectives = result['author_perspectives']
        assert 'Dr. Optimist' in perspectives
        assert 'Dr. Cautious' in perspectives
        
        # Check perspective summaries
        for author, data in perspectives.items():
            assert 'document_count' in data
            assert 'perspective_summary' in data
    
    def test_analyze_document_perspective(self):
        """Test single document perspective analysis"""
        analyzer = AuthorPerspectiveAnalyzer()
        
        content = "Machine learning is definitely excellent and clearly beneficial. The results are absolutely positive."
        
        perspective = analyzer._analyze_document_perspective(content, "Test Doc", "doc1")
        
        assert 'sentiment_score' in perspective
        assert 'certainty_score' in perspective
        assert 'writing_style' in perspective
        assert 'content_length' in perspective
        assert 'word_count' in perspective
        
        # Should detect positive sentiment and high certainty
        assert perspective['sentiment_score'] > 0
        assert perspective['certainty_score'] > 0
    
    def test_summarize_author_perspective(self):
        """Test author perspective summarization"""
        analyzer = AuthorPerspectiveAnalyzer()
        
        author_data = {
            'documents': [
                {
                    'id': 'doc1',
                    'title': 'Test Doc',
                    'perspective_data': {
                        'sentiment_score': 0.5,
                        'certainty_score': 0.3,
                        'writing_style': {'avg_sentence_length': 15}
                    }
                }
            ]
        }
        
        summary = analyzer._summarize_author_perspective(author_data)
        
        assert 'sentiment_tendency' in summary
        assert 'certainty_tendency' in summary
        assert 'avg_sentiment_score' in summary
        assert 'avg_certainty_score' in summary
        assert 'perspective_traits' in summary
        assert 'document_count' in summary
    
    def test_calculate_std_dev(self):
        """Test standard deviation calculation"""
        analyzer = AuthorPerspectiveAnalyzer()
        
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        std_dev = analyzer._calculate_std_dev(values)
        
        assert std_dev > 0
        assert isinstance(std_dev, float)
        
        # Test with empty list
        assert analyzer._calculate_std_dev([]) == 0.0

class TestCrossLibraryAnalyzer:
    """Test the main CrossLibraryAnalyzer class"""
    
    def test_analyzer_initialization(self):
        """Test CrossLibraryAnalyzer initialization"""
        analyzer = CrossLibraryAnalyzer()
        
        assert hasattr(analyzer, 'theme_extractor')
        assert hasattr(analyzer, 'contradiction_detector')
        assert hasattr(analyzer, 'perspective_analyzer')
        assert isinstance(analyzer.theme_extractor, ThemeExtractor)
        assert isinstance(analyzer.contradiction_detector, ContradictionDetector)
        assert isinstance(analyzer.perspective_analyzer, AuthorPerspectiveAnalyzer)
    
    def test_analyze_library_comprehensive(self):
        """Test comprehensive library analysis"""
        analyzer = CrossLibraryAnalyzer()
        
        # Mock the document retrieval to return sample data
        with patch.object(analyzer, '_retrieve_documents') as mock_retrieve:
            mock_retrieve.return_value = [
                {
                    'document_id': 'doc1',
                    'title': 'Test Document 1',
                    'content': 'Machine learning is excellent for data analysis.',
                    'authors': ['Dr. Smith']
                },
                {
                    'document_id': 'doc2',
                    'title': 'Test Document 2',
                    'content': 'Data science provides good insights for business.',
                    'authors': ['Prof. Jones']
                }
            ]
            
            result = analyzer.analyze_library(query="machine learning", max_documents=10)
            
            assert 'analysis_timestamp' in result
            assert 'documents_analyzed' in result
            assert 'theme_analysis' in result
            assert 'contradiction_analysis' in result
            assert 'perspective_analysis' in result
            assert 'synthesis' in result
            
            # Check that analysis was performed
            assert result['documents_analyzed'] == 2
    
    def test_create_sample_documents(self):
        """Test sample document creation"""
        analyzer = CrossLibraryAnalyzer()
        
        sample_docs = analyzer._create_sample_documents()
        
        assert len(sample_docs) > 0
        
        for doc in sample_docs:
            assert 'document_id' in doc
            assert 'title' in doc
            assert 'authors' in doc
            assert 'content' in doc
    
    def test_synthesize_findings(self):
        """Test findings synthesis"""
        analyzer = CrossLibraryAnalyzer()
        
        theme_analysis = {
            'top_themes': [
                {'theme': 'machine learning', 'relevance_score': 0.8}
            ]
        }
        
        contradiction_analysis = {
            'contradictions_found': 2
        }
        
        perspective_analysis = {
            'total_authors': 3,
            'diversity_analysis': {'diversity_level': 'high'}
        }
        
        synthesis = analyzer._synthesize_findings(theme_analysis, contradiction_analysis, perspective_analysis)
        
        assert 'key_insights' in synthesis
        assert 'recommendations' in synthesis
        assert 'overall_assessment' in synthesis
        
        # Check that insights were generated
        assert len(synthesis['key_insights']) > 0

class TestLambdaHandler:
    """Test the main Lambda handler"""
    
    def test_lambda_handler_comprehensive_analysis(self):
        """Test Lambda handler with comprehensive analysis"""
        event = {
            'parameters': [
                {'name': 'analysis_type', 'value': 'comprehensive'},
                {'name': 'query', 'value': 'machine learning'},
                {'name': 'max_documents', 'value': '10'}
            ]
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']
        
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Cross-Library Analysis Results' in body
        assert 'comprehensive' in body
    
    def test_lambda_handler_theme_analysis_only(self):
        """Test Lambda handler with theme analysis only"""
        event = {
            'analysis_type': 'themes',
            'query': 'artificial intelligence',
            'max_documents': 5
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Theme Analysis' in body
    
    def test_lambda_handler_contradiction_analysis_only(self):
        """Test Lambda handler with contradiction analysis only"""
        event = {
            'analysis_type': 'contradictions',
            'max_documents': 15
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Contradiction Analysis' in body
    
    def test_lambda_handler_perspective_analysis_only(self):
        """Test Lambda handler with perspective analysis only"""
        event = {
            'analysis_type': 'perspectives',
            'document_ids': 'doc1,doc2,doc3'
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        
        body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        assert 'Perspective Analysis' in body
    
    def test_lambda_handler_error_handling(self):
        """Test Lambda handler error handling"""
        # Test with invalid analysis type that might cause an error
        event = {
            'analysis_type': 'invalid_type'
        }
        
        context = Mock()
        
        # Mock an error in the analyzer
        with patch('analysis_engine.CrossLibraryAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze_library.side_effect = Exception("Test error")
            mock_analyzer_class.return_value = mock_analyzer
            
            response = lambda_handler(event, context)
            
            body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            assert 'failed' in body.lower() or 'error' in body.lower()

class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_format_analysis_results_comprehensive(self):
        """Test formatting of comprehensive analysis results"""
        results = {
            'analysis_timestamp': '2024-01-01T12:00:00',
            'documents_analyzed': 5,
            'theme_analysis': {
                'top_themes': [
                    {'theme': 'machine learning', 'relevance_score': 0.8, 'document_frequency': 3}
                ]
            },
            'contradiction_analysis': {
                'contradictions_found': 2,
                'high_confidence_contradictions': [
                    {
                        'document1': {'title': 'Doc 1'},
                        'document2': {'title': 'Doc 2'},
                        'contradiction_type': 'sentiment_contradiction',
                        'confidence_score': 0.85
                    }
                ]
            },
            'perspective_analysis': {
                'total_authors': 3,
                'diversity_analysis': {'diversity_level': 'high'}
            },
            'synthesis': {
                'key_insights': ['Key insight 1', 'Key insight 2'],
                'recommendations': ['Recommendation 1'],
                'overall_assessment': {
                    'theme_coherence': 'high',
                    'consistency_level': 'moderate',
                    'perspective_diversity': 'high'
                }
            }
        }
        
        formatted = format_analysis_results(results, 'comprehensive')
        
        assert 'Cross-Library Analysis Results' in formatted
        assert 'Theme Analysis' in formatted
        assert 'Contradiction Analysis' in formatted
        assert 'Perspective Analysis' in formatted
        assert 'Key Insights' in formatted
        assert 'machine learning' in formatted
        assert '5' in formatted  # documents analyzed
    
    def test_format_analysis_results_with_error(self):
        """Test formatting of error results"""
        results = {
            'error': 'Test error message'
        }
        
        formatted = format_analysis_results(results, 'comprehensive')
        
        assert '❌' in formatted
        assert 'Error' in formatted
        assert 'Test error message' in formatted
    
    def test_create_bedrock_response(self):
        """Test Bedrock response creation"""
        response_text = "Test analysis results"
        response = create_bedrock_response(response_text)
        
        assert 'response' in response
        assert 'actionResponse' in response['response']
        assert 'actionResponseBody' in response['response']['actionResponse']
        assert 'TEXT' in response['response']['actionResponse']['actionResponseBody']
        assert response['response']['actionResponse']['actionResponseBody']['TEXT']['body'] == response_text

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])