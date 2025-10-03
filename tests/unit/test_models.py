"""
Unit tests for shared data models
"""

import pytest
from datetime import datetime, timedelta
from src.shared.models import (
    Document,
    DocumentChunk,
    ResearchQuery,
    QueryIntent,
    AgentResponse,
    ReasoningStep,
    Source,
    ToolInvocation,
    ValidationError,
    DocumentType,
    QueryIntentType,
    SourceType,
    ToolType,
    validate_document,
    validate_query,
    validate_document_chunk,
    validate_agent_response,
    create_document_id,
    create_chunk_id,
    create_query_id,
    create_basic_document,
    create_basic_query
)

class TestDocument:
    """Test cases for Document model."""
    
    def test_document_creation_valid(self):
        """Test valid document creation."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One", "Author Two"],
            publication_date=datetime.now() - timedelta(days=1),
            content="This is test content.",
            document_type=DocumentType.PDF
        )
        
        assert doc.id == "test-doc-1"
        assert doc.title == "Test Document"
        assert len(doc.authors) == 2
        assert doc.content == "This is test content."
        assert doc.document_type == DocumentType.PDF
    
    def test_document_validation_empty_id(self):
        """Test document validation with empty ID."""
        with pytest.raises(ValidationError, match="Document ID must be a non-empty string"):
            Document(
                id="",
                title="Test Document",
                authors=["Author One"],
                publication_date=datetime.now(),
                content="Test content"
            )
    
    def test_document_validation_empty_title(self):
        """Test document validation with empty title."""
        with pytest.raises(ValidationError, match="Document title must be a non-empty string"):
            Document(
                id="test-doc-1",
                title="",
                authors=["Author One"],
                publication_date=datetime.now(),
                content="Test content"
            )
    
    def test_document_validation_long_title(self):
        """Test document validation with overly long title."""
        with pytest.raises(ValidationError, match="Document title must be 500 characters or less"):
            Document(
                id="test-doc-1",
                title="x" * 501,
                authors=["Author One"],
                publication_date=datetime.now(),
                content="Test content"
            )
    
    def test_document_validation_no_authors(self):
        """Test document validation with no authors."""
        with pytest.raises(ValidationError, match="Document must have at least one author"):
            Document(
                id="test-doc-1",
                title="Test Document",
                authors=[],
                publication_date=datetime.now(),
                content="Test content"
            )
    
    def test_document_validation_future_date(self):
        """Test document validation with future publication date."""
        with pytest.raises(ValidationError, match="Publication date cannot be in the future"):
            Document(
                id="test-doc-1",
                title="Test Document",
                authors=["Author One"],
                publication_date=datetime.now() + timedelta(days=1),
                content="Test content"
            )
    
    def test_document_validation_empty_content(self):
        """Test document validation with empty content."""
        with pytest.raises(ValidationError, match="Document content must be a non-empty string"):
            Document(
                id="test-doc-1",
                title="Test Document",
                authors=["Author One"],
                publication_date=datetime.now(),
                content=""
            )
    
    def test_document_to_dict(self):
        """Test document serialization to dictionary."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One"],
            publication_date=datetime(2024, 1, 1),
            content="Test content",
            document_type=DocumentType.PDF
        )
        
        doc_dict = doc.to_dict()
        
        assert doc_dict['id'] == "test-doc-1"
        assert doc_dict['title'] == "Test Document"
        assert doc_dict['authors'] == ["Author One"]
        assert doc_dict['content'] == "Test content"
        assert doc_dict['document_type'] == "pdf"
    
    def test_document_from_dict(self):
        """Test document creation from dictionary."""
        doc_data = {
            'id': 'test-doc-1',
            'title': 'Test Document',
            'authors': ['Author One'],
            'publication_date': '2024-01-01T00:00:00',
            'content': 'Test content',
            'document_type': 'pdf',
            'chunks': [],
            'metadata': {},
            'embedding_version': 'titan-v1'
        }
        
        doc = Document.from_dict(doc_data)
        
        assert doc.id == "test-doc-1"
        assert doc.title == "Test Document"
        assert doc.authors == ["Author One"]
        assert doc.document_type == DocumentType.PDF
    
    def test_document_add_chunk(self):
        """Test adding chunks to document."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One"],
            publication_date=datetime.now() - timedelta(days=1),
            content="Test content"
        )
        
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            document_id="test-doc-1",
            content="Chunk content"
        )
        
        doc.add_chunk(chunk)
        assert len(doc.chunks) == 1
        assert doc.chunks[0].chunk_id == "chunk-1"
    
    def test_document_word_count(self):
        """Test document word count calculation."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One"],
            publication_date=datetime.now() - timedelta(days=1),
            content="This is a test document with multiple words."
        )
        
        assert doc.get_word_count() == 8

