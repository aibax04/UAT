"""
Base Module Interface for Enterprise Capabilities
==================================================

All capability modules must extend this base class to ensure
consistent interface and observability.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from playwright.sync_api import Page


class BaseCapabilityModule(ABC):
    """Base class for all enterprise capability modules"""
    
    def __init__(self, page: Page, on_update_callback: Optional[Callable] = None):
        """
        Initialize the capability module
        
        Args:
            page: Playwright page object
            on_update_callback: Optional callback for execution updates
        """
        self.page = page
        self.on_update_callback = on_update_callback
    
    def _emit_update(self, update_type: str, data: Dict[str, Any]):
        """Emit execution update through callback"""
        if self.on_update_callback:
            self.on_update_callback({
                'type': update_type,
                'module': self.__class__.__name__,
                **data
            })
    
    def _capture_screenshot(self, description: str = ""):
        """Capture screenshot for observability"""
        try:
            screenshot = self.page.screenshot(full_page=False)
            return screenshot
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            return None
    
    @abstractmethod
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """
        Check if this module can handle the given intent
        
        Args:
            intent_data: Task intent/metadata
            
        Returns:
            bool: True if module can handle this intent
        """
        pass
    
    @abstractmethod
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the capability
        
        Args:
            intent_data: Task intent/metadata with required parameters
            
        Returns:
            Dict with keys:
                - success: bool
                - result: Any (module-specific result data)
                - metadata: Dict (execution metadata)
                - error: Optional[str] (error message if failed)
        """
        pass
    
    def _create_result(self, success: bool, result: Any = None, 
                      metadata: Optional[Dict] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """Helper to create standardized result dictionary"""
        return {
            'success': success,
            'result': result,
            'metadata': metadata or {},
            'error': error
        }

