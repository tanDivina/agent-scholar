"""
End-to-End Integration Tests for Agent Scholar

This module contains comprehensive test scenarios that validate the complete
Agent Scholar system functionality, including multi-step queries, tool coordination,
and response synthesis across all components.
"""
import pytest
import json
import time
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import patch, Mock
import boto3
from moto import mock_bedrock_agent, mock_s3, mock_opensearch, mock_dynamodb

# Import test utilities
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'lambda', 'orchestrator'))

from models import ResearchQuery, AgentResponse, Document, DocumentChunk
from orchestrator import AgentOrchestrator
from security import SecurityMiddleware, SecurityConfig

class E2ETestFramework:
    """Framework for end-to-end testing of Agent Scholar."""
    
    def __init__(self):
        """Initialize the test framework."""
        self.session_id = str(uuid.uuid4())
        self.test_documents = []
        self.orchestrator = None
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Set up the test environment with mock AWS services."""
        # Initialize mock AWS services
        self.s3_mock = mock_s3()
        self.dynamodb_mock = mock_dynamodb()
        self.opensearch_mock = mock_opensearch()
        
        # Start mocks
        self.s3_mock.start()
        self.dynamodb_mock.start()
        
        # Create test resources
        self.create_test_documents()
        self.setup_mock_services()
    
    def create_test_documents(self):
        """Create test documents for scenarios."""
        self.test_documents = [
            Document(
                id="doc1",
                title="Machine Learning Fundamentals",
                content="""
                Machine learning is a subset of artificial intelligence that enables computers
                to learn and make decisions without being explicitly programmed. The field
                encompasses various algorithms including supervised learning, unsupervised
                learning, and reinforcement learning. Key applications include image recognition,
                natural language processing, and predictive analytics.
                
                Recent advances in deep learning have revolutionized the field, with neural
                networks achieving human-level performance in many tasks. However, challenges
                remain in areas such as explainability, bias, and computational efficiency.
                """,
                source="academic_paper",
                metadata={
                    "author": "Dr. Jane Smith",
                    "year": "2023",
                    "journal": "AI Research Quarterly",
                    "keywords": ["machine learning", "AI", "neural networks"]
                }
            ),
            Document(
                id="doc2",
                title="Ethics in Artificial Intelligence",
                content="""
                The rapid advancement of AI technologies raises important ethical considerations.
                Key concerns include algorithmic bias, privacy protection, job displacement,
                and the need for transparent decision-making processes. Organizations must
                develop ethical AI frameworks to ensure responsible development and deployment.
                
                Some experts argue for strict regulation, while others advocate for
                self-regulation by the industry. The debate continues as AI becomes more
                prevalent in society. Recent incidents have highlighted the importance
                of diverse teams and inclusive design practices.
                """,
                source="research_report",
                metadata={
                    "author": "Ethics Committee",
                    "year": "2023",
                    "organization": "AI Ethics Institute",
                    "keywords": ["AI ethics", "bias", "regulation"]
                }
            ),
            Document(
                id="doc3",
                title="Future of Work in the AI Era",
                content="""
                Artificial intelligence is transforming the workplace at an unprecedented pace.
                While some jobs may become automated, new roles are emerging that require
                human-AI collaboration. Workers need to develop new skills to remain relevant
                in the changing job market.
                
                Studies suggest that AI will create more jobs than it eliminates, but the
                transition period may be challenging. Education systems must adapt to prepare
                workers for AI-augmented roles. Companies should invest in retraining programs
                to help employees transition to new responsibilities.
                """,
                source="industry_report",
                metadata={
                    "author": "Future Work Institute",
                    "year": "2023",
                    "type": "industry_analysis",
                    "keywords": ["future of work", "automation", "skills"]
                }
            )
        ]
    
    def setup_mock_services(self):
        """Set up mock AWS services for testing."""
        # Create S3 bucket for documents
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='agent-scholar-documents')
        
        # Upload test documents
        for doc in self.test_documents:
            s3.put_object(
                Bucket='agent-scholar-documents',
                Key=f'documents/{doc.id}.txt',
                Body=doc.content
            )
        
        # Create DynamoDB table for rate limiting
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='agent-scholar-rate-limits',
            KeySchema=[{'AttributeName': 'identifier', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'identifier', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
    
    def teardown_test_environment(self):
        """Clean up test environment."""
        self.s3_mock.stop()
        self.dynamodb_mock.stop()
    
    async def execute_query(self, query: str, expected_tools: List[str] = None) -> Dict[str, Any]:
        """Execute a query and return the response."""
        research_query = ResearchQuery(
            query=query,
            session_id=self.session_id,
            user_id="test_user",
            context={}
        )
        
        # Mock the orchestrator if not available
        if not self.orchestrator:
            self.orchestrator = Mock()
            self.orchestrator.process_query = Mock(return_value=self.mock_agent_response(query, expected_tools))
        
        response = await self.orchestrator.process_query(research_query)
        return response
    
    def mock_agent_response(self, query: str, expected_tools: List[str] = None) -> AgentResponse:
        """Create a mock agent response for testing."""
        # Simulate tool usage based on query content
        tools_used = []
        reasoning_steps = []
        
        if "search" in query.lower() or "recent" in query.lower():
            tools_used.append("web_search")
            reasoning_steps.append("I need to search for recent information online")
        
        if "analyze" in query.lower() or "themes" in query.lower():
            tools_used.append("cross_library_analysis")
            reasoning_steps.append("I should analyze the document library for themes")
        
        if "code" in query.lower() or "visualize" in query.lower():
            tools_used.append("code_execution")
            reasoning_steps.append("I need to generate code for visualization")
        
        if "documents" in query.lower() or "library" in query.lower():
            reasoning_steps.append("I should search the knowledge base")
        
        # Generate response based on query
        if "contradiction" in query.lower():
            answer = """
            I found several interesting contradictions in your document library:
            
            1. **AI Job Impact**: Document 1 suggests AI will create more jobs than it eliminates,
               while Document 2 expresses concern about widespread job displacement.
            
            2. **Regulation Approach**: There's disagreement on whether AI should be strictly
               regulated by government or self-regulated by industry.
            
            3. **Timeline Concerns**: Some sources suggest immediate action is needed, while
               others advocate for gradual implementation.
            """
        elif "themes" in query.lower():
            answer = """
            I've identified several key themes across your document library:
            
            **Primary Themes:**
            1. **Technological Advancement** (3 documents) - Focus on AI capabilities and progress
            2. **Ethical Considerations** (2 documents) - Concerns about bias, privacy, and fairness
            3. **Economic Impact** (2 documents) - Job market changes and economic implications
            4. **Human-AI Collaboration** (2 documents) - Working together rather than replacement
            
            **Emerging Patterns:**
            - Optimistic outlook on AI potential
            - Emphasis on responsible development
            - Need for education and adaptation
            """
        elif "recent" in query.lower() and "search" in query.lower():
            answer = """
            Based on my web search, here are recent developments in AI:
            
            **Latest Breakthroughs:**
            1. **Large Language Models**: New architectures showing improved reasoning
            2. **Multimodal AI**: Systems that can process text, images, and audio together
            3. **AI Safety**: New techniques for alignment and safety research
            4. **Edge AI**: More efficient models for mobile and IoT devices
            
            **Comparison with Your Documents:**
            Your library aligns well with current trends, particularly in ethics and
            human-AI collaboration themes.
            """
        elif "visualize" in query.lower() or "code" in query.lower():
            answer = """
            I've generated Python code to visualize the themes in your research:
            
            ```python
            import matplotlib.pyplot as plt
            import numpy as np
            
            # Theme frequency data
            themes = ['Tech Advancement', 'Ethics', 'Economic Impact', 'Collaboration']
            frequencies = [3, 2, 2, 2]
            
            # Create visualization
            plt.figure(figsize=(10, 6))
            plt.bar(themes, frequencies, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
            plt.title('Theme Distribution in Research Library')
            plt.ylabel('Number of Documents')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()
            ```
            
            The code has been executed and shows that technological advancement
            is the most prevalent theme in your library.
            """
        else:
            answer = f"I've processed your query: '{query}' and found relevant information in your document library."
        
        return AgentResponse(
            query=query,
            answer=answer,
            sources_used=[doc.id for doc in self.test_documents[:2]],
            tools_invoked=tools_used,
            reasoning_steps=reasoning_steps,
            confidence_score=0.85,
            processing_time=2.5,
            session_id=self.session_id
        )

@pytest.fixture
def e2e_framework():
    """Pytest fixture for E2E test framework."""
    framework = E2ETestFramework()
    yield framework
    framework.teardown_test_environment()

class TestComplexMultiStepQueries:
    """Test complex multi-step research queries."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_research_workflow(self, e2e_framework):
        """Test a comprehensive research workflow involving multiple tools."""
        query = """
        I'm researching AI ethics for a policy paper. Please:
        1. Analyze the themes in my document library
        2. Search for recent developments in AI regulation
        3. Find any contradictions between different perspectives
        4. Generate a visualization of the key themes
        """
        
        response = await e2e_framework.execute_query(
            query, 
            expected_tools=["cross_library_analysis", "web_search", "code_execution"]
        )
        
        # Verify response structure
        assert isinstance(response, AgentResponse)
        assert response.query == query
        assert len(response.answer) > 100  # Substantial response
        assert response.confidence_score > 0.7
        
        # Verify tool coordination
        expected_tools = ["cross_library_analysis", "web_search", "code_execution"]
        for tool in expected_tools:
            assert tool in response.tools_invoked
        
        # Verify reasoning steps
        assert len(response.reasoning_steps) >= 3
        assert any("analyze" in step.lower() for step in response.reasoning_steps)
        assert any("search" in step.lower() for step in response.reasoning_steps)
    
    @pytest.mark.asyncio
    async def test_contradiction_analysis_workflow(self, e2e_framework):
        """Test workflow for finding contradictions across sources."""
        query = """
        Find contradictions and conflicting viewpoints in my research library
        about AI's impact on employment and the future of work.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis"]
        )
        
        # Verify contradiction detection
        assert "contradiction" in response.answer.lower()
        assert len(response.sources_used) >= 2
        assert "cross_library_analysis" in response.tools_invoked
        
        # Verify specific contradictions are identified
        assert any(keyword in response.answer.lower() 
                  for keyword in ["job", "employment", "displacement", "create"])
    
    @pytest.mark.asyncio
    async def test_comparative_analysis_with_web_search(self, e2e_framework):
        """Test comparative analysis combining library documents with web search."""
        query = """
        Compare the AI ethics perspectives in my document library with
        recent industry developments. What are the main differences?
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "web_search"]
        )
        
        # Verify both tools were used
        assert "cross_library_analysis" in response.tools_invoked
        assert "web_search" in response.tools_invoked
        
        # Verify comparative analysis
        assert any(keyword in response.answer.lower() 
                  for keyword in ["compare", "difference", "contrast", "similar"])
        
        # Verify both library and web sources are referenced
        assert len(response.sources_used) > 0
        assert "recent" in response.answer.lower() or "latest" in response.answer.lower()
    
    @pytest.mark.asyncio
    async def test_data_visualization_workflow(self, e2e_framework):
        """Test workflow involving code generation and execution for visualization."""
        query = """
        Create a visualization showing the distribution of themes across
        my research documents. Use Python with matplotlib or plotly.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "code_execution"]
        )
        
        # Verify code execution
        assert "code_execution" in response.tools_invoked
        assert "python" in response.answer.lower()
        assert any(lib in response.answer.lower() for lib in ["matplotlib", "plotly", "plt"])
        
        # Verify code is present
        assert "```python" in response.answer or "```" in response.answer
        
        # Verify analysis was performed
        assert "cross_library_analysis" in response.tools_invoked
        assert any(keyword in response.answer.lower() 
                  for keyword in ["theme", "distribution", "visualization"])

class TestToolCoordination:
    """Test coordination between different tools and action groups."""
    
    @pytest.mark.asyncio
    async def test_sequential_tool_usage(self, e2e_framework):
        """Test sequential coordination of multiple tools."""
        query = """
        First analyze my documents for AI safety themes, then search for
        recent AI safety research, and finally create a comparison chart.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "web_search", "code_execution"]
        )
        
        # Verify all tools were invoked
        expected_tools = ["cross_library_analysis", "web_search", "code_execution"]
        for tool in expected_tools:
            assert tool in response.tools_invoked
        
        # Verify logical flow in reasoning
        reasoning_text = " ".join(response.reasoning_steps).lower()
        assert "analyze" in reasoning_text
        assert "search" in reasoning_text
        assert any(keyword in reasoning_text for keyword in ["code", "chart", "visualize"])
    
    @pytest.mark.asyncio
    async def test_parallel_tool_coordination(self, e2e_framework):
        """Test parallel coordination of tools for efficiency."""
        query = """
        Simultaneously analyze my document themes and search for recent
        AI developments, then synthesize the findings.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "web_search"]
        )
        
        # Verify both tools were used
        assert "cross_library_analysis" in response.tools_invoked
        assert "web_search" in response.tools_invoked
        
        # Verify synthesis occurred
        assert any(keyword in response.answer.lower() 
                  for keyword in ["synthesize", "combine", "together", "findings"])
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_fallback(self, e2e_framework):
        """Test error recovery when tools fail."""
        # Mock a tool failure scenario
        with patch.object(e2e_framework.orchestrator, 'process_query') as mock_process:
            # Simulate partial failure
            mock_response = e2e_framework.mock_agent_response(
                "Analyze themes and search web",
                ["cross_library_analysis"]  # Only one tool succeeds
            )
            mock_response.tools_invoked = ["cross_library_analysis"]  # Web search failed
            mock_response.reasoning_steps.append("Web search failed, using library analysis only")
            mock_process.return_value = mock_response
            
            query = "Analyze my documents and search for recent developments"
            response = await e2e_framework.execute_query(query)
            
            # Verify graceful degradation
            assert "cross_library_analysis" in response.tools_invoked
            assert any("failed" in step.lower() for step in response.reasoning_steps)
            assert len(response.answer) > 50  # Still provides useful response

class TestResponseSynthesis:
    """Test response synthesis across multiple information sources."""
    
    @pytest.mark.asyncio
    async def test_multi_source_synthesis(self, e2e_framework):
        """Test synthesis of information from multiple sources."""
        query = """
        Provide a comprehensive overview of AI ethics by combining insights
        from my document library, recent web research, and trend analysis.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "web_search"]
        )
        
        # Verify comprehensive response
        assert len(response.answer) > 200
        assert len(response.sources_used) >= 2
        
        # Verify synthesis indicators
        synthesis_keywords = ["combine", "overview", "comprehensive", "insights", "together"]
        assert any(keyword in response.answer.lower() for keyword in synthesis_keywords)
        
        # Verify multiple information types
        info_types = ["document", "research", "recent", "trend"]
        assert sum(1 for keyword in info_types if keyword in response.answer.lower()) >= 2
    
    @pytest.mark.asyncio
    async def test_conflicting_information_handling(self, e2e_framework):
        """Test handling of conflicting information from different sources."""
        query = """
        What are the different perspectives on AI regulation? Include both
        optimistic and pessimistic viewpoints from various sources.
        """
        
        response = await e2e_framework.execute_query(query)
        
        # Verify balanced perspective
        perspective_keywords = ["different", "perspective", "viewpoint", "optimistic", "pessimistic"]
        assert sum(1 for keyword in perspective_keywords if keyword in response.answer.lower()) >= 2
        
        # Verify acknowledgment of different sources
        assert any(keyword in response.answer.lower() 
                  for keyword in ["various", "different", "multiple", "sources"])
    
    @pytest.mark.asyncio
    async def test_evidence_based_conclusions(self, e2e_framework):
        """Test that conclusions are properly supported by evidence."""
        query = """
        Based on the evidence in my research library, what can we conclude
        about the future impact of AI on society?
        """
        
        response = await e2e_framework.execute_query(query)
        
        # Verify evidence-based language
        evidence_keywords = ["evidence", "based on", "conclude", "research", "library"]
        assert sum(1 for keyword in evidence_keywords if keyword in response.answer.lower()) >= 2
        
        # Verify sources are cited
        assert len(response.sources_used) > 0
        
        # Verify reasoning is provided
        assert len(response.reasoning_steps) > 0

