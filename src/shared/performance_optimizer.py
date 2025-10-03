"""
Performance Optimization Module for Agent Scholar

This module provides performance optimization utilities including caching,
connection pooling, batch processing, and resource management for improved
system performance and efficiency.
"""
import asyncio
import time
import json
import hashlib
from typing import Dict, Any, List, Optional, Callable, Union
from functools import wraps, lru_cache
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import logging
import boto3
from botocore.config import Config
import redis
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    execution_time: float
    memory_usage_mb: float
    cache_hit_rate: float
    concurrent_requests: int
    error_rate: float
    throughput_rps: float

class ConnectionPoolManager:
    """Manages connection pools for AWS services and external APIs."""
    
    def __init__(self):
        """Initialize connection pool manager."""
        self._pools = {}
        self._lock = threading.Lock()
        self.config = Config(
            region_name='us-east-1',
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50,
            connect_timeout=5,
            read_timeout=30
        )
    
    def get_bedrock_client(self) -> boto3.client:
        """Get optimized Bedrock client with connection pooling."""
        if 'bedrock' not in self._pools:
            with self._lock:
                if 'bedrock' not in self._pools:
                    self._pools['bedrock'] = boto3.client(
                        'bedrock-agent-runtime',
                        config=self.config
                    )
        return self._pools['bedrock']
    
    def get_opensearch_client(self) -> boto3.client:
        """Get optimized OpenSearch client with connection pooling."""
        if 'opensearch' not in self._pools:
            with self._lock:
                if 'opensearch' not in self._pools:
                    self._pools['opensearch'] = boto3.client(
                        'opensearchserverless',
                        config=self.config
                    )
        return self._pools['opensearch']
    
    def get_s3_client(self) -> boto3.client:
        """Get optimized S3 client with connection pooling."""
        if 's3' not in self._pools:
            with self._lock:
                if 's3' not in self._pools:
                    self._pools['s3'] = boto3.client(
                        's3',
                        config=self.config
                    )
        return self._pools['s3']
    
    def get_dynamodb_resource(self) -> boto3.resource:
        """Get optimized DynamoDB resource with connection pooling."""
        if 'dynamodb' not in self._pools:
            with self._lock:
                if 'dynamodb' not in self._pools:
                    self._pools['dynamodb'] = boto3.resource(
                        'dynamodb',
                        config=self.config
                    )
        return self._pools['dynamodb']

