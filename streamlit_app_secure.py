"""
Agent Scholar - Secure Streamlit Chat Interface with Authentication

A sophisticated chat interface for the Agent Scholar AI research assistant
with integrated authentication, session management, and security features.
"""

import streamlit as st
import requests
import json
import uuid
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import base64
import io
import pandas as pd
import jwt
import hashlib

# Page configuration
st.set_page_config(
    page_title="Agent Scholar - AI Research Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
API_BASE_URL = st.secrets.get("API_BASE_URL", "https://your-api-gateway-url.com")
JWT_SECRET = st.secrets.get("JWT_SECRET", "your-jwt-secret")  # For token validation

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
    
    .assistant-message {
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
    
    .tool-call {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.25rem;
        padding: 0.5rem;
        margin: 0.25rem 0;
        font-family: monospace;
        font-size: 0.8rem;
    }
    
    .login-form {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        border: 1px solid #ddd;
        border-radius: 0.5rem;
        background-color: #f9f9f9;
    }
    
    .security-info {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        padding: 0.75rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class AuthManager:
    """Handle authentication and session management."""
    
    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return token."""
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("error", "Login failed")}
                
        except Exception as e:
            return {"error": f"Connection error: {str(e)}"}
    
    @staticmethod
    def refresh_token(refresh_token: str) -> Dict[str, Any]:
        """Refresh authentication token."""
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/refresh",
                json={"refresh_token": refresh_token},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("error", "Token refresh failed")}
                
        except Exception as e:
            return {"error": f"Connection error: {str(e)}"}
    
    @staticmethod
    def get_user_profile(token: str) -> Dict[str, Any]:
        """Get user profile information."""
        try:
            response = requests.get(
                f"{API_BASE_URL}/auth/profile",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.json().get("error", "Failed to get profile")}
                
        except Exception as e:
            return {"error": f"Connection error: {str(e)}"}
    
    @staticmethod
    def validate_token(token: str) -> bool:
        """Validate JWT token locally."""
        try:
            # Decode token without verification for basic checks
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Check expiration
            exp = payload.get('exp')
            if exp and datetime.utcnow().timestamp() > exp:
                return False
                
            return True
        except:
            return False
    
    @staticmethod
    def logout():
        """Clear session data."""
        for key in ['token', 'user_id', 'user_profile', 'session_id']:
            if key in st.session_state:
                del st.session_state[key]

def show_login_form():
    """Display login form."""
    st.markdown('<div class="main-header">🧠 Agent Scholar</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header" style="font-size: 1.2rem; margin-bottom: 3rem;">AI Research Assistant</div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="login-form">', unsafe_allow_html=True)
        
        st.subheader("🔐 Login")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@example.com")
            password = st.text_input("Password", type="password", placeholder="Your password")
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("Login", use_container_width=True)
            with col2:
                demo_button = st.form_submit_button("Demo Login", use_container_width=True)
        
        if login_button and email and password:
            with st.spinner("Authenticating..."):
                result = AuthManager.login(email, password)
                
                if "error" in result:
                    st.error(f"Login failed: {result['error']}")
                else:
                    # Store authentication data
                    st.session_state.token = result['token']
                    st.session_state.user_id = result['user_id']
                    st.session_state.user_roles = result.get('roles', [])
                    st.session_state.user_permissions = result.get('permissions', [])
                    st.session_state.session_id = str(uuid.uuid4())
                    
                    st.success("Login successful!")
                    st.rerun()
        
        if demo_button:
            # Demo login with predefined credentials
            with st.spinner("Logging in with demo account..."):
                result = AuthManager.login("user@example.com", "UserPassword123!")
                
                if "error" in result:
                    st.error(f"Demo login failed: {result['error']}")
                else:
                    st.session_state.token = result['token']
                    st.session_state.user_id = result['user_id']
                    st.session_state.user_roles = result.get('roles', [])
                    st.session_state.user_permissions = result.get('permissions', [])
                    st.session_state.session_id = str(uuid.uuid4())
                    
                    st.success("Demo login successful!")
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Security information
        with st.expander("🛡️ Security Information"):
            st.markdown("""
            <div class="security-info">
            <strong>Security Features:</strong>
            <ul>
                <li>🔐 JWT-based authentication</li>
                <li>🛡️ Rate limiting protection</li>
                <li>🔍 Input validation and sanitization</li>
                <li>📊 Security monitoring and logging</li>
                <li>🚫 XSS and SQL injection protection</li>
            </ul>
            
            <strong>Demo Accounts:</strong>
            <ul>
                <li><code>user@example.com</code> / <code>UserPassword123!</code> - Regular user</li>
                <li><code>researcher@example.com</code> / <code>ResearchPassword123!</code> - Researcher</li>
                <li><code>admin@example.com</code> / <code>AdminPassword123!</code> - Administrator</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

def show_user_sidebar():
    """Display user information and controls in sidebar."""
    with st.sidebar:
        st.markdown("### 👤 User Information")
        
        # User profile
        if 'user_profile' not in st.session_state:
            with st.spinner("Loading profile..."):
                profile_result = AuthManager.get_user_profile(st.session_state.token)
                if "error" not in profile_result:
                    st.session_state.user_profile = profile_result.get('profile', {})
                else:
                    st.session_state.user_profile = {}
        
        profile = st.session_state.get('user_profile', {})
        
        st.write(f"**Email:** {st.session_state.user_id}")
        st.write(f"**Name:** {profile.get('name', 'Unknown')}")
        st.write(f"**Subscription:** {profile.get('subscription_tier', 'free').title()}")
        st.write(f"**API Quota:** {profile.get('api_quota', 0)}")
        
        # Roles and permissions
        with st.expander("🔑 Roles & Permissions"):
            st.write("**Roles:**")
            for role in st.session_state.get('user_roles', []):
                st.write(f"- {role}")
            
            st.write("**Permissions:**")
            for perm in st.session_state.get('user_permissions', []):
                st.write(f"- {perm}")
        
        # Session information
        with st.expander("📊 Session Info"):
            st.write(f"**Session ID:** {st.session_state.get('session_id', 'N/A')[:8]}...")
            st.write(f"**Login Time:** {datetime.now().strftime('%H:%M:%S')}")
            
            # Token validation
            if AuthManager.validate_token(st.session_state.token):
                st.success("🟢 Token Valid")
            else:
                st.warning("🟡 Token Expired")
                if st.button("Refresh Token"):
                    # In a real app, you'd use a refresh token
                    st.info("Token refresh would happen here")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            AuthManager.logout()
            st.rerun()

def make_authenticated_request(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Make authenticated API request."""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 401:
            st.error("Authentication expired. Please login again.")
            AuthManager.logout()
            st.rerun()
            return {"error": "Authentication expired"}
        elif response.status_code == 403:
            st.error("Access denied. Insufficient permissions.")
            return {"error": "Access denied"}
        elif response.status_code == 429:
            st.error("Rate limit exceeded. Please wait before making more requests.")
            return {"error": "Rate limit exceeded"}
        elif response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Request failed with status {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def show_main_interface():
    """Display main chat interface for authenticated users."""
    # Header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="main-header">🧠 Agent Scholar</div>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    # Sidebar with user info and controls
    show_user_sidebar()
    
    # Main chat interface
    st.markdown("### 💬 Research Assistant Chat")
    
    # File upload section
    with st.expander("📁 Upload Documents"):
        uploaded_files = st.file_uploader(
            "Upload research documents (PDF, DOCX, TXT)",
            type=['pdf', 'docx', 'txt'],
            accept_multiple_files=True,
            help="Upload documents to add to your knowledge base"
        )
        
        if uploaded_files:
            if st.button("Process Documents"):
                with st.spinner("Processing documents..."):
                    # Process uploaded files
                    for file in uploaded_files:
                        file_content = base64.b64encode(file.read()).decode()
                        
                        result = make_authenticated_request("/documents/upload", {
                            "filename": file.name,
                            "content": file_content,
                            "content_type": file.type,
                            "session_id": st.session_state.session_id
                        })
                        
                        if "error" in result:
                            st.error(f"Failed to process {file.name}: {result['error']}")
                        else:
                            st.success(f"Successfully processed {file.name}")
    
    # Chat messages display
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(f'<div class="chat-message user-message">{message["content"]}</div>', 
                           unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-message assistant-message">{message["content"]}</div>', 
                           unsafe_allow_html=True)
                
                # Show reasoning steps if available
                if "reasoning" in message:
                    with st.expander("🧠 Agent Reasoning"):
                        for step in message["reasoning"]:
                            st.markdown(f'<div class="reasoning-step">{step}</div>', 
                                       unsafe_allow_html=True)
                
                # Show tool calls if available
                if "tool_calls" in message:
                    with st.expander("🔧 Tool Usage"):
                        for tool_call in message["tool_calls"]:
                            st.markdown(f'<div class="tool-call">{tool_call}</div>', 
                                       unsafe_allow_html=True)
                
                # Show visualizations if available
                if "visualizations" in message:
                    for viz in message["visualizations"]:
                        if viz["type"] == "plotly":
                            st.plotly_chart(viz["data"], use_container_width=True)
                        elif viz["type"] == "dataframe":
                            st.dataframe(viz["data"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your research..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(f'<div class="chat-message user-message">{prompt}</div>', 
                       unsafe_allow_html=True)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Agent is thinking..."):
                # Make authenticated request to research endpoint
                result = make_authenticated_request("/research", {
                    "query": prompt,
                    "session_id": st.session_state.session_id,
                    "user_id": st.session_state.user_id
                })
                
                if "error" in result:
                    error_msg = f"Sorry, I encountered an error: {result['error']}"
                    st.markdown(f'<div class="chat-message assistant-message">{error_msg}</div>', 
                               unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                else:
                    response_content = result.get("response", "I'm sorry, I couldn't process your request.")
                    
                    # Display response
                    st.markdown(f'<div class="chat-message assistant-message">{response_content}</div>', 
                               unsafe_allow_html=True)
                    
                    # Prepare message data
                    message_data = {
                        "role": "assistant",
                        "content": response_content
                    }
                    
                    # Add reasoning if available
                    if "reasoning" in result:
                        message_data["reasoning"] = result["reasoning"]
                        with st.expander("🧠 Agent Reasoning"):
                            for step in result["reasoning"]:
                                st.markdown(f'<div class="reasoning-step">{step}</div>', 
                                           unsafe_allow_html=True)
                    
                    # Add tool calls if available
                    if "tool_calls" in result:
                        message_data["tool_calls"] = result["tool_calls"]
                        with st.expander("🔧 Tool Usage"):
                            for tool_call in result["tool_calls"]:
                                st.markdown(f'<div class="tool-call">{tool_call}</div>', 
                                           unsafe_allow_html=True)
                    
                    # Add visualizations if available
                    if "visualizations" in result:
                        message_data["visualizations"] = result["visualizations"]
                        for viz in result["visualizations"]:
                            if viz["type"] == "plotly":
                                st.plotly_chart(viz["data"], use_container_width=True)
                            elif viz["type"] == "dataframe":
                                st.dataframe(viz["data"])
                    
                    st.session_state.messages.append(message_data)
    
    # Quick action buttons
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 Analyze Documents", use_container_width=True):
            st.session_state.messages.append({
                "role": "user", 
                "content": "Analyze the themes and patterns in my document library"
            })
            st.rerun()
    
    with col2:
        if st.button("🔍 Web Search", use_container_width=True):
            st.session_state.messages.append({
                "role": "user", 
                "content": "Search for recent developments in AI and machine learning"
            })
            st.rerun()
    
    with col3:
        if st.button("💻 Code Analysis", use_container_width=True):
            st.session_state.messages.append({
                "role": "user", 
                "content": "Generate Python code to visualize data trends from my research"
            })
            st.rerun()
    
    with col4:
        if st.button("🔄 Compare Sources", use_container_width=True):
            st.session_state.messages.append({
                "role": "user", 
                "content": "Find contradictions and different perspectives in my documents"
            })
            st.rerun()

def main():
    """Main application entry point."""
    # Check authentication
    if 'token' not in st.session_state or not AuthManager.validate_token(st.session_state.token):
        show_login_form()
    else:
        show_main_interface()

if __name__ == "__main__":
    main()