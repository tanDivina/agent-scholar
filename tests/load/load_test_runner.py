"""
Load Testing Framework for Agent Scholar

This module provides comprehensive load testing capabilities to validate
system performance under various load conditions and identify scaling requirements.
"""
import asyncio
import aiohttp
import time
import json
import statistics
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime, timedelta
import uuid
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    base_url: str
    total_requests: int
    concurrent_users: int
    ramp_up_time: int  # seconds
    test_duration: int  # seconds
    request_timeout: int  # seconds
    think_time_min: float  # seconds between requests
    think_time_max: float  # seconds between requests
    auth_token: Optional[str] = None
    test_scenarios: List[str] = None

@dataclass
class RequestResult:
    """Result of a single request."""
    timestamp: float
    response_time: float
    status_code: int
    success: bool
    error_message: Optional[str] = None
    response_size: int = 0
    scenario: str = "default"

@dataclass
class LoadTestResults:
    """Comprehensive load test results."""
    config: LoadTestConfig
    start_time: datetime
    end_time: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    requests_per_second: float
    errors_per_second: float
    success_rate: float
    error_rate: float
    throughput_mb_per_sec: float
    concurrent_users_achieved: int
    error_breakdown: Dict[str, int]
    response_time_distribution: List[float]
    detailed_results: List[RequestResult]

class LoadTestScenarios:
    """Predefined load test scenarios for Agent Scholar."""
    
    @staticmethod
    def simple_query_scenario() -> Dict[str, Any]:
        """Simple research query scenario."""
        queries = [
            "What is machine learning?",
            "Define artificial intelligence",
            "Explain neural networks",
            "What are the benefits of AI?",
            "How does deep learning work?"
        ]
        
        return {
            "endpoint": "/research",
            "method": "POST",
            "payload": {
                "query": random.choice(queries),
                "session_id": str(uuid.uuid4())
            },
            "scenario": "simple_query"
        }
    
    @staticmethod
    def complex_analysis_scenario() -> Dict[str, Any]:
        """Complex analysis scenario with multiple tools."""
        queries = [
            "Analyze the themes in my document library and create a visualization",
            "Search for recent AI developments and compare with my research",
            "Find contradictions in AI ethics perspectives across sources",
            "Generate code to visualize machine learning trends",
            "Synthesize insights from multiple research papers"
        ]
        
        return {
            "endpoint": "/research",
            "method": "POST",
            "payload": {
                "query": random.choice(queries),
                "session_id": str(uuid.uuid4()),
                "enable_tools": ["web_search", "cross_library_analysis", "code_execution"]
            },
            "scenario": "complex_analysis"
        }
    
    @staticmethod
    def document_upload_scenario() -> Dict[str, Any]:
        """Document upload and processing scenario."""
        return {
            "endpoint": "/documents/upload",
            "method": "POST",
            "payload": {
                "filename": f"test_document_{uuid.uuid4().hex[:8]}.txt",
                "content": "This is a test document for load testing. " * 100,
                "content_type": "text/plain"
            },
            "scenario": "document_upload"
        }
    
    @staticmethod
    def authentication_scenario() -> Dict[str, Any]:
        """Authentication scenario."""
        return {
            "endpoint": "/auth/login",
            "method": "POST",
            "payload": {
                "email": f"testuser{random.randint(1, 1000)}@example.com",
                "password": "TestPassword123!"
            },
            "scenario": "authentication"
        }
    
    @staticmethod
    def mixed_workload_scenario() -> Dict[str, Any]:
        """Mixed workload scenario."""
        scenarios = [
            LoadTestScenarios.simple_query_scenario,
            LoadTestScenarios.complex_analysis_scenario,
            LoadTestScenarios.document_upload_scenario,
            LoadTestScenarios.authentication_scenario
        ]
        
        return random.choice(scenarios)()