class CacheManager:
    """Advanced caching system with multiple cache layers."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize cache manager with Redis and in-memory caching."""
        self.memory_cache = {}
        self.cache_stats = {'hits': 0, 'misses': 0}
        self.max_memory_cache_size = 1000
        self._lock = threading.Lock()
        
        # Initialize Redis if available
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=20
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}")
                self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments."""
        key_data = json.dumps({
            'args': args,
            'kwargs': sorted(kwargs.items())
        }, sort_keys=True, default=str)
        
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (Redis first, then memory)."""
        # Try Redis first
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value is not None:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        # Try memory cache
        with self._lock:
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if entry['expires'] > time.time():
                    self.cache_stats['hits'] += 1
                    return entry['value']
                else:
                    del self.memory_cache[key]
        
        self.cache_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set value in cache with TTL."""
        serialized_value = json.dumps(value, default=str)
        
        # Set in Redis
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, serialized_value)
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
        
        # Set in memory cache
        with self._lock:
            # Implement LRU eviction if cache is full
            if len(self.memory_cache) >= self.max_memory_cache_size:
                oldest_key = min(
                    self.memory_cache.keys(),
                    key=lambda k: self.memory_cache[k]['created']
                )
                del self.memory_cache[oldest_key]
            
            self.memory_cache[key] = {
                'value': value,
                'expires': time.time() + ttl,
                'created': time.time()
            }
    
    def delete(self, key: str) -> None:
        """Delete key from all cache layers."""
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")
        
        with self._lock:
            self.memory_cache.pop(key, None)
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        return self.cache_stats['hits'] / total if total > 0 else 0.0
    
    def clear(self) -> None:
        """Clear all caches."""
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        with self._lock:
            self.memory_cache.clear()
            self.cache_stats = {'hits': 0, 'misses': 0}

class BatchProcessor:
    """Batch processing utilities for improved throughput."""
    
    def __init__(self, max_batch_size: int = 10, max_wait_time: float = 1.0):
        """Initialize batch processor."""
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.pending_items = []
        self.last_batch_time = time.time()
        self._lock = threading.Lock()
    
    async def add_item(self, item: Any, processor_func: Callable) -> Any:
        """Add item to batch for processing."""
        with self._lock:
            self.pending_items.append((item, processor_func))
            
            # Process batch if conditions are met
            should_process = (
                len(self.pending_items) >= self.max_batch_size or
                time.time() - self.last_batch_time >= self.max_wait_time
            )
        
        if should_process:
            return await self._process_batch()
        else:
            # Wait for batch to be ready
            await asyncio.sleep(0.1)
            return await self.add_item(item, processor_func)
    
    async def _process_batch(self) -> List[Any]:
        """Process current batch of items."""
        with self._lock:
            if not self.pending_items:
                return []
            
            batch = self.pending_items.copy()
            self.pending_items.clear()
            self.last_batch_time = time.time()
        
        # Group items by processor function
        processor_groups = {}
        for item, processor_func in batch:
            func_name = processor_func.__name__
            if func_name not in processor_groups:
                processor_groups[func_name] = {'func': processor_func, 'items': []}
            processor_groups[func_name]['items'].append(item)
        
        # Process each group
        results = []
        for group_name, group_data in processor_groups.items():
            try:
                if asyncio.iscoroutinefunction(group_data['func']):
                    group_results = await group_data['func'](group_data['items'])
                else:
                    group_results = group_data['func'](group_data['items'])
                results.extend(group_results)
            except Exception as e:
                logger.error(f"Batch processing error for {group_name}: {e}")
                # Return error results for failed items
                results.extend([{'error': str(e)} for _ in group_data['items']])
        
        return results

class ResourceMonitor:
    """Monitor and optimize resource usage."""
    
    def __init__(self):
        """Initialize resource monitor."""
        self.metrics_history = []
        self.max_history_size = 1000
        self._lock = threading.Lock()
    
    def record_metrics(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics."""
        with self._lock:
            self.metrics_history.append({
                'timestamp': time.time(),
                'metrics': metrics
            })
            
            # Maintain history size
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    def get_average_metrics(self, window_minutes: int = 5) -> Optional[PerformanceMetrics]:
        """Get average metrics over specified time window."""
        cutoff_time = time.time() - (window_minutes * 60)
        
        with self._lock:
            recent_metrics = [
                entry['metrics'] for entry in self.metrics_history
                if entry['timestamp'] >= cutoff_time
            ]
        
        if not recent_metrics:
            return None
        
        return PerformanceMetrics(
            execution_time=sum(m.execution_time for m in recent_metrics) / len(recent_metrics),
            memory_usage_mb=sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics),
            cache_hit_rate=sum(m.cache_hit_rate for m in recent_metrics) / len(recent_metrics),
            concurrent_requests=max(m.concurrent_requests for m in recent_metrics),
            error_rate=sum(m.error_rate for m in recent_metrics) / len(recent_metrics),
            throughput_rps=sum(m.throughput_rps for m in recent_metrics) / len(recent_metrics)
        )
    
    def should_scale_up(self, threshold_metrics: Dict[str, float]) -> bool:
        """Determine if system should scale up based on metrics."""
        current_metrics = self.get_average_metrics(2)  # 2-minute window
        
        if not current_metrics:
            return False
        
        # Check scaling triggers
        triggers = [
            current_metrics.execution_time > threshold_metrics.get('max_execution_time', 10.0),
            current_metrics.memory_usage_mb > threshold_metrics.get('max_memory_mb', 200),
            current_metrics.error_rate > threshold_metrics.get('max_error_rate', 0.05),
            current_metrics.concurrent_requests > threshold_metrics.get('max_concurrent', 50)
        ]
        
        return any(triggers)
    
    def should_scale_down(self, threshold_metrics: Dict[str, float]) -> bool:
        """Determine if system should scale down based on metrics."""
        current_metrics = self.get_average_metrics(10)  # 10-minute window for scale down
        
        if not current_metrics:
            return False
        
        # Check scale-down conditions (all must be true)
        conditions = [
            current_metrics.execution_time < threshold_metrics.get('min_execution_time', 2.0),
            current_metrics.memory_usage_mb < threshold_metrics.get('min_memory_mb', 50),
            current_metrics.error_rate < threshold_metrics.get('min_error_rate', 0.01),
            current_metrics.concurrent_requests < threshold_metrics.get('min_concurrent', 5)
        ]
        
        return all(conditions)

# Global instances
connection_pool = ConnectionPoolManager()
cache_manager = CacheManager()
batch_processor = BatchProcessor()
resource_monitor = ResourceMonitor()

