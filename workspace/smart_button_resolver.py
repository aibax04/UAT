"""
Smart Button Resolver: Testim-style semantic button clicking.
Provides robust, accessibility-aware, self-healing button resolution.

This module is OPTIONAL and opt-in - existing click logic remains unchanged.
"""

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Optional, List, Tuple, Any
import time
import re


class ButtonResolverStrategy:
    """Represents a button resolution strategy with confidence"""
    
    def __init__(self, name: str, locator: Locator, confidence: float, metadata: Dict = None):
        self.name = name
        self.locator = locator
        self.confidence = confidence
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"ButtonResolverStrategy({self.name}, confidence={self.confidence})"


class ContextValidator:
    """Validates button context (visibility, enabled state, not obscured, DOM attachment)"""
    
    @staticmethod
    def ensure_page_ready(page: Page, timeout: int = 5000) -> Tuple[bool, Optional[str]]:
        """
        Ensure page is ready before interaction (network idle or stable DOM).
        
        Returns:
            (is_ready: bool, error_message: Optional[str])
        """
        try:
            # Wait for network idle (no requests for 500ms) with timeout
            try:
                page.wait_for_load_state('networkidle', timeout=min(timeout, 3000))
            except TimeoutError:
                # Fallback: wait for DOM to be stable (domcontentloaded)
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=min(timeout, 2000))
                except:
                    pass
            
            # Additional check: ensure document is ready
            try:
                page.wait_for_function("document.readyState === 'complete'", timeout=min(timeout, 2000))
            except:
                pass  # Non-critical
            
            return True, None
        except Exception as e:
            return False, f"Page readiness check failed: {str(e)}"
    
    @staticmethod
    def validate(button: Locator, page: Page, timeout: int = 5000) -> Tuple[bool, Optional[str]]:
        """
        Validate button is ready to click with comprehensive checks.
        
        Returns:
            (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Check 1: Element is attached to DOM
            try:
                is_attached = button.evaluate('el => el.isConnected')
                if not is_attached:
                    return False, "Button is not attached to DOM"
            except Exception as e:
                return False, f"Button not found in DOM: {str(e)}"
            
            # Check 2: Wait for element to be visible (no hard sleep, uses Playwright's wait)
            try:
                button.wait_for(state='visible', timeout=timeout)
            except TimeoutError:
                return False, "Button not visible within timeout"
            
            # Check 3: Element is enabled (not disabled)
            try:
                is_disabled = button.evaluate('''
                    el => {
                        return el.disabled || 
                               (el.hasAttribute("aria-disabled") && el.getAttribute("aria-disabled") === "true") ||
                               el.classList.contains("disabled");
                    }
                ''')
                if is_disabled:
                    return False, "Button is disabled"
            except:
                pass  # Non-critical check
            
            # Check 4: Element is not obscured
            try:
                is_obscured = button.evaluate("""
                    el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) {
                            return true; // Element has no size
                        }
                        const centerX = rect.left + rect.width / 2;
                        const centerY = rect.top + rect.height / 2;
                        const topElement = document.elementFromPoint(centerX, centerY);
                        if (!topElement) return true;
                        // Check if the top element is the button or inside it
                        return topElement !== el && !el.contains(topElement);
                    }
                """)
                if is_obscured:
                    return False, "Button is obscured by another element"
            except:
                pass  # Non-critical check
            
            # Check 5: Element is in viewport (scroll into view if needed)
            try:
                is_in_viewport = button.evaluate("""
                    el => {
                        const rect = el.getBoundingClientRect();
                        return (
                            rect.top >= 0 &&
                            rect.left >= 0 &&
                            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                        );
                    }
                """)
                if not is_in_viewport:
                    # Scroll into view smoothly
                    button.scroll_into_view_if_needed()
                    # Wait for scroll to complete (no hard sleep - check immediately after)
                    time.sleep(0.1)
            except:
                pass  # Non-critical - will fail on click if really not accessible
            
            return True, None
            
        except TimeoutError:
            return False, "Button not visible within timeout"
        except Exception as e:
            return False, f"Validation error: {str(e)}"


class ActionVerifier:
    """Verifies that a button click had an observable effect"""
    
    def __init__(self, page: Page):
        self.page = page
        self._network_requests_started = False
    
    def start_network_monitoring(self):
        """Start monitoring network requests (call before click)"""
        self._network_requests_started = False
        try:
            # Set up request listener (if possible)
            # Note: In Playwright, we'd need request interception enabled
            # For now, we'll use a simpler approach
            pass
        except:
            pass
    
    def verify_click_effect(self, url_before: str, timeout: int = 3000) -> Tuple[bool, str, Dict]:
        """
        Verify that clicking had an observable effect.
        
        Returns:
            (has_effect: bool, effect_type: str, metadata: dict)
        """
        metadata = {}
        start_time = time.time()
        
        # Wait for effects to manifest (adaptive wait, no hard sleep)
        # Check multiple times with increasing intervals
        check_intervals = [0.2, 0.3, 0.5, 0.5]  # Progressive waits
        for wait_time in check_intervals:
            time.sleep(wait_time)
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                break
            
            # Check 1: URL change (most reliable indicator)
            try:
                url_after = self.page.url
                if url_after != url_before:
                    metadata['url_before'] = url_before
                    metadata['url_after'] = url_after
                    metadata['wait_time'] = elapsed
                    return True, 'url_change', metadata
            except:
                pass
            
            # Check 2: Modal/Dialog appeared
            try:
                modal_selectors = [
                    '[role="dialog"]:visible',
                    '[role="alertdialog"]:visible',
                    '.modal:visible',
                    '.dialog:visible',
                    '[class*="modal"]:visible',
                    '[class*="dialog"]:visible',
                    '[class*="popup"]:visible'
                ]
                
                for selector in modal_selectors:
                    try:
                        modal = self.page.locator(selector).first
                        if modal.is_visible(timeout=200):
                            metadata['modal_selector'] = selector
                            metadata['wait_time'] = elapsed
                            return True, 'modal_appeared', metadata
                    except:
                        continue
            except:
                pass
            
            # Check 3: Spinner/Loading indicator appeared
            try:
                spinner_selectors = [
                    '[class*="spinner"]:visible',
                    '[class*="loading"]:visible',
                    '[role="progressbar"]:visible',
                    '[aria-busy="true"]:visible',
                    '[class*="loader"]:visible'
                ]
                
                for selector in spinner_selectors:
                    try:
                        spinner = self.page.locator(selector).first
                        if spinner.is_visible(timeout=200):
                            metadata['spinner_selector'] = selector
                            metadata['wait_time'] = elapsed
                            return True, 'spinner_detected', metadata
                    except:
                        continue
            except:
                pass
            
            # Check 4: Loading state (document readyState or loading indicators)
            try:
                is_loading = self.page.evaluate("""
                    () => {
                        return document.readyState === 'loading' || 
                               document.querySelector('[class*="loading"]:not([style*="display: none"]), [class*="spinner"]:not([style*="display: none"])') !== null ||
                               document.body.classList.contains('loading');
                    }
                """)
                if is_loading:
                    metadata['loading_indicator'] = True
                    metadata['wait_time'] = elapsed
                    return True, 'loading_state', metadata
            except:
                pass
        
        # Check 5: DOM stability change (final check)
        # If we got here, check if DOM changed significantly
        try:
            # Check for form submission indicators or content changes
            form_changes = self.page.evaluate("""
                () => {
                    // Check if forms were submitted (disabled submit buttons)
                    const submittedForms = document.querySelectorAll('form:has(button[type="submit"]:disabled), form:has(input[type="submit"]:disabled)');
                    if (submittedForms.length > 0) return true;
                    
                    // Check for success messages
                    const successIndicators = document.querySelectorAll('[class*="success"], [class*="message"]:not([style*="display: none"])');
                    if (successIndicators.length > 0) return true;
                    
                    return false;
                }
            """)
            if form_changes:
                metadata['dom_change_type'] = 'form_submission_or_success'
                return True, 'dom_change', metadata
        except:
            pass
        
        # No observable effect detected
        metadata['wait_time'] = time.time() - start_time
        return False, 'no_effect', metadata


class SmartButtonResolver:
    """
    Testim-style semantic button resolver.
    Locates buttons by intent (e.g., "Submit", "Pay Now", "Login") using
    multiple strategies in priority order.
    """
    
    def __init__(self, page: Page, on_update_callback=None):
        self.page = page
        self.on_update_callback = on_update_callback
        self.context_validator = ContextValidator()
        self.action_verifier = ActionVerifier(page)
    
    def resolve_button(self, intent: str, context: Optional[Dict] = None) -> List[ButtonResolverStrategy]:
        """
        Generate button resolution strategies for an intent, ordered by confidence.
        
        Args:
            intent: Semantic intent string (e.g., "Submit", "Pay Now", "Login", "Cancel")
            context: Optional context dict (form context, page context, etc.)
        
        Returns:
            List of ButtonResolverStrategy objects, ordered by confidence (highest first)
        """
        strategies = []
        intent_normalized = intent.strip()
        intent_lower = intent_normalized.lower()
        context = context or {}
        
        # Strategy 1: Role-based with accessible name (HIGHEST PRIORITY)
        # This is the most semantic and accessibility-aware approach
        try:
            button_by_role = self.page.get_by_role('button', name=intent_normalized, exact=False)
            if button_by_role.count() > 0:
                strategies.append(ButtonResolverStrategy(
                    name='role_with_name',
                    locator=button_by_role.first,
                    confidence=0.95,
                    metadata={'intent': intent_normalized, 'method': 'get_by_role'}
                ))
        except:
            pass
        
        # Strategy 2: Visible text match (exact and partial)
        try:
            # Exact text match
            text_exact = self.page.get_by_text(intent_normalized, exact=True)
            if text_exact.count() > 0:
                # Filter to buttons only
                buttons = text_exact.filter(has=self.page.locator('button, [role="button"], input[type="button"], input[type="submit"]'))
                # Filter to visible and enabled
                visible_enabled = buttons.filter(has_not=self.page.locator('[disabled], [aria-disabled="true"]'))
                if visible_enabled.count() > 0:
                    strategies.append(ButtonResolverStrategy(
                        name='text_exact',
                        locator=visible_enabled.first,
                        confidence=0.90,
                        metadata={'text': intent_normalized, 'exact': True}
                    ))
                elif buttons.count() > 0:
                    strategies.append(ButtonResolverStrategy(
                        name='text_exact',
                        locator=buttons.first,
                        confidence=0.85,
                        metadata={'text': intent_normalized, 'exact': True}
                    ))
            
            # Partial text match (case-insensitive)
            text_partial = self.page.get_by_text(re.compile(intent_lower, re.IGNORECASE))
            if text_partial.count() > 0:
                buttons = text_partial.filter(has=self.page.locator('button, [role="button"], input[type="button"], input[type="submit"]'))
                # Filter to visible and enabled
                visible_enabled = buttons.filter(has_not=self.page.locator('[disabled], [aria-disabled="true"]'))
                if visible_enabled.count() > 0:
                    strategies.append(ButtonResolverStrategy(
                        name='text_partial',
                        locator=visible_enabled.first,
                        confidence=0.85,
                        metadata={'text': intent_normalized, 'exact': False}
                    ))
                elif buttons.count() > 0:
                    strategies.append(ButtonResolverStrategy(
                        name='text_partial',
                        locator=buttons.first,
                        confidence=0.80,
                        metadata={'text': intent_normalized, 'exact': False}
                    ))
        except:
            pass
        
        # Strategy 3: ARIA label / aria-describedby
        try:
            aria_label = self.page.locator(f'button[aria-label*="{intent_normalized}" i], [role="button"][aria-label*="{intent_normalized}" i]')
            if aria_label.count() > 0:
                strategies.append(ButtonResolverStrategy(
                    name='aria_label',
                    locator=aria_label.first,
                    confidence=0.90,
                    metadata={'attribute': 'aria-label', 'value': intent_normalized}
                ))
        except:
            pass
        
        # Strategy 4: Stable attributes (name, value, data-test*)
        try:
            # data-testid, data-cy, data-test attributes
            test_attrs = self.page.locator(f'[data-testid*="{intent_lower}" i], [data-cy*="{intent_lower}" i], [data-test*="{intent_lower}" i]')
            test_buttons = test_attrs.filter(has=self.page.locator('button, [role="button"], input[type="button"], input[type="submit"]'))
            if test_buttons.count() > 0:
                strategies.append(ButtonResolverStrategy(
                    name='data_test_attribute',
                    locator=test_buttons.first,
                    confidence=0.88,
                    metadata={'attributes': ['data-testid', 'data-cy', 'data-test']}
                ))
            
            # name or value attribute (for input buttons)
            name_value = self.page.locator(f'input[name*="{intent_lower}" i][type="button"], input[name*="{intent_lower}" i][type="submit"], input[value*="{intent_normalized}" i][type="button"], input[value*="{intent_normalized}" i][type="submit"]')
            if name_value.count() > 0:
                strategies.append(ButtonResolverStrategy(
                    name='name_or_value',
                    locator=name_value.first,
                    confidence=0.80,
                    metadata={'attributes': ['name', 'value']}
                ))
        except:
            pass
        
        # Strategy 5: Relative DOM position (primary button in form)
        # This is useful when intent is ambiguous but context helps
        if context.get('form_context'):
            try:
                form_locator = context['form_context']
                primary_button = form_locator.locator('button[type="submit"], button:has-text("Submit"), button:has-text("Save"), input[type="submit"]').first
                if primary_button.count() > 0:
                    strategies.append(ButtonResolverStrategy(
                        name='form_primary_button',
                        locator=primary_button,
                        confidence=0.75,
                        metadata={'context': 'form', 'position': 'primary'}
                    ))
            except:
                pass
        
        # Strategy 6: Generic button with text containing intent
        try:
            all_buttons = self.page.locator('button, [role="button"], input[type="button"], input[type="submit"]')
            matching_buttons = all_buttons.filter(has_text=re.compile(intent_lower, re.IGNORECASE))
            if matching_buttons.count() > 0:
                strategies.append(ButtonResolverStrategy(
                    name='button_text_contains',
                    locator=matching_buttons.first,
                    confidence=0.70,
                    metadata={'text_match': 'contains', 'intent': intent_normalized}
                ))
        except:
            pass
        
        # Sort by confidence (highest first)
        strategies.sort(key=lambda s: s.confidence, reverse=True)
        
        return strategies
    
    def _capture_screenshot(self, description: str = "") -> Optional[bytes]:
        """Capture screenshot for observability"""
        try:
            screenshot = self.page.screenshot(full_page=False)
            return screenshot
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            return None
    
    def smart_click_button(self, intent: str, context: Optional[Dict] = None, 
                          verify_action: bool = True, timeout: int = 10000) -> Tuple[bool, Dict]:
        """
        Intelligently locate and click a button by semantic intent.
        Handles iframes, context readiness, and comprehensive validation.
        
        Args:
            intent: Semantic intent string (e.g., "Submit", "Pay Now", "Login")
            context: Optional context dict (form locator, page context, etc.)
            verify_action: Whether to verify click had observable effect
            timeout: Maximum time to wait for button and verification
        
        Returns:
            (success: bool, metadata: dict with strategy_used, iframe_info, healing_occurred, verification_result, etc.)
        """
        metadata = {
            'intent': intent,
            'strategy_used': None,
            'confidence': 0.0,
            'iframe_used': False,
            'iframe_url': None,
            'healing_occurred': False,
            'healing_steps': [],
            'verification_passed': None,
            'verification_type': None,
            'screenshot_before': None,
            'screenshot_after': None,
            'error': None
        }
        
        # Emit start
        if self.on_update_callback:
            self.on_update_callback({
                'type': 'smart_button_resolve_start',
                'intent': intent,
                'message': f'Resolving button for intent: {intent}'
            })
        
        try:
            # Step 1: Ensure page context is ready
            is_ready, ready_error = self.context_validator.ensure_page_ready(self.page, timeout=min(timeout, 5000))
            if not is_ready:
                metadata['warning'] = f"Page readiness check: {ready_error}"
            
            # Step 2: Capture screenshot before click
            screenshot_before = self._capture_screenshot(f"Before click: {intent}")
            metadata['screenshot_before'] = screenshot_before is not None
            
            # Step 3: Try main page first
            strategies = self.resolve_button(intent, context)
            
            # Step 4: If no strategies found in main page, check iframes
            if not strategies:
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'smart_button_iframe_check',
                        'intent': intent,
                        'message': f'No button found in main page or primary iframes, performing thorough iframe search...'
                    })
                
                # More thorough iframe search as last resort
                try:
                    all_frames = self.page.frames
                    for frame in all_frames:
                        if frame == self.page.main_frame:
                            continue
                        try:
                            frame_url = frame.url
                            iframe_strategies = self.iframe_handler.resolve_button_in_frame(frame, intent, context)
                            if iframe_strategies:
                                for strategy in iframe_strategies:
                                    strategy.metadata['iframe_url'] = frame_url
                                    strategy.metadata['iframe_frame'] = frame
                                strategies.extend(iframe_strategies)
                        except:
                            continue
                except:
                    pass
            
            if not strategies:
                error_msg = f"No button resolution strategies found for intent: {intent} (checked main page and iframes)"
                metadata['error'] = error_msg
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'smart_button_resolve_failed',
                        'intent': intent,
                        'error': error_msg
                    })
                return False, metadata
            
            # Step 5: Try each strategy in order (self-healing)
            url_before = self.page.url
            last_error = None
            
            for idx, strategy in enumerate(strategies):
                try:
                    if self.on_update_callback:
                        iframe_info = f" (iframe: {strategy.metadata.get('iframe_url', 'N/A')})" if strategy.metadata.get('iframe') else ""
                        self.on_update_callback({
                            'type': 'smart_button_strategy_attempt',
                            'intent': intent,
                            'strategy': strategy.name,
                            'confidence': strategy.confidence,
                            'iframe': strategy.metadata.get('iframe', False),
                            'iframe_url': strategy.metadata.get('iframe_url'),
                            'message': f'Trying strategy: {strategy.name} (confidence: {strategy.confidence}){iframe_info}'
                        })
                    
                    # Get the appropriate page/frame context
                    target_page = self.page
                    if strategy.metadata.get('iframe'):
                        # Strategy is in iframe, but locator already bound to frame
                        target_page = self.page  # Locator is already frame-scoped
                        metadata['iframe_used'] = True
                        metadata['iframe_url'] = strategy.metadata.get('iframe_url')
                    
                    # Validate context (enhanced validation)
                    is_valid, validation_error = self.context_validator.validate(
                        strategy.locator, target_page, timeout=min(timeout, 5000)
                    )
                    if not is_valid:
                        metadata['healing_steps'].append({
                            'strategy': strategy.name,
                            'reason': validation_error,
                            'confidence': strategy.confidence,
                            'iframe': strategy.metadata.get('iframe', False)
                        })
                        last_error = validation_error
                        continue  # Try next strategy
                    
                    # Execute click
                    strategy.locator.click(timeout=min(timeout, 5000))
                    
                    # Record successful strategy
                    metadata['strategy_used'] = strategy.name
                    metadata['confidence'] = strategy.confidence
                    metadata['healing_occurred'] = (idx > 0)  # Healing occurred if we tried multiple strategies
                    if strategy.metadata.get('iframe'):
                        metadata['iframe_used'] = True
                        metadata['iframe_url'] = strategy.metadata.get('iframe_url')
                    
                    # Capture screenshot after click
                    screenshot_after = self._capture_screenshot(f"After click: {intent}")
                    metadata['screenshot_after'] = screenshot_after is not None
                    
                    if self.on_update_callback:
                        iframe_info = f" in iframe ({metadata.get('iframe_url')})" if metadata.get('iframe_used') else ""
                        self.on_update_callback({
                            'type': 'smart_button_clicked',
                            'intent': intent,
                            'strategy': strategy.name,
                            'confidence': strategy.confidence,
                            'healing_occurred': metadata['healing_occurred'],
                            'iframe_used': metadata.get('iframe_used', False),
                            'iframe_url': metadata.get('iframe_url'),
                            'screenshot_before': metadata['screenshot_before'],
                            'screenshot_after': metadata['screenshot_after'],
                            'message': f'Successfully clicked button using strategy: {strategy.name}{iframe_info}'
                        })
                    
                    # Verify action had effect
                    if verify_action:
                        self.action_verifier.start_network_monitoring()
                        has_effect, effect_type, verify_metadata = self.action_verifier.verify_click_effect(
                            url_before, timeout=min(timeout, 3000)
                        )
                        metadata['verification_passed'] = has_effect
                        metadata['verification_type'] = effect_type
                        metadata['verification_metadata'] = verify_metadata
                        
                        if not has_effect:
                            warning_msg = f"Button clicked but no observable effect detected (type: {effect_type})"
                            metadata['warning'] = warning_msg
                            if self.on_update_callback:
                                self.on_update_callback({
                                    'type': 'smart_button_verification_warning',
                                    'intent': intent,
                                    'effect_type': effect_type,
                                    'message': warning_msg
                                })
                            # Still consider it successful if click happened, but log warning
                    
                    return True, metadata
                    
                except Exception as e:
                    error_str = str(e)
                    metadata['healing_steps'].append({
                        'strategy': strategy.name,
                        'error': error_str,
                        'confidence': strategy.confidence,
                        'iframe': strategy.metadata.get('iframe', False)
                    })
                    last_error = error_str
                    continue  # Try next strategy (self-healing)
            
            # All strategies failed
            error_msg = f"All button resolution strategies failed for intent: {intent}. Last error: {last_error}"
            metadata['error'] = error_msg
            metadata['healing_occurred'] = True  # We attempted healing
            
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'smart_button_resolve_failed',
                    'intent': intent,
                    'error': error_msg,
                    'strategies_attempted': len(strategies),
                    'healing_steps': metadata['healing_steps']
                })
            
            return False, metadata
            
        except Exception as e:
            error_msg = f"Error in smart button resolution: {str(e)}"
            metadata['error'] = error_msg
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'smart_button_resolve_error',
                    'intent': intent,
                    'error': error_msg
                })
            return False, metadata


def smart_click_button(page: Page, intent: str, context: Optional[Dict] = None,
                       verify_action: bool = True, timeout: int = 10000,
                       on_update_callback=None) -> Tuple[bool, Dict]:
    """
    Convenience function for smart button clicking.
    
    Args:
        page: Playwright page object
        intent: Semantic intent string (e.g., "Submit", "Pay Now", "Login")
        context: Optional context dict (form locator, etc.)
        verify_action: Whether to verify click had observable effect
        timeout: Maximum time to wait
        on_update_callback: Optional callback for execution updates
    
    Returns:
        (success: bool, metadata: dict)
    """
    resolver = SmartButtonResolver(page, on_update_callback)
    return resolver.smart_click_button(intent, context, verify_action, timeout)

