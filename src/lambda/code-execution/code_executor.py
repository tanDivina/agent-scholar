"""
Code Execution Action Group Lambda Function for Agent Scholar

This Lambda function provides secure Python code execution capabilities
for analysis, visualization, and validation of concepts from documents.
"""

import json
import logging
import os
import sys
import io
import contextlib
import resource
import signal
import time
import traceback
import tempfile
import base64
import subprocess
from typing import Dict, List, Any, Optional
import threading
import queue

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Security configuration
MAX_EXECUTION_TIME = int(os.getenv('MAX_EXECUTION_TIME', '30'))  # seconds
MAX_MEMORY_MB = int(os.getenv('MAX_MEMORY_MB', '256'))  # MB
MAX_OUTPUT_SIZE = int(os.getenv('MAX_OUTPUT_SIZE', '10000'))  # characters

# Allowed scientific libraries
ALLOWED_IMPORTS = {
    'numpy', 'np', 'pandas', 'pd', 'matplotlib', 'plt', 'seaborn', 'sns',
    'scipy', 'sklearn', 'plotly', 'sympy', 'networkx', 'nx', 'math',
    'statistics', 'random', 'datetime', 'json', 're', 'collections',
    'itertools', 'functools', 'operator', 'decimal', 'fractions'
}

# Restricted built-ins (security)
SAFE_BUILTINS = {
    'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes', 'callable',
    'chr', 'classmethod', 'complex', 'dict', 'dir', 'divmod', 'enumerate',
    'filter', 'float', 'format', 'frozenset', 'getattr', 'globals',
    'hasattr', 'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass',
    'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min',
    'next', 'object', 'oct', 'ord', 'pow', 'print', 'property', 'range',
    'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted',
    'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip'
}

class ExecutionTimeoutError(Exception):
    """Raised when code execution exceeds time limit"""
    pass

class ExecutionSecurityError(Exception):
    """Raised when code violates security constraints"""
    pass