def cached(ttl: int = 3600, prefix: str = "default"):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = cache_manager._generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            cache_manager.set(cache_key, result, ttl)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = cache_manager._generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def performance_monitor(func: Callable) -> Callable:
    """Decorator for monitoring function performance."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        import psutil
        import threading
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        concurrent_requests = threading.active_count()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            error_occurred = False
        except Exception as e:
            error_occurred = True
            raise
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            metrics = PerformanceMetrics(
                execution_time=end_time - start_time,
                memory_usage_mb=end_memory - start_memory,
                cache_hit_rate=cache_manager.get_hit_rate(),
                concurrent_requests=concurrent_requests,
                error_rate=1.0 if error_occurred else 0.0,
                throughput_rps=1.0 / (end_time - start_time) if end_time > start_time else 0.0
            )
            
            resource_monitor.record_metrics(metrics)
        
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        import psutil
        import threading
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        concurrent_requests = threading.active_count()
        
        try:
            result = func(*args, **kwargs)
            error_occurred = False
        except Exception as e:
            error_occurred = True
            raise
        finally:
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            metrics = PerformanceMetrics(
                execution_time=end_time - start_time,
                memory_usage_mb=end_memory - start_memory,
                cache_hit_rate=cache_manager.get_hit_rate(),
                concurrent_requests=concurrent_requests,
                error_rate=1.0 if error_occurred else 0.0,
                throughput_rps=1.0 / (end_time - start_time) if end_time > start_time else 0.0
            )
            
            resource_monitor.record_metrics(metrics)
        
        return result
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

def batch_process(max_batch_size: int = 10, max_wait_time: float = 1.0):
    """Decorator for batch processing function calls."""
    def decorator(func: Callable) -> Callable:
        processor = BatchProcessor(max_batch_size, max_wait_time)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await processor.add_item((args, kwargs), func)
        
        return wrapper
    
    return decorator

class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self):
        """Initialize performance optimizer."""
        self.connection_pool = connection_pool
        self.cache_manager = cache_manager
        self.batch_processor = batch_processor
        self.resource_monitor = resource_monitor
        
        # Performance thresholds
        self.scale_up_thresholds = {
            'max_execution_time': 10.0,
            'max_memory_mb': 200,
            'max_error_rate': 0.05,
            'max_concurrent': 50
        }
        
        self.scale_down_thresholds = {
            'min_execution_time': 2.0,
            'min_memory_mb': 50,
            'min_error_rate': 0.01,
            'min_concurrent': 5
        }
    
    def optimize_lambda_function(self, func: Callable) -> Callable:
        """Apply comprehensive optimizations to a Lambda function."""
        # Apply decorators in optimal order
        optimized_func = performance_monitor(func)
        optimized_func = cached(ttl=1800, prefix=func.__name__)(optimized_func)
        
        return optimized_func
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get performance optimization recommendations based on metrics."""
        recommendations = []
        current_metrics = self.resource_monitor.get_average_metrics(5)
        
        if not current_metrics:
            return ["Insufficient metrics data for recommendations"]
        
        # Execution time recommendations
        if current_metrics.execution_time > 5.0:
            recommendations.append("Consider implementing caching for frequently accessed data")
            recommendations.append("Optimize database queries and API calls")
            recommendations.append("Implement batch processing for multiple operations")
        
        # Memory usage recommendations
        if current_metrics.memory_usage_mb > 150:
            recommendations.append("Optimize memory usage by clearing unused variables")
            recommendations.append("Consider streaming large datasets instead of loading into memory")
            recommendations.append("Implement object pooling for frequently created objects")
        
        # Cache hit rate recommendations
        if current_metrics.cache_hit_rate < 0.5:
            recommendations.append("Increase cache TTL for stable data")
            recommendations.append("Implement cache warming strategies")
            recommendations.append("Review cache key strategies for better hit rates")
        
        # Error rate recommendations
        if current_metrics.error_rate > 0.02:
            recommendations.append("Implement better error handling and retry logic")
            recommendations.append("Add circuit breakers for external service calls")
            recommendations.append("Review input validation to prevent errors")
        
        # Concurrency recommendations
        if current_metrics.concurrent_requests > 30:
            recommendations.append("Consider implementing request queuing")
            recommendations.append("Optimize resource usage to handle more concurrent requests")
            recommendations.append("Implement auto-scaling policies")
        
        return recommendations if recommendations else ["System performance is optimal"]
    
    def should_trigger_scaling(self) -> Dict[str, bool]:
        """Determine if scaling should be triggered."""
        return {
            'scale_up': self.resource_monitor.should_scale_up(self.scale_up_thresholds),
            'scale_down': self.resource_monitor.should_scale_down(self.scale_down_thresholds)
        }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        current_metrics = self.resource_monitor.get_average_metrics(5)
        scaling_decisions = self.should_trigger_scaling()
        recommendations = self.get_optimization_recommendations()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current_metrics': current_metrics.__dict__ if current_metrics else None,
            'cache_hit_rate': self.cache_manager.get_hit_rate(),
            'scaling_recommendations': scaling_decisions,
            'optimization_recommendations': recommendations,
            'system_health': 'healthy' if current_metrics and current_metrics.error_rate < 0.05 else 'degraded'
        }

# Global optimizer instance
performance_optimizer = PerformanceOptimizer()