"""
Unit tests for shared utility functions
"""

import pytest
import json
from datetime import datetime
from src.shared.utils import (
    generate_id,
    hash_content,
    chunk_text,
    format_timestamp,
    safe_json_loads,
    safe_json_dumps,
    create_bedrock_response
)

class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_generate_id(self):
        """Test ID generation."""
        # Test without prefix
        id1 = generate_id()
        assert len(id1) == 36  # UUID4 length
        
        # Test with prefix
        id2 = generate_id("test-")
        assert id2.startswith("test-")
        assert len(id2) == 41  # prefix + UUID4 length
        
        # Test uniqueness
        id3 = generate_id()
        assert id1 != id3
    
    def test_hash_content(self):
        """Test content hashing."""
        content1 = "This is test content"
        content2 = "This is test content"
        content3 = "This is different content"
        
        hash1 = hash_content(content1)
        hash2 = hash_content(content2)
        hash3 = hash_content(content3)
        
        # Same content should produce same hash
        assert hash1 == hash2
        
        # Different content should produce different hash
        assert hash1 != hash3
        
        # Hash should be 64 characters (SHA-256)
        assert len(hash1) == 64
    
    def test_chunk_text_small(self):
        """Test text chunking with small text."""
        text = "This is a small text."
        chunks = chunk_text(text, chunk_size=100)
        
        assert len(chunks) == 1
        assert chunks[0]['content'] == text
        assert chunks[0]['start_position'] == 0
        assert chunks[0]['end_position'] == len(text)
    
    def test_chunk_text_large(self):
        """Test text chunking with large text."""
        text = "This is a sentence. " * 100  # Create long text
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        
        assert len(chunks) > 1
        
        # Check that chunks have proper structure
        for chunk in chunks:
            assert 'content' in chunk
            assert 'start_position' in chunk
            assert 'end_position' in chunk
            assert 'chunk_index' in chunk
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2024, 1, 1, 12, 30, 45)
        formatted = format_timestamp(dt)
        
        assert formatted == "2024-01-01 12:30:45 UTC"
    
    def test_safe_json_loads_valid(self):
        """Test safe JSON loading with valid JSON."""
        json_str = '{"key": "value", "number": 42}'
        result = safe_json_loads(json_str)
        
        assert result == {"key": "value", "number": 42}
    
    def test_safe_json_loads_invalid(self):
        """Test safe JSON loading with invalid JSON."""
        json_str = '{"key": "value", invalid}'
        default_value = {"default": True}
        result = safe_json_loads(json_str, default_value)
        
        assert result == default_value
    
    def test_safe_json_dumps_valid(self):
        """Test safe JSON dumping with valid object."""
        obj = {"key": "value", "number": 42}
        result = safe_json_dumps(obj)
        
        parsed = json.loads(result)
        assert parsed == obj
    
    def test_create_bedrock_response(self):
        """Test Bedrock response creation."""
        response_text = "This is a test response"
        response = create_bedrock_response(response_text)
        
        expected_structure = {
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
        
        assert response == expected_structure