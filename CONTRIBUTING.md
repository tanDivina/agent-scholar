# Contributing to Agent Scholar

Thank you for your interest in contributing to Agent Scholar! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Reporting Issues

1. **Search existing issues** to avoid duplicates
2. **Use issue templates** when available
3. **Provide detailed information**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Error messages and logs

### Suggesting Features

1. **Check existing feature requests** in issues and discussions
2. **Describe the use case** and problem you're trying to solve
3. **Provide examples** of how the feature would be used
4. **Consider implementation complexity** and maintenance burden

### Code Contributions

#### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/agent-scholar.git
   cd agent-scholar
   ```
3. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   npm install
   ```

#### Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our coding standards

3. **Write tests** for new functionality:
   ```bash
   # Run tests to ensure they pass
   pytest tests/unit/ -v
   pytest tests/integration/ -v
   ```

4. **Update documentation** if needed

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## 📝 Coding Standards

### Python Code Style

- **Follow PEP 8** style guidelines
- **Use type hints** for function parameters and return values
- **Write docstrings** for all public functions and classes
- **Maximum line length**: 100 characters
- **Use meaningful variable names**

Example:
```python
def process_research_query(query: str, session_id: str) -> AgentResponse:
    """
    Process a research query using the AI agent.
    
    Args:
        query: The research question to process
        session_id: Unique session identifier
        
    Returns:
        AgentResponse containing the processed result
        
    Raises:
        ValidationError: If query is invalid
    """
    # Implementation here
    pass
```

### TypeScript Code Style

- **Use TypeScript strict mode**
- **Follow AWS CDK best practices**
- **Use meaningful interface names**
- **Document complex constructs**

Example:
```typescript
export interface AgentScholarStackProps extends cdk.StackProps {
  /**
   * The foundation model to use for the Bedrock agent
   * @default 'anthropic.claude-3-sonnet-20240229-v1:0'
   */
  foundationModel?: string;
  
  /**
   * Email address for alerts and notifications
   */
  alertEmail?: string;
}
```

### Testing Standards

- **Write unit tests** for all new functions
- **Include integration tests** for API endpoints
- **Add end-to-end tests** for complete workflows
- **Maintain >80% code coverage**

Example test:
```python
def test_research_query_processing():
    """Test that research queries are processed correctly."""
    # Arrange
    query = "What are the latest AI developments?"
    session_id = "test-session-123"
    
    # Act
    result = process_research_query(query, session_id)
    
    # Assert
    assert result.query == query
    assert result.session_id == session_id
    assert len(result.answer) > 0
    assert result.confidence_score > 0.5
```

## 🏗️ Architecture Guidelines

### Adding New Lambda Functions

1. **Create function directory** in `src/lambda/`
2. **Follow naming convention**: `kebab-case-function-name`
3. **Include proper error handling** and logging
4. **Add corresponding CDK construct** in `infrastructure/constructs/`
5. **Write comprehensive tests**

### Adding New Action Groups

1. **Define action group schema** with clear descriptions
2. **Implement handler function** with input validation
3. **Add to Bedrock agent configuration**
4. **Include in integration tests**
5. **Update documentation**

### Infrastructure Changes

1. **Use CDK constructs** for reusability
2. **Follow AWS best practices** for security and performance
3. **Include monitoring and alerting**
4. **Test in development environment** before production
5. **Update deployment scripts** if needed

## 🧪 Testing Guidelines

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v --cov=src

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
python tests/e2e/test_runner.py --all

# Load tests
python tests/load/load_test_runner.py --url http://localhost:8000
```

### Test Categories

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user workflows
- **Load Tests**: Test performance under load
- **Security Tests**: Test security features and vulnerabilities

### Test Data

- **Use realistic test data** that represents actual use cases
- **Include edge cases** and error conditions
- **Mock external services** to ensure test reliability
- **Clean up test data** after test completion

## 📚 Documentation

### Code Documentation

- **Write clear docstrings** for all public APIs
- **Include usage examples** in docstrings
- **Document complex algorithms** and business logic
- **Keep comments up-to-date** with code changes

### User Documentation

- **Update README.md** for new features
- **Add to API documentation** for new endpoints
- **Include in demo scenarios** if applicable
- **Update deployment guide** for infrastructure changes

## 🔒 Security Considerations

### Security Best Practices

- **Never commit secrets** or API keys
- **Use environment variables** for configuration
- **Validate all inputs** to prevent injection attacks
- **Follow principle of least privilege** for IAM roles
- **Encrypt sensitive data** in transit and at rest

### Security Review Process

1. **Run security tests** before submitting PR
2. **Review IAM policies** for minimal permissions
3. **Check for hardcoded secrets** or credentials
4. **Validate input sanitization** and output encoding
5. **Test authentication and authorization** flows

## 🚀 Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] Security review completed
- [ ] Performance benchmarks meet requirements
- [ ] Deployment tested in staging environment
- [ ] Release notes prepared

## 🎯 Pull Request Guidelines

### PR Title Format

Use conventional commit format:
- `feat: add new research analysis capability`
- `fix: resolve authentication timeout issue`
- `docs: update API documentation`
- `test: add integration tests for web search`
- `refactor: improve code organization`

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added for new functionality
```

### Review Process

1. **Automated checks** must pass (tests, linting, security)
2. **Code review** by at least one maintainer
3. **Manual testing** for significant changes
4. **Documentation review** for user-facing changes
5. **Security review** for security-related changes

## 🏷️ Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `security`: Security-related issue
- `performance`: Performance-related issue

## 💬 Communication

### Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussions
- **Pull Requests**: Code review and technical discussions

### Code of Conduct

- **Be respectful** and inclusive
- **Provide constructive feedback**
- **Focus on the code**, not the person
- **Help others learn** and grow
- **Follow community guidelines**

## 🎉 Recognition

Contributors will be recognized in:
- **README.md contributors section**
- **Release notes** for significant contributions
- **GitHub contributors page**

Thank you for contributing to Agent Scholar! Your contributions help make AI research more accessible and powerful for everyone.