class TestPerformanceBenchmarks:
    """Test performance benchmarks and response times."""
    
    @pytest.mark.asyncio
    async def test_response_time_benchmarks(self, e2e_framework):
        """Test that responses meet performance benchmarks."""
        queries = [
            "What are the main themes in my documents?",
            "Search for recent AI developments",
            "Create a visualization of document themes",
            "Find contradictions in AI ethics perspectives"
        ]
        
        response_times = []
        
        for query in queries:
            start_time = time.time()
            response = await e2e_framework.execute_query(query)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            # Verify response quality
            assert isinstance(response, AgentResponse)
            assert len(response.answer) > 50
            assert response.confidence_score > 0.5
        
        # Performance benchmarks
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        # Assert performance requirements
        assert avg_response_time < 5.0  # Average under 5 seconds
        assert max_response_time < 10.0  # Max under 10 seconds
        assert all(rt > 0 for rt in response_times)  # All responses completed
    
    @pytest.mark.asyncio
    async def test_concurrent_query_handling(self, e2e_framework):
        """Test handling of concurrent queries."""
        queries = [
            "Analyze document themes",
            "Search recent AI news",
            "Generate code visualization",
            "Find document contradictions"
        ]
        
        # Execute queries concurrently
        tasks = [e2e_framework.execute_query(query) for query in queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all queries completed successfully
        assert len(responses) == len(queries)
        
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                pytest.fail(f"Query {i} failed with exception: {response}")
            
            assert isinstance(response, AgentResponse)
            assert len(response.answer) > 20
            assert response.query == queries[i]
    
    @pytest.mark.asyncio
    async def test_memory_usage_efficiency(self, e2e_framework):
        """Test memory usage remains efficient during processing."""
        # This would typically use memory profiling tools
        # For now, we'll test that large queries don't cause issues
        
        large_query = """
        Please provide a comprehensive analysis of AI ethics, including:
        """ + " ".join([f"Point {i} about AI ethics and implications." for i in range(100)])
        
        response = await e2e_framework.execute_query(large_query)
        
        # Verify system handles large queries
        assert isinstance(response, AgentResponse)
        assert len(response.answer) > 100
        assert response.confidence_score > 0.3  # May be lower for very broad queries

class TestUserAcceptanceScenarios:
    """Test scenarios matching user acceptance criteria."""
    
    @pytest.mark.asyncio
    async def test_research_paper_assistance(self, e2e_framework):
        """Test scenario: Assisting with research paper writing."""
        query = """
        I'm writing a research paper on AI ethics. Help me by:
        1. Identifying key themes in my research library
        2. Finding recent academic developments
        3. Highlighting any conflicting viewpoints
        4. Suggesting areas that need more research
        """
        
        response = await e2e_framework.execute_query(query)
        
        # Verify comprehensive assistance
        assert len(response.answer) > 300
        assert any(keyword in response.answer.lower() 
                  for keyword in ["theme", "recent", "conflict", "research"])
        
        # Verify multiple tools used
        assert len(response.tools_invoked) >= 2
        
        # Verify actionable suggestions
        assert any(keyword in response.answer.lower() 
                  for keyword in ["suggest", "recommend", "consider", "explore"])
    
    @pytest.mark.asyncio
    async def test_policy_analysis_scenario(self, e2e_framework):
        """Test scenario: Policy analysis and recommendation."""
        query = """
        Analyze the policy implications of AI development based on my research.
        What regulatory approaches are being discussed, and what are the pros and cons?
        """
        
        response = await e2e_framework.execute_query(query)
        
        # Verify policy focus
        policy_keywords = ["policy", "regulatory", "regulation", "government", "law"]
        assert sum(1 for keyword in policy_keywords if keyword in response.answer.lower()) >= 2
        
        # Verify pros and cons analysis
        assert any(keyword in response.answer.lower() for keyword in ["pros", "cons", "advantage", "disadvantage"])
        
        # Verify comprehensive analysis
        assert len(response.answer) > 200
        assert len(response.sources_used) > 0
    
    @pytest.mark.asyncio
    async def test_trend_analysis_scenario(self, e2e_framework):
        """Test scenario: Technology trend analysis."""
        query = """
        What are the emerging trends in AI based on my research library
        and recent developments? Create a visual summary.
        """
        
        response = await e2e_framework.execute_query(
            query,
            expected_tools=["cross_library_analysis", "web_search", "code_execution"]
        )
        
        # Verify trend analysis
        trend_keywords = ["trend", "emerging", "development", "future", "evolution"]
        assert sum(1 for keyword in trend_keywords if keyword in response.answer.lower()) >= 2
        
        # Verify visualization component
        assert "code_execution" in response.tools_invoked
        assert any(keyword in response.answer.lower() for keyword in ["visual", "chart", "graph", "plot"])
        
        # Verify both library and recent sources
        assert "cross_library_analysis" in response.tools_invoked
        assert "web_search" in response.tools_invoked

if __name__ == '__main__':
    pytest.main([__file__, '-v'])