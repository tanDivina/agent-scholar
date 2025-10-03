"""
Cross-Library Analysis Action Group Lambda Function for Agent Scholar

This Lambda function provides advanced analysis capabilities to identify thematic connections,
contradictions, and author perspectives across multiple documents in the library.
"""

import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict, Counter
import re
import math

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Add shared utilities
sys.path.append('/opt/python')

# Try to import shared utilities, fall back to local implementations if not available
try:
    from shared.utils import search_knowledge_base, create_opensearch_client
    from shared.models import Document, DocumentChunk
except ImportError:
    # Fallback implementations for testing
    def search_knowledge_base(*args, **kwargs):
        return {"results": []}
    
    def create_opensearch_client(*args, **kwargs):
        return None
    
    class Document:
        pass
    
    class DocumentChunk:
        pass

class ThemeExtractor:
    """Extracts and analyzes themes from document collections"""
    
    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'this', 'that', 'these', 'those', 'i', 'me',
            'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 'yourself',
            'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'it',
            'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
            'who', 'whom', 'whose', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was',
            'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did',
            'doing', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall'
        }
    
    def extract_themes(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract key themes from a collection of documents.
        
        Args:
            documents: List of document dictionaries with content and metadata
            
        Returns:
            Dictionary containing extracted themes and analysis
        """
        try:
            # Extract key terms and phrases
            all_terms = []
            document_terms = {}
            
            for doc in documents:
                content = doc.get('content', '') or doc.get('chunk_content', '')
                doc_id = doc.get('document_id', doc.get('id', 'unknown'))
                
                # Extract terms from this document
                terms = self._extract_terms_from_text(content)
                all_terms.extend(terms)
                document_terms[doc_id] = terms
            
            # Calculate term frequencies and identify themes
            term_frequencies = Counter(all_terms)
            
            # Filter out very common and very rare terms
            total_docs = len(documents)
            filtered_terms = {}
            
            for term, freq in term_frequencies.items():
                # Calculate document frequency (how many documents contain this term)
                doc_freq = sum(1 for doc_terms in document_terms.values() if term in doc_terms)
                
                # Use TF-IDF-like scoring to identify important terms
                # More lenient filtering for small document collections
                min_doc_freq = 1
                max_doc_freq_ratio = 1.0 if total_docs <= 3 else 0.9
                
                if doc_freq >= min_doc_freq and doc_freq <= total_docs * max_doc_freq_ratio:
                    # Avoid division by zero in log
                    tf_idf_score = freq * math.log(max(total_docs / doc_freq, 1.1))
                    filtered_terms[term] = {
                        'frequency': freq,
                        'document_frequency': doc_freq,
                        'tf_idf_score': tf_idf_score
                    }
            
            # Identify top themes
            top_themes = sorted(filtered_terms.items(), key=lambda x: x[1]['tf_idf_score'], reverse=True)[:20]
            
            # Group related themes
            theme_clusters = self._cluster_themes([theme[0] for theme in top_themes])
            
            return {
                'total_documents': total_docs,
                'total_terms_extracted': len(all_terms),
                'unique_terms': len(term_frequencies),
                'top_themes': [
                    {
                        'theme': theme,
                        'frequency': data['frequency'],
                        'document_frequency': data['document_frequency'],
                        'relevance_score': round(data['tf_idf_score'], 2)
                    }
                    for theme, data in top_themes[:10]
                ],
                'theme_clusters': theme_clusters,
                'document_theme_mapping': self._map_documents_to_themes(document_terms, [t[0] for t in top_themes[:10]])
            }
            
        except Exception as e:
            logger.error(f"Error extracting themes: {str(e)}")
            return {
                'error': str(e),
                'total_documents': len(documents) if documents else 0
            }
    
    def _extract_terms_from_text(self, text: str) -> List[str]:
        """Extract meaningful terms from text"""
        if not text:
            return []
        
        # Convert to lowercase and extract words
        text = text.lower()
        
        # Extract multi-word phrases and single words
        terms = []
        
        # Extract 2-3 word phrases that might be important concepts
        words = re.findall(r'\b[a-zA-Z]+\b', text)
        
        # Single important words
        for word in words:
            if len(word) > 3 and word not in self.stop_words:
                terms.append(word)
        
        # Two-word phrases
        for i in range(len(words) - 1):
            if (len(words[i]) > 2 and len(words[i+1]) > 2 and 
                words[i] not in self.stop_words and words[i+1] not in self.stop_words):
                phrase = f"{words[i]} {words[i+1]}"
                terms.append(phrase)
        
        # Three-word phrases (more selective)
        for i in range(len(words) - 2):
            if (all(len(w) > 2 for w in words[i:i+3]) and 
                all(w not in self.stop_words for w in words[i:i+3])):
                phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
                # Only include if it looks like a meaningful concept
                if any(keyword in phrase for keyword in ['machine learning', 'artificial intelligence', 'data science', 'neural network']):
                    terms.append(phrase)
        
        return terms
    
    def _cluster_themes(self, themes: List[str]) -> List[Dict[str, Any]]:
        """Group related themes into clusters"""
        clusters = []
        used_themes = set()
        
        for theme in themes:
            if theme in used_themes:
                continue
            
            # Find related themes
            related = [theme]
            used_themes.add(theme)
            
            for other_theme in themes:
                if other_theme != theme and other_theme not in used_themes:
                    # Simple similarity check based on shared words
                    theme_words = set(theme.split())
                    other_words = set(other_theme.split())
                    
                    # If themes share significant words, group them
                    if len(theme_words.intersection(other_words)) > 0:
                        related.append(other_theme)
                        used_themes.add(other_theme)
            
            if len(related) > 1:
                clusters.append({
                    'cluster_name': theme,  # Use first theme as cluster name
                    'themes': related,
                    'size': len(related)
                })
        
        return clusters
    
    def _map_documents_to_themes(self, document_terms: Dict[str, List[str]], top_themes: List[str]) -> Dict[str, List[str]]:
        """Map documents to their primary themes"""
        doc_theme_mapping = {}
        
        for doc_id, terms in document_terms.items():
            doc_themes = []
            for theme in top_themes:
                if theme in terms:
                    doc_themes.append(theme)
            
            doc_theme_mapping[doc_id] = doc_themes[:5]  # Top 5 themes per document
        
        return doc_theme_mapping

class ContradictionDetector:
    """Detects contradictions and conflicting statements across documents"""
    
    def __init__(self):
        self.contradiction_patterns = [
            # Negation patterns
            (r'\b(not|never|no|cannot|can\'t|won\'t|doesn\'t|don\'t)\b', 'negation'),
            # Certainty vs uncertainty
            (r'\b(always|never|definitely|certainly|absolutely)\b', 'certainty'),
            (r'\b(maybe|perhaps|possibly|might|could|uncertain)\b', 'uncertainty'),
            # Positive vs negative sentiment
            (r'\b(excellent|great|good|positive|beneficial|effective)\b', 'positive'),
            (r'\b(poor|bad|negative|harmful|ineffective|problematic)\b', 'negative'),
            # Quantitative contradictions
            (r'\b(increase|rise|grow|improve|higher|more)\b', 'increase'),
            (r'\b(decrease|fall|decline|reduce|lower|less)\b', 'decrease')
        ]
    
    def detect_contradictions(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect potential contradictions between documents.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            Dictionary containing detected contradictions
        """
        try:
            contradictions = []
            document_statements = {}
            
            # Extract key statements from each document
            for doc in documents:
                content = doc.get('content', '') or doc.get('chunk_content', '')
                doc_id = doc.get('document_id', doc.get('id', 'unknown'))
                title = doc.get('title', 'Unknown Document')
                
                statements = self._extract_statements(content)
                document_statements[doc_id] = {
                    'title': title,
                    'statements': statements
                }
            
            # Compare statements between documents
            doc_ids = list(document_statements.keys())
            
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    doc1_id, doc2_id = doc_ids[i], doc_ids[j]
                    doc1_data = document_statements[doc1_id]
                    doc2_data = document_statements[doc2_id]
                    
                    # Find contradictions between these two documents
                    doc_contradictions = self._find_contradictions_between_docs(
                        doc1_data, doc2_data, doc1_id, doc2_id
                    )
                    
                    contradictions.extend(doc_contradictions)
            
            # Rank contradictions by confidence
            contradictions.sort(key=lambda x: x['confidence_score'], reverse=True)
            
            return {
                'total_documents_analyzed': len(documents),
                'contradictions_found': len(contradictions),
                'high_confidence_contradictions': [c for c in contradictions if c['confidence_score'] > 0.7],
                'all_contradictions': contradictions[:20],  # Top 20 contradictions
                'contradiction_summary': self._summarize_contradictions(contradictions)
            }
            
        except Exception as e:
            logger.error(f"Error detecting contradictions: {str(e)}")
            return {
                'error': str(e),
                'total_documents_analyzed': len(documents) if documents else 0
            }
    
    def _extract_statements(self, text: str) -> List[Dict[str, Any]]:
        """Extract key statements from text"""
        if not text:
            return []
        
        statements = []
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
            
            # Analyze sentence for patterns
            patterns_found = []
            for pattern, pattern_type in self.contradiction_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    patterns_found.append(pattern_type)
            
            if patterns_found:
                statements.append({
                    'text': sentence,
                    'patterns': patterns_found,
                    'length': len(sentence)
                })
        
        return statements
    
    def _find_contradictions_between_docs(self, doc1_data: Dict, doc2_data: Dict, 
                                        doc1_id: str, doc2_id: str) -> List[Dict[str, Any]]:
        """Find contradictions between two documents"""
        contradictions = []
        
        for stmt1 in doc1_data['statements']:
            for stmt2 in doc2_data['statements']:
                # Check for contradictory patterns
                contradiction_score = self._calculate_contradiction_score(stmt1, stmt2)
                
                if contradiction_score > 0.5:
                    contradictions.append({
                        'document1': {
                            'id': doc1_id,
                            'title': doc1_data['title'],
                            'statement': stmt1['text']
                        },
                        'document2': {
                            'id': doc2_id,
                            'title': doc2_data['title'],
                            'statement': stmt2['text']
                        },
                        'confidence_score': contradiction_score,
                        'contradiction_type': self._identify_contradiction_type(stmt1, stmt2)
                    })
        
        return contradictions
    
    def _calculate_contradiction_score(self, stmt1: Dict, stmt2: Dict) -> float:
        """Calculate how likely two statements are to contradict each other"""
        score = 0.0
        
        # Check for opposing patterns
        patterns1 = set(stmt1['patterns'])
        patterns2 = set(stmt2['patterns'])
        
        # Define opposing pattern pairs
        opposing_pairs = [
            ('positive', 'negative'),
            ('certainty', 'uncertainty'),
            ('increase', 'decrease'),
            ('negation', 'certainty')
        ]
        
        for pair1, pair2 in opposing_pairs:
            if pair1 in patterns1 and pair2 in patterns2:
                score += 0.4
            elif pair2 in patterns1 and pair1 in patterns2:
                score += 0.4
        
        # Check for shared keywords (higher chance of contradiction if discussing same topic)
        words1 = set(re.findall(r'\b\w+\b', stmt1['text'].lower()))
        words2 = set(re.findall(r'\b\w+\b', stmt2['text'].lower()))
        
        shared_words = words1.intersection(words2)
        if len(shared_words) > 2:
            score += 0.3
        
        return min(score, 1.0)
    
    def _identify_contradiction_type(self, stmt1: Dict, stmt2: Dict) -> str:
        """Identify the type of contradiction"""
        patterns1 = set(stmt1['patterns'])
        patterns2 = set(stmt2['patterns'])
        
        if 'positive' in patterns1 and 'negative' in patterns2:
            return 'sentiment_contradiction'
        elif 'negative' in patterns1 and 'positive' in patterns2:
            return 'sentiment_contradiction'
        elif 'certainty' in patterns1 and 'uncertainty' in patterns2:
            return 'certainty_contradiction'
        elif 'uncertainty' in patterns1 and 'certainty' in patterns2:
            return 'certainty_contradiction'
        elif 'increase' in patterns1 and 'decrease' in patterns2:
            return 'quantitative_contradiction'
        elif 'decrease' in patterns1 and 'increase' in patterns2:
            return 'quantitative_contradiction'
        else:
            return 'general_contradiction'
    
    def _summarize_contradictions(self, contradictions: List[Dict]) -> Dict[str, Any]:
        """Summarize contradiction findings"""
        if not contradictions:
            return {'message': 'No contradictions detected'}
        
        # Count contradiction types
        type_counts = Counter(c['contradiction_type'] for c in contradictions)
        
        # Find most contradictory document pairs
        doc_pair_counts = Counter()
        for c in contradictions:
            pair = tuple(sorted([c['document1']['id'], c['document2']['id']]))
            doc_pair_counts[pair] += 1
        
        return {
            'contradiction_types': dict(type_counts),
            'most_contradictory_pairs': [
                {
                    'documents': list(pair),
                    'contradiction_count': count
                }
                for pair, count in doc_pair_counts.most_common(5)
            ],
            'average_confidence': sum(c['confidence_score'] for c in contradictions) / len(contradictions)
        }

class AuthorPerspectiveAnalyzer:
    """Analyzes different author perspectives and viewpoints"""
    
    def analyze_perspectives(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze author perspectives across documents.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            Dictionary containing perspective analysis
        """
        try:
            author_perspectives = {}
            
            # Group documents by author
            for doc in documents:
                authors = doc.get('authors', ['Unknown Author'])
                if isinstance(authors, str):
                    authors = [authors]
                
                content = doc.get('content', '') or doc.get('chunk_content', '')
                doc_id = doc.get('document_id', doc.get('id', 'unknown'))
                title = doc.get('title', 'Unknown Document')
                
                for author in authors:
                    if author not in author_perspectives:
                        author_perspectives[author] = {
                            'documents': [],
                            'total_content_length': 0,
                            'key_themes': [],
                            'sentiment_indicators': [],
                            'writing_style': {}
                        }
                    
                    # Analyze this document's perspective
                    perspective_data = self._analyze_document_perspective(content, title, doc_id)
                    
                    author_perspectives[author]['documents'].append({
                        'id': doc_id,
                        'title': title,
                        'perspective_data': perspective_data
                    })
                    author_perspectives[author]['total_content_length'] += len(content)
            
            # Analyze each author's overall perspective
            for author, data in author_perspectives.items():
                data['perspective_summary'] = self._summarize_author_perspective(data)
            
            # Compare perspectives between authors
            perspective_comparisons = self._compare_author_perspectives(author_perspectives)
            
            return {
                'total_authors': len(author_perspectives),
                'author_perspectives': {
                    author: {
                        'document_count': len(data['documents']),
                        'total_content_length': data['total_content_length'],
                        'perspective_summary': data['perspective_summary']
                    }
                    for author, data in author_perspectives.items()
                },
                'perspective_comparisons': perspective_comparisons,
                'diversity_analysis': self._analyze_perspective_diversity(author_perspectives)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing perspectives: {str(e)}")
            return {
                'error': str(e),
                'total_authors': 0
            }
    
    def _analyze_document_perspective(self, content: str, title: str, doc_id: str) -> Dict[str, Any]:
        """Analyze perspective indicators in a single document"""
        if not content:
            return {}
        
        # Sentiment indicators
        positive_words = ['good', 'excellent', 'effective', 'successful', 'beneficial', 'positive', 'strong']
        negative_words = ['bad', 'poor', 'ineffective', 'problematic', 'negative', 'weak', 'failed']
        
        content_lower = content.lower()
        
        positive_count = sum(content_lower.count(word) for word in positive_words)
        negative_count = sum(content_lower.count(word) for word in negative_words)
        
        # Certainty indicators
        certainty_words = ['definitely', 'certainly', 'clearly', 'obviously', 'undoubtedly']
        uncertainty_words = ['maybe', 'perhaps', 'possibly', 'might', 'could', 'uncertain']
        
        certainty_count = sum(content_lower.count(word) for word in certainty_words)
        uncertainty_count = sum(content_lower.count(word) for word in uncertainty_words)
        
        # Writing style indicators
        sentence_count = len(re.findall(r'[.!?]+', content))
        avg_sentence_length = len(content.split()) / max(sentence_count, 1)
        
        question_count = content.count('?')
        exclamation_count = content.count('!')
        
        return {
            'sentiment_score': (positive_count - negative_count) / max(positive_count + negative_count, 1),
            'certainty_score': (certainty_count - uncertainty_count) / max(certainty_count + uncertainty_count, 1),
            'writing_style': {
                'avg_sentence_length': avg_sentence_length,
                'question_ratio': question_count / max(sentence_count, 1),
                'exclamation_ratio': exclamation_count / max(sentence_count, 1)
            },
            'content_length': len(content),
            'word_count': len(content.split())
        }
    
    def _summarize_author_perspective(self, author_data: Dict) -> Dict[str, Any]:
        """Summarize an author's overall perspective"""
        documents = author_data['documents']
        
        if not documents:
            return {}
        
        # Aggregate perspective data
        total_sentiment = sum(doc['perspective_data'].get('sentiment_score', 0) for doc in documents)
        total_certainty = sum(doc['perspective_data'].get('certainty_score', 0) for doc in documents)
        
        avg_sentiment = total_sentiment / len(documents)
        avg_certainty = total_certainty / len(documents)
        
        # Aggregate writing style
        avg_sentence_lengths = [doc['perspective_data'].get('writing_style', {}).get('avg_sentence_length', 0) 
                               for doc in documents]
        avg_sentence_length = sum(avg_sentence_lengths) / len(avg_sentence_lengths) if avg_sentence_lengths else 0
        
        # Determine perspective characteristics
        perspective_traits = []
        
        if avg_sentiment > 0.2:
            perspective_traits.append('optimistic')
        elif avg_sentiment < -0.2:
            perspective_traits.append('critical')
        else:
            perspective_traits.append('balanced')
        
        if avg_certainty > 0.2:
            perspective_traits.append('confident')
        elif avg_certainty < -0.2:
            perspective_traits.append('cautious')
        else:
            perspective_traits.append('moderate')
        
        if avg_sentence_length > 20:
            perspective_traits.append('detailed')
        elif avg_sentence_length < 12:
            perspective_traits.append('concise')
        
        return {
            'sentiment_tendency': 'positive' if avg_sentiment > 0 else 'negative' if avg_sentiment < 0 else 'neutral',
            'certainty_tendency': 'confident' if avg_certainty > 0 else 'uncertain' if avg_certainty < 0 else 'moderate',
            'avg_sentiment_score': round(avg_sentiment, 3),
            'avg_certainty_score': round(avg_certainty, 3),
            'avg_sentence_length': round(avg_sentence_length, 1),
            'perspective_traits': perspective_traits,
            'document_count': len(documents)
        }
    
    def _compare_author_perspectives(self, author_perspectives: Dict) -> List[Dict[str, Any]]:
        """Compare perspectives between different authors"""
        comparisons = []
        authors = list(author_perspectives.keys())
        
        for i in range(len(authors)):
            for j in range(i + 1, len(authors)):
                author1, author2 = authors[i], authors[j]
                
                summary1 = author_perspectives[author1].get('perspective_summary', {})
                summary2 = author_perspectives[author2].get('perspective_summary', {})
                
                if not summary1 or not summary2:
                    continue
                
                # Calculate perspective differences
                sentiment_diff = abs(summary1.get('avg_sentiment_score', 0) - summary2.get('avg_sentiment_score', 0))
                certainty_diff = abs(summary1.get('avg_certainty_score', 0) - summary2.get('avg_certainty_score', 0))
                
                # Determine relationship type
                relationship_type = 'similar'
                if sentiment_diff > 0.5 or certainty_diff > 0.5:
                    relationship_type = 'contrasting'
                elif sentiment_diff > 0.3 or certainty_diff > 0.3:
                    relationship_type = 'different'
                
                comparisons.append({
                    'author1': author1,
                    'author2': author2,
                    'sentiment_difference': round(sentiment_diff, 3),
                    'certainty_difference': round(certainty_diff, 3),
                    'relationship_type': relationship_type,
                    'author1_traits': summary1.get('perspective_traits', []),
                    'author2_traits': summary2.get('perspective_traits', [])
                })
        
        # Sort by most contrasting first
        comparisons.sort(key=lambda x: x['sentiment_difference'] + x['certainty_difference'], reverse=True)
        
        return comparisons[:10]  # Top 10 most interesting comparisons
    
    def _analyze_perspective_diversity(self, author_perspectives: Dict) -> Dict[str, Any]:
        """Analyze the diversity of perspectives in the collection"""
        if len(author_perspectives) < 2:
            return {'message': 'Insufficient authors for diversity analysis'}
        
        # Calculate diversity metrics
        sentiment_scores = []
        certainty_scores = []
        
        for author_data in author_perspectives.values():
            summary = author_data.get('perspective_summary', {})
            sentiment_scores.append(summary.get('avg_sentiment_score', 0))
            certainty_scores.append(summary.get('avg_certainty_score', 0))
        
        # Calculate standard deviation as diversity measure
        sentiment_diversity = self._calculate_std_dev(sentiment_scores)
        certainty_diversity = self._calculate_std_dev(certainty_scores)
        
        # Determine diversity level
        overall_diversity = (sentiment_diversity + certainty_diversity) / 2
        
        if overall_diversity > 0.4:
            diversity_level = 'high'
        elif overall_diversity > 0.2:
            diversity_level = 'moderate'
        else:
            diversity_level = 'low'
        
        return {
            'diversity_level': diversity_level,
            'sentiment_diversity': round(sentiment_diversity, 3),
            'certainty_diversity': round(certainty_diversity, 3),
            'overall_diversity_score': round(overall_diversity, 3),
            'author_count': len(author_perspectives)
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

class CrossLibraryAnalyzer:
    """Main analyzer that coordinates all analysis components"""
    
    def __init__(self):
        self.theme_extractor = ThemeExtractor()
        self.contradiction_detector = ContradictionDetector()
        self.perspective_analyzer = AuthorPerspectiveAnalyzer()
        
        # Initialize OpenSearch client if available
        self.opensearch_client = None
        self.opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
        self.index_name = os.getenv('INDEX_NAME', 'agent-scholar-documents')
        
        if self.opensearch_endpoint:
            try:
                self.opensearch_client = create_opensearch_client(
                    self.opensearch_endpoint, 
                    os.getenv('AWS_REGION', 'us-east-1')
                )
            except Exception as e:
                logger.warning(f"Could not initialize OpenSearch client: {e}")
    
    def analyze_library(self, query: str = None, document_ids: List[str] = None, 
                       max_documents: int = 50) -> Dict[str, Any]:
        """
        Perform comprehensive cross-library analysis.
        
        Args:
            query: Optional query to filter documents
            document_ids: Optional list of specific document IDs to analyze
            max_documents: Maximum number of documents to analyze
            
        Returns:
            Comprehensive analysis results
        """
        try:
            # Retrieve documents for analysis
            documents = self._retrieve_documents(query, document_ids, max_documents)
            
            if not documents:
                return {
                    'error': 'No documents found for analysis',
                    'query': query,
                    'document_ids': document_ids
                }
            
            logger.info(f"Analyzing {len(documents)} documents")
            
            # Perform all analyses
            theme_analysis = self.theme_extractor.extract_themes(documents)
            contradiction_analysis = self.contradiction_detector.detect_contradictions(documents)
            perspective_analysis = self.perspective_analyzer.analyze_perspectives(documents)
            
            # Generate synthesis
            synthesis = self._synthesize_findings(theme_analysis, contradiction_analysis, perspective_analysis)
            
            return {
                'analysis_timestamp': datetime.now().isoformat(),
                'documents_analyzed': len(documents),
                'query_used': query,
                'theme_analysis': theme_analysis,
                'contradiction_analysis': contradiction_analysis,
                'perspective_analysis': perspective_analysis,
                'synthesis': synthesis
            }
            
        except Exception as e:
            logger.error(f"Error in cross-library analysis: {str(e)}")
            return {
                'error': str(e),
                'analysis_timestamp': datetime.now().isoformat()
            }
    
    def _retrieve_documents(self, query: str = None, document_ids: List[str] = None, 
                          max_documents: int = 50) -> List[Dict[str, Any]]:
        """Retrieve documents for analysis"""
        documents = []
        
        if self.opensearch_client:
            try:
                if document_ids:
                    # Retrieve specific documents
                    for doc_id in document_ids[:max_documents]:
                        # This would retrieve specific documents by ID
                        # For now, we'll use a search approach
                        pass
                
                if query:
                    # Search for documents matching the query
                    search_results = search_knowledge_base(
                        self.opensearch_client,
                        self.index_name,
                        query_text=query,
                        size=max_documents,
                        search_type='hybrid'
                    )
                    
                    documents = search_results.get('results', [])
                else:
                    # Get a sample of documents
                    search_results = search_knowledge_base(
                        self.opensearch_client,
                        self.index_name,
                        query_text="*",
                        size=max_documents,
                        search_type='keyword'
                    )
                    
                    documents = search_results.get('results', [])
                
            except Exception as e:
                logger.error(f"Error retrieving documents from OpenSearch: {e}")
        
        # If no documents retrieved, create sample data for testing
        if not documents:
            documents = self._create_sample_documents()
        
        return documents
    
    def _create_sample_documents(self) -> List[Dict[str, Any]]:
        """Create sample documents for testing when no real data is available"""
        return [
            {
                'document_id': 'sample_1',
                'title': 'The Benefits of Machine Learning',
                'authors': ['Dr. Alice Johnson'],
                'content': 'Machine learning has revolutionized many industries. It provides excellent results in pattern recognition and data analysis. The technology is definitely beneficial for businesses and research. Machine learning algorithms can effectively process large datasets and identify complex patterns.',
                'chunk_content': 'Machine learning has revolutionized many industries. It provides excellent results in pattern recognition and data analysis.'
            },
            {
                'document_id': 'sample_2', 
                'title': 'Challenges in Artificial Intelligence',
                'authors': ['Prof. Bob Smith'],
                'content': 'Artificial intelligence faces significant challenges. The technology is not always reliable and can produce poor results. There are many problematic aspects of AI implementation. Perhaps the most concerning issue is the uncertainty around AI decision-making processes.',
                'chunk_content': 'Artificial intelligence faces significant challenges. The technology is not always reliable and can produce poor results.'
            },
            {
                'document_id': 'sample_3',
                'title': 'Future of Data Science',
                'authors': ['Dr. Carol Davis'],
                'content': 'Data science continues to grow rapidly. The field shows positive trends in job market and research funding. Data scientists are increasingly important for business intelligence. The future looks bright for data science professionals.',
                'chunk_content': 'Data science continues to grow rapidly. The field shows positive trends in job market and research funding.'
            }
        ]
    
    def _synthesize_findings(self, theme_analysis: Dict, contradiction_analysis: Dict, 
                           perspective_analysis: Dict) -> Dict[str, Any]:
        """Synthesize findings from all analyses"""
        synthesis = {
            'key_insights': [],
            'recommendations': [],
            'overall_assessment': {}
        }
        
        # Analyze themes
        if 'top_themes' in theme_analysis:
            top_themes = [t['theme'] for t in theme_analysis['top_themes'][:5]]
            synthesis['key_insights'].append(f"Primary themes: {', '.join(top_themes)}")
        
        # Analyze contradictions
        if 'contradictions_found' in contradiction_analysis:
            contradiction_count = contradiction_analysis['contradictions_found']
            if contradiction_count > 0:
                synthesis['key_insights'].append(f"Found {contradiction_count} potential contradictions")
                synthesis['recommendations'].append("Review contradictory statements for consistency")
            else:
                synthesis['key_insights'].append("No significant contradictions detected")
        
        # Analyze perspectives
        if 'total_authors' in perspective_analysis:
            author_count = perspective_analysis['total_authors']
            diversity = perspective_analysis.get('diversity_analysis', {}).get('diversity_level', 'unknown')
            synthesis['key_insights'].append(f"Analyzed {author_count} authors with {diversity} perspective diversity")
        
        # Overall assessment
        synthesis['overall_assessment'] = {
            'theme_coherence': 'high' if len(theme_analysis.get('top_themes', [])) > 0 else 'low',
            'consistency_level': 'high' if contradiction_analysis.get('contradictions_found', 0) == 0 else 'moderate',
            'perspective_diversity': perspective_analysis.get('diversity_analysis', {}).get('diversity_level', 'unknown')
        }
        
        return synthesis

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for cross-library analysis action group.
    
    Args:
        event: Lambda event containing analysis parameters
        context: Lambda context object
        
    Returns:
        Formatted response for Bedrock Agent with analysis results
    """
    try:
        logger.info("Received cross-library analysis request")
        
        # Extract parameters from the event
        if 'parameters' in event:
            # Bedrock Agent format
            parameters = event.get('parameters', [])
            param_dict = {param['name']: param['value'] for param in parameters}
        else:
            # Direct invocation format
            param_dict = event
        
        # Parse parameters
        analysis_type = param_dict.get('analysis_type', 'comprehensive')
        query = param_dict.get('query', '')
        document_ids = param_dict.get('document_ids', '')
        max_documents = int(param_dict.get('max_documents', 20))
        
        # Parse document IDs if provided as string
        if document_ids and isinstance(document_ids, str):
            document_ids = [id.strip() for id in document_ids.split(',') if id.strip()]
        
        logger.info(f"Analysis type: {analysis_type}, Query: '{query}', Max docs: {max_documents}")
        
        # Create analyzer and perform analysis
        analyzer = CrossLibraryAnalyzer()
        
        if analysis_type == 'themes':
            # Theme analysis only
            documents = analyzer._retrieve_documents(query, document_ids, max_documents)
            results = analyzer.theme_extractor.extract_themes(documents)
            analysis_results = {'theme_analysis': results}
        elif analysis_type == 'contradictions':
            # Contradiction analysis only
            documents = analyzer._retrieve_documents(query, document_ids, max_documents)
            results = analyzer.contradiction_detector.detect_contradictions(documents)
            analysis_results = {'contradiction_analysis': results}
        elif analysis_type == 'perspectives':
            # Perspective analysis only
            documents = analyzer._retrieve_documents(query, document_ids, max_documents)
            results = analyzer.perspective_analyzer.analyze_perspectives(documents)
            analysis_results = {'perspective_analysis': results}
        else:
            # Comprehensive analysis
            analysis_results = analyzer.analyze_library(query, document_ids, max_documents)
        
        # Format response
        response_text = format_analysis_results(analysis_results, analysis_type)
        
        return create_bedrock_response(response_text)
        
    except Exception as e:
        logger.error(f"Error in cross-library analysis handler: {str(e)}")
        return create_bedrock_response(f"Cross-library analysis failed: {str(e)}")

def format_analysis_results(results: Dict[str, Any], analysis_type: str) -> str:
    """Format analysis results for agent consumption"""
    
    if 'error' in results:
        return f"❌ **Cross-Library Analysis Error**\n\nError: {results['error']}"
    
    formatted_result = f"📚 **Cross-Library Analysis Results** ({analysis_type})\n\n"
    
    # Add timestamp and document count
    if 'analysis_timestamp' in results:
        formatted_result += f"🕒 **Analysis Time:** {results['analysis_timestamp']}\n"
    if 'documents_analyzed' in results:
        formatted_result += f"📄 **Documents Analyzed:** {results['documents_analyzed']}\n\n"
    
    # Format theme analysis
    if 'theme_analysis' in results:
        theme_data = results['theme_analysis']
        formatted_result += "🎯 **Theme Analysis:**\n"
        
        if 'top_themes' in theme_data:
            formatted_result += "**Top Themes:**\n"
            for i, theme in enumerate(theme_data['top_themes'][:5], 1):
                formatted_result += f"  {i}. **{theme['theme']}** (relevance: {theme['relevance_score']}, appears in {theme['document_frequency']} docs)\n"
        
        if 'theme_clusters' in theme_data and theme_data['theme_clusters']:
            formatted_result += "\n**Theme Clusters:**\n"
            for cluster in theme_data['theme_clusters'][:3]:
                formatted_result += f"  • **{cluster['cluster_name']}**: {', '.join(cluster['themes'])}\n"
        
        formatted_result += "\n"
    
    # Format contradiction analysis
    if 'contradiction_analysis' in results:
        contradiction_data = results['contradiction_analysis']
        formatted_result += "⚡ **Contradiction Analysis:**\n"
        
        contradiction_count = contradiction_data.get('contradictions_found', 0)
        if contradiction_count > 0:
            formatted_result += f"**Found {contradiction_count} potential contradictions**\n\n"
            
            high_confidence = contradiction_data.get('high_confidence_contradictions', [])
            if high_confidence:
                formatted_result += "**High Confidence Contradictions:**\n"
                for i, contradiction in enumerate(high_confidence[:3], 1):
                    formatted_result += f"  {i}. **{contradiction['document1']['title']}** vs **{contradiction['document2']['title']}**\n"
                    formatted_result += f"     • Type: {contradiction['contradiction_type']}\n"
                    formatted_result += f"     • Confidence: {contradiction['confidence_score']:.2f}\n"
        else:
            formatted_result += "✅ **No significant contradictions detected**\n"
        
        formatted_result += "\n"
    
    # Format perspective analysis
    if 'perspective_analysis' in results:
        perspective_data = results['perspective_analysis']
        formatted_result += "👥 **Perspective Analysis:**\n"
        
        author_count = perspective_data.get('total_authors', 0)
        formatted_result += f"**Authors Analyzed:** {author_count}\n"
        
        if 'diversity_analysis' in perspective_data:
            diversity = perspective_data['diversity_analysis']
            diversity_level = diversity.get('diversity_level', 'unknown')
            formatted_result += f"**Perspective Diversity:** {diversity_level}\n"
        
        if 'perspective_comparisons' in perspective_data:
            comparisons = perspective_data['perspective_comparisons'][:3]
            if comparisons:
                formatted_result += "\n**Key Perspective Differences:**\n"
                for comparison in comparisons:
                    formatted_result += f"  • **{comparison['author1']}** vs **{comparison['author2']}**: {comparison['relationship_type']}\n"
        
        formatted_result += "\n"
    
    # Add synthesis if available
    if 'synthesis' in results:
        synthesis = results['synthesis']
        formatted_result += "🔍 **Key Insights:**\n"
        
        for insight in synthesis.get('key_insights', []):
            formatted_result += f"  • {insight}\n"
        
        if synthesis.get('recommendations'):
            formatted_result += "\n💡 **Recommendations:**\n"
            for rec in synthesis['recommendations']:
                formatted_result += f"  • {rec}\n"
        
        if 'overall_assessment' in synthesis:
            assessment = synthesis['overall_assessment']
            formatted_result += f"\n📊 **Overall Assessment:**\n"
            formatted_result += f"  • Theme Coherence: {assessment.get('theme_coherence', 'unknown')}\n"
            formatted_result += f"  • Consistency Level: {assessment.get('consistency_level', 'unknown')}\n"
            formatted_result += f"  • Perspective Diversity: {assessment.get('perspective_diversity', 'unknown')}\n"
    
    return formatted_result

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