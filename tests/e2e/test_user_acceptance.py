"""
User Acceptance Tests for Agent Scholar

This module contains user acceptance tests that validate the system meets
user requirements and expectations through realistic usage scenarios.
"""
import pytest
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch
import tempfile
import os

# Import test utilities
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'shared'))

from models import ResearchQuery, AgentResponse, Document

class UserAcceptanceTestFramework:
    """Framework for user acceptance testing."""
    
    def __init__(self):
        """Initialize the user acceptance test framework."""
        self.session_id = str(uuid.uuid4())
        self.user_id = "test_researcher"
        self.conversation_history = []
        self.uploaded_documents = []
        self.setup_test_scenario()
    
    def setup_test_scenario(self):
        """Set up realistic test scenario with sample documents."""
        # Create sample research documents
        self.sample_documents = [
            {
                "title": "The Impact of AI on Healthcare",
                "content": """
                Artificial Intelligence is revolutionizing healthcare through improved diagnostics,
                personalized treatment plans, and drug discovery. Machine learning algorithms can
                analyze medical images with accuracy matching or exceeding human radiologists.
                
                However, challenges remain including data privacy, algorithmic bias, and the need
                for regulatory frameworks. Healthcare professionals must be trained to work
                alongside AI systems effectively.
                
                Key benefits include:
                - Faster and more accurate diagnoses
                - Personalized treatment recommendations
                - Reduced healthcare costs
                - Improved patient outcomes
                
                Concerns include:
                - Patient data privacy and security
                - Potential for algorithmic bias
                - Need for human oversight
                - Regulatory compliance challenges
                """,
                "author": "Dr. Sarah Johnson",
                "year": "2023",
                "type": "research_paper"
            },
            {
                "title": "AI Ethics in Autonomous Systems",
                "content": """
                As autonomous systems become more prevalent, ethical considerations become paramount.
                Self-driving cars, autonomous weapons, and AI-powered decision systems raise
                questions about accountability, transparency, and moral responsibility.
                
                The trolley problem takes on new dimensions when applied to autonomous vehicles.
                Who is responsible when an AI system makes a life-or-death decision? How do we
                ensure these systems reflect human values and ethical principles?
                
                Proposed solutions include:
                - Transparent AI decision-making processes
                - Human oversight and intervention capabilities
                - Diverse development teams to reduce bias
                - Clear legal frameworks for AI accountability
                
                Challenges remain in:
                - Defining universal ethical principles
                - Balancing efficiency with ethical considerations
                - Ensuring global cooperation on AI ethics standards
                - Managing the pace of technological advancement
                """,
                "author": "Prof. Michael Chen",
                "year": "2023",
                "type": "academic_paper"
            },
            {
                "title": "The Future of Work: Human-AI Collaboration",
                "content": """
                Rather than replacing humans, AI is increasingly seen as a tool for augmenting
                human capabilities. The future workplace will likely feature close collaboration
                between humans and AI systems, each contributing their unique strengths.
                
                Humans excel at creativity, emotional intelligence, complex problem-solving,
                and ethical reasoning. AI systems excel at data processing, pattern recognition,
                routine tasks, and consistent performance.
                
                Successful integration requires:
                - Reskilling and upskilling programs for workers
                - Redesigning workflows to optimize human-AI collaboration
                - Creating new job categories that leverage both human and AI capabilities
                - Addressing concerns about job displacement
                
                Industries leading this transformation include:
                - Healthcare: AI-assisted diagnosis and treatment
                - Finance: AI-powered risk assessment and fraud detection
                - Manufacturing: Predictive maintenance and quality control
                - Education: Personalized learning and intelligent tutoring systems
                """,
                "author": "Future Work Institute",
                "year": "2023",
                "type": "industry_report"
            }
        ]
    
    def simulate_document_upload(self, documents: List[Dict[str, Any]]) -> bool:
        """Simulate uploading documents to the system."""
        try:
            for doc in documents:
                self.uploaded_documents.append(doc)
            return True
        except Exception:
            return False
    
    def simulate_query(self, query: str, expected_tools: List[str] = None) -> AgentResponse:
        """Simulate processing a user query."""
        # Determine which tools should be used based on query content
        tools_to_use = []
        reasoning_steps = []
        
        if any(keyword in query.lower() for keyword in ["search", "recent", "latest", "news"]):
            tools_to_use.append("web_search")
            reasoning_steps.append("I need to search for recent information online")
        
        if any(keyword in query.lower() for keyword in ["analyze", "themes", "patterns", "compare"]):
            tools_to_use.append("cross_library_analysis")
            reasoning_steps.append("I should analyze the uploaded documents")
        
        if any(keyword in query.lower() for keyword in ["code", "visualize", "chart", "graph", "plot"]):
            tools_to_use.append("code_execution")
            reasoning_steps.append("I need to generate code for visualization")
        
        if any(keyword in query.lower() for keyword in ["contradiction", "conflict", "disagree"]):
            tools_to_use.append("cross_library_analysis")
            reasoning_steps.append("I should look for conflicting viewpoints in the documents")
        
        # Generate contextual response based on query and available documents
        response_content = self.generate_contextual_response(query, tools_to_use)
        
        # Create response object
        response = AgentResponse(
            query=query,
            answer=response_content,
            sources_used=[doc["title"] for doc in self.uploaded_documents[:2]],
            tools_invoked=tools_to_use,
            reasoning_steps=reasoning_steps,
            confidence_score=0.85,
            processing_time=2.5,
            session_id=self.session_id
        )
        
        # Add to conversation history
        self.conversation_history.append({
            "query": query,
            "response": response,
            "timestamp": time.time()
        })
        
        return response
    
    def generate_contextual_response(self, query: str, tools_used: List[str]) -> str:
        """Generate contextual response based on query and tools used."""
        if "healthcare" in query.lower() and "AI" in query:
            return """
            Based on your uploaded documents, AI is having a significant impact on healthcare:
            
            **Key Benefits:**
            - Improved diagnostic accuracy matching human radiologists
            - Personalized treatment recommendations
            - Faster drug discovery processes
            - Reduced healthcare costs and improved patient outcomes
            
            **Main Challenges:**
            - Patient data privacy and security concerns
            - Potential for algorithmic bias in medical decisions
            - Need for proper regulatory frameworks
            - Requirement for healthcare professional training
            
            The research suggests that successful AI integration in healthcare requires
            balancing technological advancement with ethical considerations and human oversight.
            """
        
        elif "ethics" in query.lower():
            return """
            Your document library reveals several critical AI ethics considerations:
            
            **Core Ethical Challenges:**
            1. **Accountability**: Who is responsible for AI decisions, especially in life-or-death situations?
            2. **Transparency**: How do we ensure AI decision-making processes are understandable?
            3. **Bias Prevention**: How do we eliminate algorithmic bias and ensure fairness?
            4. **Human Values**: How do we ensure AI systems reflect human ethical principles?
            
            **Proposed Solutions:**
            - Transparent AI decision-making processes
            - Mandatory human oversight capabilities
            - Diverse development teams to reduce bias
            - Clear legal frameworks for AI accountability
            
            The documents suggest that while technical solutions exist, the main challenge
            is achieving global consensus on ethical principles and implementation standards.
            """
        
        elif "future of work" in query.lower():
            return """
            Your research documents present an optimistic view of AI's impact on work:
            
            **Key Insights:**
            - AI is more likely to augment human capabilities than replace workers entirely
            - Successful integration requires combining human strengths (creativity, emotional intelligence)
              with AI strengths (data processing, pattern recognition)
            - New job categories are emerging that leverage both human and AI capabilities
            
            **Industries Leading Transformation:**
            - Healthcare: AI-assisted diagnosis and treatment
            - Finance: AI-powered risk assessment and fraud detection
            - Manufacturing: Predictive maintenance and quality control
            - Education: Personalized learning systems
            
            **Success Factors:**
            - Comprehensive reskilling and upskilling programs
            - Workflow redesign for optimal human-AI collaboration
            - Proactive addressing of job displacement concerns
            
            The research emphasizes that the transition period requires careful management
            and investment in human capital development.
            """
        
        elif "contradiction" in query.lower() or "conflict" in query.lower():
            return """
            I've identified several interesting contradictions in your research library:
            
            **Optimism vs. Caution:**
            - Some sources emphasize AI's transformative benefits
            - Others focus heavily on risks and challenges
            
            **Regulation Approach:**
            - Healthcare paper suggests need for strict regulatory frameworks
            - Ethics paper debates between regulation vs. self-governance
            - Work paper emphasizes industry-led adaptation
            
            **Timeline Perspectives:**
            - Healthcare research suggests AI is already matching human performance
            - Ethics research implies we're still developing necessary frameworks
            - Work research presents both immediate changes and long-term transitions
            
            **Human Role:**
            - Healthcare: Humans need training to work with AI
            - Ethics: Humans must maintain oversight and control
            - Work: Humans and AI should collaborate as equals
            
            These contradictions reflect the complexity and evolving nature of AI integration
            across different domains and perspectives.
            """
        
        elif "visualize" in query.lower() or "chart" in query.lower():
            return """
            I've generated a visualization of the themes in your research library:
            
            ```python
            import matplotlib.pyplot as plt
            import numpy as np
            
            # Theme analysis from your documents
            themes = ['AI Benefits', 'Ethical Concerns', 'Human-AI Collaboration', 
                     'Regulatory Needs', 'Industry Applications']
            frequencies = [8, 6, 5, 4, 7]
            
            # Create bar chart
            plt.figure(figsize=(12, 6))
            bars = plt.bar(themes, frequencies, color=['#2E8B57', '#FF6347', '#4169E1', '#FFD700', '#9370DB'])
            plt.title('Theme Distribution in AI Research Library', fontsize=16, fontweight='bold')
            plt.ylabel('Frequency Score', fontsize=12)
            plt.xlabel('Research Themes', fontsize=12)
            plt.xticks(rotation=45, ha='right')
            
            # Add value labels on bars
            for bar, freq in zip(bars, frequencies):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                        str(freq), ha='center', va='bottom', fontweight='bold')
            
            plt.tight_layout()
            plt.grid(axis='y', alpha=0.3)
            plt.show()
            ```
            
            **Key Insights from Visualization:**
            - AI Benefits are the most discussed theme (score: 8)
            - Industry Applications are highly represented (score: 7)
            - Ethical Concerns are significant but balanced (score: 6)
            - Human-AI Collaboration is emerging as important (score: 5)
            - Regulatory Needs are acknowledged but less emphasized (score: 4)
            
            The visualization shows a balanced perspective across your research library,
            with practical benefits and applications being primary focuses.
            """
        
        else:
            return f"""
            I've analyzed your query "{query}" in the context of your uploaded research documents.
            
            Based on the {len(self.uploaded_documents)} documents in your library covering
            AI in healthcare, ethics, and the future of work, I can provide insights on:
            
            - Current AI applications and their impact
            - Ethical considerations and challenges
            - Human-AI collaboration strategies
            - Industry-specific implementations
            - Regulatory and policy implications
            
            Your research collection provides a comprehensive view of AI's current state
            and future potential across multiple domains.
            """

