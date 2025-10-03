# Agent Scholar - End-to-End Testing Framework

This directory contains comprehensive end-to-end (E2E) tests for the Agent Scholar system, validating complete workflows, performance characteristics, and user acceptance criteria.

## Overview

The E2E testing framework validates:
- **Complex Multi-Step Queries**: Scenarios involving multiple tools and reasoning steps
- **Tool Coordination**: Proper orchestration between web search, document analysis, and code execution
- **Response Synthesis**: Quality of responses combining multiple information sources
- **Performance Benchmarks**: Response times, throughput, and resource usage
- **User Acceptance**: Real-world usage scenarios and user experience validation

## Test Structure

### Test Files

- **`test_end_to_end_scenarios.py`**: Complex multi-step research workflows
- **`test_performance_benchmarks.py`**: Performance, scalability, and resource usage tests
- **`test_user_acceptance.py`**: User experience and acceptance criteria validation
- **`test_runner.py`**: Comprehensive test orchestration and reporting
- **`test_config.json`**: Configuration for test execution parameters

### Test Categories

#### 1. End-to-End Scenarios (`test_end_to_end_scenarios.py`)

**Complex Multi-Step Queries**
- Comprehensive research workflows involving multiple tools
- Contradiction analysis across document sources
- Comparative analysis combining library documents with web search
- Data visualization workflows with code generation

**Tool Coordination**
- Sequential tool usage for complex analysis
- Parallel tool coordination for efficiency
- Error recovery and fallback mechanisms
- Response synthesis across multiple information sources

**Example Test Cases:**
```python
def test_comprehensive_research_workflow():
    """Test multi-step research involving document analysis, web search, and visualization."""
    
def test_contradiction_analysis_workflow():
    """Test finding contradictions and conflicting viewpoints across sources."""
    
def test_comparative_analysis_with_web_search():
    """Test combining library analysis with recent web developments."""
```

#### 2. Performance Benchmarks (`test_performance_benchmarks.py`)

**Response Time Performance**
- Simple query response times (target: <2s average)
- Complex query response times (target: <10s average)
- Mixed workload performance validation

**Throughput and Scalability**
- Sequential request throughput (target: >0.5 RPS)
- Concurrent request handling (target: >1 RPS with 5 concurrent)
- High concurrency load testing (target: 80% success rate at 10 concurrent)
- Sustained load performance over time

**Resource Usage Efficiency**
- Memory usage monitoring (target: <100MB average)
- Memory leak detection over multiple requests
- CPU usage efficiency (target: <80% average)
- Resource cleanup validation

**Example Test Cases:**
```python
def test_simple_query_response_time():
    """Validate response times for simple queries meet performance requirements."""
    
def test_concurrent_throughput():
    """Test system handling of concurrent requests."""
    
def test_memory_usage_efficiency():
    """Validate memory usage remains within acceptable limits."""
```

#### 3. User Acceptance Tests (`test_user_acceptance.py`)

**Researcher Workflows**
- Document upload and analysis scenarios
- Literature review assistance workflows
- Policy research and analysis scenarios
- Industry analyst trend analysis

**Complex Research Scenarios**
- Comprehensive AI ethics research projects
- Comparative analysis across multiple dimensions
- Research synthesis and insight generation

**User Experience Scenarios**
- Novice user guidance and support
- Expert user detailed analysis capabilities
- Iterative refinement of research questions
- Error recovery and clarification handling

**Demo Scenarios**
- AI healthcare research demonstrations
- Multi-tool coordination showcases
- Complete research workflow demonstrations

**Example Test Cases:**
```python
def test_document_upload_and_analysis():
    """Test typical researcher workflow of uploading and analyzing documents."""
    
def test_comprehensive_ai_ethics_research():
    """Test complex multi-step research project scenario."""
    
def test_ai_healthcare_demo_scenario():
    """Test demo scenario for AI in healthcare research."""
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-timeout pytest-json-report psutil

# Install optional dependencies for enhanced reporting
pip install pytest-html pytest-cov
```

### Basic Test Execution

```bash
# Run all E2E tests
python test_runner.py --all

# Run specific test categories
python test_runner.py --performance
python test_runner.py --user-acceptance

# Run with custom configuration
python test_runner.py --config test_config.json --timeout 1200
```

### Individual Test Files

```bash
# Run end-to-end scenarios
pytest test_end_to_end_scenarios.py -v

# Run performance benchmarks
pytest test_performance_benchmarks.py -v --timeout=900

# Run user acceptance tests
pytest test_user_acceptance.py -v
```

### Advanced Options

```bash
# Run with detailed output and coverage
pytest test_end_to_end_scenarios.py -v -s --cov=src --cov-report=html

# Run specific test classes
pytest test_user_acceptance.py::TestResearcherWorkflow -v

# Run with custom markers
pytest -m "not slow" test_performance_benchmarks.py
```

## Test Configuration

