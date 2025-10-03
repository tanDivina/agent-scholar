# Agent Scholar - API Documentation

This document provides comprehensive API documentation for the Agent Scholar AI research assistant system, including all endpoints, authentication methods, and usage examples.

## 📋 Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [API Endpoints](#api-endpoints)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Code Examples](#code-examples)
- [SDKs and Libraries](#sdks-and-libraries)

## 🌐 Overview

The Agent Scholar API provides programmatic access to advanced AI research capabilities including:

- **Document Analysis**: Upload and analyze research documents
- **Web Search Integration**: Search recent developments and trends
- **Code Execution**: Generate and execute analysis code
- **Cross-Library Analysis**: Find themes, contradictions, and insights
- **Multi-Tool Coordination**: Combine multiple AI tools for comprehensive research

### API Characteristics

- **RESTful Design**: Standard HTTP methods and status codes
- **JSON Format**: All requests and responses use JSON
- **Authentication**: JWT tokens and API keys supported
- **Rate Limited**: Configurable limits based on user tier
- **Versioned**: API versioning for backward compatibility

## 🔐 Authentication

### JWT Token Authentication

Most endpoints require JWT token authentication obtained through the login process.

#### Login Request
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "UserPassword123!"
}
```

#### Login Response
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "user@example.com",
  "roles": ["user"],
  "permissions": ["read", "write"],
  "expires_in": 86400
}
```

#### Using JWT Tokens
Include the JWT token in the Authorization header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API Key Authentication

For service-to-service communication, use API key authentication:

```http
X-API-Key: as_your_api_key_here
```

### Cognito Authentication

For web applications, Cognito tokens are also supported:

```http
X-Cognito-Token: cognito_access_token_here
```

## 🌍 Base URL

- **Development**: `https://dev-api.agent-scholar.com`
- **Staging**: `https://staging-api.agent-scholar.com`
- **Production**: `https://api.agent-scholar.com`

All API endpoints are relative to the base URL.

## 📡 API Endpoints

### Health Check

#### GET /health
Check API health and status.

**Authentication**: None required

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "search": "healthy",
    "ai_models": "healthy"
  }
}
```

### Authentication Endpoints

#### POST /auth/login
Authenticate user and obtain JWT token.

**Authentication**: None required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "UserPassword123!"
}
```

**Response**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "user@example.com",
  "roles": ["user"],
  "permissions": ["read", "write"],
  "expires_in": 86400
}
```

#### POST /auth/refresh
Refresh an existing JWT token.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "refresh_token": "refresh_token_here"
}
```

**Response**:
```json
{
  "token": "new_jwt_token_here",
  "expires_in": 86400
}
```

#### GET /auth/profile
Get current user profile information.

**Authentication**: JWT token required

**Response**:
```json
{
  "user_id": "user@example.com",
  "profile": {
    "name": "John Doe",
    "subscription_tier": "professional",
    "api_quota": 1000,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "roles": ["user"],
  "permissions": ["read", "write"]
}
```

### Research Endpoints

#### POST /research
Submit a research query for AI analysis.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "query": "What are the latest developments in machine learning?",
  "session_id": "uuid-session-id",
  "user_id": "user@example.com",
  "enable_tools": ["web_search", "cross_library_analysis"],
  "context": {
    "previous_queries": [],
    "user_preferences": {}
  }
}
```

**Response**:
```json
{
  "query": "What are the latest developments in machine learning?",
  "answer": "Based on my analysis of recent developments and your document library...",
  "sources_used": ["doc1", "doc2", "web_source1"],
  "tools_invoked": ["web_search", "cross_library_analysis"],
  "reasoning_steps": [
    "I need to search for recent ML developments",
    "I should analyze your document library for context",
    "I'll synthesize findings from both sources"
  ],
  "confidence_score": 0.85,
  "processing_time": 4.2,
  "session_id": "uuid-session-id",
  "visualizations": [
    {
      "type": "plotly",
      "title": "ML Trends Over Time",
      "data": {...}
    }
  ]
}
```

#### GET /research/history
Get research query history for the current user.

**Authentication**: JWT token required

**Query Parameters**:
- `limit` (optional): Number of results to return (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `session_id` (optional): Filter by session ID

**Response**:
```json
{
  "queries": [
    {
      "id": "query-uuid",
      "query": "What are the latest developments in ML?",
      "timestamp": "2024-01-15T10:30:00Z",
      "session_id": "session-uuid",
      "tools_used": ["web_search"],
      "processing_time": 4.2
    }
  ],
  "total": 45,
  "limit": 20,
  "offset": 0
}
```

### Document Management

#### POST /documents/upload
Upload a document for analysis.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "filename": "research_paper.pdf",
  "content": "base64_encoded_content",
  "content_type": "application/pdf",
  "metadata": {
    "author": "Dr. Jane Smith",
    "year": "2023",
    "keywords": ["AI", "machine learning"]
  }
}
```

