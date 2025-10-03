"""
Batch Document Processing Lambda Function for Agent Scholar

This Lambda function handles batch processing of multiple documents
for efficient knowledge base population.
"""

import json
import logging
import os
import boto3
from typing import Dict, List, Any
from datetime import datetime
import concurrent.futures
import time
import sys
sys.path.append('/opt/python')
from shared.models import Document, DocumentChunk
from shared.utils import extract_text_from_file, chunk_text, generate_embeddings, generate_id

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_client = boto3.client('bedrock-runtime')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for batch document processing.
    
    Args:
        event: Lambda event containing batch processing request
        context: Lambda context object
        
    Returns:
        Batch processing results
    """
    try:
        logger.info("Starting batch document processing")
        
        # Parse the request
        s3_bucket = event.get('s3_bucket', os.getenv('DOCUMENTS_BUCKET'))
        s3_prefix = event.get('s3_prefix', 'documents/')
        max_documents = event.get('max_documents', 100)
        parallel_workers = event.get('parallel_workers', 5)
        
        if not s3_bucket:
            raise ValueError("S3 bucket not specified")
        
        logger.info(f"Processing documents from s3://{s3_bucket}/{s3_prefix}")
        
        # List documents in S3
        documents = list_documents_in_s3(s3_bucket, s3_prefix, max_documents)
        
        if not documents:
            logger.info("No documents found to process")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No documents found to process',
                    'processed': 0,
                    'successful': 0,
                    'failed': 0
                })
            }
        
        logger.info(f"Found {len(documents)} documents to process")
        
        # Process documents in parallel
        results = process_documents_parallel(documents, s3_bucket, parallel_workers)
        
        # Calculate summary
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        
        logger.info(f"Batch processing complete: {successful}/{len(results)} successful")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Batch processing completed',
                'processed': len(results),
                'successful': successful,
                'failed': failed,
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def list_documents_in_s3(bucket: str, prefix: str, max_documents: int) -> List[Dict[str, Any]]:
    """
    List documents in S3 bucket.
    
    Args:
        bucket: S3 bucket name
        prefix: S3 prefix to search
        max_documents: Maximum number of documents to return
        
    Returns:
        List of document information
    """
    try:
        documents = []
        
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=bucket,
            Prefix=prefix,
            MaxItems=max_documents
        )
        
        for page in page_iterator:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Skip directories and metadata files
                if key.endswith('/') or key.startswith('metadata/'):
                    continue
                
                # Check if it's a supported file type
                file_extension = os.path.splitext(key)[1].lower()
                if file_extension not in ['.txt', '.pdf', '.docx', '.html', '.md']:
                    logger.info(f"Skipping unsupported file type: {key}")
                    continue
                
                documents.append({
                    'key': key,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'file_type': file_extension.strip('.')
                })
        
        logger.info(f"Found {len(documents)} supported documents")
        return documents
        
    except Exception as e:
        logger.error(f"Error listing documents in S3: {str(e)}")
        return []


def process_documents_parallel(documents: List[Dict[str, Any]], s3_bucket: str, 
                             max_workers: int) -> List[Dict[str, Any]]:
    """
    Process documents in parallel using the indexing Lambda function.
    
    Args:
        documents: List of document information
        s3_bucket: S3 bucket name
        max_workers: Maximum number of parallel workers
        
    Returns:
        List of processing results
    """
    try:
        indexing_function_name = os.getenv('INDEXING_FUNCTION_NAME')
        if not indexing_function_name:
            raise ValueError("Indexing function name not configured")
        
        results = []
        
        # Process documents in batches to avoid overwhelming the system
        batch_size = min(max_workers, 10)
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} documents")
            
            # Use ThreadPoolExecutor for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for doc in batch:
                    future = executor.submit(
                        invoke_indexing_function,
                        indexing_function_name,
                        doc,
                        s3_bucket
                    )
                    futures.append(future)
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error in parallel processing: {str(e)}")
                        results.append({
                            'success': False,
                            'error': str(e)
                        })
            
            # Add delay between batches to avoid rate limits
            if i + batch_size < len(documents):
                time.sleep(1)
        
        return results
        
    except Exception as e:
        logger.error(f"Error in parallel processing: {str(e)}")
        return [{'success': False, 'error': str(e)} for _ in documents]


def invoke_indexing_function(function_name: str, document: Dict[str, Any], 
                           s3_bucket: str) -> Dict[str, Any]:
    """
    Invoke the document indexing function for a single document.
    
    Args:
        function_name: Name of the indexing Lambda function
        document: Document information
        s3_bucket: S3 bucket name
        
    Returns:
        Processing result
    """
    try:
        document_id = generate_document_id(document['key'])
        
        payload = {
            'Records': [{
                'body': json.dumps({
                    'document_id': document_id,
                    's3_bucket': s3_bucket,
                    's3_key': document['key'],
                    'file_type': document['file_type'],
                    'file_size': document['size']
                })
            }]
        }
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        
        if response['StatusCode'] == 200:
            body = json.loads(response_payload.get('body', '{}'))
            return {
                'success': True,
                'document_id': document_id,
                'document_key': document['key'],
                'processing_result': body
            }
        else:
            return {
                'success': False,
                'document_id': document_id,
                'document_key': document['key'],
                'error': f"Lambda invocation failed with status {response['StatusCode']}"
            }
        
    except Exception as e:
        logger.error(f"Error invoking indexing function: {str(e)}")
        return {
            'success': False,
            'document_key': document['key'],
            'error': str(e)
        }


def generate_document_id(s3_key: str) -> str:
    """
    Generate a unique document ID from S3 key.
    
    Args:
        s3_key: S3 object key
        
    Returns:
        Unique document ID
    """
    import hashlib
    
    # Create a hash of the S3 key for uniqueness
    hash_obj = hashlib.md5(s3_key.encode())
    return f"doc_{hash_obj.hexdigest()[:12]}"


def get_processing_status(batch_id: str) -> Dict[str, Any]:
    """
    Get the status of a batch processing job.
    
    Args:
        batch_id: Batch processing job ID
        
    Returns:
        Status information
    """
    # This would be implemented with a status tracking system
    # For now, return a placeholder
    return {
        'batch_id': batch_id,
        'status': 'unknown',
        'message': 'Status tracking not implemented yet'
    }