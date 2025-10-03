"""
Integration tests for the Code Execution Action Group Lambda function.
Tests the complete code execution workflow with various scenarios.
"""

import pytest
import json
import sys
sys.path.append('src/lambda/code-execution')

from code_executor import lambda_handler, CodeExecutor
from unittest.mock import Mock

class TestCodeExecutionIntegration:
    """Integration tests for code execution functionality"""
    
    def test_lambda_handler_mathematical_computation(self):
        """Test Lambda handler with mathematical computation"""
        
        event = {
            'parameters': [
                {'name': 'code', 'value': '''
import math

# Calculate some mathematical operations
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
mean = sum(numbers) / len(numbers)
variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
std_dev = math.sqrt(variance)

print(f"Numbers: {numbers}")
print(f"Mean: {mean}")
print(f"Variance: {variance:.2f}")
print(f"Standard Deviation: {std_dev:.2f}")

# Calculate factorial
factorial_5 = math.factorial(5)
print(f"5! = {factorial_5}")
'''},
                {'name': 'timeout', 'value': '10'}
            ]
        }
        
        context = Mock()
        context.function_name = 'test-code-execution'
        
        response = lambda_handler(event, context)
        
        # Verify response structure
        assert 'response' in response
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        # Verify mathematical results
        assert 'Mean: 5.5' in response_body
        assert 'Standard Deviation:' in response_body
        assert '5! = 120' in response_body
        assert '✅' in response_body  # Success indicator
        assert 'Variables Created:' in response_body
    
    def test_lambda_handler_data_analysis_simulation(self):
        """Test Lambda handler with data analysis simulation"""
        
        event = {
            'code': '''
# Simulate data analysis without external libraries
import random
import math

# Generate sample data
random.seed(42)  # For reproducible results
data = [random.gauss(100, 15) for _ in range(50)]

# Basic statistics
n = len(data)
mean = sum(data) / n
variance = sum((x - mean) ** 2 for x in data) / (n - 1)
std_dev = math.sqrt(variance)
min_val = min(data)
max_val = max(data)

print(f"Dataset Analysis (n={n}):")
print(f"Mean: {mean:.2f}")
print(f"Std Dev: {std_dev:.2f}")
print(f"Range: {min_val:.2f} to {max_val:.2f}")

# Simple histogram bins
bins = [0, 70, 80, 90, 100, 110, 120, 130, 200]
histogram = [0] * (len(bins) - 1)

for value in data:
    for i in range(len(bins) - 1):
        if bins[i] <= value < bins[i + 1]:
            histogram[i] += 1
            break

print("\\nHistogram:")
for i, count in enumerate(histogram):
    print(f"{bins[i]}-{bins[i+1]}: {'*' * count} ({count})")
''',
            'timeout': 15
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        # Verify data analysis results
        assert 'Dataset Analysis' in response_body
        assert 'Mean:' in response_body
        assert 'Std Dev:' in response_body
        assert 'Histogram:' in response_body
        assert 'Variables Created:' in response_body
        assert '✅' in response_body
    
    def test_lambda_handler_algorithm_implementation(self):
        """Test Lambda handler with algorithm implementation"""
        
        event = {
            'code': '''
# Implement sorting algorithms
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# Test the algorithms
unsorted_data = [64, 34, 25, 12, 22, 11, 90]
print(f"Original: {unsorted_data}")

sorted_data = bubble_sort(unsorted_data.copy())
print(f"Sorted: {sorted_data}")

# Test binary search
target = 25
index = binary_search(sorted_data, target)
print(f"Binary search for {target}: index {index}")

# Fibonacci sequence
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

fib_sequence = [fibonacci(i) for i in range(10)]
print(f"Fibonacci sequence: {fib_sequence}")
''',
            'timeout': 10
        }
        
        context = Mock()
        
        response = lambda_handler(event, context)
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        # Verify algorithm results
        assert 'Original: [64, 34, 25, 12, 22, 11, 90]' in response_body
        assert 'Sorted:' in response_body
        assert 'Binary search for 25:' in response_body
        assert 'Fibonacci sequence:' in response_body
        assert '✅' in response_body
    
    def test_lambda_handler_error_scenarios(self):
        """Test Lambda handler with various error scenarios"""
        
        # Test syntax error
        event = {
            'code': '''
# This has a syntax error
def broken_function(
    print("Missing closing parenthesis")
''',
            'timeout': 5
        }
        
        context = Mock()
        response = lambda_handler(event, context)
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        assert '❌' in response_body  # Error indicator
        assert 'SyntaxError' in response_body or 'Error:' in response_body
    
    def test_lambda_handler_security_violations(self):
        """Test Lambda handler with security violations"""
        
        security_test_cases = [
            {
                'code': 'import os; os.system("echo test")',
                'expected_error': 'Security violation'
            },
            {
                'code': 'exec("print(\\"dangerous\\")")',
                'expected_error': 'Security violation'
            },
            {
                'code': 'open("/etc/passwd", "r")',
                'expected_error': 'Security violation'
            }
        ]
        
        for test_case in security_test_cases:
            event = {
                'code': test_case['code'],
                'timeout': 5
            }
            
            context = Mock()
            response = lambda_handler(event, context)
            response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
            
            assert '❌' in response_body
            assert test_case['expected_error'] in response_body
    
    def test_lambda_handler_parameter_validation(self):
        """Test Lambda handler parameter validation"""
        
        # Test missing code parameter
        event = {
            'parameters': [
                {'name': 'timeout', 'value': '5'}
            ]
        }
        
        context = Mock()
        response = lambda_handler(event, context)
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        assert 'Code parameter is required' in response_body
        
        # Test unsupported language
        event = {
            'code': 'console.log("test");',
            'language': 'javascript'
        }
        
        response = lambda_handler(event, context)
        response_body = response['response']['actionResponse']['actionResponseBody']['TEXT']['body']
        
        assert 'not supported' in response_body
    
    def test_code_executor_variable_types(self):
        """Test CodeExecutor with various variable types"""
        
        executor = CodeExecutor()
        
        code = '''
# Test various Python data types
integer_var = 42
float_var = 3.14159
string_var = "Hello, World!"
list_var = [1, 2, 3, "four", 5.0]
dict_var = {"name": "Agent Scholar", "version": 1.0, "active": True}
tuple_var = (1, 2, 3)
set_var = {1, 2, 3, 4, 5}
bool_var = True

# Complex data structure
nested_data = {
    "users": [
        {"id": 1, "name": "Alice", "scores": [85, 92, 78]},
        {"id": 2, "name": "Bob", "scores": [91, 87, 94]}
    ],
    "metadata": {
        "created": "2024-01-01",
        "version": "1.0"
    }
}

print(f"Integer: {integer_var}")
print(f"Float: {float_var}")
print(f"String: {string_var}")
print(f"List length: {len(list_var)}")
print(f"Dict keys: {list(dict_var.keys())}")
print(f"Nested data users: {len(nested_data['users'])}")
'''
        
        result = executor.execute_code(code, timeout=10)
        
        assert result['success'] is True
        
        variables = result['variables']
        assert 'integer_var' in variables
        assert variables['integer_var']['type'] == 'int'
        assert variables['integer_var']['value'] == '42'
        
        assert 'string_var' in variables
        assert variables['string_var']['type'] == 'str'
        
        assert 'list_var' in variables
        assert variables['list_var']['type'] == 'list'
        
        assert 'dict_var' in variables
        assert variables['dict_var']['type'] == 'dict'
        
        assert 'nested_data' in variables
        assert variables['nested_data']['type'] == 'dict'
    
    def test_code_executor_performance_analysis(self):
        """Test CodeExecutor performance with different code complexities"""
        
        executor = CodeExecutor()
        
        # Simple operation
        simple_code = '''
result = sum(range(100))
print(f"Sum of 0-99: {result}")
'''
        
        simple_result = executor.execute_code(simple_code, timeout=5)
        assert simple_result['success'] is True
        simple_time = simple_result['execution_time']
        
        # More complex operation
        complex_code = '''
# Calculate prime numbers up to 100
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

primes = [n for n in range(2, 101) if is_prime(n)]
print(f"Primes up to 100: {len(primes)} found")
print(f"First 10 primes: {primes[:10]}")
'''
        
        complex_result = executor.execute_code(complex_code, timeout=10)
        assert complex_result['success'] is True
        complex_time = complex_result['execution_time']
        
        # Complex operation should take longer (but not always guaranteed)
        print(f"Simple execution time: {simple_time:.3f}s")
        print(f"Complex execution time: {complex_time:.3f}s")
        
        # Both should complete successfully
        assert simple_result['success'] is True
        assert complex_result['success'] is True
    
    def test_code_executor_output_formatting(self):
        """Test CodeExecutor output formatting and display"""
        
        executor = CodeExecutor()
        
        code = '''
# Test various output formats
print("=== Agent Scholar Code Execution Test ===")
print()

# Numeric output
for i in range(5):
    print(f"Count: {i}")

print()

# Formatted output
data = [
    {"name": "Alice", "score": 95},
    {"name": "Bob", "score": 87},
    {"name": "Charlie", "score": 92}
]

print("Student Scores:")
print("-" * 20)
for student in data:
    print(f"{student['name']:10} | {student['score']:3d}")

print()
print("Analysis complete!")
'''
        
        result = executor.execute_code(code, timeout=10)
        
        assert result['success'] is True
        output = result['output']
        
        # Verify output formatting
        assert '=== Agent Scholar Code Execution Test ===' in output
        assert 'Count: 0' in output
        assert 'Count: 4' in output
        assert 'Student Scores:' in output
        assert 'Alice' in output
        assert 'Analysis complete!' in output
        
        # Verify variables were created
        assert 'data' in result['variables']
        assert result['variables']['data']['type'] == 'list'

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])