**Response**:
```json
{
  "document_id": "doc-uuid",
  "filename": "research_paper.pdf",
  "status": "processing",
  "upload_time": "2024-01-15T10:30:00Z",
  "processing_status": {
    "text_extraction": "completed",
    "embedding_generation": "in_progress",
    "indexing": "pending"
  }
}
```

#### GET /documents
List uploaded documents.

**Authentication**: JWT token required

**Query Parameters**:
- `limit` (optional): Number of results (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `status` (optional): Filter by processing status

**Response**:
```json
{
  "documents": [
    {
      "document_id": "doc-uuid",
      "filename": "research_paper.pdf",
      "upload_time": "2024-01-15T10:30:00Z",
      "status": "completed",
      "metadata": {
        "author": "Dr. Jane Smith",
        "year": "2023",
        "page_count": 15
      }
    }
  ],
  "total": 12,
  "limit": 20,
  "offset": 0
}
```

#### GET /documents/{document_id}
Get details for a specific document.

**Authentication**: JWT token required

**Response**:
```json
{
  "document_id": "doc-uuid",
  "filename": "research_paper.pdf",
  "upload_time": "2024-01-15T10:30:00Z",
  "status": "completed",
  "content_preview": "This paper presents a novel approach to...",
  "metadata": {
    "author": "Dr. Jane Smith",
    "year": "2023",
    "page_count": 15,
    "word_count": 5420
  },
  "processing_details": {
    "chunks_created": 45,
    "embeddings_generated": 45,
    "processing_time": 12.3
  }
}
```

#### DELETE /documents/{document_id}
Delete a document.

**Authentication**: JWT token required

**Response**:
```json
{
  "message": "Document deleted successfully",
  "document_id": "doc-uuid"
}
```

### Analysis Endpoints

#### POST /analysis/themes
Analyze themes across documents.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "document_ids": ["doc1", "doc2", "doc3"],
  "analysis_type": "themes",
  "parameters": {
    "min_theme_frequency": 3,
    "include_sentiment": true
  }
}
```

**Response**:
```json
{
  "analysis_id": "analysis-uuid",
  "themes": [
    {
      "theme": "Machine Learning Applications",
      "frequency": 15,
      "documents": ["doc1", "doc2"],
      "sentiment": "positive",
      "key_phrases": ["neural networks", "deep learning", "AI applications"]
    }
  ],
  "processing_time": 8.7,
  "confidence_score": 0.82
}
```

#### POST /analysis/contradictions
Find contradictions between documents.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "document_ids": ["doc1", "doc2", "doc3"],
  "analysis_type": "contradictions",
  "parameters": {
    "similarity_threshold": 0.7,
    "include_context": true
  }
}
```

**Response**:
```json
{
  "analysis_id": "analysis-uuid",
  "contradictions": [
    {
      "topic": "AI Job Impact",
      "contradiction_type": "opposing_views",
      "documents": [
        {
          "document_id": "doc1",
          "position": "AI will create more jobs than it eliminates",
          "confidence": 0.85,
          "context": "The study shows that historically..."
        },
        {
          "document_id": "doc2",
          "position": "AI will lead to significant job displacement",
          "confidence": 0.78,
          "context": "Recent analysis indicates..."
        }
      ]
    }
  ],
  "processing_time": 12.4,
  "confidence_score": 0.79
}
```

### Code Execution