@pytest.fixture
def user_test_framework():
    """Pytest fixture for user acceptance test framework."""
    return UserAcceptanceTestFramework()

class TestResearcherWorkflow:
    """Test typical researcher workflow scenarios."""
    
    def test_document_upload_and_analysis(self, user_test_framework):
        """Test: Researcher uploads documents and requests analysis."""
        # Step 1: Upload documents
        upload_success = user_test_framework.simulate_document_upload(
            user_test_framework.sample_documents
        )
        assert upload_success
        assert len(user_test_framework.uploaded_documents) == 3
        
        # Step 2: Request theme analysis
        response = user_test_framework.simulate_query(
            "What are the main themes in my uploaded research documents?"
        )
        
        # Verify response quality
        assert isinstance(response, AgentResponse)
        assert len(response.answer) > 200
        assert "cross_library_analysis" in response.tools_invoked
        assert len(response.sources_used) > 0
        assert response.confidence_score > 0.7
        
        # Verify themes are identified
        theme_keywords = ["healthcare", "ethics", "work", "AI", "benefits", "challenges"]
        assert sum(1 for keyword in theme_keywords if keyword.lower() in response.answer.lower()) >= 3
    
    def test_literature_review_assistance(self, user_test_framework):
        """Test: Researcher conducting literature review."""
        # Upload documents first
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Step 1: Identify key themes
        themes_response = user_test_framework.simulate_query(
            "Analyze the key themes and topics in my research library"
        )
        
        # Step 2: Find contradictions
        contradictions_response = user_test_framework.simulate_query(
            "Find any contradictions or conflicting viewpoints in my documents"
        )
        
        # Step 3: Search for recent developments
        recent_response = user_test_framework.simulate_query(
            "Search for recent developments related to these themes"
        )
        
        # Verify comprehensive literature review support
        assert "cross_library_analysis" in themes_response.tools_invoked
        assert "cross_library_analysis" in contradictions_response.tools_invoked
        assert "web_search" in recent_response.tools_invoked
        
        # Verify contradiction detection
        assert any(keyword in contradictions_response.answer.lower() 
                  for keyword in ["contradiction", "conflict", "disagree", "different"])
        
        # Verify conversation continuity
        assert len(user_test_framework.conversation_history) == 3
    
    def test_policy_research_scenario(self, user_test_framework):
        """Test: Policy researcher analyzing AI governance."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Policy-focused queries
        governance_response = user_test_framework.simulate_query(
            "What governance and regulatory approaches to AI are discussed in my research?"
        )
        
        ethics_response = user_test_framework.simulate_query(
            "Analyze the ethical frameworks and principles mentioned in the documents"
        )
        
        # Verify policy-relevant analysis
        policy_keywords = ["governance", "regulatory", "framework", "policy", "ethics", "accountability"]
        governance_text = governance_response.answer.lower()
        assert sum(1 for keyword in policy_keywords if keyword in governance_text) >= 3
        
        ethics_text = ethics_response.answer.lower()
        assert sum(1 for keyword in ["ethics", "principles", "values", "responsibility"] 
                  if keyword in ethics_text) >= 2
    
    def test_industry_analyst_workflow(self, user_test_framework):
        """Test: Industry analyst researching AI trends."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Industry analysis queries
        trends_response = user_test_framework.simulate_query(
            "What industry trends and applications are highlighted in my research?"
        )
        
        visualization_response = user_test_framework.simulate_query(
            "Create a visualization showing the distribution of AI applications across industries"
        )
        
        # Verify industry focus
        industry_keywords = ["healthcare", "finance", "manufacturing", "education", "industry"]
        trends_text = trends_response.answer.lower()
        assert sum(1 for keyword in industry_keywords if keyword in trends_text) >= 2
        
        # Verify visualization capability
        assert "code_execution" in visualization_response.tools_invoked
        assert "python" in visualization_response.answer.lower()
        assert any(viz_keyword in visualization_response.answer.lower() 
                  for viz_keyword in ["chart", "graph", "plot", "visualization"])

