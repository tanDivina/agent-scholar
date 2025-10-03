# Agent Scholar - Streamlit Chat Interface

A sophisticated web-based chat interface for the Agent Scholar AI research assistant, built with Streamlit.

## Features

### 🧠 Intelligent Chat Interface
- Real-time conversation with Agent Scholar
- Session management with conversation history
- Context preservation across interactions

### 🔍 Agent Reasoning Display
- Step-by-step reasoning process visualization
- Tool invocation tracking
- Source citation display
- Expandable sections for detailed analysis

### 📊 Interactive Visualizations
- Session metrics and statistics
- Tool usage analytics
- Real-time charts and graphs
- Performance insights

### 📁 Document Management
- File upload support (TXT, PDF, DOCX, MD)
- Document library management
- Integration with knowledge base

### ⚙️ Advanced Features
- API health monitoring
- Customizable display settings
- Example query suggestions
- Session persistence

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements-streamlit.txt
   ```

2. **Configure API Endpoint**
   
   Edit `.streamlit/secrets.toml` and update the API_BASE_URL:
   ```toml
   API_BASE_URL = "https://your-actual-api-gateway-url.execute-api.region.amazonaws.com/prod"
   ```

3. **Run the Application**
   ```bash
   streamlit run streamlit_app.py
   ```

4. **Access the Interface**
   
   Open your browser and navigate to: `http://localhost:8501`

## Configuration

### Environment Variables
You can also set the API URL using environment variables:
```bash
export API_BASE_URL="https://your-api-gateway-url.execute-api.region.amazonaws.com/prod"
```

### Streamlit Configuration
The application includes custom configuration in `.streamlit/config.toml`:
- Custom theme colors
- Server settings
- Browser preferences

## Usage Guide

### Starting a Research Session

1. **Health Check**: Click "Check API Health" in the sidebar to verify connectivity
2. **Ask Questions**: Use the chat input to ask research questions
3. **Upload Documents**: Add research documents via the sidebar
4. **View Reasoning**: Enable "Show reasoning steps" to see the agent's thought process

### Example Queries

Try these example research queries:

- **General Research**: "What is machine learning?"
- **Comparative Analysis**: "Compare different neural network architectures"
- **Document Analysis**: "Analyze the themes in my uploaded documents"
- **Visualization**: "Create a visualization of algorithm performance"
- **Current Research**: "Find recent research on transformer models"

### Understanding Agent Responses

Each agent response includes:

1. **Main Answer**: The primary response to your query
2. **Reasoning Steps**: The agent's thought process (expandable)
3. **Tools Used**: Which action groups were invoked (expandable)
4. **Sources**: Citations and references used (expandable)

### Session Management

- **Session ID**: Each conversation has a unique session ID
- **History**: Conversation history is maintained during the session
- **Clear Chat**: Use the sidebar button to start a new session
- **Metrics**: View session statistics in the right panel

## Features in Detail

### Real-time Agent Reasoning
The interface displays the agent's reasoning process in real-time:
- **Step-by-step analysis**: See how the agent breaks down complex queries
- **Tool selection**: Understand which tools the agent chooses and why
- **Source integration**: View how different sources are combined

### Interactive Visualizations
Built-in charts and graphs show:
- **Tool usage statistics**: Which tools are used most frequently
- **Session metrics**: Message counts and interaction patterns
- **Performance insights**: Response times and success rates

### Document Upload and Management
- **Multi-format support**: TXT, PDF, DOCX, and Markdown files
- **Real-time processing**: Documents are processed and indexed automatically
- **Library management**: View and manage your uploaded documents

### Advanced Chat Features
- **Context preservation**: Conversations maintain context across messages
- **Session persistence**: Chat history is preserved during the session
- **Error handling**: Graceful handling of API errors and connectivity issues

## Troubleshooting

### Common Issues

1. **API Connection Error**
   - Verify the API_BASE_URL in secrets.toml
   - Check that your API Gateway is deployed and accessible
   - Use the "Check API Health" button to test connectivity

2. **File Upload Issues**
   - Ensure files are in supported formats (TXT, PDF, DOCX, MD)
   - Check file size limits
   - Verify file permissions

3. **Slow Response Times**
   - Complex queries may take 30-60 seconds
   - Check your internet connection
   - Monitor the API Gateway logs for performance issues

### Debug Mode
To run in debug mode with detailed logging:
```bash
streamlit run streamlit_app.py --logger.level=debug
```

### API Health Check
Use the built-in health check feature:
1. Click "Check API Health" in the sidebar
2. Look for the green checkmark (✅) for healthy status
3. Red X (❌) indicates connection issues

## Deployment

### Local Development
```bash
streamlit run streamlit_app.py
```

### Production Deployment

#### Streamlit Cloud
1. Push your code to GitHub
2. Connect your repository to Streamlit Cloud
3. Configure secrets in the Streamlit Cloud dashboard
4. Deploy automatically

#### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements-streamlit.txt .
RUN pip install -r requirements-streamlit.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py"]
```

#### AWS EC2 Deployment
1. Launch an EC2 instance
2. Install Python and dependencies
3. Configure security groups for port 8501
4. Run the application with proper environment variables

## Security Considerations

### API Security
- Use HTTPS endpoints only
- Implement proper authentication if required
- Monitor API usage and rate limits

### Data Privacy
- Uploaded documents are processed by the AI system
- Session data is temporary and not permanently stored
- Consider data sensitivity when uploading documents

### Network Security
- Use secure connections (HTTPS/WSS)
- Implement proper CORS settings
- Consider VPN access for sensitive deployments

## Performance Optimization

### Client-Side Optimization
- Enable caching for static content
- Optimize image and file uploads
- Use efficient data structures for chat history

### Server-Side Optimization
- Monitor API response times
- Implement proper error handling
- Use connection pooling for API requests

## Support and Maintenance

### Monitoring
- Monitor API health regularly
- Track user engagement metrics
- Log errors and performance issues

### Updates
- Keep Streamlit and dependencies updated
- Monitor for security patches
- Test new features in development environment

### Backup and Recovery
- Backup configuration files
- Document deployment procedures
- Maintain rollback procedures

## Contributing

To contribute to the Streamlit interface:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add docstrings to all functions
- Include error handling
- Test with different screen sizes
- Ensure accessibility compliance

## License

This project is part of the Agent Scholar system and follows the same licensing terms.