class TestDocumentChunk:
    """Test cases for DocumentChunk model."""
    
    def test_chunk_creation_valid(self):
        """Test valid chunk creation."""
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="This is a chunk of text.",
            start_position=0,
            end_position=25,
            chunk_index=0
        )
        
        assert chunk.chunk_id == "chunk-1"
        assert chunk.document_id == "doc-1"
        assert chunk.content == "This is a chunk of text."
        assert chunk.start_position == 0
        assert chunk.end_position == 25
        assert chunk.chunk_index == 0
    
    def test_chunk_validation_empty_id(self):
        """Test chunk validation with empty chunk ID."""
        with pytest.raises(ValidationError, match="Chunk ID must be a non-empty string"):
            DocumentChunk(
                chunk_id="",
                document_id="doc-1",
                content="Test content"
            )
    
    def test_chunk_validation_invalid_positions(self):
        """Test chunk validation with invalid positions."""
        with pytest.raises(ValidationError, match="End position must be >= start position"):
            DocumentChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="Test content",
                start_position=10,
                end_position=5
            )
    
    def test_chunk_validation_negative_index(self):
        """Test chunk validation with negative chunk index."""
        with pytest.raises(ValidationError, match="Chunk index must be a non-negative integer"):
            DocumentChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="Test content",
                chunk_index=-1
            )
    
    def test_chunk_validation_oversized_content(self):
        """Test chunk validation with oversized content."""
        with pytest.raises(ValidationError, match="Chunk content exceeds maximum size limit"):
            DocumentChunk(
                chunk_id="chunk-1",
                document_id="doc-1",
                content="x" * 8001
            )
    
    def test_chunk_to_dict(self):
        """Test chunk serialization to dictionary."""
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3]
        )
        
        chunk_dict = chunk.to_dict()
        
        assert chunk_dict['chunk_id'] == "chunk-1"
        assert chunk_dict['document_id'] == "doc-1"
        assert chunk_dict['content'] == "Test content"
        assert chunk_dict['embedding'] == [0.1, 0.2, 0.3]
    
    def test_chunk_from_dict(self):
        """Test chunk creation from dictionary."""
        chunk_data = {
            'chunk_id': 'chunk-1',
            'document_id': 'doc-1',
            'content': 'Test content',
            'embedding': [0.1, 0.2, 0.3],
            'start_position': 0,
            'end_position': 12,
            'chunk_index': 0,
            'metadata': {},
            'embedding_model': 'titan-embed-text-v1',
            'created_at': '2024-01-01T00:00:00'
        }
        
        chunk = DocumentChunk.from_dict(chunk_data)
        
        assert chunk.chunk_id == "chunk-1"
        assert chunk.document_id == "doc-1"
        assert chunk.content == "Test content"
        assert chunk.embedding == [0.1, 0.2, 0.3]
    
    def test_chunk_has_embedding(self):
        """Test chunk embedding detection."""
        chunk_with_embedding = DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3]
        )
        
        chunk_without_embedding = DocumentChunk(
            chunk_id="chunk-2",
            document_id="doc-1",
            content="Test content"
        )
        
        assert chunk_with_embedding.has_embedding() is True
        assert chunk_without_embedding.has_embedding() is False
    
    def test_chunk_embedding_dimension(self):
        """Test chunk embedding dimension calculation."""
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
        )
        
        assert chunk.get_embedding_dimension() == 5