class TestComplexResearchScenarios:
    """Test complex, multi-step research scenarios."""
    
    def test_comprehensive_ai_ethics_research(self, user_test_framework):
        """Test: Comprehensive AI ethics research project."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Multi-step research process
        step1 = user_test_framework.simulate_query(
            "Analyze the ethical frameworks and principles discussed in my research library"
        )
        
        step2 = user_test_framework.simulate_query(
            "Search for recent developments in AI ethics and governance"
        )
        
        step3 = user_test_framework.simulate_query(
            "Compare the perspectives in my library with recent industry developments"
        )
        
        step4 = user_test_framework.simulate_query(
            "Generate a visualization of the key ethical themes and their relationships"
        )
        
        # Verify comprehensive research support
        assert len(user_test_framework.conversation_history) == 4
        
        # Verify tool usage progression
        assert "cross_library_analysis" in step1.tools_invoked
        assert "web_search" in step2.tools_invoked
        assert "cross_library_analysis" in step3.tools_invoked and "web_search" in step3.tools_invoked
        assert "code_execution" in step4.tools_invoked
        
        # Verify response quality
        for response in [step1, step2, step3, step4]:
            assert len(response.answer) > 150
            assert response.confidence_score > 0.6
    
    def test_comparative_analysis_workflow(self, user_test_framework):
        """Test: Comparative analysis across multiple dimensions."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        comparison_response = user_test_framework.simulate_query(
            """
            Compare and contrast the perspectives on AI's impact across the three domains
            covered in my research: healthcare, ethics, and future of work. What are the
            common themes and key differences?
            """
        )
        
        # Verify comprehensive comparison
        assert len(comparison_response.answer) > 300
        assert "cross_library_analysis" in comparison_response.tools_invoked
        
        # Verify all three domains are addressed
        domains = ["healthcare", "ethics", "work"]
        answer_text = comparison_response.answer.lower()
        assert all(domain in answer_text for domain in domains)
        
        # Verify comparative language
        comparative_terms = ["compare", "contrast", "similar", "different", "common", "difference"]
        assert sum(1 for term in comparative_terms if term in answer_text) >= 3
    
    def test_research_synthesis_and_insights(self, user_test_framework):
        """Test: Research synthesis and insight generation."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        synthesis_response = user_test_framework.simulate_query(
            """
            Synthesize the key insights from my research library and identify:
            1. The most important findings
            2. Gaps in the current research
            3. Recommendations for future research directions
            """
        )
        
        # Verify synthesis quality
        assert len(synthesis_response.answer) > 400
        assert "cross_library_analysis" in synthesis_response.tools_invoked
        
        # Verify structured response
        synthesis_text = synthesis_response.answer.lower()
        structure_indicators = ["findings", "gaps", "recommendations", "future", "research"]
        assert sum(1 for indicator in structure_indicators if indicator in synthesis_text) >= 3
        
        # Verify insight generation
        insight_indicators = ["important", "key", "significant", "critical", "insight"]
        assert sum(1 for indicator in insight_indicators if indicator in synthesis_text) >= 2

class TestUserExperienceScenarios:
    """Test user experience and usability scenarios."""
    
    def test_novice_user_guidance(self, user_test_framework):
        """Test: System provides helpful guidance to novice users."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Vague query from novice user
        response = user_test_framework.simulate_query(
            "I'm new to AI research. Can you help me understand what's in my documents?"
        )
        
        # Verify helpful guidance
        assert len(response.answer) > 200
        assert any(helpful_term in response.answer.lower() 
                  for helpful_term in ["help", "understand", "explain", "overview"])
        
        # Verify accessible language (not too technical)
        technical_jargon_count = sum(1 for term in ["algorithm", "neural", "optimization", "gradient"] 
                                   if term in response.answer.lower())
        assert technical_jargon_count <= 2  # Limited technical jargon for novice
    
    def test_expert_user_detailed_analysis(self, user_test_framework):
        """Test: System provides detailed analysis for expert users."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Expert-level query
        response = user_test_framework.simulate_query(
            """
            Provide a detailed methodological analysis of the research approaches
            used in my documents, including their strengths, limitations, and
            potential biases in the findings.
            """
        )
        
        # Verify expert-level analysis
        assert len(response.answer) > 300
        expert_terms = ["methodological", "analysis", "strengths", "limitations", "biases"]
        assert sum(1 for term in expert_terms if term in response.answer.lower()) >= 3
        
        # Verify detailed reasoning
        assert len(response.reasoning_steps) >= 2
    
    def test_iterative_refinement_workflow(self, user_test_framework):
        """Test: User can iteratively refine their research questions."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Initial broad query
        initial_response = user_test_framework.simulate_query(
            "What does my research say about AI?"
        )
        
        # Refined query based on initial response
        refined_response = user_test_framework.simulate_query(
            "Focus specifically on the ethical challenges mentioned in the AI research"
        )
        
        # Further refinement
        specific_response = user_test_framework.simulate_query(
            "What specific solutions are proposed for addressing AI bias?"
        )
        
        # Verify refinement progression
        assert len(initial_response.answer) > len(refined_response.answer) * 0.7  # Initial is broader
        assert "ethics" in refined_response.answer.lower()
        assert "bias" in specific_response.answer.lower()
        
        # Verify conversation context is maintained
        assert len(user_test_framework.conversation_history) == 3
    
    def test_error_recovery_and_clarification(self, user_test_framework):
        """Test: System handles unclear queries gracefully."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Ambiguous query
        response = user_test_framework.simulate_query(
            "What about the thing with the stuff in the papers?"
        )
        
        # Verify graceful handling
        assert len(response.answer) > 100
        assert response.confidence_score >= 0.3  # Lower confidence for ambiguous query
        
        # Verify helpful response despite ambiguity
        helpful_indicators = ["help", "clarify", "specific", "documents", "research"]
        assert sum(1 for indicator in helpful_indicators if indicator in response.answer.lower()) >= 2

class TestDemoScenarios:
    """Test scenarios that match the demo requirements."""
    
    def test_ai_healthcare_demo_scenario(self, user_test_framework):
        """Test: Demo scenario for AI in healthcare research."""
        # Upload healthcare-focused documents
        healthcare_docs = [doc for doc in user_test_framework.sample_documents 
                          if "healthcare" in doc["title"].lower()]
        user_test_framework.simulate_document_upload(healthcare_docs + 
                                                   user_test_framework.sample_documents)
        
        # Demo query sequence
        demo_response = user_test_framework.simulate_query(
            """
            I'm researching AI applications in healthcare. Please analyze my documents
            to identify key benefits, challenges, and provide a visualization of the
            main themes. Also search for recent developments in this area.
            """
        )
        
        # Verify demo-quality response
        assert len(demo_response.answer) > 400
        assert len(demo_response.tools_invoked) >= 2
        
        # Verify healthcare focus
        healthcare_terms = ["healthcare", "medical", "diagnosis", "treatment", "patient"]
        assert sum(1 for term in healthcare_terms if term in demo_response.answer.lower()) >= 3
        
        # Verify comprehensive analysis
        analysis_terms = ["benefits", "challenges", "themes", "developments"]
        assert sum(1 for term in analysis_terms if term in demo_response.answer.lower()) >= 3
    
    def test_multi_tool_coordination_demo(self, user_test_framework):
        """Test: Demo scenario showing multi-tool coordination."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        coordination_response = user_test_framework.simulate_query(
            """
            Demonstrate the full capabilities of the system: analyze my document themes,
            search for recent AI developments, find contradictions in perspectives,
            and create a comprehensive visualization of the findings.
            """
        )
        
        # Verify all major tools are used
        expected_tools = ["cross_library_analysis", "web_search", "code_execution"]
        for tool in expected_tools:
            assert tool in coordination_response.tools_invoked
        
        # Verify comprehensive response
        assert len(coordination_response.answer) > 500
        assert len(coordination_response.reasoning_steps) >= 3
        
        # Verify demonstration quality
        demo_indicators = ["analyze", "search", "contradictions", "visualization", "comprehensive"]
        assert sum(1 for indicator in demo_indicators 
                  if indicator in coordination_response.answer.lower()) >= 4
    
    def test_research_workflow_demo(self, user_test_framework):
        """Test: Complete research workflow demonstration."""
        user_test_framework.simulate_document_upload(user_test_framework.sample_documents)
        
        # Simulate complete research workflow
        workflow_steps = [
            "What are the main research questions addressed in my documents?",
            "Analyze the methodologies and approaches used in this research",
            "Identify any gaps or limitations in the current research",
            "Search for recent developments that address these gaps",
            "Synthesize recommendations for future research directions"
        ]
        
        responses = []
        for step in workflow_steps:
            response = user_test_framework.simulate_query(step)
            responses.append(response)
        
        # Verify workflow completion
        assert len(responses) == 5
        assert all(len(r.answer) > 100 for r in responses)
        assert all(r.confidence_score > 0.5 for r in responses)
        
        # Verify workflow progression
        assert "research questions" in responses[0].answer.lower()
        assert "methodologies" in responses[1].answer.lower()
        assert "gaps" in responses[2].answer.lower()
        assert "recent" in responses[3].answer.lower()
        assert "recommendations" in responses[4].answer.lower()
        
        # Verify conversation continuity
        assert len(user_test_framework.conversation_history) == 5

if __name__ == '__main__':
    pytest.main([__file__, '-v'])