class LoadTestRunner:
    """Main load testing framework."""
    
    def __init__(self, config: LoadTestConfig):
        """Initialize load test runner."""
        self.config = config
        self.results = []
        self.start_time = None
        self.end_time = None
        self.active_users = 0
        self.lock = threading.Lock()
        
        # Scenario mapping
        self.scenarios = {
            "simple_query": LoadTestScenarios.simple_query_scenario,
            "complex_analysis": LoadTestScenarios.complex_analysis_scenario,
            "document_upload": LoadTestScenarios.document_upload_scenario,
            "authentication": LoadTestScenarios.authentication_scenario,
            "mixed_workload": LoadTestScenarios.mixed_workload_scenario
        }
    
    async def run_load_test(self) -> LoadTestResults:
        """Execute the load test."""
        logger.info(f"Starting load test with {self.config.concurrent_users} concurrent users")
        logger.info(f"Target: {self.config.total_requests} requests over {self.config.test_duration} seconds")
        
        self.start_time = datetime.now()
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.config.concurrent_users)
        
        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,
            limit_per_host=self.config.concurrent_users,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._get_default_headers()
        ) as session:
            # Generate tasks based on test strategy
            if self.config.test_duration > 0:
                tasks = await self._create_duration_based_tasks(session, semaphore)
            else:
                tasks = await self._create_request_based_tasks(session, semaphore)
            
            # Execute all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            self.results = [r for r in results if isinstance(r, RequestResult)]
        
        self.end_time = datetime.now()
        
        return self._analyze_results()
    
    async def _create_duration_based_tasks(self, session: aiohttp.ClientSession, 
                                         semaphore: asyncio.Semaphore) -> List[asyncio.Task]:
        """Create tasks for duration-based testing."""
        tasks = []
        end_time = time.time() + self.config.test_duration
        
        # Ramp up users gradually
        ramp_up_delay = self.config.ramp_up_time / self.config.concurrent_users
        
        for user_id in range(self.config.concurrent_users):
            task = asyncio.create_task(
                self._user_session(session, semaphore, user_id, end_time)
            )
            tasks.append(task)
            
            # Add ramp-up delay
            if ramp_up_delay > 0:
                await asyncio.sleep(ramp_up_delay)
        
        return tasks
    
    async def _create_request_based_tasks(self, session: aiohttp.ClientSession,
                                        semaphore: asyncio.Semaphore) -> List[asyncio.Task]:
        """Create tasks for request-count-based testing."""
        tasks = []
        requests_per_user = self.config.total_requests // self.config.concurrent_users
        remaining_requests = self.config.total_requests % self.config.concurrent_users
        
        for user_id in range(self.config.concurrent_users):
            user_requests = requests_per_user
            if user_id < remaining_requests:
                user_requests += 1
            
            for request_id in range(user_requests):
                task = asyncio.create_task(
                    self._make_request(session, semaphore, f"user_{user_id}_req_{request_id}")
                )
                tasks.append(task)
        
        return tasks
    
    async def _user_session(self, session: aiohttp.ClientSession, 
                          semaphore: asyncio.Semaphore, user_id: int, 
                          end_time: float) -> List[RequestResult]:
        """Simulate a user session with multiple requests."""
        user_results = []
        request_count = 0
        
        while time.time() < end_time:
            result = await self._make_request(session, semaphore, f"user_{user_id}_req_{request_count}")
            user_results.append(result)
            request_count += 1
            
            # Think time between requests
            think_time = random.uniform(self.config.think_time_min, self.config.think_time_max)
            await asyncio.sleep(think_time)
        
        return user_results
    
    async def _make_request(self, session: aiohttp.ClientSession, 
                          semaphore: asyncio.Semaphore, request_id: str) -> RequestResult:
        """Make a single HTTP request."""
        async with semaphore:
            with self.lock:
                self.active_users += 1
            
            try:
                # Get scenario
                scenario_data = self._get_scenario()
                
                # Prepare request
                url = f"{self.config.base_url}{scenario_data['endpoint']}"
                method = scenario_data['method']
                payload = scenario_data['payload']
                scenario_name = scenario_data['scenario']
                
                # Make request
                start_time = time.time()
                
                if method.upper() == 'POST':
                    async with session.post(url, json=payload) as response:
                        response_text = await response.text()
                        response_size = len(response_text.encode('utf-8'))
                elif method.upper() == 'GET':
                    async with session.get(url, params=payload) as response:
                        response_text = await response.text()
                        response_size = len(response_text.encode('utf-8'))
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                end_time = time.time()
                response_time = end_time - start_time
                
                # Determine success
                success = 200 <= response.status < 400
                error_message = None if success else f"HTTP {response.status}: {response_text[:200]}"
                
                return RequestResult(
                    timestamp=start_time,
                    response_time=response_time,
                    status_code=response.status,
                    success=success,
                    error_message=error_message,
                    response_size=response_size,
                    scenario=scenario_name
                )
                
            except asyncio.TimeoutError:
                return RequestResult(
                    timestamp=time.time(),
                    response_time=self.config.request_timeout,
                    status_code=0,
                    success=False,
                    error_message="Request timeout",
                    scenario=scenario_data.get('scenario', 'unknown')
                )
            except Exception as e:
                return RequestResult(
                    timestamp=time.time(),
                    response_time=0,
                    status_code=0,
                    success=False,
                    error_message=str(e),
                    scenario=scenario_data.get('scenario', 'unknown')
                )
            finally:
                with self.lock:
                    self.active_users -= 1
    
    def _get_scenario(self) -> Dict[str, Any]:
        """Get test scenario based on configuration."""
        if not self.config.test_scenarios:
            return LoadTestScenarios.mixed_workload_scenario()
        
        scenario_name = random.choice(self.config.test_scenarios)
        scenario_func = self.scenarios.get(scenario_name, LoadTestScenarios.mixed_workload_scenario)
        return scenario_func()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AgentScholar-LoadTest/1.0'
        }
        
        if self.config.auth_token:
            headers['Authorization'] = f'Bearer {self.config.auth_token}'
        
        return headers
    
    def _analyze_results(self) -> LoadTestResults:
        """Analyze load test results."""
        if not self.results:
            raise ValueError("No results to analyze")
        
        # Basic statistics
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if r.success])
        failed_requests = total_requests - successful_requests
        
        # Response time statistics
        response_times = [r.response_time for r in self.results if r.success]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = self._percentile(response_times, 95)
            p99_response_time = self._percentile(response_times, 99)
        else:
            avg_response_time = median_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0
        
        # Throughput calculations
        test_duration = (self.end_time - self.start_time).total_seconds()
        requests_per_second = successful_requests / test_duration if test_duration > 0 else 0
        errors_per_second = failed_requests / test_duration if test_duration > 0 else 0
        
        # Success/error rates
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
        error_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0
        
        # Throughput in MB/s
        total_bytes = sum(r.response_size for r in self.results if r.success)
        throughput_mb_per_sec = (total_bytes / (1024 * 1024)) / test_duration if test_duration > 0 else 0
        
        # Error breakdown
        error_breakdown = {}
        for result in self.results:
            if not result.success and result.error_message:
                error_type = result.error_message.split(':')[0]
                error_breakdown[error_type] = error_breakdown.get(error_type, 0) + 1
        
        # Concurrent users achieved
        concurrent_users_achieved = min(self.config.concurrent_users, total_requests)
        
        return LoadTestResults(
            config=self.config,
            start_time=self.start_time,
            end_time=self.end_time,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            median_response_time=median_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            requests_per_second=requests_per_second,
            errors_per_second=errors_per_second,
            success_rate=success_rate,
            error_rate=error_rate,
            throughput_mb_per_sec=throughput_mb_per_sec,
            concurrent_users_achieved=concurrent_users_achieved,
            error_breakdown=error_breakdown,
            response_time_distribution=response_times,
            detailed_results=self.results
        )
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

