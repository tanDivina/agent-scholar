"""
Health Check Utilities for Agent Scholar

This module provides comprehensive health checking capabilities for all
system components including Lambda functions, external APIs, and AWS services.
"""

import json
import time
import boto3
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import asyncio
import concurrent.futures
from dataclasses import dataclass, asdict

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"

@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    component: str
    status: HealthStatus
    response_time: float
    message: str
    details: Dict[str, Any]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['status'] = self.status.value
        return result

class HealthChecker:
    """Comprehensive health checking system."""
    
    def __init__(self):
        self.checks = {}
        self.thresholds = {
            'response_time_warning': 5.0,  # seconds
            'response_time_critical': 10.0,  # seconds
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.10,  # 10%
        }
    
    def register_check(self, name: str, check_func: Callable, timeout: float = 30.0):
        """Register a health check function."""
        self.checks[name] = {
            'function': check_func,
            'timeout': timeout
        }
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks concurrently."""
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_name = {
                executor.submit(self._run_single_check, name, check_info): name
                for name, check_info in self.checks.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = HealthCheckResult(
                        component=name,
                        status=HealthStatus.UNHEALTHY,
                        response_time=0.0,
                        message=f"Health check failed: {str(e)}",
                        details={'error': str(e)},
                        timestamp=datetime.utcnow().isoformat()
                    )
        
        return results
    
    def _run_single_check(self, name: str, check_info: Dict[str, Any]) -> HealthCheckResult:
        """Run a single health check."""
        start_time = time.time()
        
        try:
            # Execute the health check with timeout
            result = self._execute_with_timeout(
                check_info['function'],
                check_info['timeout']
            )
            
            response_time = time.time() - start_time
            
            # Determine status based on response time and result
            if isinstance(result, dict) and result.get('status') == 'error':
                status = HealthStatus.UNHEALTHY
                message = result.get('message', 'Health check returned error')
                details = result.get('details', {})
            elif response_time > self.thresholds['response_time_critical']:
                status = HealthStatus.UNHEALTHY
                message = f"Response time too high: {response_time:.2f}s"
                details = {'response_time': response_time}
            elif response_time > self.thresholds['response_time_warning']:
                status = HealthStatus.DEGRADED
                message = f"Response time elevated: {response_time:.2f}s"
                details = {'response_time': response_time}
            else:
                status = HealthStatus.HEALTHY
                message = "Health check passed"
                details = result if isinstance(result, dict) else {}
            
            return HealthCheckResult(
                component=name,
                status=status,
                response_time=response_time,
                message=message,
                details=details,
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e)},
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _execute_with_timeout(self, func: Callable, timeout: float) -> Any:
        """Execute function with timeout."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"Health check timed out after {timeout}s")
    
    def get_overall_status(self, results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """Determine overall system health status."""
        if not results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

# Pre-defined health check functions
class StandardHealthChecks:
    """Collection of standard health check functions."""
    
    @staticmethod
    def api_gateway_health(api_url: str) -> Dict[str, Any]:
        """Check API Gateway health."""
        try:
            response = requests.get(f"{api_url}/health", timeout=10)
            
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {
                    'status': 'error',
                    'message': f"API returned status code {response.status_code}",
                    'status_code': response.status_code
                }
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"API request failed: {str(e)}"
            }
    
    @staticmethod
    def lambda_function_health(function_name: str) -> Dict[str, Any]:
        """Check Lambda function health."""
        try:
            lambda_client = boto3.client('lambda')
            
            # Get function configuration
            response = lambda_client.get_function(FunctionName=function_name)
            
            state = response['Configuration']['State']
            last_update_status = response['Configuration']['LastUpdateStatus']
            
            if state == 'Active' and last_update_status == 'Successful':
                return {
                    'status': 'healthy',
                    'state': state,
                    'last_update_status': last_update_status,
                    'runtime': response['Configuration']['Runtime'],
                    'memory_size': response['Configuration']['MemorySize']
                }
            else:
                return {
                    'status': 'error',
                    'message': f"Function state: {state}, Update status: {last_update_status}",
                    'state': state,
                    'last_update_status': last_update_status
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Lambda health check failed: {str(e)}"
            }
    
    @staticmethod
    def opensearch_health(domain_endpoint: str) -> Dict[str, Any]:
        """Check OpenSearch cluster health."""
        try:
            # For OpenSearch Serverless, we check if we can connect
            response = requests.get(f"{domain_endpoint}/_cluster/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                return {
                    'status': 'healthy' if health_data.get('status') in ['green', 'yellow'] else 'error',
                    'cluster_status': health_data.get('status'),
                    'number_of_nodes': health_data.get('number_of_nodes'),
                    'active_shards': health_data.get('active_shards')
                }
            else:
                return {
                    'status': 'error',
                    'message': f"OpenSearch returned status code {response.status_code}"
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f"OpenSearch health check failed: {str(e)}"
            }
    
    @staticmethod
    def bedrock_agent_health(agent_id: str, agent_alias_id: str) -> Dict[str, Any]:
        """Check Bedrock Agent health."""
        try:
            bedrock_agent = boto3.client('bedrock-agent')
            
            # Get agent information
            response = bedrock_agent.get_agent(agentId=agent_id)
            agent_status = response['agent']['agentStatus']
            
            # Get alias information
            alias_response = bedrock_agent.get_agent_alias(
                agentId=agent_id,
                agentAliasId=agent_alias_id
            )
            alias_status = alias_response['agentAlias']['agentAliasStatus']
            
            if agent_status == 'PREPARED' and alias_status == 'PREPARED':
                return {
                    'status': 'healthy',
                    'agent_status': agent_status,
                    'alias_status': alias_status,
                    'agent_version': response['agent']['agentVersion']
                }
            else:
                return {
                    'status': 'error',
                    'message': f"Agent status: {agent_status}, Alias status: {alias_status}",
                    'agent_status': agent_status,
                    'alias_status': alias_status
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Bedrock Agent health check failed: {str(e)}"
            }
    
    @staticmethod
    def external_api_health(api_name: str, api_url: str, api_key: str = None) -> Dict[str, Any]:
        """Check external API health (SERP API, Google Search, etc.)."""
        try:
            headers = {}
            if api_key:
                if 'serp' in api_name.lower():
                    headers['X-API-KEY'] = api_key
                elif 'google' in api_name.lower():
                    # Google API uses query parameter
                    api_url = f"{api_url}?key={api_key}"
            
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'api_name': api_name,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {
                    'status': 'error',
                    'message': f"{api_name} returned status code {response.status_code}",
                    'api_name': api_name,
                    'status_code': response.status_code
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f"{api_name} health check failed: {str(e)}",
                'api_name': api_name
            }