The `test_config.json` file controls test execution parameters:

```json
{
  "timeout": 900,
  "retry_failed": true,
  "max_retries": 2,
  "performance_benchmarks": true,
  "user_acceptance_tests": true,
  "quality_gates": {
    "min_success_rate": 95.0,
    "max_avg_response_time": 5.0,
    "max_memory_usage_mb": 150
  }
}
```

### Key Configuration Options

- **`timeout`**: Maximum time for test execution (seconds)
- **`retry_failed`**: Whether to retry failed tests
- **`quality_gates`**: Performance and quality thresholds
- **`reporting`**: Report generation and format options
- **`environment`**: Test environment configuration

## Performance Benchmarks

### Response Time Targets

| Query Type | Average | 95th Percentile | Maximum |
|------------|---------|-----------------|---------|
| Simple     | <2s     | <3s            | <5s     |
| Complex    | <10s    | <15s           | <30s    |
| Mixed      | <6s     | <12s           | <20s    |

### Throughput Targets

| Scenario | Target | Measurement |
|----------|--------|-------------|
| Sequential | >0.5 RPS | Requests per second |
| Concurrent (5) | >1.0 RPS | With 5 concurrent users |
| High Load (10) | 80% success | With 10 concurrent users |

### Resource Usage Targets

| Resource | Target | Measurement |
|----------|--------|-------------|
| Memory | <100MB average | Per request |
| CPU | <80% average | During processing |
| Memory Growth | <50MB | Over 20 requests |

## Test Reports

The test runner generates comprehensive reports including:

### JSON Report Structure
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "total_tests": 45,
  "passed_tests": 43,
  "failed_tests": 2,
  "success_rate": 95.6,
  "total_duration": 180.5,
  "performance_metrics": {
    "average_test_duration": 4.01,
    "max_test_duration": 15.2,
    "tests_per_minute": 15.0
  },
  "system_info": {
    "platform": "Linux-5.4.0",
    "python_version": "3.11.0",
    "cpu_count": 8,
    "memory_total_gb": 16.0
  }
}
```

### Report Locations
- **JSON Report**: `e2e_test_report_YYYYMMDD_HHMMSS.json`
- **HTML Report**: `e2e_test_report_YYYYMMDD_HHMMSS.html` (if enabled)
- **Console Output**: Real-time test execution status

## Quality Gates

Tests must meet these quality gates for deployment approval:

- **Success Rate**: ≥95% of tests must pass
- **Average Response Time**: ≤5 seconds for mixed workload
- **Memory Usage**: ≤150MB average per request
- **Concurrent Handling**: ≥80% success rate with 10 concurrent users

## Troubleshooting

### Common Issues

**Test Timeouts**
```bash
# Increase timeout for slow environments
python test_runner.py --timeout 1800
```

**Memory Issues**
```bash
# Run tests sequentially to reduce memory pressure
pytest test_performance_benchmarks.py -x --maxfail=1
```

**AWS Service Mocking**
```bash
# Ensure moto is installed for AWS service mocking
pip install moto[all]
```

### Debug Mode

```bash
# Run with verbose output and no capture
pytest test_end_to_end_scenarios.py -v -s --tb=long

# Run single test with debugging
pytest test_user_acceptance.py::TestResearcherWorkflow::test_document_upload_and_analysis -v -s
```

## Contributing

When adding new E2E tests:

1. **Follow Naming Conventions**: Use descriptive test names that explain the scenario
2. **Include Documentation**: Add docstrings explaining the test purpose and expected behavior
3. **Set Appropriate Timeouts**: Complex scenarios may need longer timeouts
4. **Validate Multiple Aspects**: Test functionality, performance, and user experience
5. **Use Realistic Data**: Create test scenarios that match real-world usage

### Test Template

```python
@pytest.mark.asyncio
async def test_new_scenario(e2e_framework):
    """
    Test description: What this test validates
    
    Scenario: Step-by-step description of the test scenario
    Expected: What should happen and what is being validated
    """
    # Setup
    e2e_framework.setup_test_scenario()
    
    # Execute
    response = await e2e_framework.execute_query("test query")
    
    # Validate
    assert response.success
    assert len(response.answer) > 100
    assert response.confidence_score > 0.7
```

## Integration with CI/CD

The E2E tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run E2E Tests
  run: |
    python tests/e2e/test_runner.py --all --timeout 1800
  env:
    AWS_DEFAULT_REGION: us-east-1
    
- name: Upload Test Reports
  uses: actions/upload-artifact@v2
  with:
    name: e2e-test-reports
    path: e2e_test_report_*.json
```

The test runner exits with appropriate codes:
- **0**: All tests passed (≥95% success rate)
- **1**: Some tests failed but acceptable (≥85% success rate)
- **2**: Too many failures (<85% success rate)
- **130**: Interrupted by user
- **1**: General error

This enables automated deployment decisions based on test results.