class LoadTestReporter:
    """Generate comprehensive load test reports."""
    
    @staticmethod
    def generate_console_report(results: LoadTestResults) -> None:
        """Generate console report."""
        print("\n" + "=" * 80)
        print("AGENT SCHOLAR - LOAD TEST RESULTS")
        print("=" * 80)
        
        print(f"\nTest Configuration:")
        print(f"  Base URL: {results.config.base_url}")
        print(f"  Total Requests: {results.total_requests}")
        print(f"  Concurrent Users: {results.config.concurrent_users}")
        print(f"  Test Duration: {(results.end_time - results.start_time).total_seconds():.1f} seconds")
        
        print(f"\nOverall Results:")
        print(f"  Successful Requests: {results.successful_requests}")
        print(f"  Failed Requests: {results.failed_requests}")
        print(f"  Success Rate: {results.success_rate:.1f}%")
        print(f"  Error Rate: {results.error_rate:.1f}%")
        
        print(f"\nPerformance Metrics:")
        print(f"  Requests/Second: {results.requests_per_second:.2f}")
        print(f"  Average Response Time: {results.average_response_time:.3f}s")
        print(f"  Median Response Time: {results.median_response_time:.3f}s")
        print(f"  95th Percentile: {results.p95_response_time:.3f}s")
        print(f"  99th Percentile: {results.p99_response_time:.3f}s")
        print(f"  Min Response Time: {results.min_response_time:.3f}s")
        print(f"  Max Response Time: {results.max_response_time:.3f}s")
        print(f"  Throughput: {results.throughput_mb_per_sec:.2f} MB/s")
        
        if results.error_breakdown:
            print(f"\nError Breakdown:")
            for error_type, count in results.error_breakdown.items():
                print(f"  {error_type}: {count}")
        
        # Performance assessment
        print(f"\nPerformance Assessment:")
        if results.success_rate >= 99:
            print("  ✅ Excellent: >99% success rate")
        elif results.success_rate >= 95:
            print("  ✅ Good: >95% success rate")
        elif results.success_rate >= 90:
            print("  ⚠️  Acceptable: >90% success rate")
        else:
            print("  ❌ Poor: <90% success rate")
        
        if results.p95_response_time <= 5.0:
            print("  ✅ Excellent: P95 response time ≤5s")
        elif results.p95_response_time <= 10.0:
            print("  ✅ Good: P95 response time ≤10s")
        elif results.p95_response_time <= 15.0:
            print("  ⚠️  Acceptable: P95 response time ≤15s")
        else:
            print("  ❌ Poor: P95 response time >15s")
        
        if results.requests_per_second >= 10:
            print("  ✅ Excellent: ≥10 RPS")
        elif results.requests_per_second >= 5:
            print("  ✅ Good: ≥5 RPS")
        elif results.requests_per_second >= 1:
            print("  ⚠️  Acceptable: ≥1 RPS")
        else:
            print("  ❌ Poor: <1 RPS")
    
    @staticmethod
    def generate_json_report(results: LoadTestResults, filename: str) -> None:
        """Generate JSON report."""
        report_data = asdict(results)
        
        # Convert datetime objects to strings
        report_data['start_time'] = results.start_time.isoformat()
        report_data['end_time'] = results.end_time.isoformat()
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"JSON report saved to: {filename}")
    
    @staticmethod
    def generate_csv_report(results: LoadTestResults, filename: str) -> None:
        """Generate CSV report with detailed results."""
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'timestamp', 'response_time', 'status_code', 'success',
                'error_message', 'response_size', 'scenario'
            ])
            
            # Data
            for result in results.detailed_results:
                writer.writerow([
                    result.timestamp,
                    result.response_time,
                    result.status_code,
                    result.success,
                    result.error_message or '',
                    result.response_size,
                    result.scenario
                ])
        
        print(f"CSV report saved to: {filename}")

