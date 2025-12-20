"""
Capability Router
=================

Routes tasks to appropriate capability modules based on intent detection.
Non-intrusive integration - only invokes modules when relevant.
"""

from typing import Dict, Any, Optional, Callable, List
from playwright.sync_api import Page

from .form_intelligence import FormIntelligenceModule
from .payment_handler import PaymentGatewayHandler
from .email_verification import EmailVerificationModule
from .otp_sms import OTPSMSModule
from .backend_verification import BackendVerificationModule


class CapabilityRouter:
    """
    Routes tasks to enterprise capability modules based on intent.
    Acts as a facade - existing execution flow continues unchanged if no capability matches.
    """
    
    def __init__(self, page: Page, on_update_callback: Optional[Callable] = None):
        """
        Initialize capability router
        
        Args:
            page: Playwright page object
            on_update_callback: Optional callback for execution updates
        """
        self.page = page
        self.on_update_callback = on_update_callback
        
        # Initialize all capability modules
        self.modules = {
            'form_intelligence': FormIntelligenceModule(page, on_update_callback),
            'payment': PaymentGatewayHandler(page, on_update_callback),
            'email_verification': EmailVerificationModule(page, on_update_callback),
            'otp_sms': OTPSMSModule(page, on_update_callback),
            'backend_verification': BackendVerificationModule(page, on_update_callback)
        }
        
        # Module priority order (first matching module wins)
        self.module_order = [
            'payment',
            'form_intelligence',
            'otp_sms',
            'email_verification',
            'backend_verification'
        ]
    
    def route_task(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Route a task to appropriate capability module if applicable.
        Returns None if no module should handle it (fallback to standard execution).
        
        Args:
            task: Task dictionary with action_type, description, etc.
            
        Returns:
            Result dict if a module handled it, None otherwise
        """
        # Build intent data from task
        intent_data = {
            'action_type': task.get('action_type', ''),
            'description': task.get('description', ''),
            'task_name': task.get('name', ''),
            'url': task.get('url', ''),
            'capability': task.get('capability'),  # Explicit capability hint
            **task.get('attributes', {}),  # Merge task attributes
            **task  # Include all task fields for module access
        }
        
        # Check if explicit capability is specified
        explicit_capability = intent_data.get('capability')
        if explicit_capability:
            module_key = self._normalize_capability_name(explicit_capability)
            if module_key in self.modules:
                module = self.modules[module_key]
                if module.can_handle(intent_data):
                    return module.execute(intent_data)
        
        # Try modules in priority order
        for module_key in self.module_order:
            if module_key in self.modules:
                module = self.modules[module_key]
                if module.can_handle(intent_data):
                    # Module can handle this task
                    return module.execute(intent_data)
        
        # No module matched - return None to use standard execution
        return None
    
    def _normalize_capability_name(self, name: str) -> str:
        """Normalize capability name to module key"""
        name_lower = name.lower().replace('-', '_').replace(' ', '_')
        
        # Map variations to module keys
        mappings = {
            'form': 'form_intelligence',
            'form_intelligence': 'form_intelligence',
            'fill_form': 'form_intelligence',
            'payment': 'payment',
            'payment_handler': 'payment',
            'pay': 'payment',
            'email': 'email_verification',
            'email_verification': 'email_verification',
            'verify_email': 'email_verification',
            'otp': 'otp_sms',
            'sms': 'otp_sms',
            'otp_sms': 'otp_sms',
            'backend': 'backend_verification',
            'backend_verification': 'backend_verification',
            'verify_backend': 'backend_verification',
            'api_check': 'backend_verification'
        }
        
        return mappings.get(name_lower, name_lower)
    
    def should_handle_task(self, task: Dict[str, Any]) -> bool:
        """
        Check if router should handle this task (before routing).
        Useful for conditional execution.
        
        Args:
            task: Task dictionary
            
        Returns:
            True if a capability module should handle this task
        """
        intent_data = {
            'action_type': task.get('action_type', ''),
            'description': task.get('description', ''),
            'task_name': task.get('name', ''),
            'capability': task.get('capability'),
            **task.get('attributes', {})
        }
        
        # Check explicit capability first
        if intent_data.get('capability'):
            module_key = self._normalize_capability_name(intent_data['capability'])
            if module_key in self.modules:
                return self.modules[module_key].can_handle(intent_data)
        
        # Check all modules
        for module_key in self.module_order:
            if module_key in self.modules:
                if self.modules[module_key].can_handle(intent_data):
                    return True
        
        return False
    
    def get_available_capabilities(self) -> List[str]:
        """Get list of available capability module names"""
        return list(self.modules.keys())
    
    def get_module(self, capability_name: str):
        """Get a specific capability module by name"""
        module_key = self._normalize_capability_name(capability_name)
        return self.modules.get(module_key)

