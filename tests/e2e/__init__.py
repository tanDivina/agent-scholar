"""
Agent Scholar End-to-End Testing Framework

This package contains comprehensive end-to-end tests for the Agent Scholar system,
including complex multi-step scenarios, performance benchmarks, and user acceptance tests.

Test Categories:
- End-to-End Scenarios: Complex multi-step research workflows
- Performance Benchmarks: Response times, throughput, and resource usage
- User Acceptance Tests: Real-world usage scenarios and user experience

Usage:
    # Run all E2E tests
    python -m tests.e2e.test_runner --all
    
    # Run specific test categories
    python -m tests.e2e.test_runner --performance
    
    # Run individual test files
    pytest tests/e2e/test_end_to_end_scenarios.py -v
"""

__version__ = "1.0.0"
__author__ = "Agent Scholar Team"

# Import main test framework components
from .test_runner import E2ETestRunner, TestResult, TestSuite, TestReport

# Import test frameworks
try:
    from .test_end_to_end_scenarios import E2ETestFramework
    from .test_performance_benchmarks import PerformanceBenchmark, PerformanceMetrics
    from .test_user_acceptance import UserAcceptanceTestFramework
except ImportError:
    # Handle cases where test dependencies might not be available
    pass

__all__ = [
    'E2ETestRunner',
    'TestResult', 
    'TestSuite',
    'TestReport',
    'E2ETestFramework',
    'PerformanceBenchmark',
    'PerformanceMetrics',
    'UserAcceptanceTestFramework'
]