#### POST /code/execute
Execute code for data analysis and visualization.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "code": "import matplotlib.pyplot as plt\nimport numpy as np\n\n# Generate sample data\nx = np.linspace(0, 10, 100)\ny = np.sin(x)\n\n# Create plot\nplt.figure(figsize=(10, 6))\nplt.plot(x, y)\nplt.title('Sine Wave')\nplt.show()",
  "language": "python",
  "context": {
    "data_sources": ["doc1", "doc2"],
    "analysis_type": "visualization"
  }
}
```

**Response**:
```json
{
  "execution_id": "exec-uuid",
  "status": "completed",
  "output": {
    "stdout": "Plot generated successfully",
    "stderr": "",
    "return_value": null,
    "execution_time": 2.3
  },
  "artifacts": [
    {
      "type": "image",
      "filename": "sine_wave.png",
      "url": "https://s3.amazonaws.com/bucket/sine_wave.png"
    }
  ],
  "security_report": {
    "safe": true,
    "restricted_operations": [],
    "warnings": []
  }
}
```

### Web Search

#### POST /search/web
Perform web search for recent information.

**Authentication**: JWT token required

**Request Body**:
```json
{
  "query": "latest machine learning research 2024",
  "max_results": 10,
  "search_type": "academic",
  "filters": {
    "date_range": "last_month",
    "domains": ["arxiv.org", "scholar.google.com"]
  }
}
```

**Response**:
```json
{
  "search_id": "search-uuid",
  "query": "latest machine learning research 2024",
  "results": [
    {
      "title": "Advances in Neural Architecture Search",
      "url": "https://arxiv.org/abs/2024.01234",
      "snippet": "This paper presents novel approaches to...",
      "source": "arXiv",
      "date": "2024-01-10",
      "relevance_score": 0.92
    }
  ],
  "total_results": 847,
  "processing_time": 1.8,
  "search_metadata": {
    "engines_used": ["academic", "web"],
    "filters_applied": ["date_range", "domains"]
  }
}
```

## 📊 Data Models

### ResearchQuery
```json
{
  "query": "string (required)",
  "session_id": "string (required)",
  "user_id": "string (required)",
  "enable_tools": ["string"] (optional),
  "context": "object" (optional)
}
```

### AgentResponse
```json
{
  "query": "string",
  "answer": "string",
  "sources_used": ["string"],
  "tools_invoked": ["string"],
  "reasoning_steps": ["string"],
  "confidence_score": "number (0-1)",
  "processing_time": "number (seconds)",
  "session_id": "string",
  "visualizations": ["object"] (optional)
}
```

### Document
```json
{
  "document_id": "string",
  "filename": "string",
  "content_type": "string",
  "upload_time": "string (ISO 8601)",
  "status": "string (processing|completed|failed)",
  "metadata": "object",
  "processing_details": "object" (optional)
}
```

### User Profile
```json
{
  "user_id": "string",
  "profile": {
    "name": "string",
    "subscription_tier": "string (free|professional|premium)",
    "api_quota": "number",
    "created_at": "string (ISO 8601)"
  },
  "roles": ["string"],
  "permissions": ["string"]
}
```

## ⚠️ Error Handling

### HTTP Status Codes

- **200 OK**: Request successful
- **201 Created**: Resource created successfully
- **400 Bad Request**: Invalid request parameters
- **401 Unauthorized**: Authentication required or failed
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Service temporarily unavailable

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request parameters are invalid",
    "details": {
      "field": "query",
      "issue": "Query cannot be empty"
    },
    "request_id": "req-uuid",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

- **AUTHENTICATION_FAILED**: Invalid credentials
- **TOKEN_EXPIRED**: JWT token has expired
- **INSUFFICIENT_PERMISSIONS**: User lacks required permissions
- **RATE_LIMIT_EXCEEDED**: Too many requests
- **INVALID_REQUEST**: Malformed request
- **RESOURCE_NOT_FOUND**: Requested resource doesn't exist
- **PROCESSING_ERROR**: Error during AI processing
- **QUOTA_EXCEEDED**: User quota limit reached

## 🚦 Rate Limiting

### Rate Limit Tiers

| Tier | Requests/Hour | Burst Limit | Concurrent Requests |
|------|---------------|-------------|-------------------|
| Free | 100 | 10 | 2 |
| Professional | 1,000 | 50 | 5 |
| Premium | 10,000 | 200 | 20 |

### Rate Limit Headers

Responses include rate limit information:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642262400
X-RateLimit-Retry-After: 3600
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again later.",
    "details": {
      "limit": 1000,
      "window": 3600,
      "retry_after": 1800
    }
  }
}
```

