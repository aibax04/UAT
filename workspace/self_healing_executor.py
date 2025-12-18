"""
Self-Healing Execution Engine: Attempts recovery when selectors fail.
Similar to Testim's adaptive execution.
"""
from playwright.sync_api import Page, ElementHandle, TimeoutError as PlaywrightTimeoutError
from workspace.smart_locator import SmartLocatorEngine, LocatorCandidate
from workspace.element_fingerprint import ElementFingerprint
from typing import Dict, Optional, Tuple, List
import time


class SelfHealingExecutor:
    """Executes actions with self-healing capabilities"""
    
    def __init__(self, page: Page, smart_locator: SmartLocatorEngine, on_update_callback=None):
        self.page = page
        self.smart_locator = smart_locator
        self.on_update_callback = on_update_callback
        self.healing_history = []  # Track healing attempts
    
    def execute_click(self, element_info: Dict, timeout: int = 10000) -> Tuple[bool, Dict]:
        """
        Execute click with self-healing.
        
        Returns:
            (success: bool, metadata: dict with locator_used, healing_attempted, etc.)
        """
        metadata = {
            'locator_used': None,
            'locator_strategy': None,
            'confidence': 0.0,
            'healing_attempted': False,
            'healing_successful': False,
            'healing_steps': []
        }
        
        # Generate locator candidates
        candidates = self.smart_locator.generate_locators(element_info)
        
        # Check cached locators first
        fingerprint_hash = ElementFingerprint.fingerprint_from_info(element_info)
        cached_locators = self.smart_locator.get_cached_locators(fingerprint_hash)
        if cached_locators:
            # Prepend cached locators (they have proven successful)
            candidates = cached_locators + candidates
        
        # Try each candidate
        for candidate in candidates:
            try:
                # Wait for element and click
                element = self.page.wait_for_selector(
                    candidate.locator,
                    state='visible',
                    timeout=5000
                )
                
                # Validate element context before clicking
                if not self._validate_element_context(element, 'click'):
                    metadata['healing_steps'].append({
                        'locator': candidate.locator,
                        'reason': 'Element context validation failed'
                    })
                    continue
                
                # Execute click
                element.click(timeout=timeout)
                
                # Record success
                metadata['locator_used'] = candidate.locator
                metadata['locator_strategy'] = candidate.strategy
                metadata['confidence'] = candidate.confidence
                
                # Store successful locator
                self.smart_locator.record_successful_locator(fingerprint_hash, candidate)
                
                return True, metadata
                
            except Exception as e:
                metadata['healing_steps'].append({
                    'locator': candidate.locator,
                    'strategy': candidate.strategy,
                    'error': str(e)
                })
                continue
        
        # All selectors failed - attempt fingerprint-based healing
        metadata['healing_attempted'] = True
        
        if self.on_update_callback:
            self.on_update_callback({
                'type': 'healing_start',
                'message': 'All selectors failed, attempting self-healing...',
                'element_info': element_info
            })
        
        healing_result = self._attempt_healing(element_info, 'click', timeout)
        
        if healing_result['success']:
            metadata['healing_successful'] = True
            metadata['locator_used'] = healing_result.get('locator', 'fingerprint_match')
            metadata['locator_strategy'] = 'fingerprint_healing'
            metadata['confidence'] = healing_result.get('confidence', 0.70)
            metadata['healing_steps'].append(healing_result)
            
            return True, metadata
        else:
            metadata['healing_steps'].append(healing_result)
            return False, metadata
    
    def execute_fill(self, element_info: Dict, text: str, timeout: int = 10000) -> Tuple[bool, Dict]:
        """Execute fill with self-healing"""
        metadata = {
            'locator_used': None,
            'locator_strategy': None,
            'confidence': 0.0,
            'healing_attempted': False,
            'healing_successful': False,
            'healing_steps': []
        }
        
        # Generate locator candidates
        candidates = self.smart_locator.generate_locators(element_info)
        
        # Check cached locators
        fingerprint_hash = ElementFingerprint.fingerprint_from_info(element_info)
        cached_locators = self.smart_locator.get_cached_locators(fingerprint_hash)
        if cached_locators:
            candidates = cached_locators + candidates
        
        # Try each candidate
        for candidate in candidates:
            try:
                element = self.page.wait_for_selector(
                    candidate.locator,
                    state='visible',
                    timeout=5000
                )
                
                # Validate element context
                if not self._validate_element_context(element, 'fill'):
                    continue
                
                # Clear and fill
                element.fill('', timeout=2000)
                element.fill(text, timeout=timeout)
                
                # Record success
                metadata['locator_used'] = candidate.locator
                metadata['locator_strategy'] = candidate.strategy
                metadata['confidence'] = candidate.confidence
                
                # Store successful locator
                self.smart_locator.record_successful_locator(fingerprint_hash, candidate)
                
                return True, metadata
                
            except Exception as e:
                metadata['healing_steps'].append({
                    'locator': candidate.locator,
                    'strategy': candidate.strategy,
                    'error': str(e)
                })
                continue
        
        # Attempt healing
        metadata['healing_attempted'] = True
        
        if self.on_update_callback:
            self.on_update_callback({
                'type': 'healing_start',
                'message': 'All selectors failed, attempting self-healing...',
                'element_info': element_info
            })
        
        healing_result = self._attempt_healing(element_info, 'fill', timeout, text=text)
        
        if healing_result['success']:
            metadata['healing_successful'] = True
            metadata['locator_used'] = healing_result.get('locator', 'fingerprint_match')
            metadata['locator_strategy'] = 'fingerprint_healing'
            metadata['confidence'] = healing_result.get('confidence', 0.70)
            metadata['healing_steps'].append(healing_result)
            
            return True, metadata
        else:
            metadata['healing_steps'].append(healing_result)
            return False, metadata
    
    def _attempt_healing(self, element_info: Dict, action_type: str, timeout: int, **kwargs) -> Dict:
        """
        Attempt to heal by finding element using fingerprint.
        
        Returns:
            Dict with success, locator, confidence, and details
        """
        try:
            # Create fingerprint from element info
            fingerprint = {
                'tag': element_info.get('tag', '*'),
                'text': element_info.get('text', ''),
                'attributes': element_info.get('attributes', {})
            }
            
            # Find element by fingerprint
            match_result = self.smart_locator.find_element_by_fingerprint(fingerprint)
            
            if match_result and match_result.get('element'):
                element = match_result['element']
                confidence = match_result.get('confidence', 0.70)
                
                # Validate context
                if not self._validate_element_context(element, action_type):
                    return {
                        'success': False,
                        'reason': 'Element found but context validation failed'
                    }
                
                # Execute action
                if action_type == 'click':
                    element.click(timeout=timeout)
                elif action_type == 'fill':
                    text = kwargs.get('text', '')
                    element.fill('', timeout=2000)
                    element.fill(text, timeout=timeout)
                
                # Create actual fingerprint for storage
                actual_fingerprint = ElementFingerprint.create_fingerprint(element, self.page)
                
                return {
                    'success': True,
                    'locator': f'fingerprint:{actual_fingerprint["hash"]}',
                    'confidence': confidence,
                    'fingerprint': actual_fingerprint,
                    'method': 'fingerprint_matching'
                }
            
            return {
                'success': False,
                'reason': 'Could not find element using fingerprint matching'
            }
            
        except Exception as e:
            return {
                'success': False,
                'reason': f'Healing error: {str(e)}'
            }
    
    def _validate_element_context(self, element: ElementHandle, action_type: str) -> bool:
        """
        Validate element is ready for action (visible, enabled, etc.).
        
        Args:
            element: ElementHandle
            action_type: 'click' or 'fill'
        
        Returns:
            True if element is ready
        """
        try:
            # Check visibility
            is_visible = element.is_visible()
            if not is_visible:
                return False
            
            # Check if disabled
            is_disabled = element.evaluate('el => el.disabled || el.getAttribute("aria-disabled") === "true"')
            if is_disabled and action_type in ['click', 'fill']:
                return False
            
            # Check if in viewport (for click)
            if action_type == 'click':
                box = element.bounding_box()
                if box:
                    viewport = self.page.viewport_size
                    if box['x'] < 0 or box['y'] < 0 or \
                       box['x'] + box['width'] > viewport['width'] or \
                       box['y'] + box['height'] > viewport['height']:
                        # Element not fully in viewport - scroll to it
                        element.scroll_into_view_if_needed()
                        time.sleep(0.3)  # Allow scroll to complete
            
            # Check for overlaying modals/dialogs
            has_overlay = element.evaluate('''
                el => {
                    const rect = el.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const elementAtPoint = document.elementFromPoint(centerX, centerY);
                    return elementAtPoint !== el && elementAtPoint !== null;
                }
            ''')
            
            if has_overlay:
                # Try to wait for overlay to disappear
                try:
                    self.page.wait_for_timeout(1000)
                    has_overlay = element.evaluate('''
                        el => {
                            const rect = el.getBoundingClientRect();
                            const centerX = rect.left + rect.width / 2;
                            const centerY = rect.top + rect.height / 2;
                            const elementAtPoint = document.elementFromPoint(centerX, centerY);
                            return elementAtPoint !== el && elementAtPoint !== null;
                        }
                    ''')
                except:
                    pass
            
            return not has_overlay
            
        except Exception as e:
            print(f"Error validating element context: {e}")
            return False

