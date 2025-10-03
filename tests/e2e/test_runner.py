"""
End-to-End Test Runner for Agent Scholar

This module provides a comprehensive test runner that orchestrates all
end-to-end tests, generates reports, and validates system readiness.
"""
import pytest
import json
import time
import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Container for test execution results."""
    test_name: str
    status: str  # 'passed', 'failed', 'skipped'
    duration: float
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

@dataclass
class TestSuite:
    """Container for test suite information."""
    name: str
    description: str
    test_files: List[str]
    required: bool = True
    timeout: int = 300  # 5 minutes default

@dataclass
class TestReport:
    """Container for comprehensive test report."""
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    total_duration: float
    success_rate: float
    test_results: List[TestResult]
    system_info: Dict[str, Any]
    performance_metrics: Dict[str, Any]

class E2ETestRunner:
    """Comprehensive end-to-end test runner."""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the test runner."""
        self.config = self.load_config(config_file)
        self.test_suites = self.define_test_suites()
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load test configuration."""
        default_config = {
            "parallel_execution": False,
            "max_workers": 4,
            "timeout": 600,  # 10 minutes
            "retry_failed": True,
            "max_retries": 2,
            "generate_report": True,
            "report_format": "json",
            "performance_benchmarks": True,
            "user_acceptance_tests": True,
            "integration_tests": True
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")
        
        return default_config
    
    def define_test_suites(self) -> List[TestSuite]:
        """Define all test suites to be executed."""
        return [
            TestSuite(
                name="End-to-End Scenarios",
                description="Complex multi-step query scenarios and tool coordination",
                test_files=["test_end_to_end_scenarios.py"],
                required=True,
                timeout=600
            ),
            TestSuite(
                name="Performance Benchmarks",
                description="Response time, throughput, and resource usage tests",
                test_files=["test_performance_benchmarks.py"],
                required=self.config.get("performance_benchmarks", True),
                timeout=900
            ),
            TestSuite(
                name="User Acceptance Tests",
                description="Real-world usage scenarios and user experience validation",
                test_files=["test_user_acceptance.py"],
                required=self.config.get("user_acceptance_tests", True),
                timeout=600
            )
        ]
    
    def run_all_tests(self) -> TestReport:
        """Run all test suites and generate comprehensive report."""
        logger.info("Starting comprehensive end-to-end test execution")
        self.start_time = time.time()
        
        # System information
        system_info = self.collect_system_info()
        logger.info(f"System info: {system_info}")
        
        # Execute test suites
        all_results = []
        for suite in self.test_suites:
            if suite.required or self.should_run_suite(suite):
                logger.info(f"Executing test suite: {suite.name}")
                suite_results = self.run_test_suite(suite)
                all_results.extend(suite_results)
            else:
                logger.info(f"Skipping test suite: {suite.name}")
        
        self.end_time = time.time()
        
        # Generate report
        report = self.generate_report(all_results, system_info)
        
        if self.config.get("generate_report", True):
            self.save_report(report)
        
        return report
    
    def run_test_suite(self, suite: TestSuite) -> List[TestResult]:
        """Run a specific test suite."""
        suite_results = []
        
        for test_file in suite.test_files:
            test_path = os.path.join(os.path.dirname(__file__), test_file)
            
            if not os.path.exists(test_path):
                logger.warning(f"Test file not found: {test_path}")
                suite_results.append(TestResult(
                    test_name=test_file,
                    status="skipped",
                    duration=0,
                    error_message="Test file not found"
                ))
                continue
            
            # Run pytest on the test file
            results = self.run_pytest(test_path, suite.timeout)
            suite_results.extend(results)
        
        return suite_results
    
    def run_pytest(self, test_path: str, timeout: int) -> List[TestResult]:
        """Run pytest on a specific test file."""
        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--json-report",
            "--json-report-file=/tmp/pytest_report.json"
        ]
        
        if timeout:
            cmd.extend(["--timeout", str(timeout)])
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            # Parse pytest JSON report if available
            pytest_results = self.parse_pytest_report("/tmp/pytest_report.json")
            
            if pytest_results:
                return pytest_results
            else:
                # Fallback to basic result parsing
                return self.parse_pytest_output(result, test_path, duration)
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return [TestResult(
                test_name=os.path.basename(test_path),
                status="failed",
                duration=duration,
                error_message=f"Test timed out after {timeout} seconds"
            )]
        except Exception as e:
            duration = time.time() - start_time
            return [TestResult(
                test_name=os.path.basename(test_path),
                status="failed",
                duration=duration,
                error_message=str(e)
            )]
    
    def parse_pytest_report(self, report_path: str) -> Optional[List[TestResult]]:
        """Parse pytest JSON report."""
        try:
            if not os.path.exists(report_path):
                return None
                
            with open(report_path, 'r') as f:
                report_data = json.load(f)
            
            results = []
            for test in report_data.get("tests", []):
                status = "passed" if test["outcome"] == "passed" else "failed"
                if test["outcome"] == "skipped":
                    status = "skipped"
                
                results.append(TestResult(
                    test_name=test["nodeid"],
                    status=status,
                    duration=test.get("duration", 0),
                    error_message=test.get("call", {}).get("longrepr") if status == "failed" else None,
                    details={
                        "setup_duration": test.get("setup", {}).get("duration", 0),
                        "call_duration": test.get("call", {}).get("duration", 0),
                        "teardown_duration": test.get("teardown", {}).get("duration", 0)
                    }
                ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to parse pytest report: {e}")
            return None
    
    def parse_pytest_output(self, result: subprocess.CompletedProcess, 
                          test_path: str, duration: float) -> List[TestResult]:
        """Parse pytest output when JSON report is not available."""
        test_name = os.path.basename(test_path)
        
        if result.returncode == 0:
            status = "passed"
            error_message = None
        else:
            status = "failed"
            error_message = result.stderr or result.stdout
        
        return [TestResult(
            test_name=test_name,
            status=status,
            duration=duration,
            error_message=error_message
        )]
    
    def should_run_suite(self, suite: TestSuite) -> bool:
        """Determine if a test suite should be run based on configuration."""
        if suite.name == "Performance Benchmarks":
            return self.config.get("performance_benchmarks", True)
        elif suite.name == "User Acceptance Tests":
            return self.config.get("user_acceptance_tests", True)
        else:
            return True
    
    def collect_system_info(self) -> Dict[str, Any]:
        """Collect system information for the report."""
        try:
            import platform
            import psutil
            
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Failed to collect system info: {e}")
            return {"error": str(e)}
    
    def generate_report(self, results: List[TestResult], 
                       system_info: Dict[str, Any]) -> TestReport:
        """Generate comprehensive test report."""
        total_tests = len(results)
        passed_tests = len([r for r in results if r.status == "passed"])
        failed_tests = len([r for r in results if r.status == "failed"])
        skipped_tests = len([r for r in results if r.status == "skipped"])
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Calculate performance metrics
        performance_metrics = self.calculate_performance_metrics(results)
        
        return TestReport(
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            total_duration=total_duration,
            success_rate=success_rate,
            test_results=results,
            system_info=system_info,
            performance_metrics=performance_metrics
        )
    
    def calculate_performance_metrics(self, results: List[TestResult]) -> Dict[str, Any]:
        """Calculate performance metrics from test results."""
        durations = [r.duration for r in results if r.status == "passed"]
        
        if not durations:
            return {}
        
        return {
            "average_test_duration": sum(durations) / len(durations),
            "max_test_duration": max(durations),
            "min_test_duration": min(durations),
            "total_execution_time": sum(durations),
            "tests_per_minute": len(durations) / (sum(durations) / 60) if sum(durations) > 0 else 0
        }
    
    def save_report(self, report: TestReport) -> None:
        """Save test report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.config.get("report_format", "json") == "json":
            filename = f"e2e_test_report_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(asdict(report), f, indent=2, default=str)
        else:
            filename = f"e2e_test_report_{timestamp}.txt"
            with open(filename, 'w') as f:
                self.write_text_report(f, report)
        
        logger.info(f"Test report saved to: {filename}")
    
    def write_text_report(self, file, report: TestReport) -> None:
        """Write human-readable text report."""
        file.write("=" * 80 + "\n")
        file.write("AGENT SCHOLAR - END-TO-END TEST REPORT\n")
        file.write("=" * 80 + "\n\n")
        
        file.write(f"Timestamp: {report.timestamp}\n")
        file.write(f"Total Duration: {report.total_duration:.2f} seconds\n\n")
        
        file.write("SUMMARY\n")
        file.write("-" * 40 + "\n")
        file.write(f"Total Tests: {report.total_tests}\n")
        file.write(f"Passed: {report.passed_tests}\n")
        file.write(f"Failed: {report.failed_tests}\n")
        file.write(f"Skipped: {report.skipped_tests}\n")
        file.write(f"Success Rate: {report.success_rate:.1f}%\n\n")
        
        if report.performance_metrics:
            file.write("PERFORMANCE METRICS\n")
            file.write("-" * 40 + "\n")
            for key, value in report.performance_metrics.items():
                file.write(f"{key.replace('_', ' ').title()}: {value:.2f}\n")
            file.write("\n")
        
        file.write("SYSTEM INFORMATION\n")
        file.write("-" * 40 + "\n")
        for key, value in report.system_info.items():
            file.write(f"{key.replace('_', ' ').title()}: {value}\n")
        file.write("\n")
        
        if report.failed_tests > 0:
            file.write("FAILED TESTS\n")
            file.write("-" * 40 + "\n")
            for result in report.test_results:
                if result.status == "failed":
                    file.write(f"Test: {result.test_name}\n")
                    file.write(f"Duration: {result.duration:.2f}s\n")
                    if result.error_message:
                        file.write(f"Error: {result.error_message[:200]}...\n")
                    file.write("\n")
    
    def print_summary(self, report: TestReport) -> None:
        """Print test summary to console."""
        print("\n" + "=" * 80)
        print("AGENT SCHOLAR - END-TO-END TEST SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal Tests: {report.total_tests}")
        print(f"Passed: {report.passed_tests} ({report.passed_tests/report.total_tests*100:.1f}%)")
        print(f"Failed: {report.failed_tests} ({report.failed_tests/report.total_tests*100:.1f}%)")
        print(f"Skipped: {report.skipped_tests} ({report.skipped_tests/report.total_tests*100:.1f}%)")
        print(f"Success Rate: {report.success_rate:.1f}%")
        print(f"Total Duration: {report.total_duration:.2f} seconds")
        
        if report.performance_metrics:
            print(f"\nAverage Test Duration: {report.performance_metrics.get('average_test_duration', 0):.2f}s")
            print(f"Tests per Minute: {report.performance_metrics.get('tests_per_minute', 0):.1f}")
        
        if report.failed_tests > 0:
            print(f"\n⚠️  {report.failed_tests} tests failed. Check the detailed report for more information.")
        
        if report.success_rate >= 95:
            print("\n✅ System is ready for deployment!")
        elif report.success_rate >= 85:
            print("\n⚠️  System has some issues but may be acceptable for deployment.")
        else:
            print("\n❌ System has significant issues and should not be deployed.")

def main():
    """Main entry point for the test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Scholar E2E Test Runner")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--user-acceptance", action="store_true", help="Run user acceptance tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--timeout", type=int, default=600, help="Test timeout in seconds")
    
    args = parser.parse_args()
    
    # Override config based on command line arguments
    config_overrides = {}
    if args.performance:
        config_overrides["performance_benchmarks"] = True
    if args.user_acceptance:
        config_overrides["user_acceptance_tests"] = True
    if args.all:
        config_overrides.update({
            "performance_benchmarks": True,
            "user_acceptance_tests": True,
            "integration_tests": True
        })
    if args.timeout:
        config_overrides["timeout"] = args.timeout
    
    # Initialize and run tests
    runner = E2ETestRunner(args.config)
    runner.config.update(config_overrides)
    
    try:
        report = runner.run_all_tests()
        runner.print_summary(report)
        
        # Exit with appropriate code
        if report.success_rate >= 95:
            sys.exit(0)  # Success
        elif report.success_rate >= 85:
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Failure
            
    except KeyboardInterrupt:
        logger.info("Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()