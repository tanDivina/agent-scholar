import json
import boto3
import os
import logging
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth
import sys
sys.path.append('/opt/python')
from shared.models import Document, DocumentChunk
from shared.utils import generate_embeddings, chunk_text, extract_text_from_file

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class DocumentIndexer:
    def __init__(self):
        self.opensearch_endpoint = os.environ['OPENSEARCH_ENDPOINT']
        self.index_name = os.environ['INDEX_NAME']
        self.region = os.environ['AWS_REGION']
        
        # Initialize OpenSearch client
        credentials = boto3.Session().get_credentials()
        awsauth = AWSRequestsAuth(credentials, self.region, 'aoss')
        
        self.opensearch_client = OpenSearch(
            hosts=[{'host': self.opensearch_endpoint.replace('https://', ''), 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60
        )
        
        # Initialize Bedrock client for embeddings
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=self.region)
        
        # Ensure index exists
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """Create the vector index if it doesn't exist"""
        try:
            if not self.opensearch_client.indices.exists(index=self.index_name):
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
                                "dimension": 1536,  # Titan Text Embeddings dimension
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
                
                self.opensearch_client.indices.create(
                    index=self.index_name,
                    body=index_mapping
                )
                logger.info(f"Created index: {self.index_name}")
            else:
                logger.info(f"Index {self.index_name} already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring index exists: {str(e)}")
            raise
    
    def index_document(self, document: Document) -> Dict[str, Any]:
        """Index a single document with all its chunks"""
        try:
            indexed_chunks = []
            
            for chunk in document.chunks:
                # Prepare document for indexing
                doc_body = {
                    "document_id": document.id,
                    "chunk_id": chunk.chunk_id,
                    "title": document.title,
                    "authors": document.authors,
                    "publication_date": document.publication_date.isoformat() if document.publication_date else None,
                    "content": document.content,
                    "chunk_content": chunk.content,
                    "start_position": chunk.start_position,
                    "end_position": chunk.end_position,
                    "embedding": chunk.embedding,
                    "metadata": document.metadata,
                    "created_at": "now",
                    "embedding_version": document.embedding_version
                }
                
                # Index the chunk
                response = self.opensearch_client.index(
                    index=self.index_name,
                    id=chunk.chunk_id,
                    body=doc_body
                )
                
                indexed_chunks.append({
                    "chunk_id": chunk.chunk_id,
                    "status": "indexed",
                    "opensearch_response": response
                })
            
            logger.info(f"Successfully indexed document {document.id} with {len(indexed_chunks)} chunks")
            
            return {
                "document_id": document.id,
                "status": "success",
                "chunks_indexed": len(indexed_chunks),
                "chunks": indexed_chunks
            }
            
        except Exception as e:
            logger.error(f"Error indexing document {document.id}: {str(e)}")
            return {
                "document_id": document.id,
                "status": "error",
                "error": str(e)
            }
    
    def batch_index_documents(self, documents: List[Document]) -> Dict[str, Any]:
        """Index multiple documents in batch"""
        results = {
            "total_documents": len(documents),
            "successful": 0,
            "failed": 0,
            "results": []
        }
        
        for document in documents:
            result = self.index_document(document)
            results["results"].append(result)
            
            if result["status"] == "success":
                results["successful"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"Batch indexing completed: {results['successful']} successful, {results['failed']} failed")
        return results
    
    def search_documents(self, 
                        query_text: str = None,
                        query_embedding: List[float] = None,
                        size: int = 10,
                        min_score: float = 0.7,
                        filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search documents using vector similarity and optional filters"""
        try:
            # Build the search query
            search_body = {
                "size": size,
                "_source": {
                    "excludes": ["embedding"]  # Don't return embeddings in results
                }
            }
            
            # If we have a query embedding, use vector search
            if query_embedding:
                search_body["query"] = {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": size
                        }
                    }
                }
            # If we have query text but no embedding, generate embedding first
            elif query_text:
                query_embedding = generate_embeddings([query_text], self.bedrock_client)[0]
                search_body["query"] = {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": size
                        }
                    }
                }
            else:
                # Fallback to match_all if no query provided
                search_body["query"] = {"match_all": {}}
            
            # Add filters if provided
            if filters:
                if "query" in search_body and "knn" in search_body["query"]:
                    # Combine knn with filters using bool query
                    search_body["query"] = {
                        "bool": {
                            "must": [search_body["query"]],
                            "filter": self._build_filters(filters)
                        }
                    }
                else:
                    search_body["query"] = {
                        "bool": {
                            "filter": self._build_filters(filters)
                        }
                    }
            
            # Add minimum score threshold
            search_body["min_score"] = min_score
            
            # Execute search
            response = self.opensearch_client.search(
                index=self.index_name,
                body=search_body
            )
            
            # Process results
            hits = response.get("hits", {}).get("hits", [])
            processed_results = []
            
            for hit in hits:
                processed_results.append({
                    "chunk_id": hit["_id"],
                    "score": hit["_score"],
                    "document_id": hit["_source"]["document_id"],
                    "title": hit["_source"]["title"],
                    "authors": hit["_source"]["authors"],
                    "chunk_content": hit["_source"]["chunk_content"],
                    "start_position": hit["_source"]["start_position"],
                    "end_position": hit["_source"]["end_position"],
                    "metadata": hit["_source"]["metadata"]
                })
            
            return {
                "total_hits": response.get("hits", {}).get("total", {}).get("value", 0),
                "max_score": response.get("hits", {}).get("max_score", 0),
                "results": processed_results
            }
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return {
                "error": str(e),
                "results": []
            }
    
    def _build_filters(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build OpenSearch filter clauses from filter dictionary"""
        filter_clauses = []
        
        for field, value in filters.items():
            if isinstance(value, list):
                filter_clauses.append({"terms": {field: value}})
            elif isinstance(value, dict) and "range" in value:
                filter_clauses.append({"range": {field: value["range"]}})
            else:
                filter_clauses.append({"term": {field: value}})
        
        return filter_clauses
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Delete all chunks for a document"""
        try:
            # Search for all chunks of this document
            search_body = {
                "query": {
                    "term": {"document_id": document_id}
                },
                "size": 1000  # Assuming max 1000 chunks per document
            }
            
            response = self.opensearch_client.search(
                index=self.index_name,
                body=search_body
            )
            
            # Delete each chunk
            deleted_chunks = []
            for hit in response.get("hits", {}).get("hits", []):
                chunk_id = hit["_id"]
                delete_response = self.opensearch_client.delete(
                    index=self.index_name,
                    id=chunk_id
                )
                deleted_chunks.append(chunk_id)
            
            logger.info(f"Deleted document {document_id} with {len(deleted_chunks)} chunks")
            
            return {
                "document_id": document_id,
                "status": "success",
                "chunks_deleted": len(deleted_chunks),
                "deleted_chunk_ids": deleted_chunks
            }
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return {
                "document_id": document_id,
                "status": "error",
                "error": str(e)
            }

def lambda_handler(event, context):
    """Lambda handler for document indexing operations"""
    try:
        indexer = DocumentIndexer()
        
        # Parse the event
        operation = event.get('operation', 'index')
        
        if operation == 'index':
            # Handle document indexing
            documents_data = event.get('documents', [])
            
            # Convert to Document objects
            documents = []
            for doc_data in documents_data:
                # Process document if it's raw content
                if 'content' in doc_data and 'chunks' not in doc_data:
                    # Generate chunks and embeddings
                    chunks = chunk_text(doc_data['content'])
                    embeddings = generate_embeddings([chunk.content for chunk in chunks], indexer.bedrock_client)
                    
                    # Add embeddings to chunks
                    for i, chunk in enumerate(chunks):
                        chunk.embedding = embeddings[i]
                    
                    doc_data['chunks'] = chunks
                
                document = Document(**doc_data)
                documents.append(document)
            
            # Index documents
            result = indexer.batch_index_documents(documents)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif operation == 'search':
            # Handle search operations
            query_text = event.get('query_text')
            query_embedding = event.get('query_embedding')
            size = event.get('size', 10)
            min_score = event.get('min_score', 0.7)
            filters = event.get('filters')
            
            result = indexer.search_documents(
                query_text=query_text,
                query_embedding=query_embedding,
                size=size,
                min_score=min_score,
                filters=filters
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif operation == 'delete':
            # Handle document deletion
            document_id = event.get('document_id')
            if not document_id:
                raise ValueError("document_id is required for delete operation")
            
            result = indexer.delete_document(document_id)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown operation: {operation}'})
            }
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }