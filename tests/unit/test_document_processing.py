"""
Unit tests for document processing and embedding pipeline
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from src.shared.utils import (
    extract_text_from_file,
    chunk_text,
    chunk_text_semantic,
    generate_embeddings,
    generate_embedding_batch,
    process_document_for_embedding,
    process_text_for_embedding,
    validate_embedding_vector,
    calculate_embedding_similarity,
    _clean_extracted_text,
    _find_optimal_break_point
)


class TestTextExtraction:
    """Test cases for text extraction from various file formats."""
    
    def test_extract_text_from_txt_file(self):
        """Test text extraction from TXT file."""
        # Create a temporary TXT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_content = "This is a test document.\nIt has multiple lines.\nAnd some content."
            f.write(test_content)
            temp_path = f.name
        
        try:
            extracted_text = extract_text_from_file(temp_path, 'txt')
            assert extracted_text.strip() == test_content.strip()
        finally:
            os.unlink(temp_path)
    
    def test_extract_text_file_not_found(self):
        """Test text extraction with non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_text_from_file('/nonexistent/file.txt', 'txt')
    
    def test_extract_text_unsupported_format(self):
        """Test text extraction with unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                extract_text_from_file(temp_path, 'xyz')
        finally:
            os.unlink(temp_path)
    
    def test_extract_text_from_html_file(self):
        """Test text extraction from HTML file."""
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Test Document</h1>
            <p>This is a paragraph with <strong>bold</strong> text.</p>
            <script>console.log('script');</script>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = f.name
        
        try:
            extracted_text = extract_text_from_file(temp_path, 'html')
            assert 'Test Document' in extracted_text
            assert 'This is a paragraph with bold text.' in extracted_text
            assert 'script' not in extracted_text  # Script should be removed
        finally:
            os.unlink(temp_path)
    
    def test_extract_text_from_markdown_file(self):
        """Test text extraction from Markdown file."""
        markdown_content = """
# Test Document

This is a **bold** text and *italic* text.

## Section 2

- List item 1
- List item 2

```python
print("code block")
```

