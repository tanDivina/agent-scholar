"""
Performance Monitoring Lambda Function

This function continuously monitors system performance metrics,
triggers auto-scaling decisions, and provides performance insights.
"""
import json
import logging
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

# Import performance optimization modules
import sys
sys.path.append('/opt/python')
from performance_optimizer import (
    performance_optimizer, resource_monitor, cache_manager,
    PerformanceMetrics, performance_monitor
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
application_autoscaling = boto3.client('application-autoscaling')
lambda_client = boto3.client('lambda')
sns = boto3.client('sns')

# Configuration
PERFORMANCE_THRESHOLD_CONFIG = {
    'scale_up_thresholds': {
        'max_execution_time': float(os.environ.get('MAX_EXECUTION_TIME', '10.0')),
        'max_memory_mb': float(os.environ.get('MAX_MEMORY_MB', '200')),
        'max_error_rate': float(os.environ.get('MAX_ERROR_RATE', '0.05')),
        'max_concurrent': int(os.environ.get('MAX_CONCURRENT', '50'))
    },
    'scale_down_thresholds': {
        'min_execution_time': float(os.environ.get('MIN_EXECUTION_TIME', '2.0')),
        'min_memory_mb': float(os.environ.get('MIN_MEMORY_MB', '50')),
        'min_error_rate': float(os.environ.get('MIN_ERROR_RATE', '0.01')),
        'min_concurrent': int(os.environ.get('MIN_CONCURRENT', '5'))
    }
}

ALERT_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')
LAMBDA_FUNCTIONS = os.environ.get('LAMBDA_FUNCTIONS', '').split(',')

@performance_monitor
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for performance monitoring.
    
    This function:
    1. Collects performance metrics from all system components
    2. Analyzes performance trends and identifies issues
    3. Triggers auto-scaling decisions when needed
    4. Sends alerts for performance degradation
    5. Provides optimization recommendations
    """
    try:
        logger.info("Starting performance monitoring cycle")
        
        # Collect current performance metrics
        current_metrics = collect_system_metrics()
        
        # Analyze performance trends
        performance_analysis = analyze_performance_trends(current_metrics)
        
        # Check scaling requirements
        scaling_decisions = evaluate_scaling_requirements(current_metrics)
        
        # Execute scaling actions if needed
        scaling_results = execute_scaling_actions(scaling_decisions)
        
        # Send alerts if necessary
        alert_results = send_performance_alerts(current_metrics, performance_analysis)
        
        # Generate optimization recommendations
        recommendations = generate_optimization_recommendations(current_metrics)
        
        # Publish custom metrics to CloudWatch
        publish_custom_metrics(current_metrics, performance_analysis)
        
        # Prepare response
        response = {
            'statusCode': 200,
            'body': json.dumps({
                'timestamp': datetime.now().isoformat(),
                'current_metrics': current_metrics,
                'performance_analysis': performance_analysis,
                'scaling_decisions': scaling_decisions,
                'scaling_results': scaling_results,
                'alert_results': alert_results,
                'recommendations': recommendations,
                'monitoring_status': 'healthy'
            })
        }
        
        logger.info("Performance monitoring cycle completed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Performance monitoring failed: {str(e)}")
        
        # Send critical alert
        if ALERT_TOPIC_ARN:
            try:
                sns.publish(
                    TopicArn=ALERT_TOPIC_ARN,
                    Subject='Agent Scholar - Performance Monitoring Failure',
                    Message=f'Performance monitoring failed with error: {str(e)}'
                )
            except Exception as alert_error:
                logger.error(f"Failed to send alert: {str(alert_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'monitoring_status': 'failed'
            })
        }

def collect_system_metrics() -> Dict[str, Any]:
    """Collect comprehensive system performance metrics."""
    logger.info("Collecting system performance metrics")
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'lambda_metrics': {},
        'api_gateway_metrics': {},
        'system_metrics': {},
        'cache_metrics': {},
        'error_metrics': {}
    }
    
    try:
        # Collect Lambda function metrics
        for function_name in LAMBDA_FUNCTIONS:
            if function_name.strip():
                metrics['lambda_metrics'][function_name] = collect_lambda_metrics(function_name)
        
        # Collect API Gateway metrics
        metrics['api_gateway_metrics'] = collect_api_gateway_metrics()
        
        # Collect system-wide metrics
        metrics['system_metrics'] = collect_system_wide_metrics()
        
        # Collect cache metrics
        metrics['cache_metrics'] = collect_cache_metrics()
        
        # Collect error metrics
        metrics['error_metrics'] = collect_error_metrics()
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {str(e)}")
        metrics['collection_error'] = str(e)
    
    return metrics

def collect_lambda_metrics(function_name: str) -> Dict[str, Any]:
    """Collect metrics for a specific Lambda function."""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        # Get CloudWatch metrics
        metrics = {}
        
        # Duration metric
        duration_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average', 'Maximum']
        )
        
        if duration_response['Datapoints']:
            latest_duration = duration_response['Datapoints'][-1]
            metrics['average_duration'] = latest_duration['Average']
            metrics['max_duration'] = latest_duration['Maximum']
        
        # Invocation metric
        invocation_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if invocation_response['Datapoints']:
            metrics['invocations'] = invocation_response['Datapoints'][-1]['Sum']
        
        # Error metric
        error_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Errors',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if error_response['Datapoints']:
            metrics['errors'] = error_response['Datapoints'][-1]['Sum']
            metrics['error_rate'] = metrics['errors'] / max(metrics.get('invocations', 1), 1)
        
        # Throttle metric
        throttle_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Throttles',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if throttle_response['Datapoints']:
            metrics['throttles'] = throttle_response['Datapoints'][-1]['Sum']
        
        # Concurrent executions
        concurrent_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='ConcurrentExecutions',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Maximum']
        )
        
        if concurrent_response['Datapoints']:
            metrics['concurrent_executions'] = concurrent_response['Datapoints'][-1]['Maximum']
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error collecting Lambda metrics for {function_name}: {str(e)}")
        return {'error': str(e)}

def collect_api_gateway_metrics() -> Dict[str, Any]:
    """Collect API Gateway performance metrics."""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        metrics = {}
        
        # Get API Gateway metrics (would need API name from environment)
        api_name = os.environ.get('API_GATEWAY_NAME', 'agent-scholar-api')
        
        # Request count
        count_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ApiGateway',
            MetricName='Count',
            Dimensions=[{'Name': 'ApiName', 'Value': api_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if count_response['Datapoints']:
            metrics['request_count'] = count_response['Datapoints'][-1]['Sum']
        
        # Latency
        latency_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ApiGateway',
            MetricName='Latency',
            Dimensions=[{'Name': 'ApiName', 'Value': api_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average', 'Maximum']
        )
        
        if latency_response['Datapoints']:
            latest_latency = latency_response['Datapoints'][-1]
            metrics['average_latency'] = latest_latency['Average']
            metrics['max_latency'] = latest_latency['Maximum']
        
        # 4XX Errors
        error_4xx_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ApiGateway',
            MetricName='4XXError',
            Dimensions=[{'Name': 'ApiName', 'Value': api_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if error_4xx_response['Datapoints']:
            metrics['4xx_errors'] = error_4xx_response['Datapoints'][-1]['Sum']
        
        # 5XX Errors
        error_5xx_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/ApiGateway',
            MetricName='5XXError',
            Dimensions=[{'Name': 'ApiName', 'Value': api_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )
        
        if error_5xx_response['Datapoints']:
            metrics['5xx_errors'] = error_5xx_response['Datapoints'][-1]['Sum']
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error collecting API Gateway metrics: {str(e)}")
        return {'error': str(e)}

def collect_system_wide_metrics() -> Dict[str, Any]:
    """Collect system-wide performance metrics."""
    try:
        # Get metrics from resource monitor
        current_metrics = resource_monitor.get_average_metrics(5)  # 5-minute window
        
        if current_metrics:
            return {
                'average_execution_time': current_metrics.execution_time,
                'average_memory_usage_mb': current_metrics.memory_usage_mb,
                'cache_hit_rate': current_metrics.cache_hit_rate,
                'concurrent_requests': current_metrics.concurrent_requests,
                'error_rate': current_metrics.error_rate,
                'throughput_rps': current_metrics.throughput_rps
            }
        else:
            return {'status': 'no_data_available'}
            
    except Exception as e:
        logger.error(f"Error collecting system-wide metrics: {str(e)}")
        return {'error': str(e)}

def collect_cache_metrics() -> Dict[str, Any]:
    """Collect cache performance metrics."""
    try:
        return {
            'hit_rate': cache_manager.get_hit_rate(),
            'total_hits': cache_manager.cache_stats['hits'],
            'total_misses': cache_manager.cache_stats['misses'],
            'memory_cache_size': len(cache_manager.memory_cache),
            'redis_available': cache_manager.redis_client is not None
        }
    except Exception as e:
        logger.error(f"Error collecting cache metrics: {str(e)}")
        return {'error': str(e)}

def collect_error_metrics() -> Dict[str, Any]:
    """Collect error and failure metrics."""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=15)  # 15-minute window for errors
        
        metrics = {
            'total_errors': 0,
            'error_breakdown': {},
            'error_rate_trend': []
        }
        
        # Collect errors from all Lambda functions
        for function_name in LAMBDA_FUNCTIONS:
            if function_name.strip():
                try:
                    error_response = cloudwatch.get_metric_statistics(
                        Namespace='AWS/Lambda',
                        MetricName='Errors',
                        Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=['Sum']
                    )
                    
                    if error_response['Datapoints']:
                        function_errors = sum(dp['Sum'] for dp in error_response['Datapoints'])
                        metrics['total_errors'] += function_errors
                        metrics['error_breakdown'][function_name] = function_errors
                        
                except Exception as e:
                    logger.warning(f"Could not collect errors for {function_name}: {str(e)}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error collecting error metrics: {str(e)}")
        return {'error': str(e)}

def analyze_performance_trends(current_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze performance trends and identify issues."""
    logger.info("Analyzing performance trends")
    
    analysis = {
        'overall_health': 'healthy',
        'performance_issues': [],
        'trend_analysis': {},
        'recommendations': []
    }
    
    try:
        # Analyze Lambda performance
        lambda_issues = []
        for function_name, metrics in current_metrics.get('lambda_metrics', {}).items():
            if isinstance(metrics, dict) and 'error' not in metrics:
                # Check duration
                avg_duration = metrics.get('average_duration', 0)
                if avg_duration > 10000:  # 10 seconds
                    lambda_issues.append(f"{function_name}: High average duration ({avg_duration/1000:.1f}s)")
                
                # Check error rate
                error_rate = metrics.get('error_rate', 0)
                if error_rate > 0.05:  # 5%
                    lambda_issues.append(f"{function_name}: High error rate ({error_rate*100:.1f}%)")
                
                # Check throttling
                throttles = metrics.get('throttles', 0)
                if throttles > 0:
                    lambda_issues.append(f"{function_name}: Experiencing throttling ({throttles} throttles)")
        
        if lambda_issues:
            analysis['performance_issues'].extend(lambda_issues)
        
        # Analyze API Gateway performance
        api_metrics = current_metrics.get('api_gateway_metrics', {})
        if isinstance(api_metrics, dict) and 'error' not in api_metrics:
            avg_latency = api_metrics.get('average_latency', 0)
            if avg_latency > 5000:  # 5 seconds
                analysis['performance_issues'].append(f"API Gateway: High latency ({avg_latency/1000:.1f}s)")
            
            error_4xx = api_metrics.get('4xx_errors', 0)
            error_5xx = api_metrics.get('5xx_errors', 0)
            total_requests = api_metrics.get('request_count', 1)
            
            if (error_4xx + error_5xx) / total_requests > 0.05:  # 5% error rate
                analysis['performance_issues'].append("API Gateway: High error rate")
        
        # Analyze system metrics
        system_metrics = current_metrics.get('system_metrics', {})
        if isinstance(system_metrics, dict) and 'error' not in system_metrics:
            cache_hit_rate = system_metrics.get('cache_hit_rate', 0)
            if cache_hit_rate < 0.3:  # 30%
                analysis['performance_issues'].append(f"Low cache hit rate ({cache_hit_rate*100:.1f}%)")
            
            throughput = system_metrics.get('throughput_rps', 0)
            if throughput < 0.5:  # 0.5 RPS
                analysis['performance_issues'].append(f"Low system throughput ({throughput:.2f} RPS)")
        
        # Determine overall health
        if len(analysis['performance_issues']) == 0:
            analysis['overall_health'] = 'healthy'
        elif len(analysis['performance_issues']) <= 2:
            analysis['overall_health'] = 'degraded'
        else:
            analysis['overall_health'] = 'critical'
        
        # Generate trend analysis
        analysis['trend_analysis'] = {
            'performance_trend': 'stable',  # Would need historical data for real trend analysis
            'capacity_utilization': calculate_capacity_utilization(current_metrics),
            'bottlenecks_identified': identify_bottlenecks(current_metrics)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing performance trends: {str(e)}")
        analysis['analysis_error'] = str(e)
    
    return analysis

def evaluate_scaling_requirements(current_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate if auto-scaling actions are needed."""
    logger.info("Evaluating scaling requirements")
    
    scaling_decisions = {
        'scale_up_needed': False,
        'scale_down_needed': False,
        'scaling_actions': [],
        'reasoning': []
    }
    
    try:
        # Use performance optimizer to determine scaling needs
        scaling_recommendations = performance_optimizer.should_trigger_scaling()
        
        scaling_decisions['scale_up_needed'] = scaling_recommendations.get('scale_up', False)
        scaling_decisions['scale_down_needed'] = scaling_recommendations.get('scale_down', False)
        
        # Determine specific scaling actions
        if scaling_decisions['scale_up_needed']:
            scaling_decisions['scaling_actions'].append({
                'action': 'scale_up',
                'target': 'lambda_concurrency',
                'current_capacity': get_current_lambda_capacity(),
                'recommended_capacity': calculate_recommended_capacity(current_metrics, 'up')
            })
            scaling_decisions['reasoning'].append("High resource utilization detected")
        
        if scaling_decisions['scale_down_needed']:
            scaling_decisions['scaling_actions'].append({
                'action': 'scale_down',
                'target': 'lambda_concurrency',
                'current_capacity': get_current_lambda_capacity(),
                'recommended_capacity': calculate_recommended_capacity(current_metrics, 'down')
            })
            scaling_decisions['reasoning'].append("Low resource utilization detected")
        
    except Exception as e:
        logger.error(f"Error evaluating scaling requirements: {str(e)}")
        scaling_decisions['evaluation_error'] = str(e)
    
    return scaling_decisions

def execute_scaling_actions(scaling_decisions: Dict[str, Any]) -> Dict[str, Any]:
    """Execute auto-scaling actions."""
    logger.info("Executing scaling actions")
    
    results = {
        'actions_executed': [],
        'actions_failed': [],
        'scaling_status': 'no_action_needed'
    }
    
    try:
        for action in scaling_decisions.get('scaling_actions', []):
            try:
                if action['action'] == 'scale_up':
                    result = scale_up_lambda_concurrency(
                        action['target'],
                        action['recommended_capacity']
                    )
                    results['actions_executed'].append({
                        'action': 'scale_up',
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    results['scaling_status'] = 'scaled_up'
                
                elif action['action'] == 'scale_down':
                    result = scale_down_lambda_concurrency(
                        action['target'],
                        action['recommended_capacity']
                    )
                    results['actions_executed'].append({
                        'action': 'scale_down',
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    results['scaling_status'] = 'scaled_down'
                
            except Exception as action_error:
                logger.error(f"Failed to execute scaling action {action['action']}: {str(action_error)}")
                results['actions_failed'].append({
                    'action': action['action'],
                    'error': str(action_error),
                    'timestamp': datetime.now().isoformat()
                })
                results['scaling_status'] = 'scaling_failed'
    
    except Exception as e:
        logger.error(f"Error executing scaling actions: {str(e)}")
        results['execution_error'] = str(e)
        results['scaling_status'] = 'execution_failed'
    
    return results

def send_performance_alerts(current_metrics: Dict[str, Any], 
                          performance_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Send performance alerts if issues are detected."""
    logger.info("Checking for performance alerts")
    
    alert_results = {
        'alerts_sent': [],
        'alert_status': 'no_alerts'
    }
    
    try:
        if not ALERT_TOPIC_ARN:
            logger.warning("No alert topic configured")
            return alert_results
        
        # Check if alerts should be sent
        overall_health = performance_analysis.get('overall_health', 'healthy')
        performance_issues = performance_analysis.get('performance_issues', [])
        
        if overall_health in ['degraded', 'critical'] or len(performance_issues) > 0:
            # Prepare alert message
            alert_message = prepare_alert_message(current_metrics, performance_analysis)
            
            # Send alert
            response = sns.publish(
                TopicArn=ALERT_TOPIC_ARN,
                Subject=f'Agent Scholar - Performance Alert ({overall_health.upper()})',
                Message=alert_message
            )
            
            alert_results['alerts_sent'].append({
                'type': 'performance_degradation',
                'severity': overall_health,
                'message_id': response['MessageId'],
                'timestamp': datetime.now().isoformat()
            })
            alert_results['alert_status'] = 'alerts_sent'
            
            logger.info(f"Performance alert sent: {overall_health}")
    
    except Exception as e:
        logger.error(f"Error sending performance alerts: {str(e)}")
        alert_results['alert_error'] = str(e)
        alert_results['alert_status'] = 'alert_failed'
    
    return alert_results

def generate_optimization_recommendations(current_metrics: Dict[str, Any]) -> List[str]:
    """Generate performance optimization recommendations."""
    try:
        return performance_optimizer.get_optimization_recommendations()
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        return [f"Error generating recommendations: {str(e)}"]

def publish_custom_metrics(current_metrics: Dict[str, Any], 
                         performance_analysis: Dict[str, Any]) -> None:
    """Publish custom metrics to CloudWatch."""
    try:
        metric_data = []
        
        # System-wide metrics
        system_metrics = current_metrics.get('system_metrics', {})
        if isinstance(system_metrics, dict) and 'error' not in system_metrics:
            if 'throughput_rps' in system_metrics:
                metric_data.append({
                    'MetricName': 'SystemThroughput',
                    'Value': system_metrics['throughput_rps'],
                    'Unit': 'Count/Second'
                })
            
            if 'cache_hit_rate' in system_metrics:
                metric_data.append({
                    'MetricName': 'CacheHitRate',
                    'Value': system_metrics['cache_hit_rate'] * 100,
                    'Unit': 'Percent'
                })
            
            if 'average_execution_time' in system_metrics:
                metric_data.append({
                    'MetricName': 'AverageResponseTime',
                    'Value': system_metrics['average_execution_time'],
                    'Unit': 'Seconds'
                })
        
        # Performance health score
        health_score = calculate_health_score(performance_analysis)
        metric_data.append({
            'MetricName': 'PerformanceHealthScore',
            'Value': health_score,
            'Unit': 'None'
        })
        
        # Publish metrics in batches
        if metric_data:
            cloudwatch.put_metric_data(
                Namespace='AgentScholar/Performance',
                MetricData=metric_data
            )
            logger.info(f"Published {len(metric_data)} custom metrics")
    
    except Exception as e:
        logger.error(f"Error publishing custom metrics: {str(e)}")

# Helper functions
def calculate_capacity_utilization(metrics: Dict[str, Any]) -> float:
    """Calculate overall capacity utilization."""
    # Simplified calculation - would be more sophisticated in production
    try:
        lambda_metrics = metrics.get('lambda_metrics', {})
        total_utilization = 0
        function_count = 0
        
        for function_name, function_metrics in lambda_metrics.items():
            if isinstance(function_metrics, dict) and 'concurrent_executions' in function_metrics:
                # Assume max capacity of 100 concurrent executions per function
                utilization = min(function_metrics['concurrent_executions'] / 100, 1.0)
                total_utilization += utilization
                function_count += 1
        
        return total_utilization / max(function_count, 1)
    except:
        return 0.5  # Default to 50% if calculation fails

def identify_bottlenecks(metrics: Dict[str, Any]) -> List[str]:
    """Identify system bottlenecks."""
    bottlenecks = []
    
    try:
        # Check Lambda function bottlenecks
        lambda_metrics = metrics.get('lambda_metrics', {})
        for function_name, function_metrics in lambda_metrics.items():
            if isinstance(function_metrics, dict):
                if function_metrics.get('average_duration', 0) > 8000:  # 8 seconds
                    bottlenecks.append(f"Lambda function {function_name} has high execution time")
                
                if function_metrics.get('throttles', 0) > 0:
                    bottlenecks.append(f"Lambda function {function_name} is being throttled")
        
        # Check cache bottlenecks
        cache_metrics = metrics.get('cache_metrics', {})
        if isinstance(cache_metrics, dict):
            hit_rate = cache_metrics.get('hit_rate', 0)
            if hit_rate < 0.3:
                bottlenecks.append("Low cache hit rate indicates caching inefficiency")
        
        # Check API Gateway bottlenecks
        api_metrics = metrics.get('api_gateway_metrics', {})
        if isinstance(api_metrics, dict):
            if api_metrics.get('average_latency', 0) > 3000:  # 3 seconds
                bottlenecks.append("API Gateway has high latency")
    
    except Exception as e:
        logger.error(f"Error identifying bottlenecks: {str(e)}")
    
    return bottlenecks

def get_current_lambda_capacity() -> Dict[str, int]:
    """Get current Lambda concurrency capacity."""
    # This would query actual Lambda configurations
    return {'total_capacity': 1000, 'reserved_capacity': 100}

def calculate_recommended_capacity(metrics: Dict[str, Any], direction: str) -> int:
    """Calculate recommended capacity for scaling."""
    current_capacity = get_current_lambda_capacity()['reserved_capacity']
    
    if direction == 'up':
        return min(current_capacity * 2, 1000)  # Double capacity, max 1000
    else:
        return max(current_capacity // 2, 10)   # Half capacity, min 10

def scale_up_lambda_concurrency(target: str, new_capacity: int) -> Dict[str, Any]:
    """Scale up Lambda concurrency."""
    # This would implement actual scaling logic
    logger.info(f"Scaling up {target} to {new_capacity}")
    return {'status': 'success', 'new_capacity': new_capacity}

def scale_down_lambda_concurrency(target: str, new_capacity: int) -> Dict[str, Any]:
    """Scale down Lambda concurrency."""
    # This would implement actual scaling logic
    logger.info(f"Scaling down {target} to {new_capacity}")
    return {'status': 'success', 'new_capacity': new_capacity}

def prepare_alert_message(metrics: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """Prepare alert message for SNS."""
    message_parts = [
        "Agent Scholar Performance Alert",
        "=" * 40,
        f"Timestamp: {datetime.now().isoformat()}",
        f"Overall Health: {analysis.get('overall_health', 'unknown').upper()}",
        ""
    ]
    
    # Add performance issues
    issues = analysis.get('performance_issues', [])
    if issues:
        message_parts.append("Performance Issues:")
        for issue in issues:
            message_parts.append(f"  - {issue}")
        message_parts.append("")
    
    # Add system metrics summary
    system_metrics = metrics.get('system_metrics', {})
    if isinstance(system_metrics, dict) and 'error' not in system_metrics:
        message_parts.extend([
            "System Metrics:",
            f"  - Throughput: {system_metrics.get('throughput_rps', 0):.2f} RPS",
            f"  - Cache Hit Rate: {system_metrics.get('cache_hit_rate', 0)*100:.1f}%",
            f"  - Average Response Time: {system_metrics.get('average_execution_time', 0):.2f}s",
            ""
        ])
    
    # Add recommendations
    recommendations = analysis.get('recommendations', [])
    if recommendations:
        message_parts.append("Recommendations:")
        for rec in recommendations[:3]:  # Top 3 recommendations
            message_parts.append(f"  - {rec}")
    
    return "\n".join(message_parts)

def calculate_health_score(analysis: Dict[str, Any]) -> float:
    """Calculate overall system health score (0-100)."""
    health = analysis.get('overall_health', 'healthy')
    issues_count = len(analysis.get('performance_issues', []))
    
    if health == 'healthy' and issues_count == 0:
        return 100.0
    elif health == 'healthy':
        return max(90.0 - (issues_count * 5), 70.0)
    elif health == 'degraded':
        return max(70.0 - (issues_count * 10), 40.0)
    else:  # critical
        return max(40.0 - (issues_count * 10), 10.0)