class TestResearchQuery:
    """Test cases for ResearchQuery model."""
    
    def test_query_creation(self):
        """Test basic query creation."""
        intent = QueryIntent(
            primary_intent="search",
            entities=["AI", "machine learning"],
            complexity_level=2
        )
        
        query = ResearchQuery(
            query_id="query-1",
            user_id="user-1",
            original_text="What is machine learning?",
            processed_intent=intent
        )
        
        assert query.query_id == "query-1"
        assert query.user_id == "user-1"
        assert query.original_text == "What is machine learning?"
        assert query.processed_intent.primary_intent == "search"

class TestValidation:
    """Test cases for validation functions (legacy tests - kept for compatibility)."""
    
    def test_validate_document_valid(self):
        """Test validation of valid document."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One"],
            publication_date=datetime.now() - timedelta(days=1),
            content="Test content"
        )
        
        assert validate_document(doc) is True
    
    def test_validate_document_invalid(self):
        """Test validation with invalid document type."""
        with pytest.raises(ValidationError, match="Input must be a Document instance"):
            validate_document("not a document")
    
    def test_validate_query_valid(self):
        """Test validation of valid query."""
        intent = QueryIntent(primary_intent=QueryIntentType.SEARCH)
        query = ResearchQuery(
            query_id="query-1",
            user_id="user-1",
            original_text="Test query",
            processed_intent=intent,
            session_id="session-123"
        )
        
        assert validate_query(query) is True
    
    def test_validate_query_invalid(self):
        """Test validation with invalid query type."""
        with pytest.raises(ValidationError, match="Input must be a ResearchQuery instance"):
            validate_query("not a query")


class TestQueryIntent:
    """Test cases for QueryIntent model."""
    
    def test_query_intent_creation_valid(self):
        """Test valid query intent creation."""
        intent = QueryIntent(
            primary_intent=QueryIntentType.SEARCH,
            entities=["AI", "machine learning"],
            complexity_level=2,
            confidence_score=0.8
        )
        
        assert intent.primary_intent == QueryIntentType.SEARCH
        assert intent.entities == ["AI", "machine learning"]
        assert intent.complexity_level == 2
        assert intent.confidence_score == 0.8
    
    def test_query_intent_validation_invalid_complexity(self):
        """Test query intent validation with invalid complexity level."""
        with pytest.raises(ValidationError, match="Complexity level must be an integer between 1 and 5"):
            QueryIntent(
                primary_intent=QueryIntentType.SEARCH,
                complexity_level=6
            )
    
    def test_query_intent_validation_invalid_confidence(self):
        """Test query intent validation with invalid confidence score."""
        with pytest.raises(ValidationError, match="Confidence score must be a number between 0.0 and 1.0"):
            QueryIntent(
                primary_intent=QueryIntentType.SEARCH,
                confidence_score=1.5
            )
    
    def test_query_intent_to_dict(self):
        """Test query intent serialization to dictionary."""
        intent = QueryIntent(
            primary_intent=QueryIntentType.ANALYZE,
            entities=["data", "statistics"],
            required_tools=[ToolType.CODE_EXECUTION]
        )
        
        intent_dict = intent.to_dict()
        
        assert intent_dict['primary_intent'] == "analyze"
        assert intent_dict['entities'] == ["data", "statistics"]
        assert intent_dict['required_tools'] == ["code_execution"]
    
    def test_query_intent_from_dict(self):
        """Test query intent creation from dictionary."""
        intent_data = {
            'primary_intent': 'search',
            'entities': ['AI', 'ML'],
            'complexity_level': 3,
            'confidence_score': 0.9,
            'required_tools': ['web_search']
        }
        
        intent = QueryIntent.from_dict(intent_data)
        
        assert intent.primary_intent == QueryIntentType.SEARCH
        assert intent.entities == ['AI', 'ML']
        assert intent.required_tools == [ToolType.WEB_SEARCH]


class TestResearchQuery:
    """Test cases for ResearchQuery model."""
    
    def test_research_query_creation_valid(self):
        """Test valid research query creation."""
        intent = QueryIntent(
            primary_intent=QueryIntentType.SEARCH,
            entities=["AI", "machine learning"],
            complexity_level=2
        )
        
        query = ResearchQuery(
            query_id="query-1",
            user_id="user-1",
            original_text="What is machine learning?",
            processed_intent=intent,
            session_id="session-123"
        )
        
        assert query.query_id == "query-1"
        assert query.user_id == "user-1"
        assert query.original_text == "What is machine learning?"
        assert query.processed_intent.primary_intent == QueryIntentType.SEARCH
        assert query.session_id == "session-123"
    
    def test_research_query_validation_empty_query_id(self):
        """Test research query validation with empty query ID."""
        intent = QueryIntent(primary_intent=QueryIntentType.SEARCH)
        
        with pytest.raises(ValidationError, match="Query ID must be a non-empty string"):
            ResearchQuery(
                query_id="",
                user_id="user-1",
                original_text="Test query",
                processed_intent=intent,
                session_id="session-123"
            )
    
    def test_research_query_validation_long_text(self):
        """Test research query validation with overly long text."""
        intent = QueryIntent(primary_intent=QueryIntentType.SEARCH)
        
        with pytest.raises(ValidationError, match="Query text exceeds maximum length"):
            ResearchQuery(
                query_id="query-1",
                user_id="user-1",
                original_text="x" * 10001,
                processed_intent=intent,
                session_id="session-123"
            )
    
    def test_research_query_to_dict(self):
        """Test research query serialization to dictionary."""
        intent = QueryIntent(primary_intent=QueryIntentType.ANALYZE)
        query = ResearchQuery(
            query_id="query-1",
            user_id="user-1",
            original_text="Analyze this data",
            processed_intent=intent,
            session_id="session-123"
        )
        
        query_dict = query.to_dict()
        
        assert query_dict['query_id'] == "query-1"
        assert query_dict['user_id'] == "user-1"
        assert query_dict['original_text'] == "Analyze this data"
        assert query_dict['session_id'] == "session-123"


class TestReasoningStep:
    """Test cases for ReasoningStep model."""
    
    def test_reasoning_step_creation_valid(self):
        """Test valid reasoning step creation."""
        step = ReasoningStep(
            step_number=1,
            action="Search knowledge base",
            rationale="Need to find relevant documents",
            result="Found 5 relevant documents",
            tool_used=ToolType.KNOWLEDGE_BASE_SEARCH
        )
        
        assert step.step_number == 1
        assert step.action == "Search knowledge base"
        assert step.tool_used == ToolType.KNOWLEDGE_BASE_SEARCH
    
    def test_reasoning_step_validation_invalid_step_number(self):
        """Test reasoning step validation with invalid step number."""
        with pytest.raises(ValidationError, match="Step number must be a positive integer"):
            ReasoningStep(
                step_number=0,
                action="Test action",
                rationale="Test rationale",
                result="Test result"
            )
    
    def test_reasoning_step_to_dict(self):
        """Test reasoning step serialization to dictionary."""
        step = ReasoningStep(
            step_number=1,
            action="Execute code",
            rationale="Need to calculate statistics",
            result="Calculated mean and std dev",
            tool_used=ToolType.CODE_EXECUTION,
            execution_time=2.5
        )
        
        step_dict = step.to_dict()
        
        assert step_dict['step_number'] == 1
        assert step_dict['action'] == "Execute code"
        assert step_dict['tool_used'] == "code_execution"
        assert step_dict['execution_time'] == 2.5


class TestSource:
    """Test cases for Source model."""
    
    def test_source_creation_valid(self):
        """Test valid source creation."""
        source = Source(
            source_id="src-1",
            source_type=SourceType.DOCUMENT,
            title="Research Paper on AI",
            authors=["Dr. Smith", "Dr. Jones"],
            relevance_score=0.9
        )
        
        assert source.source_id == "src-1"
        assert source.source_type == SourceType.DOCUMENT
        assert source.title == "Research Paper on AI"
        assert source.relevance_score == 0.9
    
    def test_source_validation_invalid_relevance_score(self):
        """Test source validation with invalid relevance score."""
        with pytest.raises(ValidationError, match="Relevance score must be a number between 0.0 and 1.0"):
            Source(
                source_id="src-1",
                source_type=SourceType.WEB,
                title="Web Article",
                relevance_score=1.5
            )
    
    def test_source_validation_invalid_url(self):
        """Test source validation with invalid URL."""
        with pytest.raises(ValidationError, match="URL must be a valid URL"):
            Source(
                source_id="src-1",
                source_type=SourceType.WEB,
                title="Web Article",
                url="not-a-valid-url"
            )
    
    def test_source_to_dict(self):
        """Test source serialization to dictionary."""
        pub_date = datetime(2024, 1, 1)
        source = Source(
            source_id="src-1",
            source_type=SourceType.WEB,
            title="Web Article",
            url="https://example.com/article",
            authors=["Author One"],
            publication_date=pub_date,
            relevance_score=0.8
        )
        
        source_dict = source.to_dict()
        
        assert source_dict['source_id'] == "src-1"
        assert source_dict['source_type'] == "web"
        assert source_dict['url'] == "https://example.com/article"
        assert source_dict['publication_date'] == "2024-01-01T00:00:00"


class TestToolInvocation:
    """Test cases for ToolInvocation model."""
    
    def test_tool_invocation_creation_valid(self):
        """Test valid tool invocation creation."""
        invocation = ToolInvocation(
            invocation_id="inv-1",
            tool_name=ToolType.WEB_SEARCH,
            parameters={"query": "AI research"},
            result={"results": ["result1", "result2"]},
            execution_time=1.5,
            success=True
        )
        
        assert invocation.invocation_id == "inv-1"
        assert invocation.tool_name == ToolType.WEB_SEARCH
        assert invocation.parameters == {"query": "AI research"}
        assert invocation.success is True
        assert invocation.execution_time == 1.5
    
    def test_tool_invocation_validation_negative_time(self):
        """Test tool invocation validation with negative execution time."""
        with pytest.raises(ValidationError, match="Execution time must be a non-negative number"):
            ToolInvocation(
                invocation_id="inv-1",
                tool_name=ToolType.CODE_EXECUTION,
                parameters={},
                result={},
                execution_time=-1.0,
                success=False
            )
    
    def test_tool_invocation_to_dict(self):
        """Test tool invocation serialization to dictionary."""
        invocation = ToolInvocation(
            invocation_id="inv-1",
            tool_name=ToolType.CROSS_LIBRARY_ANALYSIS,
            parameters={"analysis_type": "themes"},
            result={"themes": ["theme1", "theme2"]},
            execution_time=3.2,
            success=True,
            error_message=None
        )
        
        inv_dict = invocation.to_dict()
        
        assert inv_dict['invocation_id'] == "inv-1"
        assert inv_dict['tool_name'] == "cross_library_analysis"
        assert inv_dict['parameters'] == {"analysis_type": "themes"}
        assert inv_dict['execution_time'] == 3.2


class TestAgentResponse:
    """Test cases for AgentResponse model."""
    
    def test_agent_response_creation_valid(self):
        """Test valid agent response creation."""
        step = ReasoningStep(
            step_number=1,
            action="Search",
            rationale="Need info",
            result="Found results"
        )
        
        source = Source(
            source_id="src-1",
            source_type=SourceType.DOCUMENT,
            title="Test Document"
        )
        
        tool = ToolInvocation(
            invocation_id="inv-1",
            tool_name=ToolType.WEB_SEARCH,
            parameters={},
            result={},
            execution_time=1.0,
            success=True
        )
        
        response = AgentResponse(
            response_id="resp-1",
            query_id="query-1",
            final_answer="This is the final answer",
            reasoning_steps=[step],
            sources_used=[source],
            tools_invoked=[tool],
            confidence_score=0.9,
            total_processing_time=5.0
        )
        
        assert response.response_id == "resp-1"
        assert response.query_id == "query-1"
        assert response.final_answer == "This is the final answer"
        assert len(response.reasoning_steps) == 1
        assert len(response.sources_used) == 1
        assert len(response.tools_invoked) == 1
        assert response.confidence_score == 0.9
    
    def test_agent_response_validation_invalid_confidence(self):
        """Test agent response validation with invalid confidence score."""
        with pytest.raises(ValidationError, match="Confidence score must be a number between 0.0 and 1.0"):
            AgentResponse(
                response_id="resp-1",
                query_id="query-1",
                final_answer="Answer",
                confidence_score=1.5
            )
    
    def test_agent_response_add_methods(self):
        """Test agent response add methods."""
        response = AgentResponse(
            response_id="resp-1",
            query_id="query-1",
            final_answer="Answer"
        )
        
        step = ReasoningStep(
            step_number=1,
            action="Test",
            rationale="Test",
            result="Test"
        )
        
        source = Source(
            source_id="src-1",
            source_type=SourceType.WEB,
            title="Test"
        )
        
        tool = ToolInvocation(
            invocation_id="inv-1",
            tool_name=ToolType.CODE_EXECUTION,
            parameters={},
            result={},
            execution_time=1.0,
            success=True
        )
        
        response.add_reasoning_step(step)
        response.add_source(source)
        response.add_tool_invocation(tool)
        
        assert len(response.reasoning_steps) == 1
        assert len(response.sources_used) == 1
        assert len(response.tools_invoked) == 1


class TestValidationFunctions:
    """Test cases for validation functions."""
    
    def test_validate_document_valid(self):
        """Test validation of valid document."""
        doc = Document(
            id="test-doc-1",
            title="Test Document",
            authors=["Author One"],
            publication_date=datetime.now() - timedelta(days=1),
            content="Test content"
        )
        
        assert validate_document(doc) is True
    
    def test_validate_document_invalid_type(self):
        """Test validation with invalid document type."""
        with pytest.raises(ValidationError, match="Input must be a Document instance"):
            validate_document("not a document")
    
    def test_validate_query_valid(self):
        """Test validation of valid query."""
        intent = QueryIntent(primary_intent=QueryIntentType.SEARCH)
        query = ResearchQuery(
            query_id="query-1",
            user_id="user-1",
            original_text="Test query",
            processed_intent=intent,
            session_id="session-123"
        )
        
        assert validate_query(query) is True
    
    def test_validate_document_chunk_valid(self):
        """Test validation of valid document chunk."""
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="Test content"
        )
        
        assert validate_document_chunk(chunk) is True


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_create_document_id(self):
        """Test document ID creation."""
        doc_id = create_document_id("Test Title", ["Author One", "Author Two"])
        
        assert doc_id.startswith("doc_")
        assert len(doc_id) == 16  # "doc_" + 12 character hash
    
    def test_create_chunk_id(self):
        """Test chunk ID creation."""
        chunk_id = create_chunk_id("doc-123", 5)
        
        assert chunk_id == "doc-123_chunk_0005"
    
    def test_create_query_id(self):
        """Test query ID creation."""
        query_id = create_query_id()
        
        assert query_id.startswith("query_")
        assert len(query_id) == 18  # "query_" + 12 character hex
    
    def test_create_basic_document(self):
        """Test basic document creation utility."""
        doc = create_basic_document(
            title="Test Document",
            authors=["Author One"],
            content="Test content",
            document_type=DocumentType.PDF
        )
        
        assert doc.title == "Test Document"
        assert doc.authors == ["Author One"]
        assert doc.content == "Test content"
        assert doc.document_type == DocumentType.PDF
        assert doc.id.startswith("doc_")
    
    def test_create_basic_query(self):
        """Test basic query creation utility."""
        query = create_basic_query(
            user_id="user-123",
            query_text="What is AI?",
            session_id="session-456"
        )
        
        assert query.user_id == "user-123"
        assert query.original_text == "What is AI?"
        assert query.session_id == "session-456"
        assert query.processed_intent.primary_intent == QueryIntentType.SEARCH
        assert query.query_id.startswith("query_")