async def main():
    """Main function for running load tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Scholar Load Test Runner")
    parser.add_argument("--url", required=True, help="Base URL for testing")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests")
    parser.add_argument("--users", type=int, default=10, help="Concurrent users")
    parser.add_argument("--duration", type=int, default=0, help="Test duration in seconds (0 for request-based)")
    parser.add_argument("--ramp-up", type=int, default=10, help="Ramp-up time in seconds")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--think-time", type=float, default=1.0, help="Think time between requests")
    parser.add_argument("--auth-token", help="Authentication token")
    parser.add_argument("--scenarios", nargs='+', help="Test scenarios to run")
    parser.add_argument("--output", help="Output file prefix for reports")
    
    args = parser.parse_args()
    
    # Create configuration
    config = LoadTestConfig(
        base_url=args.url,
        total_requests=args.requests,
        concurrent_users=args.users,
        ramp_up_time=args.ramp_up,
        test_duration=args.duration,
        request_timeout=args.timeout,
        think_time_min=args.think_time * 0.5,
        think_time_max=args.think_time * 1.5,
        auth_token=args.auth_token,
        test_scenarios=args.scenarios
    )
    
    # Run load test
    runner = LoadTestRunner(config)
    results = await runner.run_load_test()
    
    # Generate reports
    LoadTestReporter.generate_console_report(results)
    
    if args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        LoadTestReporter.generate_json_report(results, f"{args.output}_{timestamp}.json")
        LoadTestReporter.generate_csv_report(results, f"{args.output}_{timestamp}.csv")

if __name__ == "__main__":
    asyncio.run(main())