"""
Performance Benchmarking Tests for Agent Scholar

This module contains performance tests that validate response times,
resource usage, throughput, and scalability of the Agent Scholar system.
"""
import pytest
import time
import asyncio
import statistics
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple
import json
import uuid
from dataclasses import dataclass

# Import test utilities
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'shared'))

from models import ResearchQuery, AgentResponse

@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    response_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error_message: str = None
    tokens_processed: int = 0
    tools_used: int = 0

class PerformanceBenchmark:
    """Performance benchmarking framework."""
    
    def __init__(self):
        """Initialize the performance benchmark framework."""
        self.baseline_metrics = {}
        self.test_results = []
        self.process = psutil.Process()
    
    def measure_performance(self, func, *args, **kwargs) -> PerformanceMetrics:
        """Measure performance of a function execution."""
        # Get initial system state
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = self.process.cpu_percent()
        
        start_time = time.time()
        success = True
        error_message = None
        result = None
        
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            success = False
            error_message = str(e)
        
        end_time = time.time()
        
        # Get final system state
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        final_cpu = self.process.cpu_percent()
        
        # Calculate metrics
        response_time = end_time - start_time
        memory_usage = final_memory - initial_memory
        cpu_usage = (initial_cpu + final_cpu) / 2
        
        # Extract additional metrics from result
        tokens_processed = 0
        tools_used = 0
        
        if success and isinstance(result, AgentResponse):
            tokens_processed = len(result.answer.split())
            tools_used = len(result.tools_invoked)
        
        return PerformanceMetrics(
            response_time=response_time,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            success=success,
            error_message=error_message,
            tokens_processed=tokens_processed,
            tools_used=tools_used
        )
    
    def run_load_test(self, func, num_requests: int, concurrency: int = 1) -> List[PerformanceMetrics]:
        """Run load test with specified number of requests and concurrency."""
        results = []
        
        if concurrency == 1:
            # Sequential execution
            for i in range(num_requests):
                query = f"Test query {i}: What are the main themes in AI research?"
                metrics = self.measure_performance(func, query)
                results.append(metrics)
        else:
            # Concurrent execution
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = []
                
                for i in range(num_requests):
                    query = f"Concurrent test query {i}: Analyze AI trends and developments"
                    future = executor.submit(self.measure_performance, func, query)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        metrics = future.result()
                        results.append(metrics)
                    except Exception as e:
                        # Record failed request
                        results.append(PerformanceMetrics(
                            response_time=0,
                            memory_usage_mb=0,
                            cpu_usage_percent=0,
                            success=False,
                            error_message=str(e)
                        ))
        
        return results
    
    def analyze_results(self, results: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze performance test results."""
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        if not successful_results:
            return {
                'success_rate': 0.0,
                'total_requests': len(results),
                'failed_requests': len(failed_results),
                'error_rate': 1.0
            }
        
        response_times = [r.response_time for r in successful_results]
        memory_usage = [r.memory_usage_mb for r in successful_results]
        cpu_usage = [r.cpu_usage_percent for r in successful_results]
        tokens_processed = [r.tokens_processed for r in successful_results]
        
        return {
            'success_rate': len(successful_results) / len(results),
            'error_rate': len(failed_results) / len(results),
            'total_requests': len(results),
            'successful_requests': len(successful_results),
            'failed_requests': len(failed_results),
            'response_time': {
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'min': min(response_times),
                'max': max(response_times),
                'p95': self.percentile(response_times, 95),
                'p99': self.percentile(response_times, 99)
            },
            'memory_usage_mb': {
                'mean': statistics.mean(memory_usage),
                'max': max(memory_usage),
                'min': min(memory_usage)
            },
            'cpu_usage_percent': {
                'mean': statistics.mean(cpu_usage),
                'max': max(cpu_usage)
            },
            'throughput_rps': len(successful_results) / sum(response_times) if response_times else 0,
            'tokens_per_second': sum(tokens_processed) / sum(response_times) if response_times else 0
        }
    
    @staticmethod
    def percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

# Mock agent function for testing
def mock_agent_query(query: str) -> AgentResponse:
    """Mock agent query function for performance testing."""
    # Simulate processing time based on query complexity
    base_time = 0.5
    if "complex" in query.lower():
        time.sleep(base_time * 2)
    elif "simple" in query.lower():
        time.sleep(base_time * 0.5)
    else:
        time.sleep(base_time)
    
    # Simulate different tool usage
    tools_used = []
    if "search" in query.lower():
        tools_used.append("web_search")
    if "analyze" in query.lower():
        tools_used.append("cross_library_analysis")
    if "code" in query.lower() or "visualize" in query.lower():
        tools_used.append("code_execution")
    
    # Generate response
    answer = f"This is a response to: {query}. " * (len(query.split()) // 5 + 1)
    
    return AgentResponse(
        query=query,
        answer=answer,
        sources_used=["doc1", "doc2"],
        tools_invoked=tools_used,
        reasoning_steps=["Step 1: Analyze query", "Step 2: Process information"],
        confidence_score=0.85,
        processing_time=base_time,
        session_id=str(uuid.uuid4())
    )

class TestResponseTimePerformance:
    """Test response time performance requirements."""
    
    def setup_method(self):
        """Set up performance benchmark."""
        self.benchmark = PerformanceBenchmark()
    
    def test_simple_query_response_time(self):
        """Test response time for simple queries."""
        simple_queries = [
            "What is machine learning?",
            "Define artificial intelligence",
            "Explain neural networks",
            "What are the benefits of AI?"
        ]
        
        results = []
        for query in simple_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Performance requirements for simple queries
        assert analysis['success_rate'] >= 0.95  # 95% success rate
        assert analysis['response_time']['mean'] <= 2.0  # Average under 2 seconds
        assert analysis['response_time']['p95'] <= 3.0  # 95th percentile under 3 seconds
        assert analysis['response_time']['max'] <= 5.0  # Max under 5 seconds
    
    def test_complex_query_response_time(self):
        """Test response time for complex queries."""
        complex_queries = [
            "Complex analysis: Compare AI ethics perspectives across multiple sources and generate visualizations",
            "Complex search: Find recent developments in machine learning and analyze trends with code execution",
            "Complex synthesis: Combine document analysis, web search, and data visualization for comprehensive report"
        ]
        
        results = []
        for query in complex_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Performance requirements for complex queries
        assert analysis['success_rate'] >= 0.90  # 90% success rate
        assert analysis['response_time']['mean'] <= 10.0  # Average under 10 seconds
        assert analysis['response_time']['p95'] <= 15.0  # 95th percentile under 15 seconds
        assert analysis['response_time']['max'] <= 30.0  # Max under 30 seconds
    
    def test_mixed_workload_performance(self):
        """Test performance with mixed simple and complex queries."""
        mixed_queries = [
            "What is AI?",  # Simple
            "Complex: Analyze themes and search recent developments",  # Complex
            "Define machine learning",  # Simple
            "Complex: Generate code visualization of document analysis",  # Complex
            "Explain deep learning",  # Simple
        ]
        
        results = []
        for query in mixed_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Performance requirements for mixed workload
        assert analysis['success_rate'] >= 0.95
        assert analysis['response_time']['mean'] <= 6.0  # Average under 6 seconds
        assert analysis['throughput_rps'] >= 0.2  # At least 0.2 requests per second

class TestThroughputAndScalability:
    """Test system throughput and scalability."""
    
    def setup_method(self):
        """Set up performance benchmark."""
        self.benchmark = PerformanceBenchmark()
    
    def test_sequential_throughput(self):
        """Test sequential request throughput."""
        num_requests = 20
        results = self.benchmark.run_load_test(mock_agent_query, num_requests, concurrency=1)
        analysis = self.benchmark.analyze_results(results)
        
        # Throughput requirements
        assert analysis['success_rate'] >= 0.95
        assert analysis['throughput_rps'] >= 0.5  # At least 0.5 RPS sequential
        assert analysis['response_time']['mean'] <= 3.0
    
    def test_concurrent_throughput(self):
        """Test concurrent request handling."""
        num_requests = 20
        concurrency = 5
        
        results = self.benchmark.run_load_test(mock_agent_query, num_requests, concurrency)
        analysis = self.benchmark.analyze_results(results)
        
        # Concurrent throughput requirements
        assert analysis['success_rate'] >= 0.90  # Allow for some failures under load
        assert analysis['throughput_rps'] >= 1.0  # At least 1 RPS with concurrency
        assert analysis['response_time']['p95'] <= 10.0
    
    def test_high_concurrency_handling(self):
        """Test handling of high concurrency loads."""
        num_requests = 30
        concurrency = 10
        
        results = self.benchmark.run_load_test(mock_agent_query, num_requests, concurrency)
        analysis = self.benchmark.analyze_results(results)
        
        # High concurrency requirements (more lenient)
        assert analysis['success_rate'] >= 0.80  # 80% success under high load
        assert analysis['error_rate'] <= 0.20  # Max 20% error rate
        assert analysis['response_time']['mean'] <= 15.0
    
    def test_sustained_load_performance(self):
        """Test performance under sustained load."""
        # Simulate sustained load over time
        total_requests = 50
        batch_size = 10
        batches = total_requests // batch_size
        
        all_results = []
        
        for batch in range(batches):
            batch_results = self.benchmark.run_load_test(
                mock_agent_query, batch_size, concurrency=3
            )
            all_results.extend(batch_results)
            
            # Small delay between batches
            time.sleep(0.5)
        
        analysis = self.benchmark.analyze_results(all_results)
        
        # Sustained load requirements
        assert analysis['success_rate'] >= 0.85
        assert analysis['response_time']['mean'] <= 8.0
        assert len([r for r in all_results if r.success]) >= 40  # At least 40 successful

class TestResourceUsageEfficiency:
    """Test memory and CPU usage efficiency."""
    
    def setup_method(self):
        """Set up performance benchmark."""
        self.benchmark = PerformanceBenchmark()
    
    def test_memory_usage_efficiency(self):
        """Test memory usage remains efficient."""
        # Test with various query sizes
        queries = [
            "Short query",
            "Medium length query about AI and machine learning topics",
            "Very long query " + "with lots of repeated content " * 20,
            "Complex analysis query requiring multiple tools and comprehensive response generation"
        ]
        
        results = []
        for query in queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Memory efficiency requirements
        assert analysis['memory_usage_mb']['mean'] <= 100  # Average under 100MB
        assert analysis['memory_usage_mb']['max'] <= 200   # Max under 200MB
        assert all(r.success for r in results)  # No memory-related failures
    
    def test_memory_leak_detection(self):
        """Test for memory leaks over multiple requests."""
        initial_memory = self.benchmark.process.memory_info().rss / 1024 / 1024
        
        # Run multiple requests
        for i in range(20):
            query = f"Memory test query {i}: Analyze AI developments"
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            assert metrics.success
        
        final_memory = self.benchmark.process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        
        # Memory leak detection
        assert memory_growth <= 50  # Memory growth under 50MB
    
    def test_cpu_usage_efficiency(self):
        """Test CPU usage efficiency."""
        num_requests = 15
        results = self.benchmark.run_load_test(mock_agent_query, num_requests, concurrency=3)
        analysis = self.benchmark.analyze_results(results)
        
        # CPU efficiency requirements
        assert analysis['cpu_usage_percent']['mean'] <= 80  # Average CPU under 80%
        assert analysis['success_rate'] >= 0.90
    
    def test_resource_cleanup(self):
        """Test that resources are properly cleaned up."""
        initial_threads = threading.active_count()
        initial_memory = self.benchmark.process.memory_info().rss / 1024 / 1024
        
        # Run concurrent requests
        results = self.benchmark.run_load_test(mock_agent_query, 10, concurrency=5)
        
        # Wait for cleanup
        time.sleep(2)
        
        final_threads = threading.active_count()
        final_memory = self.benchmark.process.memory_info().rss / 1024 / 1024
        
        # Resource cleanup verification
        assert final_threads <= initial_threads + 2  # Allow for some thread variance
        assert final_memory - initial_memory <= 30   # Memory increase under 30MB
        assert all(r.success for r in results if r.success)

class TestScalabilityLimits:
    """Test system scalability limits and breaking points."""
    
    def setup_method(self):
        """Set up performance benchmark."""
        self.benchmark = PerformanceBenchmark()
    
    def test_maximum_concurrent_requests(self):
        """Test maximum number of concurrent requests the system can handle."""
        max_concurrency_levels = [5, 10, 15, 20]
        results_by_concurrency = {}
        
        for concurrency in max_concurrency_levels:
            results = self.benchmark.run_load_test(
                mock_agent_query, 
                num_requests=concurrency * 2,  # 2 requests per concurrent thread
                concurrency=concurrency
            )
            analysis = self.benchmark.analyze_results(results)
            results_by_concurrency[concurrency] = analysis
        
        # Find the breaking point
        acceptable_success_rate = 0.80
        max_acceptable_concurrency = 0
        
        for concurrency, analysis in results_by_concurrency.items():
            if analysis['success_rate'] >= acceptable_success_rate:
                max_acceptable_concurrency = concurrency
            else:
                break
        
        # Verify system can handle reasonable concurrency
        assert max_acceptable_concurrency >= 10  # At least 10 concurrent requests
        
        # Verify graceful degradation
        for concurrency, analysis in results_by_concurrency.items():
            if concurrency <= max_acceptable_concurrency:
                assert analysis['success_rate'] >= acceptable_success_rate
    
    def test_large_response_handling(self):
        """Test handling of queries that generate large responses."""
        large_queries = [
            "Generate a comprehensive analysis " + "with detailed explanations " * 50,
            "Create extensive documentation " + "covering all aspects " * 30,
            "Provide thorough research summary " + "including all findings " * 40
        ]
        
        results = []
        for query in large_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Large response handling requirements
        assert analysis['success_rate'] >= 0.90
        assert analysis['response_time']['max'] <= 20.0  # Max 20 seconds for large responses
        assert analysis['memory_usage_mb']['max'] <= 300  # Max 300MB for large responses
    
    def test_burst_traffic_handling(self):
        """Test handling of sudden traffic bursts."""
        # Simulate burst traffic pattern
        burst_sizes = [5, 15, 25, 10, 5]  # Sudden spike then gradual decrease
        all_results = []
        
        for burst_size in burst_sizes:
            burst_results = self.benchmark.run_load_test(
                mock_agent_query, 
                num_requests=burst_size,
                concurrency=min(burst_size, 10)
            )
            all_results.extend(burst_results)
            time.sleep(1)  # Brief pause between bursts
        
        analysis = self.benchmark.analyze_results(all_results)
        
        # Burst handling requirements
        assert analysis['success_rate'] >= 0.75  # 75% success during bursts
        assert analysis['response_time']['p95'] <= 15.0
        assert analysis['error_rate'] <= 0.25

class TestPerformanceRegression:
    """Test for performance regressions."""
    
    def setup_method(self):
        """Set up performance benchmark."""
        self.benchmark = PerformanceBenchmark()
        
        # Baseline performance metrics (would be loaded from previous runs)
        self.baseline_metrics = {
            'simple_query_mean_time': 1.5,
            'complex_query_mean_time': 8.0,
            'throughput_rps': 0.8,
            'memory_usage_mb': 75,
            'success_rate': 0.95
        }
    
    def test_performance_regression_detection(self):
        """Test detection of performance regressions."""
        # Run current performance tests
        simple_queries = ["What is AI?", "Define ML", "Explain DL"]
        complex_queries = ["Complex: Analyze and visualize AI trends with multiple tools"]
        
        simple_results = []
        for query in simple_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            simple_results.append(metrics)
        
        complex_results = []
        for query in complex_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            complex_results.append(metrics)
        
        simple_analysis = self.benchmark.analyze_results(simple_results)
        complex_analysis = self.benchmark.analyze_results(complex_results)
        
        # Check for regressions (allow 20% degradation)
        regression_threshold = 1.2
        
        assert simple_analysis['response_time']['mean'] <= self.baseline_metrics['simple_query_mean_time'] * regression_threshold
        assert complex_analysis['response_time']['mean'] <= self.baseline_metrics['complex_query_mean_time'] * regression_threshold
        assert simple_analysis['success_rate'] >= self.baseline_metrics['success_rate'] * 0.95  # 5% degradation allowed
    
    def test_performance_improvement_validation(self):
        """Test validation of performance improvements."""
        # This test would validate that optimizations actually improve performance
        # For now, we'll test that current performance meets or exceeds targets
        
        test_queries = [
            "Analyze AI ethics themes",
            "Search recent ML developments", 
            "Generate visualization code"
        ]
        
        results = []
        for query in test_queries:
            metrics = self.benchmark.measure_performance(mock_agent_query, query)
            results.append(metrics)
        
        analysis = self.benchmark.analyze_results(results)
        
        # Performance targets (should meet or exceed baseline)
        assert analysis['response_time']['mean'] <= 5.0
        assert analysis['success_rate'] >= 0.95
        assert analysis['throughput_rps'] >= 0.3

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])