[Link text](http://example.com)
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(markdown_content)
            temp_path = f.name
        
        try:
            extracted_text = extract_text_from_file(temp_path, 'md')
            assert 'Test Document' in extracted_text
            assert 'bold' in extracted_text
            assert 'italic' in extracted_text
            assert 'Link text' in extracted_text
        finally:
            os.unlink(temp_path)
    
    def test_clean_extracted_text(self):
        """Test text cleaning function."""
        dirty_text = "  This   is   a\n\n\n\ntest   document  \n\n  with   extra   whitespace  "
        cleaned = _clean_extracted_text(dirty_text)
        
        assert cleaned == "This is a\n\ntest document\n\nwith extra whitespace"
    
    def test_clean_extracted_text_empty(self):
        """Test text cleaning with empty input."""
        assert _clean_extracted_text("") == ""
        assert _clean_extracted_text("   ") == ""


class TestTextChunking:
    """Test cases for text chunking algorithms."""
    
    def test_chunk_text_small_text(self):
        """Test chunking with text smaller than chunk size."""
        text = "This is a small text."
        chunks = chunk_text(text, chunk_size=100)
        
        assert len(chunks) == 1
        assert chunks[0]['content'] == text
        assert chunks[0]['start_position'] == 0
        assert chunks[0]['end_position'] == len(text)
        assert chunks[0]['chunk_index'] == 0
    
    def test_chunk_text_large_text(self):
        """Test chunking with text larger than chunk size."""
        text = "This is a sentence. " * 100  # Create long text
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        
        assert len(chunks) > 1
        
        # Check chunk structure
        for i, chunk in enumerate(chunks):
            assert 'content' in chunk
            assert 'start_position' in chunk
            assert 'end_position' in chunk
            assert 'chunk_index' in chunk
            assert chunk['chunk_index'] == i
            assert len(chunk['content']) <= 100 + 50  # Allow some flexibility for sentence boundaries
    
    def test_chunk_text_with_paragraphs(self):
        """Test chunking with paragraph preservation."""
        text = "First paragraph.\n\nSecond paragraph with more content.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=50, preserve_paragraphs=True)
        
        assert len(chunks) > 1
        
        # Check that paragraph boundaries are respected when possible
        for chunk in chunks:
            assert chunk['content'].strip()  # No empty chunks
    
    def test_chunk_text_empty_input(self):
        """Test chunking with empty input."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []
    
    def test_chunk_text_semantic(self):
        """Test semantic chunking algorithm."""
        text = """First paragraph with some content.

Second paragraph with different content.

Third paragraph with more information.

Fourth paragraph to test chunking."""
        
        chunks = chunk_text_semantic(text, max_chunk_size=100, min_chunk_size=20)
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert 'content' in chunk
            assert 'semantic_type' in chunk
            assert len(chunk['content']) >= 20 or chunk == chunks[-1]  # Last chunk can be smaller
    
    def test_find_optimal_break_point(self):
        """Test optimal break point finding."""
        text = "This is a sentence. This is another sentence.\n\nThis is a new paragraph."
        
        # Test sentence boundary detection
        break_point = _find_optimal_break_point(text, 0, 30, True, True)
        assert break_point <= 30
        
        # Test paragraph boundary detection
        break_point = _find_optimal_break_point(text, 0, 50, True, True)
        assert break_point <= 50


class TestEmbeddingGeneration:
    """Test cases for embedding generation."""
    
    @patch('src.shared.utils.get_aws_client')
    def test_generate_embeddings_success(self, mock_get_client):
        """Test successful embedding generation."""
        # Mock Bedrock client
        mock_client = Mock()
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = '{"embedding": [0.1, 0.2, 0.3]}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        texts = ["Test text 1", "Test text 2"]
        embeddings = generate_embeddings(texts)
        
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.1, 0.2, 0.3]
    
    @patch('src.shared.utils.get_aws_client')
    def test_generate_embeddings_empty_text(self, mock_get_client):
        """Test embedding generation with empty text."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        texts = ["", "  ", "Valid text"]
        
        # Mock response for valid text
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = '{"embedding": [0.1, 0.2, 0.3]}'
        mock_client.invoke_model.return_value = mock_response
        
        embeddings = generate_embeddings(texts)
        
        assert len(embeddings) == 3
        assert embeddings[0] == [0.0] * 1536  # Zero vector for empty text
        assert embeddings[1] == [0.0] * 1536  # Zero vector for whitespace
        assert embeddings[2] == [0.1, 0.2, 0.3]  # Real embedding for valid text
    
    @patch('src.shared.utils.generate_embeddings')
    def test_generate_embedding_batch(self, mock_generate):
        """Test batch embedding generation."""
        mock_generate.side_effect = [
            [[0.1, 0.2], [0.3, 0.4]],  # First batch
            [[0.5, 0.6]]  # Second batch
        ]
        
        texts = ["text1", "text2", "text3"]
        embeddings = generate_embedding_batch(texts, batch_size=2)
        
        assert len(embeddings) == 3
        assert embeddings == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]


class TestDocumentProcessing:
    """Test cases for complete document processing pipeline."""
    
    @patch('src.shared.utils.generate_embedding_batch')
    @patch('src.shared.utils.extract_text_from_file')
    def test_process_document_for_embedding(self, mock_extract, mock_embed):
        """Test complete document processing pipeline."""
        # Mock text extraction
        mock_extract.return_value = "This is test content. " * 50  # Long enough to chunk
        
        # Mock embedding generation
        mock_embed.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            chunks = process_document_for_embedding(f.name, "doc-123", chunk_size=100, overlap=20)
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert 'chunk_id' in chunk
            assert 'document_id' in chunk
            assert 'content' in chunk
            assert 'embedding' in chunk
            assert chunk['document_id'] == "doc-123"
            assert chunk['chunk_id'].startswith("doc-123_chunk_")
    
    @patch('src.shared.utils.generate_embedding_batch')
    def test_process_text_for_embedding(self, mock_embed):
        """Test text processing for embedding."""
        # Mock embedding generation
        mock_embed.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        
        text = "This is test content. " * 50  # Long enough to chunk
        chunks = process_text_for_embedding(text, "doc-456", chunk_size=100, overlap=20)
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert 'chunk_id' in chunk
            assert 'document_id' in chunk
            assert 'content' in chunk
            assert 'embedding' in chunk
            assert chunk['document_id'] == "doc-456"
    
    def test_process_text_for_embedding_empty(self):
        """Test text processing with empty input."""
        chunks = process_text_for_embedding("", "doc-789")
        assert chunks == []
        
        chunks = process_text_for_embedding("   ", "doc-789")
        assert chunks == []


