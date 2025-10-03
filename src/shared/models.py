"""
Shared data models for Agent Scholar

This module contains the core data classes and validation functions
used across all Lambda functions and components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import json
import re
import uuid
from urllib.parse import urlparse


class ValidationError(Exception):
    """Custom exception for data validation errors."""
    pass


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "md"


class QueryIntentType(Enum):
    """Types of query intents."""
    SEARCH = "search"
    ANALYZE = "analyze"
    COMPARE = "compare"
    VALIDATE = "validate"
    SYNTHESIZE = "synthesize"
    CODE_EXECUTE = "code_execute"
    SUMMARIZE = "summarize"


class SourceType(Enum):
    """Types of information sources."""
    DOCUMENT = "document"
    WEB = "web"
    KNOWLEDGE_BASE = "knowledge_base"
    CODE_EXECUTION = "code_execution"
    ANALYSIS = "analysis"


class ToolType(Enum):
    """Available tool types."""
    WEB_SEARCH = "web_search"
    CODE_EXECUTION = "code_execution"
    CROSS_LIBRARY_ANALYSIS = "cross_library_analysis"
    KNOWLEDGE_BASE_SEARCH = "knowledge_base_search"

@dataclass
class Document:
    """Document model for knowledge base storage."""
    id: str
    title: str
    authors: List[str]
    publication_date: datetime
    content: str
    document_type: DocumentType = DocumentType.TXT
    chunks: List['DocumentChunk'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_version: str = "titan-v1"
    file_size: Optional[int] = None
    language: str = "en"
    source_url: Optional[str] = None
    
    def __post_init__(self):
        """Validate document data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate document data integrity."""
        if not self.id or not isinstance(self.id, str):
            raise ValidationError("Document ID must be a non-empty string")
        
        if not self.title or not isinstance(self.title, str):
            raise ValidationError("Document title must be a non-empty string")
        
        if len(self.title) > 500:
            raise ValidationError("Document title must be 500 characters or less")
        
        if not isinstance(self.authors, list):
            raise ValidationError("Authors must be a list")
        
        if not self.authors:
            raise ValidationError("Document must have at least one author")
        
        for author in self.authors:
            if not isinstance(author, str) or not author.strip():
                raise ValidationError("All authors must be non-empty strings")
        
        if not isinstance(self.publication_date, datetime):
            raise ValidationError("Publication date must be a datetime object")
        
        if self.publication_date > datetime.now():
            raise ValidationError("Publication date cannot be in the future")
        
        if not self.content or not isinstance(self.content, str):
            raise ValidationError("Document content must be a non-empty string")
        
        if len(self.content) > 10_000_000:  # 10MB text limit
            raise ValidationError("Document content exceeds maximum size limit")
        
        if not isinstance(self.document_type, DocumentType):
            raise ValidationError("Document type must be a valid DocumentType enum")
        
        if self.source_url and not self._is_valid_url(self.source_url):
            raise ValidationError("Source URL must be a valid URL")
        
        if self.file_size is not None and (not isinstance(self.file_size, int) or self.file_size < 0):
            raise ValidationError("File size must be a non-negative integer")
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary for serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'authors': self.authors,
            'publication_date': self.publication_date.isoformat(),
            'content': self.content,
            'document_type': self.document_type.value,
            'chunks': [chunk.to_dict() for chunk in self.chunks],
            'metadata': self.metadata,
            'embedding_version': self.embedding_version,
            'file_size': self.file_size,
            'language': self.language,
            'source_url': self.source_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """Create document from dictionary with validation."""
        try:
            return cls(
                id=data['id'],
                title=data['title'],
                authors=data['authors'],
                publication_date=datetime.fromisoformat(data['publication_date']),
                content=data['content'],
                document_type=DocumentType(data.get('document_type', 'txt')),
                chunks=[DocumentChunk.from_dict(chunk) for chunk in data.get('chunks', [])],
                metadata=data.get('metadata', {}),
                embedding_version=data.get('embedding_version', 'titan-v1'),
                file_size=data.get('file_size'),
                language=data.get('language', 'en'),
                source_url=data.get('source_url')
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")
    
    def add_chunk(self, chunk: 'DocumentChunk') -> None:
        """Add a chunk to the document with validation."""
        if not isinstance(chunk, DocumentChunk):
            raise ValidationError("Chunk must be a DocumentChunk instance")
        
        if chunk.document_id != self.id:
            raise ValidationError("Chunk document_id must match document id")
        
        self.chunks.append(chunk)
    
    def get_word_count(self) -> int:
        """Get approximate word count of the document."""
        return len(self.content.split())
    
    def get_summary_metadata(self) -> Dict[str, Any]:
        """Get summary metadata for the document."""
        return {
            'id': self.id,
            'title': self.title,
            'authors': self.authors,
            'publication_date': self.publication_date.isoformat(),
            'document_type': self.document_type.value,
            'word_count': self.get_word_count(),
            'chunk_count': len(self.chunks),
            'language': self.language
        }

@dataclass
class DocumentChunk:
    """Document chunk model for vector storage."""
    chunk_id: str
    document_id: str
    content: str
    embedding: List[float] = field(default_factory=list)
    start_position: int = 0
    end_position: int = 0
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding_model: str = "titan-embed-text-v1"
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate chunk data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate chunk data integrity."""
        if not self.chunk_id or not isinstance(self.chunk_id, str):
            raise ValidationError("Chunk ID must be a non-empty string")
        
        if not self.document_id or not isinstance(self.document_id, str):
            raise ValidationError("Document ID must be a non-empty string")
        
        if not self.content or not isinstance(self.content, str):
            raise ValidationError("Chunk content must be a non-empty string")
        
        if len(self.content) > 8000:  # Reasonable chunk size limit
            raise ValidationError("Chunk content exceeds maximum size limit")
        
        if not isinstance(self.embedding, list):
            raise ValidationError("Embedding must be a list")
        
        if self.embedding and not all(isinstance(x, (int, float)) for x in self.embedding):
            raise ValidationError("All embedding values must be numbers")
        
        if not isinstance(self.start_position, int) or self.start_position < 0:
            raise ValidationError("Start position must be a non-negative integer")
        
        if not isinstance(self.end_position, int) or self.end_position < self.start_position:
            raise ValidationError("End position must be >= start position")
        
        if not isinstance(self.chunk_index, int) or self.chunk_index < 0:
            raise ValidationError("Chunk index must be a non-negative integer")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary for serialization."""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'content': self.content,
            'embedding': self.embedding,
            'start_position': self.start_position,
            'end_position': self.end_position,
            'chunk_index': self.chunk_index,
            'metadata': self.metadata,
            'embedding_model': self.embedding_model,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Create chunk from dictionary with validation."""
        try:
            return cls(
                chunk_id=data['chunk_id'],
                document_id=data['document_id'],
                content=data['content'],
                embedding=data.get('embedding', []),
                start_position=data.get('start_position', 0),
                end_position=data.get('end_position', 0),
                chunk_index=data.get('chunk_index', 0),
                metadata=data.get('metadata', {}),
                embedding_model=data.get('embedding_model', 'titan-embed-text-v1'),
                created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")
    
    def get_word_count(self) -> int:
        """Get word count of the chunk."""
        return len(self.content.split())
    
    def has_embedding(self) -> bool:
        """Check if chunk has an embedding vector."""
        return len(self.embedding) > 0
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vector."""
        return len(self.embedding)

@dataclass
class QueryIntent:
    """Query intent analysis model."""
    primary_intent: QueryIntentType
    entities: List[str] = field(default_factory=list)
    temporal_scope: Optional[str] = None
    complexity_level: int = 1
    confidence_score: float = 0.0
    secondary_intents: List[QueryIntentType] = field(default_factory=list)
    required_tools: List[ToolType] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate intent data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate query intent data."""
        if not isinstance(self.primary_intent, QueryIntentType):
            raise ValidationError("Primary intent must be a QueryIntentType enum")
        
        if not isinstance(self.entities, list):
            raise ValidationError("Entities must be a list")
        
        for entity in self.entities:
            if not isinstance(entity, str) or not entity.strip():
                raise ValidationError("All entities must be non-empty strings")
        
        if not isinstance(self.complexity_level, int) or not (1 <= self.complexity_level <= 5):
            raise ValidationError("Complexity level must be an integer between 1 and 5")
        
        if not isinstance(self.confidence_score, (int, float)) or not (0.0 <= self.confidence_score <= 1.0):
            raise ValidationError("Confidence score must be a number between 0.0 and 1.0")
        
        if not isinstance(self.secondary_intents, list):
            raise ValidationError("Secondary intents must be a list")
        
        for intent in self.secondary_intents:
            if not isinstance(intent, QueryIntentType):
                raise ValidationError("All secondary intents must be QueryIntentType enums")
        
        if not isinstance(self.required_tools, list):
            raise ValidationError("Required tools must be a list")
        
        for tool in self.required_tools:
            if not isinstance(tool, ToolType):
                raise ValidationError("All required tools must be ToolType enums")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intent to dictionary for serialization."""
        return {
            'primary_intent': self.primary_intent.value,
            'entities': self.entities,
            'temporal_scope': self.temporal_scope,
            'complexity_level': self.complexity_level,
            'confidence_score': self.confidence_score,
            'secondary_intents': [intent.value for intent in self.secondary_intents],
            'required_tools': [tool.value for tool in self.required_tools]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueryIntent':
        """Create intent from dictionary with validation."""
        try:
            return cls(
                primary_intent=QueryIntentType(data['primary_intent']),
                entities=data.get('entities', []),
                temporal_scope=data.get('temporal_scope'),
                complexity_level=data.get('complexity_level', 1),
                confidence_score=data.get('confidence_score', 0.0),
                secondary_intents=[QueryIntentType(intent) for intent in data.get('secondary_intents', [])],
                required_tools=[ToolType(tool) for tool in data.get('required_tools', [])]
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")


@dataclass
class ResearchQuery:
    """Research query model for processing user requests."""
    query_id: str
    user_id: str
    original_text: str
    processed_intent: QueryIntent
    session_id: str
    session_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time: Optional[float] = None
    
    def __post_init__(self):
        """Validate query data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate research query data."""
        if not self.query_id or not isinstance(self.query_id, str):
            raise ValidationError("Query ID must be a non-empty string")
        
        if not self.user_id or not isinstance(self.user_id, str):
            raise ValidationError("User ID must be a non-empty string")
        
        if not self.original_text or not isinstance(self.original_text, str):
            raise ValidationError("Original text must be a non-empty string")
        
        if len(self.original_text) > 10000:
            raise ValidationError("Query text exceeds maximum length")
        
        if not isinstance(self.processed_intent, QueryIntent):
            raise ValidationError("Processed intent must be a QueryIntent instance")
        
        if not self.session_id or not isinstance(self.session_id, str):
            raise ValidationError("Session ID must be a non-empty string")
        
        if not isinstance(self.session_context, dict):
            raise ValidationError("Session context must be a dictionary")
        
        if self.processing_time is not None and (not isinstance(self.processing_time, (int, float)) or self.processing_time < 0):
            raise ValidationError("Processing time must be a non-negative number")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert query to dictionary for serialization."""
        return {
            'query_id': self.query_id,
            'user_id': self.user_id,
            'original_text': self.original_text,
            'processed_intent': self.processed_intent.to_dict(),
            'session_id': self.session_id,
            'session_context': self.session_context,
            'timestamp': self.timestamp.isoformat(),
            'processing_time': self.processing_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchQuery':
        """Create query from dictionary with validation."""
        try:
            return cls(
                query_id=data['query_id'],
                user_id=data['user_id'],
                original_text=data['original_text'],
                processed_intent=QueryIntent.from_dict(data['processed_intent']),
                session_id=data['session_id'],
                session_context=data.get('session_context', {}),
                timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
                processing_time=data.get('processing_time')
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")
    
    def get_required_tools(self) -> List[ToolType]:
        """Get list of required tools from the processed intent."""
        return self.processed_intent.required_tools

@dataclass
class ReasoningStep:
    """Individual reasoning step in agent processing."""
    step_number: int
    action: str
    rationale: str
    result: str
    tool_used: Optional[ToolType] = None
    execution_time: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate reasoning step data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate reasoning step data."""
        if not isinstance(self.step_number, int) or self.step_number < 1:
            raise ValidationError("Step number must be a positive integer")
        
        if not self.action or not isinstance(self.action, str):
            raise ValidationError("Action must be a non-empty string")
        
        if not self.rationale or not isinstance(self.rationale, str):
            raise ValidationError("Rationale must be a non-empty string")
        
        if not self.result or not isinstance(self.result, str):
            raise ValidationError("Result must be a non-empty string")
        
        if self.tool_used is not None and not isinstance(self.tool_used, ToolType):
            raise ValidationError("Tool used must be a ToolType enum or None")
        
        if self.execution_time is not None and (not isinstance(self.execution_time, (int, float)) or self.execution_time < 0):
            raise ValidationError("Execution time must be a non-negative number")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for serialization."""
        return {
            'step_number': self.step_number,
            'action': self.action,
            'rationale': self.rationale,
            'result': self.result,
            'tool_used': self.tool_used.value if self.tool_used else None,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningStep':
        """Create reasoning step from dictionary with validation."""
        try:
            return cls(
                step_number=data['step_number'],
                action=data['action'],
                rationale=data['rationale'],
                result=data['result'],
                tool_used=ToolType(data['tool_used']) if data.get('tool_used') else None,
                execution_time=data.get('execution_time'),
                timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")


@dataclass
class Source:
    """Source reference model for citations."""
    source_id: str
    source_type: SourceType
    title: str
    url: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[datetime] = None
    relevance_score: float = 0.0
    excerpt: Optional[str] = None
    page_number: Optional[int] = None
    
    def __post_init__(self):
        """Validate source data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate source data."""
        if not self.source_id or not isinstance(self.source_id, str):
            raise ValidationError("Source ID must be a non-empty string")
        
        if not isinstance(self.source_type, SourceType):
            raise ValidationError("Source type must be a SourceType enum")
        
        if not self.title or not isinstance(self.title, str):
            raise ValidationError("Title must be a non-empty string")
        
        if self.url and not self._is_valid_url(self.url):
            raise ValidationError("URL must be a valid URL")
        
        if not isinstance(self.authors, list):
            raise ValidationError("Authors must be a list")
        
        for author in self.authors:
            if not isinstance(author, str) or not author.strip():
                raise ValidationError("All authors must be non-empty strings")
        
        if self.publication_date and not isinstance(self.publication_date, datetime):
            raise ValidationError("Publication date must be a datetime object or None")
        
        if not isinstance(self.relevance_score, (int, float)) or not (0.0 <= self.relevance_score <= 1.0):
            raise ValidationError("Relevance score must be a number between 0.0 and 1.0")
        
        if self.page_number is not None and (not isinstance(self.page_number, int) or self.page_number < 1):
            raise ValidationError("Page number must be a positive integer")
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert source to dictionary for serialization."""
        return {
            'source_id': self.source_id,
            'source_type': self.source_type.value,
            'title': self.title,
            'url': self.url,
            'authors': self.authors,
            'publication_date': self.publication_date.isoformat() if self.publication_date else None,
            'relevance_score': self.relevance_score,
            'excerpt': self.excerpt,
            'page_number': self.page_number
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Source':
        """Create source from dictionary with validation."""
        try:
            return cls(
                source_id=data['source_id'],
                source_type=SourceType(data['source_type']),
                title=data['title'],
                url=data.get('url'),
                authors=data.get('authors', []),
                publication_date=datetime.fromisoformat(data['publication_date']) if data.get('publication_date') else None,
                relevance_score=data.get('relevance_score', 0.0),
                excerpt=data.get('excerpt'),
                page_number=data.get('page_number')
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")


@dataclass
class ToolInvocation:
    """Tool invocation tracking model."""
    invocation_id: str
    tool_name: ToolType
    parameters: Dict[str, Any]
    result: Dict[str, Any]
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate tool invocation data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate tool invocation data."""
        if not self.invocation_id or not isinstance(self.invocation_id, str):
            raise ValidationError("Invocation ID must be a non-empty string")
        
        if not isinstance(self.tool_name, ToolType):
            raise ValidationError("Tool name must be a ToolType enum")
        
        if not isinstance(self.parameters, dict):
            raise ValidationError("Parameters must be a dictionary")
        
        if not isinstance(self.result, dict):
            raise ValidationError("Result must be a dictionary")
        
        if not isinstance(self.execution_time, (int, float)) or self.execution_time < 0:
            raise ValidationError("Execution time must be a non-negative number")
        
        if not isinstance(self.success, bool):
            raise ValidationError("Success must be a boolean")
        
        if self.error_message is not None and not isinstance(self.error_message, str):
            raise ValidationError("Error message must be a string or None")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert invocation to dictionary for serialization."""
        return {
            'invocation_id': self.invocation_id,
            'tool_name': self.tool_name.value,
            'parameters': self.parameters,
            'result': self.result,
            'execution_time': self.execution_time,
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolInvocation':
        """Create tool invocation from dictionary with validation."""
        try:
            return cls(
                invocation_id=data['invocation_id'],
                tool_name=ToolType(data['tool_name']),
                parameters=data['parameters'],
                result=data['result'],
                execution_time=data['execution_time'],
                success=data['success'],
                error_message=data.get('error_message'),
                timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")


@dataclass
class AgentResponse:
    """Agent response model for structured output."""
    response_id: str
    query_id: str
    final_answer: str
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    sources_used: List[Source] = field(default_factory=list)
    tools_invoked: List[ToolInvocation] = field(default_factory=list)
    confidence_score: float = 0.0
    total_processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate agent response data after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate agent response data."""
        if not self.response_id or not isinstance(self.response_id, str):
            raise ValidationError("Response ID must be a non-empty string")
        
        if not self.query_id or not isinstance(self.query_id, str):
            raise ValidationError("Query ID must be a non-empty string")
        
        if not self.final_answer or not isinstance(self.final_answer, str):
            raise ValidationError("Final answer must be a non-empty string")
        
        if not isinstance(self.reasoning_steps, list):
            raise ValidationError("Reasoning steps must be a list")
        
        for step in self.reasoning_steps:
            if not isinstance(step, ReasoningStep):
                raise ValidationError("All reasoning steps must be ReasoningStep instances")
        
        if not isinstance(self.sources_used, list):
            raise ValidationError("Sources used must be a list")
        
        for source in self.sources_used:
            if not isinstance(source, Source):
                raise ValidationError("All sources must be Source instances")
        
        if not isinstance(self.tools_invoked, list):
            raise ValidationError("Tools invoked must be a list")
        
        for tool in self.tools_invoked:
            if not isinstance(tool, ToolInvocation):
                raise ValidationError("All tools must be ToolInvocation instances")
        
        if not isinstance(self.confidence_score, (int, float)) or not (0.0 <= self.confidence_score <= 1.0):
            raise ValidationError("Confidence score must be a number between 0.0 and 1.0")
        
        if not isinstance(self.total_processing_time, (int, float)) or self.total_processing_time < 0:
            raise ValidationError("Total processing time must be a non-negative number")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for serialization."""
        return {
            'response_id': self.response_id,
            'query_id': self.query_id,
            'final_answer': self.final_answer,
            'reasoning_steps': [step.to_dict() for step in self.reasoning_steps],
            'sources_used': [source.to_dict() for source in self.sources_used],
            'tools_invoked': [tool.to_dict() for tool in self.tools_invoked],
            'confidence_score': self.confidence_score,
            'total_processing_time': self.total_processing_time,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentResponse':
        """Create agent response from dictionary with validation."""
        try:
            return cls(
                response_id=data['response_id'],
                query_id=data['query_id'],
                final_answer=data['final_answer'],
                reasoning_steps=[ReasoningStep.from_dict(step) for step in data.get('reasoning_steps', [])],
                sources_used=[Source.from_dict(source) for source in data.get('sources_used', [])],
                tools_invoked=[ToolInvocation.from_dict(tool) for tool in data.get('tools_invoked', [])],
                confidence_score=data.get('confidence_score', 0.0),
                total_processing_time=data.get('total_processing_time', 0.0),
                timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
                session_id=data.get('session_id')
            )
        except KeyError as e:
            raise ValidationError(f"Missing required field: {e}")
        except ValueError as e:
            raise ValidationError(f"Invalid data format: {e}")
    
    def add_reasoning_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step to the response."""
        if not isinstance(step, ReasoningStep):
            raise ValidationError("Step must be a ReasoningStep instance")
        self.reasoning_steps.append(step)
    
    def add_source(self, source: Source) -> None:
        """Add a source to the response."""
        if not isinstance(source, Source):
            raise ValidationError("Source must be a Source instance")
        self.sources_used.append(source)
    
    def add_tool_invocation(self, tool: ToolInvocation) -> None:
        """Add a tool invocation to the response."""
        if not isinstance(tool, ToolInvocation):
            raise ValidationError("Tool must be a ToolInvocation instance")
        self.tools_invoked.append(tool)

# Validation functions (enhanced with proper error handling)
def validate_document(document: Document) -> bool:
    """
    Validate document data integrity.
    
    Args:
        document: Document instance to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If validation fails with detailed error message
    """
    try:
        if not isinstance(document, Document):
            raise ValidationError("Input must be a Document instance")
        
        # Validation is handled in __post_init__, so if we get here, it's valid
        return True
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unexpected validation error: {str(e)}")


def validate_query(query: ResearchQuery) -> bool:
    """
    Validate research query data.
    
    Args:
        query: ResearchQuery instance to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If validation fails with detailed error message
    """
    try:
        if not isinstance(query, ResearchQuery):
            raise ValidationError("Input must be a ResearchQuery instance")
        
        # Validation is handled in __post_init__, so if we get here, it's valid
        return True
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unexpected validation error: {str(e)}")


def validate_document_chunk(chunk: DocumentChunk) -> bool:
    """
    Validate document chunk data integrity.
    
    Args:
        chunk: DocumentChunk instance to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If validation fails with detailed error message
    """
    try:
        if not isinstance(chunk, DocumentChunk):
            raise ValidationError("Input must be a DocumentChunk instance")
        
        # Validation is handled in __post_init__, so if we get here, it's valid
        return True
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unexpected validation error: {str(e)}")


def validate_agent_response(response: AgentResponse) -> bool:
    """
    Validate agent response data integrity.
    
    Args:
        response: AgentResponse instance to validate
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValidationError: If validation fails with detailed error message
    """
    try:
        if not isinstance(response, AgentResponse):
            raise ValidationError("Input must be an AgentResponse instance")
        
        # Validation is handled in __post_init__, so if we get here, it's valid
        return True
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unexpected validation error: {str(e)}")


# Utility functions for model creation
def create_document_id(title: str, authors: List[str]) -> str:
    """
    Create a unique document ID based on title and authors.
    
    Args:
        title: Document title
        authors: List of authors
        
    Returns:
        Unique document ID
    """
    import hashlib
    
    # Create a hash based on title and authors for uniqueness
    content = f"{title}{''.join(sorted(authors))}"
    hash_obj = hashlib.md5(content.encode())
    return f"doc_{hash_obj.hexdigest()[:12]}"


def create_chunk_id(document_id: str, chunk_index: int) -> str:
    """
    Create a unique chunk ID.
    
    Args:
        document_id: Parent document ID
        chunk_index: Index of the chunk within the document
        
    Returns:
        Unique chunk ID
    """
    return f"{document_id}_chunk_{chunk_index:04d}"


def create_query_id() -> str:
    """
    Create a unique query ID.
    
    Returns:
        Unique query ID
    """
    return f"query_{uuid.uuid4().hex[:12]}"


def create_response_id(query_id: str) -> str:
    """
    Create a unique response ID based on query ID.
    
    Args:
        query_id: Associated query ID
        
    Returns:
        Unique response ID
    """
    return f"resp_{query_id}_{uuid.uuid4().hex[:8]}"


def create_invocation_id(tool_name: ToolType) -> str:
    """
    Create a unique tool invocation ID.
    
    Args:
        tool_name: Type of tool being invoked
        
    Returns:
        Unique invocation ID
    """
    return f"inv_{tool_name.value}_{uuid.uuid4().hex[:8]}"


# Model factory functions
def create_basic_document(title: str, authors: List[str], content: str, 
                         document_type: DocumentType = DocumentType.TXT) -> Document:
    """
    Create a basic document with minimal required fields.
    
    Args:
        title: Document title
        authors: List of authors
        content: Document content
        document_type: Type of document
        
    Returns:
        Document instance
    """
    doc_id = create_document_id(title, authors)
    return Document(
        id=doc_id,
        title=title,
        authors=authors,
        publication_date=datetime.now(),
        content=content,
        document_type=document_type
    )


def create_basic_query(user_id: str, query_text: str, session_id: str) -> ResearchQuery:
    """
    Create a basic research query with minimal processing.
    
    Args:
        user_id: User identifier
        query_text: Query text
        session_id: Session identifier
        
    Returns:
        ResearchQuery instance
    """
    query_id = create_query_id()
    
    # Create basic intent (will be enhanced by intent processing)
    intent = QueryIntent(
        primary_intent=QueryIntentType.SEARCH,
        confidence_score=0.5
    )
    
    return ResearchQuery(
        query_id=query_id,
        user_id=user_id,
        original_text=query_text,
        processed_intent=intent,
        session_id=session_id
    )