## 💻 Code Examples

### Python Example

```python
import requests
import json

class AgentScholarClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url
        self.api_key = api_key
        self.token = None
    
    def login(self, email, password):
        """Authenticate and get JWT token"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data['token']
            return data
        else:
            raise Exception(f"Login failed: {response.text}")
    
    def research_query(self, query, session_id=None):
        """Submit a research query"""
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "query": query,
            "session_id": session_id or "default-session"
        }
        
        response = requests.post(
            f"{self.base_url}/research",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Query failed: {response.text}")
    
    def upload_document(self, filename, content, content_type):
        """Upload a document for analysis"""
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "filename": filename,
            "content": content,
            "content_type": content_type
        }
        
        response = requests.post(
            f"{self.base_url}/documents/upload",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Upload failed: {response.text}")

# Usage example
client = AgentScholarClient("https://api.agent-scholar.com")
client.login("user@example.com", "password")

# Submit research query
result = client.research_query("What are the latest AI developments?")
print(f"Answer: {result['answer']}")
print(f"Tools used: {result['tools_invoked']}")
```

### JavaScript Example

```javascript
class AgentScholarClient {
    constructor(baseUrl, apiKey = null) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.token = null;
    }
    
    async login(email, password) {
        const response = await fetch(`${this.baseUrl}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            this.token = data.token;
            return data;
        } else {
            throw new Error(`Login failed: ${await response.text()}`);
        }
    }
    
    async researchQuery(query, sessionId = null) {
        const response = await fetch(`${this.baseUrl}/research`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query,
                session_id: sessionId || 'default-session'
            })
        });
        
        if (response.ok) {
            return await response.json();
        } else {
            throw new Error(`Query failed: ${await response.text()}`);
        }
    }
    
    async uploadDocument(filename, content, contentType) {
        const response = await fetch(`${this.baseUrl}/documents/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename,
                content,
                content_type: contentType
            })
        });
        
        if (response.ok) {
            return await response.json();
        } else {
            throw new Error(`Upload failed: ${await response.text()}`);
        }
    }
}

// Usage example
const client = new AgentScholarClient('https://api.agent-scholar.com');

async function example() {
    try {
        await client.login('user@example.com', 'password');
        
        const result = await client.researchQuery('What are the latest AI developments?');
        console.log('Answer:', result.answer);
        console.log('Tools used:', result.tools_invoked);
    } catch (error) {
        console.error('Error:', error.message);
    }
}

example();
```

### cURL Examples

```bash
# Login
curl -X POST https://api.agent-scholar.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Research query
curl -X POST https://api.agent-scholar.com/research \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest AI developments?",
    "session_id": "session-123"
  }'

# Upload document
curl -X POST https://api.agent-scholar.com/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "research.pdf",
    "content": "base64_encoded_content",
    "content_type": "application/pdf"
  }'

# Get documents
curl -X GET https://api.agent-scholar.com/documents \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 📚 SDKs and Libraries

### Official SDKs

- **Python SDK**: `pip install agent-scholar-python`
- **JavaScript SDK**: `npm install agent-scholar-js`
- **Go SDK**: `go get github.com/agent-scholar/go-sdk`

### Community Libraries

- **R Package**: Available on CRAN
- **Java Client**: Maven Central
- **PHP Library**: Packagist

### Postman Collection

Import our Postman collection for easy API testing:
[Download Postman Collection](https://api.agent-scholar.com/postman/collection.json)

---

## 🔗 Additional Resources

- **API Status Page**: [status.agent-scholar.com](https://status.agent-scholar.com)
- **Developer Portal**: [developers.agent-scholar.com](https://developers.agent-scholar.com)
- **GitHub Repository**: [github.com/agent-scholar/api](https://github.com/agent-scholar/api)
- **Support**: [support@agent-scholar.com](mailto:support@agent-scholar.com)

For the most up-to-date API documentation, visit our [interactive API explorer](https://api.agent-scholar.com/docs).