class TestEmbeddingUtilities:
    """Test cases for embedding utility functions."""
    
    def test_validate_embedding_vector_valid(self):
        """Test embedding vector validation with valid input."""
        embedding = [0.1, 0.2, 0.3] + [0.0] * 1533  # 1536 dimensions
        assert validate_embedding_vector(embedding) is True
    
    def test_validate_embedding_vector_invalid_dimension(self):
        """Test embedding vector validation with wrong dimension."""
        embedding = [0.1, 0.2, 0.3]  # Wrong dimension
        assert validate_embedding_vector(embedding) is False
    
    def test_validate_embedding_vector_invalid_type(self):
        """Test embedding vector validation with invalid types."""
        embedding = ["0.1", "0.2"] + [0.0] * 1534  # String values
        assert validate_embedding_vector(embedding) is False
    
    def test_validate_embedding_vector_nan_values(self):
        """Test embedding vector validation with NaN values."""
        import math
        embedding = [0.1, math.nan, 0.3] + [0.0] * 1533
        assert validate_embedding_vector(embedding) is False
    
    def test_calculate_embedding_similarity(self):
        """Test cosine similarity calculation."""
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]
        
        similarity = calculate_embedding_similarity(embedding1, embedding2)
        assert abs(similarity - 1.0) < 1e-6  # Should be 1.0 (identical)
        
        embedding3 = [-1.0, 0.0, 0.0]
        similarity = calculate_embedding_similarity(embedding1, embedding3)
        assert abs(similarity - (-1.0)) < 1e-6  # Should be -1.0 (opposite)
        
        embedding4 = [0.0, 1.0, 0.0]
        similarity = calculate_embedding_similarity(embedding1, embedding4)
        assert abs(similarity - 0.0) < 1e-6  # Should be 0.0 (orthogonal)
    
    def test_calculate_embedding_similarity_different_dimensions(self):
        """Test similarity calculation with different dimensions."""
        embedding1 = [1.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]
        
        with pytest.raises(ValueError, match="Embeddings must have the same dimension"):
            calculate_embedding_similarity(embedding1, embedding2)
    
    def test_calculate_embedding_similarity_zero_vectors(self):
        """Test similarity calculation with zero vectors."""
        embedding1 = [0.0, 0.0, 0.0]
        embedding2 = [1.0, 0.0, 0.0]
        
        similarity = calculate_embedding_similarity(embedding1, embedding2)
        assert similarity == 0.0


