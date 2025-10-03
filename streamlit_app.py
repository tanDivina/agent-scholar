"""
Agent Scholar - Streamlit Chat Interface

A sophisticated chat interface for the Agent Scholar AI research assistant.
Features real-time agent reasoning display, file upload capabilities, and
visualization support for research workflows.
"""

import streamlit as st
import requests
import json
import uuid
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from typing import Dict, Any, List, Optional
import base64
import io
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Agent Scholar - AI Research Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    
    .user-message {
        background-color: #f0f2f6;
        border-left-color: #ff7f0e;
    }
    
    .agent-message {
        background-color: #e8f4fd;
        border-left-color: #1f77b4;
    }
    
    .reasoning-step {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.25rem;
        padding: 0.5rem;
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
    
    .tool-invocation {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.25rem;
        padding: 0.5rem;
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
    
    .source-citation {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.25rem;
        padding: 0.5rem;
        margin: 0.25rem 0;
        font-size: 0.85rem;
    }
    
    .metrics-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
API_BASE_URL = st.secrets.get("API_BASE_URL", "https://your-api-gateway-url.execute-api.region.amazonaws.com/prod")
MAX_CHAT_HISTORY = 50

class AgentScholarChat:
    """Main chat interface class for Agent Scholar."""
    
    def __init__(self):
        """Initialize the chat interface."""
        self.initialize_session_state()
    
    def initialize_session_state(self):
        """Initialize Streamlit session state variables."""
        if 'session_id' not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
        
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        if 'reasoning_visible' not in st.session_state:
            st.session_state.reasoning_visible = True
        
        if 'uploaded_documents' not in st.session_state:
            st.session_state.uploaded_documents = []
        
        if 'api_status' not in st.session_state:
            st.session_state.api_status = None
    
    def check_api_health(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            if response.status_code == 200:
                st.session_state.api_status = "healthy"
                return True
            else:
                st.session_state.api_status = f"unhealthy (status: {response.status_code})"
                return False
        except Exception as e:
            st.session_state.api_status = f"error: {str(e)}"
            return False
    
    def send_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Send a message to the Agent Scholar API."""
        try:
            payload = {
                'query': message,
                'session_id': st.session_state.session_id
            }
            
            with st.spinner("🧠 Agent Scholar is thinking..."):
                response = requests.post(
                    f"{API_BASE_URL}/chat",
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=120
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
            return None
    
    def display_reasoning_steps(self, reasoning_steps: List[Dict[str, Any]]):
        """Display agent reasoning steps."""
        if not reasoning_steps or not st.session_state.reasoning_visible:
            return
        
        with st.expander("🔍 Agent Reasoning Process", expanded=False):
            for i, step in enumerate(reasoning_steps, 1):
                st.markdown(f"""
                <div class="reasoning-step">
                    <strong>Step {i}:</strong> {step.get('rationale', step.get('step', 'Unknown step'))}
                    <br><small>⏰ {step.get('timestamp', 'Unknown time')}</small>
                </div>
                """, unsafe_allow_html=True)
    
    def display_tool_invocations(self, tool_invocations: List[Dict[str, Any]]):
        """Display tool invocations."""
        if not tool_invocations:
            return
        
        with st.expander("🛠️ Tools Used", expanded=False):
            for tool in tool_invocations:
                action_group = tool.get('action_group', 'Unknown')
                api_path = tool.get('api_path', '')
                timestamp = tool.get('timestamp', 'Unknown time')
                
                st.markdown(f"""
                <div class="tool-invocation">
                    <strong>🔧 {action_group}</strong>
                    {f"<br>📍 Path: {api_path}" if api_path else ""}
                    <br><small>⏰ {timestamp}</small>
                </div>
                """, unsafe_allow_html=True)
    
    def display_sources(self, sources: List[Dict[str, Any]]):
        """Display source citations."""
        if not sources:
            return
        
        with st.expander("📚 Sources Used", expanded=False):
            for i, source in enumerate(sources, 1):
                source_type = source.get('type', 'Unknown')
                content = source.get('content', 'No content available')
                score = source.get('score', 0)
                metadata = source.get('metadata', {})
                
                st.markdown(f"""
                <div class="source-citation">
                    <strong>Source {i} ({source_type})</strong>
                    <br>📄 {content}
                    <br>🎯 Relevance Score: {score:.3f}
                    {f"<br>📋 Metadata: {metadata}" if metadata else ""}
                </div>
                """, unsafe_allow_html=True)
    
    def display_chat_message(self, message: Dict[str, Any], is_user: bool = False):
        """Display a chat message with proper formatting."""
        css_class = "user-message" if is_user else "agent-message"
        icon = "👤" if is_user else "🧠"
        
        if is_user:
            st.markdown(f"""
            <div class="chat-message {css_class}">
                {icon} <strong>You:</strong><br>
                {message.get('content', message.get('query', ''))}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Agent message with full response details
            response_data = message.get('response', {})
            answer = response_data.get('answer', 'No response available')
            
            st.markdown(f"""
            <div class="chat-message {css_class}">
                {icon} <strong>Agent Scholar:</strong><br>
                {answer}
            </div>
            """, unsafe_allow_html=True)
            
            # Display additional information
            self.display_reasoning_steps(response_data.get('reasoning_steps', []))
            self.display_tool_invocations(response_data.get('tool_invocations', []))
            self.display_sources(response_data.get('sources_used', []))
    
    def display_session_metrics(self):
        """Display session metrics and statistics."""
        if len(st.session_state.chat_history) == 0:
            return
        
        # Calculate metrics
        total_messages = len(st.session_state.chat_history)
        user_messages = sum(1 for msg in st.session_state.chat_history if msg.get('is_user', False))
        agent_messages = total_messages - user_messages
        
        # Tool usage statistics
        tool_usage = {}
        for msg in st.session_state.chat_history:
            if not msg.get('is_user', False):
                tools = msg.get('response', {}).get('tool_invocations', [])
                for tool in tools:
                    action_group = tool.get('action_group', 'Unknown')
                    tool_usage[action_group] = tool_usage.get(action_group, 0) + 1
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Messages", total_messages)
        
        with col2:
            st.metric("Your Questions", user_messages)
        
        with col3:
            st.metric("Agent Responses", agent_messages)
        
        with col4:
            st.metric("Tools Used", len(tool_usage))
        
        # Tool usage chart
        if tool_usage:
            fig = px.bar(
                x=list(tool_usage.keys()),
                y=list(tool_usage.values()),
                title="Tool Usage Statistics",
                labels={'x': 'Tool', 'y': 'Usage Count'}
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    def handle_file_upload(self):
        """Handle document file uploads."""
        uploaded_files = st.file_uploader(
            "Upload research documents",
            type=['txt', 'pdf', 'docx', 'md'],
            accept_multiple_files=True,
            help="Upload documents to add to your research library"
        )
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file not in st.session_state.uploaded_documents:
                    st.session_state.uploaded_documents.append(uploaded_file)
                    st.success(f"📄 Uploaded: {uploaded_file.name}")
        
        # Display uploaded documents
        if st.session_state.uploaded_documents:
            st.subheader("📚 Uploaded Documents")
            for doc in st.session_state.uploaded_documents:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {doc.name} ({doc.size} bytes)")
                with col2:
                    if st.button("🗑️", key=f"delete_{doc.name}"):
                        st.session_state.uploaded_documents.remove(doc)
                        st.rerun()
    
    def render_sidebar(self):
        """Render the sidebar with controls and information."""
        with st.sidebar:
            st.markdown("## 🧠 Agent Scholar")
            st.markdown("*AI Research Assistant*")
            
            # API Status
            st.subheader("🔌 Connection Status")
            if st.button("Check API Health"):
                self.check_api_health()
            
            if st.session_state.api_status:
                if "healthy" in st.session_state.api_status:
                    st.success(f"✅ {st.session_state.api_status}")
                else:
                    st.error(f"❌ {st.session_state.api_status}")
            
            # Session Information
            st.subheader("📊 Session Info")
            st.text(f"Session ID: {st.session_state.session_id[:8]}...")
            st.text(f"Messages: {len(st.session_state.chat_history)}")
            
            # Settings
            st.subheader("⚙️ Settings")
            st.session_state.reasoning_visible = st.checkbox(
                "Show reasoning steps",
                value=st.session_state.reasoning_visible,
                help="Display the agent's reasoning process"
            )
            
            # File Upload
            st.subheader("📁 Document Upload")
            self.handle_file_upload()
            
            # Clear Chat
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history = []
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()
            
            # Example Queries
            st.subheader("💡 Example Queries")
            example_queries = [
                "What is machine learning?",
                "Compare different neural network architectures",
                "Analyze the themes in my uploaded documents",
                "Create a visualization of algorithm performance",
                "Find recent research on transformer models"
            ]
            
            for query in example_queries:
                if st.button(f"💬 {query[:30]}...", key=f"example_{hash(query)}"):
                    st.session_state.current_query = query
                    st.rerun()
    
    def run(self):
        """Main application loop."""
        # Header
        st.markdown('<h1 class="main-header">🧠 Agent Scholar</h1>', unsafe_allow_html=True)
        st.markdown("### *Your AI Research Assistant*")
        
        # Render sidebar
        self.render_sidebar()
        
        # Main chat interface
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Chat history
            st.subheader("💬 Research Conversation")
            
            # Display chat history
            for message in st.session_state.chat_history:
                self.display_chat_message(message, message.get('is_user', False))
            
            # Chat input
            user_input = st.chat_input("Ask me anything about your research...")
            
            # Handle example query selection
            if hasattr(st.session_state, 'current_query'):
                user_input = st.session_state.current_query
                delattr(st.session_state, 'current_query')
            
            # Process user input
            if user_input:
                # Add user message to history
                user_message = {
                    'content': user_input,
                    'timestamp': datetime.now().isoformat(),
                    'is_user': True
                }
                st.session_state.chat_history.append(user_message)
                
                # Send to API and get response
                api_response = self.send_message(user_input)
                
                if api_response:
                    # Add agent response to history
                    agent_message = {
                        'response': api_response.get('response', {}),
                        'timestamp': datetime.now().isoformat(),
                        'is_user': False
                    }
                    st.session_state.chat_history.append(agent_message)
                    
                    # Limit chat history
                    if len(st.session_state.chat_history) > MAX_CHAT_HISTORY:
                        st.session_state.chat_history = st.session_state.chat_history[-MAX_CHAT_HISTORY:]
                
                # Rerun to display new messages
                st.rerun()
        
        with col2:
            # Session metrics and statistics
            st.subheader("📈 Session Metrics")
            self.display_session_metrics()


def main():
    """Main application entry point."""
    try:
        chat_app = AgentScholarChat()
        chat_app.run()
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()