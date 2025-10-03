"""
Integration tests for OpenSearch document indexing and retrieval.
Tests the complete pipeline from document processing to search.
"""

import pytest
import boto3
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any
import sys
sys.path.append('src/shared')
from models import Document, DocumentChunk
from utils import generate_embeddings, chunk_text, generate_id

# Test configuration
TEST_INDEX_NAME = "test-agent-scholar-documents"
TEST_OPENSEARCH_ENDPOINT = os.getenv('TEST_OPENSEARCH_ENDPOINT')
TEST_REGION = os.getenv('AWS_REGION', 'us-east-1')

@pytest.fixture(scope="module")
def opensearch_client():
    """Create OpenSearch client for testing"""
    if not TEST_OPENSEARCH_ENDPOINT:
        pytest.skip("TEST_OPENSEARCH_ENDPOINT not configured")
    
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from aws_requests_auth.aws_auth import AWSRequestsAuth
    
    credentials = boto3.Session().get_credentials()
    awsauth = AWSRequestsAuth(credentials, TEST_REGION, 'aoss')
    
    client = OpenSearch(
        hosts=[{'host': TEST_OPENSEARCH_ENDPOINT.replace('https://', ''), 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60
    )
    
    return client

@pytest.fixture(scope="module")
def bedrock_client():
    """Create Bedrock client for testing"""
    return boto3.client('bedrock-runtime', region_name=TEST_REGION)

@pytest.fixture(scope="module")
def test_documents():
    """Create test documents for indexing"""
    documents = []
    
    # Document 1: AI Research Paper
    doc1_content = """
    Artificial Intelligence and Machine Learning: A Comprehensive Overview
    
    Abstract:
    This paper provides a comprehensive overview of artificial intelligence and machine learning
    technologies, their applications, and future directions. We examine various algorithms,
    methodologies, and real-world implementations.
    
    Introduction:
    Artificial Intelligence (AI) has emerged as one of the most transformative technologies
    of the 21st century. Machine learning, a subset of AI, enables systems to automatically
    learn and improve from experience without being explicitly programmed.
    
    Deep Learning:
    Deep learning represents a significant advancement in machine learning, utilizing neural
    networks with multiple layers to model and understand complex patterns in data.
    """
    
    doc1 = Document(
        id=generate_id(),
        title="Artificial Intelligence and Machine Learning: A Comprehensive Overview",
        authors=["Dr. Jane Smith", "Prof. John Doe"],
        publication_date=datetime(2023, 6, 15),
        content=doc1_content,
        chunks=[],
        metadata={
            "journal": "AI Research Quarterly",
            "doi": "10.1000/test.doi.123",
            "keywords": ["artificial intelligence", "machine learning", "deep learning"]
        },
        embedding_version="titan-text-v1"
    )
    
    # Document 2: Climate Change Study
    doc2_content = """
    Climate Change Impacts on Global Ecosystems
    
    Executive Summary:
    This study examines the far-reaching impacts of climate change on global ecosystems,
    including biodiversity loss, habitat destruction, and species migration patterns.
    
    Methodology:
    We analyzed climate data from 1950 to 2023, examining temperature trends, precipitation
    patterns, and their correlation with ecosystem changes across different biomes.
    
    Findings:
    Our research indicates significant shifts in species distribution, with many species
    migrating toward polar regions as temperatures rise. Ocean acidification has also
    severely impacted marine ecosystems.
    """
    
    doc2 = Document(
        id=generate_id(),
        title="Climate Change Impacts on Global Ecosystems",
        authors=["Dr. Maria Garcia", "Dr. Robert Chen"],
        publication_date=datetime(2023, 8, 22),
        content=doc2_content,
        chunks=[],
        metadata={
            "journal": "Environmental Science Today",
            "doi": "10.1000/test.doi.456",
            "keywords": ["climate change", "ecosystems", "biodiversity"]
        },
        embedding_version="titan-text-v1"
    )
    
    documents.append(doc1)
    documents.append(doc2)
    
    return documents

@pytest.fixture(scope="module")
def processed_documents(test_documents, bedrock_client):
    """Process test documents with chunks and embeddings"""
    processed = []
    
    for doc in test_documents:
        # Create chunks
        chunks = chunk_text(doc.content, chunk_size=500, overlap=100, document_id=doc.id)
        
        # Generate embeddings
        chunk_texts = [chunk.content for chunk in chunks]
        embeddings = generate_embeddings(chunk_texts, bedrock_client)
        
        # Add embeddings to chunks
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]
        
        doc.chunks = chunks
        processed.append(doc)
    
    return processed

class TestOpenSearchIntegration:
    """Integration tests for OpenSearch document operations"""
    
    def test_index_creation(self, opensearch_client):
        """Test creating the document index"""
        # Delete index if it exists
        if opensearch_client.indices.exists(index=TEST_INDEX_NAME):
            opensearch_client.indices.delete(index=TEST_INDEX_NAME)
        
        # Create index with proper mapping
        index_mapping = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100
                }
            },
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "authors": {"type": "keyword"},
                    "publication_date": {"type": "date"},
                    "content": {"type": "text"},
                    "chunk_content": {"type": "text"},
                    "start_position": {"type": "integer"},
                    "end_position": {"type": "integer"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1536,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "metadata": {"type": "object"},
                    "created_at": {"type": "date"},
                    "embedding_version": {"type": "keyword"}
                }
            }
        }
        
        response = opensearch_client.indices.create(
            index=TEST_INDEX_NAME,
            body=index_mapping
        )
        
        assert response['acknowledged'] == True
        assert opensearch_client.indices.exists(index=TEST_INDEX_NAME)
    
    def test_document_indexing(self, opensearch_client, processed_documents):
        """Test indexing documents with chunks"""
        indexed_chunks = []
        
        for document in processed_documents:
            for chunk in document.chunks:
                doc_body = {
                    "document_id": document.id,
                    "chunk_id": chunk.chunk_id,
                    "title": document.title,
                    "authors": document.authors,
                    "publication_date": document.publication_date.isoformat(),
                    "content": document.content,
                    "chunk_content": chunk.content,
                    "start_position": chunk.start_position,
                    "end_position": chunk.end_position,
                    "embedding": chunk.embedding,
                    "metadata": document.metadata,
                    "created_at": datetime.now().isoformat(),
                    "embedding_version": document.embedding_version
                }
                
                response = opensearch_client.index(
                    index=TEST_INDEX_NAME,
                    id=chunk.chunk_id,
                    body=doc_body
                )
                
                assert response['result'] in ['created', 'updated']
                indexed_chunks.append(chunk.chunk_id)
        
        # Wait for indexing to complete
        time.sleep(2)
        
        # Verify documents are indexed
        opensearch_client.indices.refresh(index=TEST_INDEX_NAME)
        
        # Check total document count
        count_response = opensearch_client.count(index=TEST_INDEX_NAME)
        assert count_response['count'] == len(indexed_chunks)
    
    def test_vector_search(self, opensearch_client, bedrock_client):
        """Test vector similarity search"""
        # Generate query embedding
        query_text = "machine learning algorithms and neural networks"
        query_embeddings = generate_embeddings([query_text], bedrock_client)
        query_embedding = query_embeddings[0]
        
        # Perform vector search
        search_body = {
            "size": 5,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": 5
                    }
                }
            },
            "_source": {
                "excludes": ["embedding"]
            }
        }
        
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        hits = response['hits']['hits']
        assert len(hits) > 0
        
        # Verify results are relevant (should find AI document)
        ai_related_found = False
        for hit in hits:
            source = hit['_source']
            if 'artificial intelligence' in source['chunk_content'].lower() or \
               'machine learning' in source['chunk_content'].lower():
                ai_related_found = True
                break
        
        assert ai_related_found, "Vector search should find AI-related content"
    
    def test_hybrid_search(self, opensearch_client, bedrock_client):
        """Test hybrid search combining vector and keyword search"""
        # Generate query embedding
        query_text = "climate change ecosystems"
        query_embeddings = generate_embeddings([query_text], bedrock_client)
        query_embedding = query_embeddings[0]
        
        # Perform hybrid search
        search_body = {
            "size": 5,
            "query": {
                "bool": {
                    "should": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_embedding,
                                    "k": 3
                                }
                            }
                        },
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["title", "chunk_content"],
                                "boost": 0.5
                            }
                        }
                    ]
                }
            },
            "_source": {
                "excludes": ["embedding"]
            }
        }
        
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        hits = response['hits']['hits']
        assert len(hits) > 0
        
        # Verify climate-related content is found
        climate_related_found = False
        for hit in hits:
            source = hit['_source']
            if 'climate' in source['chunk_content'].lower() or \
               'ecosystem' in source['chunk_content'].lower():
                climate_related_found = True
                break
        
        assert climate_related_found, "Hybrid search should find climate-related content"
    
    def test_filtered_search(self, opensearch_client, bedrock_client):
        """Test search with metadata filters"""
        # Search with author filter
        search_body = {
            "size": 10,
            "query": {
                "bool": {
                    "must": [
                        {"match_all": {}}
                    ],
                    "filter": [
                        {"term": {"authors": "Dr. Jane Smith"}}
                    ]
                }
            },
            "_source": {
                "excludes": ["embedding"]
            }
        }
        
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        hits = response['hits']['hits']
        assert len(hits) > 0
        
        # Verify all results have the correct author
        for hit in hits:
            source = hit['_source']
            assert "Dr. Jane Smith" in source['authors']
    
    def test_document_deletion(self, opensearch_client, processed_documents):
        """Test deleting documents and their chunks"""
        # Get a document to delete
        document_to_delete = processed_documents[0]
        
        # Search for all chunks of this document
        search_body = {
            "query": {
                "term": {"document_id": document_to_delete.id}
            },
            "size": 1000
        }
        
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        chunks_before = len(response['hits']['hits'])
        assert chunks_before > 0
        
        # Delete all chunks
        for hit in response['hits']['hits']:
            chunk_id = hit['_id']
            delete_response = opensearch_client.delete(
                index=TEST_INDEX_NAME,
                id=chunk_id
            )
            assert delete_response['result'] == 'deleted'
        
        # Wait for deletion to complete
        time.sleep(1)
        opensearch_client.indices.refresh(index=TEST_INDEX_NAME)
        
        # Verify chunks are deleted
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        chunks_after = len(response['hits']['hits'])
        assert chunks_after == 0
    
    def test_performance_benchmarks(self, opensearch_client, bedrock_client):
        """Test search performance benchmarks"""
        import time
        
        query_text = "artificial intelligence machine learning"
        query_embeddings = generate_embeddings([query_text], bedrock_client)
        query_embedding = query_embeddings[0]
        
        # Benchmark vector search
        start_time = time.time()
        
        search_body = {
            "size": 10,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": 10
                    }
                }
            }
        }
        
        response = opensearch_client.search(
            index=TEST_INDEX_NAME,
            body=search_body
        )
        
        search_time = time.time() - start_time
        
        assert search_time < 2.0, f"Vector search took {search_time:.2f}s, should be under 2s"
        assert len(response['hits']['hits']) > 0
        
        print(f"Vector search completed in {search_time:.3f} seconds")

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_index(opensearch_client):
    """Clean up test index after all tests"""
    yield
    
    # Clean up after tests
    try:
        if opensearch_client.indices.exists(index=TEST_INDEX_NAME):
            opensearch_client.indices.delete(index=TEST_INDEX_NAME)
            print(f"Cleaned up test index: {TEST_INDEX_NAME}")
    except Exception as e:
        print(f"Error cleaning up test index: {e}")

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])