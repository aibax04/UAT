"""
Backend Verification Module
===========================

Supports API-level assertions after UI actions to validate order status,
user creation, payment success, etc.
"""

import os
import json
import requests
from typing import Dict, Any, Optional, Callable, List
from playwright.sync_api import Page
from dotenv import load_dotenv

from .base_module import BaseCapabilityModule

load_dotenv()


class BackendVerificationModule(BaseCapabilityModule):
    """Verify backend state via API assertions"""
    
    def __init__(self, page: Page, on_update_callback: Optional[Callable] = None):
        super().__init__(page, on_update_callback)
        self.base_api_url = os.getenv('BACKEND_API_URL', '')
        self.api_key = os.getenv('BACKEND_API_KEY', '')
        self.default_timeout = int(os.getenv('BACKEND_VERIFY_TIMEOUT', '10'))
    
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """Check if this is a backend verification task"""
        action_type = intent_data.get('action_type', '')
        description = intent_data.get('description', '').lower()
        task_name = intent_data.get('task_name', '').lower()
        
        verify_keywords = ['verify', 'assert', 'check status', 'validate', 'confirm', 'backend', 'api']
        return (action_type in ['verify', 'assert', 'backend_check'] or
                any(keyword in description or keyword in task_name for keyword in verify_keywords) or
                intent_data.get('capability') == 'backend_verification')
    
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify backend state via API
        
        Args:
            intent_data: Must contain 'assertion_config' dict with:
                - 'endpoint': API endpoint (relative or absolute)
                - 'method': HTTP method ('GET', 'POST', etc.) - defaults to 'GET'
                - 'headers': Optional headers dict
                - 'payload': Optional request body for POST/PUT
                - 'assertions': List of assertion dicts with:
                    - 'path': JSONPath to value (e.g., 'data.order.status')
                    - 'operator': 'equals', 'contains', 'exists', 'greater_than', etc.
                    - 'expected': Expected value
                - 'auth_type': Optional auth type ('bearer', 'basic', 'api_key')
                - 'auth_value': Optional auth token/key
        
        Returns:
            Result dict with assertion results
        """
        try:
            config = intent_data.get('assertion_config', {})
            if not config:
                return self._create_result(
                    False,
                    error="assertion_config is required"
                )
            
            endpoint = config.get('endpoint', '')
            if not endpoint:
                return self._create_result(
                    False,
                    error="endpoint is required in assertion_config"
                )
            
            self._emit_update('capability_start', {
                'message': f'Verifying backend state at {endpoint}',
                'endpoint': endpoint
            })
            
            # Build full URL if relative
            if not endpoint.startswith('http'):
                base_url = config.get('base_url') or self.base_api_url
                if not base_url:
                    return self._create_result(
                        False,
                        error="Absolute endpoint URL or base_url required"
                    )
                endpoint = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Prepare request
            method = config.get('method', 'GET').upper()
            headers = config.get('headers', {}).copy()
            payload = config.get('payload')
            
            # Add authentication
            auth_type = config.get('auth_type', '').lower()
            auth_value = config.get('auth_value') or self.api_key
            if auth_value:
                if auth_type == 'bearer':
                    headers['Authorization'] = f'Bearer {auth_value}'
                elif auth_type == 'api_key':
                    headers['X-API-Key'] = auth_value
                elif auth_type == 'basic':
                    # Basic auth would need username:password format
                    headers['Authorization'] = f'Basic {auth_value}'
            
            # Make API request
            timeout = config.get('timeout', self.default_timeout)
            
            if method == 'GET':
                response = requests.get(endpoint, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(endpoint, json=payload, headers=headers, timeout=timeout)
            elif method == 'PATCH':
                response = requests.patch(endpoint, json=payload, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(endpoint, headers=headers, timeout=timeout)
            else:
                return self._create_result(
                    False,
                    error=f"Unsupported HTTP method: {method}"
                )
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {'raw_text': response.text}
            
            # Run assertions
            assertions = config.get('assertions', [])
            assertion_results = []
            all_passed = True
            
            for assertion in assertions:
                result = self._run_assertion(assertion, response_data, response.status_code)
                assertion_results.append(result)
                if not result.get('passed', False):
                    all_passed = False
            
            # Build result
            result = {
                'status_code': response.status_code,
                'assertions': assertion_results,
                'all_passed': all_passed,
                'response_data': response_data if len(str(response_data)) < 1000 else 'Response too large'
            }
            
            metadata = {
                'endpoint': endpoint,
                'method': method,
                'status_code': response.status_code,
                'timestamp': response.elapsed.total_seconds()
            }
            
            if all_passed:
                self._emit_update('capability_complete', {
                    'message': f'All backend assertions passed ({len(assertion_results)} assertions)',
                    'result': result
                })
            else:
                failed_count = sum(1 for a in assertion_results if not a.get('passed'))
                self._emit_update('capability_error', {
                    'message': f'{failed_count} assertion(s) failed',
                    'result': result
                })
            
            return self._create_result(
                all_passed,
                result=result,
                metadata=metadata,
                error=None if all_passed else f"{sum(1 for a in assertion_results if not a.get('passed'))} assertion(s) failed"
            )
            
        except Exception as e:
            error_msg = f"Backend verification error: {str(e)}"
            self._emit_update('capability_error', {'error': error_msg})
            return self._create_result(False, error=error_msg)
    
    def _run_assertion(self, assertion: Dict[str, Any], 
                      response_data: Dict[str, Any], 
                      status_code: int) -> Dict[str, Any]:
        """Run a single assertion"""
        path = assertion.get('path', '')
        operator = assertion.get('operator', 'equals').lower()
        expected = assertion.get('expected')
        
        # Get value from JSONPath (simplified - for production use jsonpath-ng)
        actual_value = self._get_json_path_value(response_data, path)
        
        # Special case: status code assertion
        if path == 'status_code' or path == '$status_code':
            actual_value = status_code
        
        # Run operator
        passed = False
        error = None
        
        try:
            if operator == 'equals':
                passed = actual_value == expected
            elif operator == 'not_equals':
                passed = actual_value != expected
            elif operator == 'contains':
                passed = expected in str(actual_value)
            elif operator == 'exists':
                passed = actual_value is not None
            elif operator == 'not_exists':
                passed = actual_value is None
            elif operator == 'greater_than':
                passed = float(actual_value) > float(expected)
            elif operator == 'less_than':
                passed = float(actual_value) < float(expected)
            elif operator == 'in':
                passed = actual_value in (expected if isinstance(expected, list) else [expected])
            elif operator == 'matches':
                import re
                passed = bool(re.search(str(expected), str(actual_value)))
            else:
                error = f"Unknown operator: {operator}"
        except Exception as e:
            error = f"Assertion evaluation error: {str(e)}"
        
        return {
            'path': path,
            'operator': operator,
            'expected': expected,
            'actual': actual_value,
            'passed': passed,
            'error': error
        }
    
    def _get_json_path_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from JSON using simple path notation (e.g., 'data.order.status')"""
        if not path or path == '$':
            return data
        
        # Handle root reference
        if path.startswith('$.'):
            path = path[2:]
        elif path.startswith('$'):
            path = path[1:]
        
        # Navigate path
        current = data
        parts = path.split('.')
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index] if 0 <= index < len(current) else None
                except ValueError:
                    return None
            else:
                return None
            
            if current is None:
                return None
        
        return current


def verify_backend_state(assertion_config: Dict[str, Any],
                        page: Optional[Page] = None,
                        on_update_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to verify backend state
    
    Args:
        assertion_config: Configuration dict (see BackendVerificationModule.execute)
        page: Optional Playwright page (for context)
        on_update_callback: Optional callback for updates
        
    Returns:
        Result dict with assertion results
    """
    module = BackendVerificationModule(page, on_update_callback)
    return module.execute({'assertion_config': assertion_config})