class CodeExecutor:
    """Secure Python code executor with sandboxing and resource limits"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='agent_scholar_')
        self.output_files = []
        
    def execute_code(self, code: str, timeout: int = MAX_EXECUTION_TIME) -> Dict[str, Any]:
        """
        Execute Python code in a secure, sandboxed environment.
        
        Args:
            code: Python code string to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Dictionary containing execution results
        """
        start_time = time.time()
        
        try:
            # Validate code security
            self._validate_code_security(code)
            
            # Prepare execution environment
            safe_globals = self._create_safe_globals()
            
            # Capture output
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            # Execute with timeout and resource limits
            result = self._execute_with_limits(
                code, safe_globals, output_buffer, error_buffer, timeout
            )
            
            execution_time = time.time() - start_time
            
            # Process results
            output = output_buffer.getvalue()
            error = error_buffer.getvalue() if error_buffer.getvalue() else result.get('error')
            
            # Capture any generated visualizations
            visualizations = self._capture_visualizations(safe_globals)
            
            return {
                'success': result.get('success', True),
                'output': output[:MAX_OUTPUT_SIZE],
                'error': error,
                'execution_time': execution_time,
                'visualizations': visualizations,
                'variables': self._extract_variables(safe_globals),
                'imports_used': self._get_imports_used(code)
            }
            
        except ExecutionTimeoutError:
            return {
                'success': False,
                'output': '',
                'error': f'Code execution timed out after {timeout} seconds',
                'execution_time': timeout,
                'visualizations': [],
                'variables': {},
                'imports_used': []
            }
        except ExecutionSecurityError as e:
            return {
                'success': False,
                'output': '',
                'error': f'Security violation: {str(e)}',
                'execution_time': time.time() - start_time,
                'visualizations': [],
                'variables': {},
                'imports_used': []
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'Execution error: {str(e)}',
                'execution_time': time.time() - start_time,
                'visualizations': [],
                'variables': {},
                'imports_used': []
            }
    
    def _validate_code_security(self, code: str) -> None:
        """
        Validate code for security violations.
        
        Args:
            code: Python code to validate
            
        Raises:
            ExecutionSecurityError: If code contains security violations
        """
        # Check for dangerous operations
        dangerous_patterns = [
            'import os', 'import subprocess', 'import sys', 
            'exec(', 'eval(', 'compile(', 'open(', 'file(',
            'input(', 'raw_input(', 'reload(', 
            '__builtins__', '__globals__', '__locals__',
            'lambda:', 'yield', 'class ', 'def ', '@', 'import requests',
            'import urllib', 'import socket', 'import http', 'import ftplib'
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                raise ExecutionSecurityError(f"Dangerous operation detected: {pattern}")
        
        # Check for excessive complexity
        if len(code) > 10000:  # 10KB limit
            raise ExecutionSecurityError("Code too long (max 10KB)")
        
        if code.count('\n') > 200:  # 200 lines limit
            raise ExecutionSecurityError("Too many lines (max 200)")
    
    def _create_safe_globals(self) -> Dict[str, Any]:
        """
        Create a restricted global namespace for code execution.
        
        Returns:
            Dictionary with safe built-ins and allowed modules
        """
        # Create restricted builtins
        safe_builtins = {}
        
        # Get the actual builtins module
        import builtins as builtins_module
        
        for name in SAFE_BUILTINS:
            if hasattr(builtins_module, name):
                safe_builtins[name] = getattr(builtins_module, name)
        
        # Add __import__ function for safe imports
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Safe import function that only allows whitelisted modules"""
            if name in ALLOWED_IMPORTS or any(name.startswith(allowed + '.') for allowed in ALLOWED_IMPORTS):
                return __import__(name, globals, locals, fromlist, level)
            else:
                raise ImportError(f"Import of '{name}' is not allowed")
        
        safe_builtins['__import__'] = safe_import
        
        # Add safe print function that captures output
        def safe_print(*args, **kwargs):
            # This will be redirected to output buffer
            print(*args, **kwargs)
        
        safe_builtins['print'] = safe_print
        
        # Create safe globals
        safe_globals = {
            '__builtins__': safe_builtins,
            '__name__': '__main__',
            '__doc__': None,
        }
        
        # Add allowed scientific libraries
        try:
            import numpy as np
            safe_globals['numpy'] = np
            safe_globals['np'] = np
        except ImportError:
            logger.warning("NumPy not available")
        
        try:
            import pandas as pd
            safe_globals['pandas'] = pd
            safe_globals['pd'] = pd
        except ImportError:
            logger.warning("Pandas not available")
        
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            safe_globals['matplotlib'] = matplotlib
            safe_globals['plt'] = plt
        except ImportError:
            logger.warning("Matplotlib not available")
        
        try:
            import seaborn as sns
            safe_globals['seaborn'] = sns
            safe_globals['sns'] = sns
        except ImportError:
            logger.warning("Seaborn not available")
        
        try:
            import scipy
            safe_globals['scipy'] = scipy
        except ImportError:
            logger.warning("SciPy not available")
        
        try:
            import sklearn
            safe_globals['sklearn'] = sklearn
        except ImportError:
            logger.warning("Scikit-learn not available")
        
        try:
            import plotly
            safe_globals['plotly'] = plotly
        except ImportError:
            logger.warning("Plotly not available")
        
        try:
            import sympy
            safe_globals['sympy'] = sympy
        except ImportError:
            logger.warning("SymPy not available")
        
        try:
            import networkx as nx
            safe_globals['networkx'] = nx
            safe_globals['nx'] = nx
        except ImportError:
            logger.warning("NetworkX not available")
        
        # Add standard library modules
        import math
        import statistics
        import random
        import datetime
        import json
        import re
        import collections
        import itertools
        import functools
        import operator
        
        safe_globals.update({
            'math': math,
            'statistics': statistics,
            'random': random,
            'datetime': datetime,
            'json': json,
            're': re,
            'collections': collections,
            'itertools': itertools,
            'functools': functools,
            'operator': operator
        })
        

        
        return safe_globals
    
    def _execute_with_limits(self, code: str, safe_globals: Dict[str, Any], 
                           output_buffer: io.StringIO, error_buffer: io.StringIO,
                           timeout: int) -> Dict[str, Any]:
        """
        Execute code with resource limits and timeout.
        
        Args:
            code: Python code to execute
            safe_globals: Safe global namespace
            output_buffer: Buffer to capture stdout
            error_buffer: Buffer to capture stderr
            timeout: Maximum execution time
            
        Returns:
            Execution result dictionary
        """
        result = {'success': True, 'error': None}
        
        try:
            # Set resource limits (if available on the platform)
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
                resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024 * 1024, MAX_MEMORY_MB * 1024 * 1024))
            except (OSError, ValueError):
                # Resource limits not available on this platform (e.g., macOS)
                logger.warning("Resource limits not available on this platform")
            
            # Simple timeout using signal (Unix-like systems only)
            def timeout_handler(signum, frame):
                raise ExecutionTimeoutError(f"Code execution exceeded {timeout} seconds")
            
            # Set up timeout signal (if available)
            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)
            except (AttributeError, OSError):
                # Signal not available (e.g., Windows)
                logger.warning("Signal-based timeout not available on this platform")
            
            try:
                # Redirect stdout and stderr
                with contextlib.redirect_stdout(output_buffer), \
                     contextlib.redirect_stderr(error_buffer):
                    
                    # Execute the code
                    exec(code, safe_globals)
                    
            finally:
                # Cancel timeout signal
                try:
                    signal.alarm(0)
                    if old_handler is not None:
                        signal.signal(signal.SIGALRM, old_handler)
                except (AttributeError, OSError):
                    pass
                    
        except ExecutionTimeoutError:
            raise
        except Exception as e:
            result['success'] = False
            result['error'] = f"{type(e).__name__}: {str(e)}"
            error_buffer.write(traceback.format_exc())
        
        return result
    
    def _capture_visualizations(self, safe_globals: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Capture any matplotlib/plotly visualizations created during execution.
        
        Args:
            safe_globals: Global namespace after execution
            
        Returns:
            List of visualization data
        """
        visualizations = []
        
        try:
            # Check for matplotlib figures
            if 'plt' in safe_globals:
                import matplotlib.pyplot as plt
                
                # Get all figures
                figures = [plt.figure(i) for i in plt.get_fignums()]
                
                for i, fig in enumerate(figures):
                    if fig.get_axes():  # Only save figures with content
                        # Save figure to base64
                        buffer = io.BytesIO()
                        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
                        buffer.seek(0)
                        
                        image_base64 = base64.b64encode(buffer.getvalue()).decode()
                        
                        visualizations.append({
                            'type': 'matplotlib',
                            'format': 'png',
                            'data': image_base64,
                            'title': f'Figure {i+1}',
                            'size': len(image_base64)
                        })
                        
                        buffer.close()
                
                # Clear figures to free memory
                plt.close('all')
                
        except Exception as e:
            logger.warning(f"Error capturing matplotlib visualizations: {e}")
        
        try:
            # Check for plotly figures (if available)
            if 'plotly' in safe_globals:
                # Plotly figures would be handled differently
                # This is a placeholder for plotly integration
                pass
                
        except Exception as e:
            logger.warning(f"Error capturing plotly visualizations: {e}")
        
        return visualizations
    
    def _extract_variables(self, safe_globals: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract interesting variables from the execution namespace.
        
        Args:
            safe_globals: Global namespace after execution
            
        Returns:
            Dictionary of variable names and their string representations
        """
        variables = {}
        
        # Skip built-in and module variables
        skip_keys = {
            '__builtins__', '__name__', '__doc__', 'numpy', 'np', 'pandas', 'pd',
            'matplotlib', 'plt', 'seaborn', 'sns', 'scipy', 'sklearn', 'plotly',
            'sympy', 'networkx', 'nx', 'math', 'statistics', 'random', 'datetime',
            'json', 're', 'collections', 'itertools', 'functools', 'operator'
        }
        
        for name, value in safe_globals.items():
            if name.startswith('_') or name in skip_keys:
                continue
            
            try:
                # Get string representation, but limit size
                str_repr = str(value)
                if len(str_repr) > 500:
                    str_repr = str_repr[:500] + '...'
                
                variables[name] = {
                    'type': type(value).__name__,
                    'value': str_repr
                }
                
            except Exception:
                variables[name] = {
                    'type': type(value).__name__,
                    'value': '<unable to display>'
                }
        
        return variables
    
    def _get_imports_used(self, code: str) -> List[str]:
        """
        Extract import statements from the code.
        
        Args:
            code: Python code
            
        Returns:
            List of imported modules/libraries
        """
        imports = []
        
        for line in code.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
        
        return imports

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for code execution action group.
    
    Args:
        event: Lambda event containing the code to execute
        context: Lambda context object
        
    Returns:
        Formatted response for Bedrock Agent with execution results
    """
    try:
        logger.info("Received code execution request")
        
        # Extract parameters from the event
        # Handle both direct parameters and Bedrock Agent format
        if 'parameters' in event:
            # Bedrock Agent format
            parameters = event.get('parameters', [])
            param_dict = {param['name']: param['value'] for param in parameters}
        else:
            # Direct invocation format
            param_dict = event
        
        code = param_dict.get('code', '')
        timeout = int(param_dict.get('timeout', MAX_EXECUTION_TIME))
        language = param_dict.get('language', 'python').lower()
        
        if not code:
            return create_bedrock_response("Code parameter is required for execution")
        
        if language != 'python':
            return create_bedrock_response(f"Language '{language}' not supported. Only Python is currently supported.")
        
        # Validate timeout
        timeout = min(timeout, MAX_EXECUTION_TIME)  # Enforce maximum timeout
        
        logger.info(f"Executing Python code with timeout: {timeout}s")
        
        # Create executor and run code
        executor = CodeExecutor()
        execution_result = executor.execute_code(code, timeout)
        
        # Format response
        response_text = format_execution_result(execution_result, code)
        
        return create_bedrock_response(response_text)
        
    except Exception as e:
        logger.error(f"Error in code execution handler: {str(e)}")
        return create_bedrock_response(f"Code execution system error: {str(e)}")

def create_bedrock_response(response_text: str) -> Dict[str, Any]:
    """Create standardized response for Bedrock Agent action groups."""
    return {
        'response': {
            'actionResponse': {
                'actionResponseBody': {
                    'TEXT': {
                        'body': response_text
                    }
                }
            }
        }
    }

def validate_code_request(code: str, timeout: int) -> Dict[str, Any]:
    """
    Validate code execution request parameters.
    
    Args:
        code: Python code to validate
        timeout: Requested timeout
        
    Returns:
        Validation result with suggestions
    """
    validation = {
        'valid': True,
        'warnings': [],
        'suggestions': []
    }
    
    # Validate code
    if not code or not code.strip():
        validation['valid'] = False
        validation['warnings'].append("Code cannot be empty")
        return validation
    
    if len(code) > 10000:
        validation['valid'] = False
        validation['warnings'].append("Code too long (max 10KB)")
    
    if code.count('\n') > 200:
        validation['warnings'].append("Code has many lines - consider breaking into smaller chunks")
    
    # Validate timeout
    if timeout < 1:
        validation['valid'] = False
        validation['warnings'].append("Timeout must be at least 1 second")
    elif timeout > MAX_EXECUTION_TIME:
        validation['warnings'].append(f"Timeout reduced to maximum allowed: {MAX_EXECUTION_TIME}s")
    
    # Provide suggestions based on code content
    code_lower = code.lower()
    
    if 'matplotlib' in code_lower or 'plt.' in code_lower:
        validation['suggestions'].append("Detected matplotlib usage - visualizations will be captured automatically")
    
    if 'pandas' in code_lower or 'pd.' in code_lower:
        validation['suggestions'].append("Detected pandas usage - consider using .head() for large datasets")
    
    if 'numpy' in code_lower or 'np.' in code_lower:
        validation['suggestions'].append("Detected NumPy usage - numerical computations are optimized")
    
    if 'for ' in code_lower and 'range(' in code_lower:
        validation['suggestions'].append("Consider using vectorized operations for better performance")
    
    return validation

def format_execution_result(result: Dict[str, Any], original_code: str = "") -> str:
    """
    Format code execution results for agent consumption.
    
    Args:
        result: Execution result dictionary
        original_code: Original code that was executed
        
    Returns:
        Formatted string representation of results
    """
    success_indicator = "✅" if result.get('success', True) else "❌"
    
    formatted_result = f"""{success_indicator} **Python Code Execution Results**

📝 **Code Summary:**
```python
{original_code[:200]}{'...' if len(original_code) > 200 else ''}
```

⏱️ **Execution Time:** {result.get('execution_time', 0):.3f} seconds
"""
    
    # Add output section
    output = result.get('output', '').strip()
    if output:
        formatted_result += f"""
📤 **Output:**
```
{output}
```"""
    else:
        formatted_result += "\n📤 **Output:** No output produced"
    
    # Add error section if there was an error
    if result.get('error'):
        formatted_result += f"""
🚨 **Error:**
```
{result['error']}
```"""
    
    # Add variables section
    variables = result.get('variables', {})
    if variables:
        formatted_result += f"\n📊 **Variables Created:** {len(variables)}"
        
        # Show first few variables
        var_items = list(variables.items())[:5]
        for name, info in var_items:
            formatted_result += f"\n  • `{name}` ({info['type']}): {info['value'][:100]}{'...' if len(info['value']) > 100 else ''}"
        
        if len(variables) > 5:
            formatted_result += f"\n  • ... and {len(variables) - 5} more variables"
    
    # Add visualizations section
    visualizations = result.get('visualizations', [])
    if visualizations:
        formatted_result += f"\n🎨 **Visualizations:** {len(visualizations)} generated"
        
        for i, viz in enumerate(visualizations):
            size_kb = viz.get('size', 0) / 1024
            formatted_result += f"\n  • {viz.get('title', f'Visualization {i+1}')} ({viz.get('format', 'unknown').upper()}, {size_kb:.1f}KB)"
    
    # Add imports section
    imports_used = result.get('imports_used', [])
    if imports_used:
        formatted_result += f"\n📚 **Libraries Used:**"
        for imp in imports_used[:5]:  # Show first 5 imports
            formatted_result += f"\n  • `{imp}`"
        if len(imports_used) > 5:
            formatted_result += f"\n  • ... and {len(imports_used) - 5} more imports"
    
    # Add performance notes
    execution_time = result.get('execution_time', 0)
    if execution_time > 10:
        formatted_result += f"\n⚠️ **Performance Note:** Execution took {execution_time:.1f}s - consider optimizing for faster results"
    elif execution_time < 0.1:
        formatted_result += f"\n⚡ **Performance:** Very fast execution ({execution_time*1000:.1f}ms)"
    
    # Add success summary
    if result.get('success', True):
        formatted_result += f"\n\n✨ **Summary:** Code executed successfully"
        if visualizations:
            formatted_result += f" with {len(visualizations)} visualization(s)"
        if variables:
            formatted_result += f" and {len(variables)} variable(s) created"
    else:
        formatted_result += f"\n\n💡 **Tip:** Check the error message above and verify your code syntax and logic"
    
    return formatted_result

def analyze_code_complexity(code: str) -> Dict[str, Any]:
    """
    Analyze code complexity and provide insights.
    
    Args:
        code: Python code to analyze
        
    Returns:
        Analysis results
    """
    analysis = {
        'lines': len(code.split('\n')),
        'characters': len(code),
        'complexity_score': 0,
        'suggestions': []
    }
    
    # Simple complexity analysis
    complexity_indicators = [
        ('for ', 2), ('while ', 2), ('if ', 1), ('elif ', 1), ('else:', 1),
        ('def ', 3), ('class ', 4), ('try:', 2), ('except', 2),
        ('import ', 1), ('from ', 1)
    ]
    
    code_lower = code.lower()
    for indicator, weight in complexity_indicators:
        count = code_lower.count(indicator)
        analysis['complexity_score'] += count * weight
    
    # Provide suggestions based on complexity
    if analysis['complexity_score'] > 50:
        analysis['suggestions'].append("High complexity detected - consider breaking into smaller functions")
    
    if analysis['lines'] > 50:
        analysis['suggestions'].append("Long code block - consider splitting for better readability")
    
    if 'matplotlib' in code_lower and 'plt.show()' in code_lower:
        analysis['suggestions'].append("Remove plt.show() - visualizations are captured automatically")
    
    return analysis

def get_execution_tips(code: str) -> List[str]:
    """
    Get execution tips based on code content.
    
    Args:
        code: Python code
        
    Returns:
        List of helpful tips
    """
    tips = []
    code_lower = code.lower()
    
    if 'pandas' in code_lower:
        tips.append("💡 Use df.head() to preview large datasets")
        tips.append("💡 Consider df.info() to understand data structure")
    
    if 'numpy' in code_lower:
        tips.append("💡 NumPy operations are vectorized and fast")
        tips.append("💡 Use np.array() for better performance than lists")
    
    if 'matplotlib' in code_lower:
        tips.append("💡 Figures are automatically saved - no need for plt.show()")
        tips.append("💡 Use plt.figure(figsize=(10,6)) for better sizing")
    
    if 'random' in code_lower:
        tips.append("💡 Set random.seed() for reproducible results")
    
    if 'range(' in code_lower and 'for ' in code_lower:
        tips.append("💡 Consider using NumPy vectorized operations instead of loops")
    
    return tips