class SystemHealthMonitor:
    """System-wide health monitoring."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.health_checker = HealthChecker()
        self._register_standard_checks()
    
    def _register_standard_checks(self):
        """Register standard health checks based on configuration."""
        
        # API Gateway health check
        if 'api_gateway_url' in self.config:
            self.health_checker.register_check(
                'api_gateway',
                lambda: StandardHealthChecks.api_gateway_health(self.config['api_gateway_url'])
            )
        
        # Lambda function health checks
        if 'lambda_functions' in self.config:
            for func_name in self.config['lambda_functions']:
                self.health_checker.register_check(
                    f'lambda_{func_name}',
                    lambda fn=func_name: StandardHealthChecks.lambda_function_health(fn)
                )
        
        # OpenSearch health check
        if 'opensearch_endpoint' in self.config:
            self.health_checker.register_check(
                'opensearch',
                lambda: StandardHealthChecks.opensearch_health(self.config['opensearch_endpoint'])
            )
        
        # Bedrock Agent health check
        if 'bedrock_agent' in self.config:
            agent_config = self.config['bedrock_agent']
            self.health_checker.register_check(
                'bedrock_agent',
                lambda: StandardHealthChecks.bedrock_agent_health(
                    agent_config['agent_id'],
                    agent_config['agent_alias_id']
                )
            )
        
        # External API health checks
        if 'external_apis' in self.config:
            for api_config in self.config['external_apis']:
                self.health_checker.register_check(
                    f"external_api_{api_config['name']}",
                    lambda cfg=api_config: StandardHealthChecks.external_api_health(
                        cfg['name'],
                        cfg['url'],
                        cfg.get('api_key')
                    )
                )
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        results = await self.health_checker.run_all_checks()
        overall_status = self.health_checker.get_overall_status(results)
        
        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'components': {name: result.to_dict() for name, result in results.items()},
            'summary': {
                'total_components': len(results),
                'healthy_components': sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY),
                'degraded_components': sum(1 for r in results.values() if r.status == HealthStatus.DEGRADED),
                'unhealthy_components': sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY)
            }
        }

# Utility function for Lambda health check endpoint
def create_health_check_handler(config: Dict[str, Any]):
    """Create a health check handler for Lambda functions."""
    
    def health_check_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Lambda handler for health checks."""
        try:
            monitor = SystemHealthMonitor(config)
            
            # Run health checks
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            health_status = loop.run_until_complete(monitor.get_system_health())
            loop.close()
            
            # Determine HTTP status code
            if health_status['overall_status'] == 'HEALTHY':
                status_code = 200
            elif health_status['overall_status'] == 'DEGRADED':
                status_code = 200  # Still operational
            else:
                status_code = 503  # Service unavailable
            
            return {
                'statusCode': status_code,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(health_status, default=str)
            }
            
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'overall_status': 'UNHEALTHY',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
            }
    
    return health_check_handler