class TestIntegration:
    """Integration tests for document processing pipeline."""
    
    def test_full_pipeline_with_sample_document(self):
        """Test the complete pipeline with a sample document."""
        # Create a sample document
        sample_text = """
        Introduction to Machine Learning
        
        Machine learning is a subset of artificial intelligence that focuses on algorithms
        that can learn from and make predictions on data. It has applications in many fields
        including computer vision, natural language processing, and robotics.
        
        Types of Machine Learning
        
        There are three main types of machine learning:
        1. Supervised learning
        2. Unsupervised learning  
        3. Reinforcement learning
        
        Each type has its own characteristics and use cases.
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_text)
            temp_path = f.name
        
        try:
            # Test text extraction
            extracted_text = extract_text_from_file(temp_path, 'txt')
            assert 'Machine learning' in extracted_text
            
            # Test chunking
            chunks = chunk_text(extracted_text, chunk_size=200, overlap=50)
            assert len(chunks) > 1
            
            # Verify chunk content
            all_content = ' '.join(chunk['content'] for chunk in chunks)
            assert 'Machine learning' in all_content
            assert 'Supervised learning' in all_content
            
        finally:
            os.unlink(temp_path)


class TestRealDocumentProcessing:
    """Integration tests with real sample documents."""
    
    def test_process_ai_research_paper(self):
        """Test processing of AI research paper."""
        sample_path = "tests/sample_documents/ai_research_paper.txt"
        
        if not os.path.exists(sample_path):
            pytest.skip("Sample document not found")
        
        # Test text extraction
        extracted_text = extract_text_from_file(sample_path, 'txt')
        
        assert 'Artificial Intelligence' in extracted_text
        assert 'Machine Learning' in extracted_text
        assert 'Deep Learning' in extracted_text
        assert len(extracted_text) > 1000  # Should be substantial content
        
        # Test chunking
        chunks = chunk_text(extracted_text, chunk_size=500, overlap=100)
        
        assert len(chunks) > 5  # Should create multiple chunks
        
        # Verify chunks have proper structure
        for chunk in chunks:
            assert len(chunk['content']) <= 600  # Allow some flexibility
            assert chunk['word_count'] > 0
            assert chunk['char_count'] > 0
        
        # Test semantic chunking
        semantic_chunks = chunk_text_semantic(extracted_text, max_chunk_size=800, min_chunk_size=200)
        
        assert len(semantic_chunks) > 0
        
        # Semantic chunks should generally be larger and better structured
        for chunk in semantic_chunks:
            assert len(chunk['content']) >= 200 or chunk == semantic_chunks[-1]
    
    def test_process_markdown_guide(self):
        """Test processing of Markdown guide."""
        sample_path = "tests/sample_documents/machine_learning_guide.md"
        
        if not os.path.exists(sample_path):
            pytest.skip("Sample document not found")
        
        # Test text extraction
        extracted_text = extract_text_from_file(sample_path, 'md')
        
        assert 'Machine Learning' in extracted_text
        assert 'Supervised Learning' in extracted_text
        assert 'Unsupervised Learning' in extracted_text
        assert 'Reinforcement Learning' in extracted_text
        
        # Should have cleaned up markdown syntax
        assert '##' not in extracted_text  # Headers should be cleaned
        assert '**' not in extracted_text  # Bold syntax should be cleaned
        
        # Test chunking with paragraph preservation
        chunks = chunk_text(extracted_text, chunk_size=600, overlap=100, preserve_paragraphs=True)
        
        assert len(chunks) > 3
        
        # Check that chunks maintain readability
        for chunk in chunks:
            # Chunks should not start or end mid-sentence when possible
            content = chunk['content'].strip()
            assert len(content) > 50  # Reasonable minimum size
    
    @patch('src.shared.utils.generate_embedding_batch')
    def test_full_pipeline_with_real_document(self, mock_embed):
        """Test complete pipeline with real document."""
        sample_path = "tests/sample_documents/ai_research_paper.txt"
        
        if not os.path.exists(sample_path):
            pytest.skip("Sample document not found")
        
        # Mock embedding generation to return realistic vectors
        def mock_embedding_generator(texts):
            return [[0.1 * i] * 1536 for i in range(len(texts))]
        
        mock_embed.side_effect = mock_embedding_generator
        
        # Process the document
        chunks = process_document_for_embedding(
            sample_path, 
            "ai-research-001", 
            chunk_size=400, 
            overlap=80
        )
        
        assert len(chunks) > 5  # Should create multiple chunks
        
        # Verify all chunks have embeddings
        for chunk in chunks:
            assert 'embedding' in chunk
            assert len(chunk['embedding']) == 1536
            assert chunk['document_id'] == "ai-research-001"
            assert chunk['chunk_id'].startswith("ai-research-001_chunk_")
            assert chunk['file_type'] == 'txt'
            assert chunk['embedding_model'] == 'amazon.titan-embed-text-v1'
        
        # Verify content coverage
        all_content = ' '.join(chunk['content'] for chunk in chunks)
        assert 'Artificial Intelligence' in all_content
        assert 'Machine Learning' in all_content
    
    def test_embedding_similarity_with_related_content(self):
        """Test embedding similarity calculation with related content."""
        # Create two similar text chunks
        text1 = "Machine learning is a subset of artificial intelligence that focuses on algorithms."
        text2 = "Artificial intelligence includes machine learning algorithms and techniques."
        
        # Create two different text chunks  
        text3 = "The weather today is sunny and warm with clear skies."
        
        chunks1 = chunk_text(text1, chunk_size=100)
        chunks2 = chunk_text(text2, chunk_size=100)
        chunks3 = chunk_text(text3, chunk_size=100)
        
        # Create mock embeddings (similar for related content, different for unrelated)
        embedding1 = [0.8, 0.6, 0.2] + [0.0] * 1533
        embedding2 = [0.7, 0.5, 0.3] + [0.0] * 1533  # Similar to embedding1
        embedding3 = [0.1, 0.2, 0.9] + [0.0] * 1533  # Different from embedding1
        
        # Test similarity calculations
        similarity_related = calculate_embedding_similarity(embedding1, embedding2)
        similarity_unrelated = calculate_embedding_similarity(embedding1, embedding3)
        
        # Related content should have higher similarity
        assert similarity_related > similarity_unrelated
        assert similarity_related > 0.5  # Should be reasonably similar
        assert -1.0 <= similarity_related <= 1.0
        assert -1.0 <= similarity_unrelated <= 1.0