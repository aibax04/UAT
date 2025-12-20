"""
BrowserSessionManager: Manages a single Playwright headless browser session.
Handles navigation, action execution, and screenshot streaming.
Enhanced with Testim-like smart locators and self-healing execution.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import threading
from typing import Dict, Optional, Callable, Any
from queue import Queue, Empty
from workspace.smart_locator import SmartLocatorEngine
from workspace.self_healing_executor import SelfHealingExecutor
from workspace.element_fingerprint import ElementFingerprint

# Optional enterprise capabilities - only imported if available
try:
    from capabilities.capability_router import CapabilityRouter
    CAPABILITIES_AVAILABLE = True
except ImportError:
    CAPABILITIES_AVAILABLE = False
    CapabilityRouter = None


class BrowserSessionManager:
    """Manages a Playwright browser session with live visual streaming"""
    
    def __init__(self, session_id, on_update_callback):
        self.session_id = session_id
        self.on_update_callback = on_update_callback
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_running = False
        self.current_url = None
        self.current_action = None
        self.smart_locator = None  # Will be initialized after page is created
        self.self_healing_executor = None  # Will be initialized after page is created
        self.execution_metadata = []  # Track execution metadata for observability
        self.action_queue = Queue()  # Thread-safe queue for actions
        self.result_queue = Queue()  # Thread-safe queue for results
        self.browser_thread = None  # Thread where browser runs
        self._stop_event = threading.Event()  # Event to stop browser thread
        self.capability_router = None  # Optional enterprise capability router
        
    def start(self, url):
        """Start the browser session and navigate to URL in a dedicated thread"""
        # Start browser in its own thread to avoid thread switching issues
        def browser_thread_func():
            try:
                self.playwright = sync_playwright().start()
                # Launch headless browser
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                # Create context with realistic viewport
                self.context = self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                self.page = self.context.new_page()
                self.is_running = True
                
                # Initialize smart locator and self-healing executor
                self.smart_locator = SmartLocatorEngine(self.page)
                self.self_healing_executor = SelfHealingExecutor(
                    self.page,
                    self.smart_locator,
                    on_update_callback=self._on_healing_update
                )
                
                # Initialize capability router if available (optional enterprise features)
                if CAPABILITIES_AVAILABLE and CapabilityRouter:
                    self.capability_router = CapabilityRouter(
                        self.page,
                        on_update_callback=self._on_capability_update
                    )
                
                # Navigate to URL
                self._navigate_to_url(url)
                self.current_url = url
                
                # Capture initial screenshot
                self.capture_and_stream("Initial page load", "setup")
                
                # Process action queue
                while not self._stop_event.is_set():
                    try:
                        # Get action from queue with timeout
                        action = self.action_queue.get(timeout=0.5)
                        if action is None:  # Poison pill to stop
                            break
                        
                        # Check if capability router should handle this action (enterprise features)
                        # This is ADDITIVE - only intercepts if a module can handle it
                        task_data = {
                            'action_type': action['action_type'],
                            **action['kwargs']
                        }
                        
                        capability_handled = False
                        if self.capability_router and self.capability_router.should_handle_task(task_data):
                            try:
                                capability_result = self.capability_router.route_task(task_data)
                                if capability_result is not None:
                                    # Capability module handled this task
                                    capability_handled = True
                                    result = capability_result.get('success', False)
                            except Exception as e:
                                print(f"Capability router error, falling back to standard execution: {e}")
                                # Fall through to standard execution on error
                        
                        # If capability didn't handle it, use standard execution (existing logic unchanged)
                        if not capability_handled:
                            result = self._execute_action_internal(
                                action['action_type'],
                                **action['kwargs']
                            )
                        
                        # Put result in result queue
                        self.result_queue.put({
                            'action_id': action.get('action_id'),
                            'result': result,
                            'success': result is not False
                        })
                        
                    except Empty:
                        continue
                    except Exception as e:
                        print(f"Error in browser thread: {e}")
                        self.result_queue.put({
                            'action_id': action.get('action_id') if 'action' in locals() else None,
                            'result': False,
                            'success': False,
                            'error': str(e)
                        })
                
            except Exception as e:
                print(f"Error starting browser session: {e}")
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'error',
                        'session_id': self.session_id,
                        'message': str(e),
                        'timestamp': time.time()
                    })
                self.is_running = False
        
        # Start browser thread
        self.browser_thread = threading.Thread(target=browser_thread_func, daemon=True)
        self.browser_thread.start()
        
        # Wait a bit for browser to initialize
        time.sleep(1)
        
        return True
    
    def _execute_action_internal(self, action_type, **kwargs):
        """Internal method to execute action - must be called from browser thread"""
        if not self.page or not self.is_running:
            return False
        
        try:
            description = kwargs.get('description', '')
            task_name = kwargs.get('task_name', '')
            self.current_action = f"{action_type}: {description}"
            
            # Emit action start with detailed description
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_start',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'action_type': action_type,
                    'description': description,
                    'task_name': task_name,
                    'timestamp': time.time()
                })
            
            # Execute action based on type with smart locators and self-healing
            if action_type == 'click':
                # Build element info for smart locator
                selector = kwargs.get('selector', '')
                element_info = {
                    'selector': selector,
                    'text': kwargs.get('text') or description,
                    'description': description,
                    'attributes': kwargs.get('attributes', {})
                }
                
                # Extract attributes from selector if it's an attribute selector
                if selector.startswith('[') and selector.endswith(']'):
                    # Parse attribute selector
                    attr_part = selector[1:-1]
                    if '=' in attr_part:
                        attr_name, attr_value = attr_part.split('=', 1)
                        attr_value = attr_value.strip('"\'')
                        element_info['attributes'][attr_name.strip()] = attr_value
                
                # Execute with self-healing
                success, metadata = self.self_healing_executor.execute_click(
                    element_info,
                    timeout=10000
                )
                
                if not success:
                    # All strategies failed - create detailed error
                    error_msg = self._create_failure_explanation(metadata, 'click')
                    raise Exception(error_msg)
                
                # Store execution metadata
                self.execution_metadata.append({
                    'action': 'click',
                    'description': description,
                    'metadata': metadata,
                    'timestamp': time.time()
                })
                
                # Emit execution metadata for UI
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'execution_metadata',
                        'action': 'click',
                        'metadata': metadata,
                        'description': description
                    })
                    
                    # Emit button clicked event for visual feedback
                    self.on_update_callback({
                        'type': 'button_clicked',
                        'session_id': self.session_id,
                        'description': description,
                        'task_name': task_name,
                        'locator_used': metadata.get('locator_used'),
                        'locator_strategy': metadata.get('locator_strategy'),
                        'confidence': metadata.get('confidence'),
                        'healing_used': metadata.get('healing_successful', False),
                        'timestamp': time.time()
                    })
                
                # Stream URL update after click (page may have navigated)
                time.sleep(0.8)  # Allow navigation to start
                # Store URL after action for travel path tracking
                url_after = self.page.url if self.page else None
                if url_after and url_after != self.current_url:
                    metadata['url_after_action'] = url_after
                self.capture_and_stream(f"Clicked: {description}", task_name)
                time.sleep(0.5)
                
            elif action_type == 'fill':
                selector = kwargs.get('selector', '')
                text = kwargs.get('text', '')
                
                # Build element info for smart locator
                element_info = {
                    'selector': selector,
                    'text': kwargs.get('label_text') or description,
                    'description': description,
                    'attributes': kwargs.get('attributes', {})
                }
                
                # Extract attributes from selector
                if selector.startswith('[') and selector.endswith(']'):
                    attr_part = selector[1:-1]
                    if '=' in attr_part:
                        attr_name, attr_value = attr_part.split('=', 1)
                        attr_value = attr_value.strip('"\'')
                        element_info['attributes'][attr_name.strip()] = attr_value
                
                # Execute with self-healing
                success, metadata = self.self_healing_executor.execute_fill(
                    element_info,
                    text,
                    timeout=10000
                )
                
                if not success:
                    error_msg = self._create_failure_explanation(metadata, 'fill')
                    raise Exception(error_msg)
                
                # Store execution metadata
                self.execution_metadata.append({
                    'action': 'fill',
                    'description': description,
                    'metadata': metadata,
                    'timestamp': time.time()
                })
                
                # Emit execution metadata
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'execution_metadata',
                        'action': 'fill',
                        'metadata': metadata,
                        'description': description
                    })
                
                # Stream update immediately after fill (form might trigger changes)
                time.sleep(0.2)
                self.capture_and_stream(f"Filled: {description}", task_name)
                
                # Check for any page changes after fill (some forms trigger navigation)
                time.sleep(0.3)
                current_url = self.page.url
                if current_url != self.current_url:
                    self.capture_and_stream(f"Page changed after fill: {description}", task_name)
                    self.current_url = current_url
                
            elif action_type == 'navigate':
                url = kwargs.get('url')
                if url:
                    self.capture_and_stream(f"Navigating to: {url}", task_name)
                    self._navigate_to_url(url)
                    self.current_url = url
                    # Stream URL after navigation
                    self.capture_and_stream(f"Navigated to: {url}", task_name)
                    
            elif action_type == 'wait':
                duration = kwargs.get('duration', 1)
                self.capture_and_stream(f"Waiting: {description}", task_name)
                time.sleep(duration)
                self.capture_and_stream(f"Wait complete: {description}", task_name)
                
            elif action_type == 'scroll':
                direction = kwargs.get('direction', 'down')
                if direction == 'down':
                    self.page.evaluate("window.scrollBy(0, 500)")
                    self.capture_and_stream(f"Scrolled down: {description}", task_name)
                elif direction == 'up':
                    self.page.evaluate("window.scrollTo(0, 0)")
                    self.capture_and_stream(f"Scrolled to top: {description}", task_name)
                time.sleep(0.5)
            
            # Emit action complete
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_complete',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'action_type': action_type,
                    'description': description,
                    'task_name': task_name,
                    'timestamp': time.time()
                })
            
            return True
            
        except Exception as e:
            print(f"Error executing action {action_type}: {e}")
            import traceback
            traceback.print_exc()
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'error',
                    'session_id': self.session_id,
                    'message': f'Action error: {str(e)}',
                    'action': self.current_action,
                    'action_type': action_type,
                    'timestamp': time.time()
                })
            return False
    
    def _navigate_to_url(self, url, timeout=30000):
        """Navigate to URL with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.page.goto(url, wait_until='networkidle', timeout=timeout)
                # Wait for page to be fully interactive
                self.page.wait_for_load_state('domcontentloaded')
                time.sleep(1)  # Allow page to render
                return True
            except PlaywrightTimeoutError:
                if attempt < max_retries - 1:
                    print(f"Navigation timeout, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    raise
            except Exception as e:
                print(f"Navigation error: {e}")
                raise
    
    def capture_and_stream(self, action_description=None, task_name=None):
        """Stream current URL for live website preview - updates iframe in real-time"""
        if not self.page or not self.is_running:
            return
        
        try:
            # Get current URL
            current_url = self.page.url
            self.current_url = current_url
            
            # Prepare update data - send URL for iframe embedding
            update_data = {
                'type': 'url_loaded',
                'session_id': self.session_id,
                'url': current_url,
                'action': action_description or self.current_action,
                'task_name': task_name,
                'timestamp': time.time(),
                'force_reload': True  # Always force reload to show latest state
            }
            
            # Emit via callback
            if self.on_update_callback:
                self.on_update_callback(update_data)
                print(f"URL update sent: {current_url} - {action_description}")
                
        except Exception as e:
            print(f"Error getting URL: {e}")
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'error',
                    'session_id': self.session_id,
                    'message': f'URL error: {str(e)}',
                    'timestamp': time.time()
                })
    
    def execute_action(self, action_type, **kwargs):
        """Execute a browser action with real-time updates (thread-safe)"""
        if not self.is_running or not self.browser_thread or not self.browser_thread.is_alive():
            return False
        
        # Generate unique action ID
        action_id = f"{action_type}_{time.time()}_{threading.current_thread().ident}"
        
        # Queue action for execution in browser thread
        self.action_queue.put({
            'action_id': action_id,
            'action_type': action_type,
            'kwargs': kwargs
        })
        
        # Wait for result (with timeout)
        try:
            timeout = 30  # 30 second timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    result = self.result_queue.get(timeout=0.5)
                    if result.get('action_id') == action_id:
                        return result.get('success', False)
                except Empty:
                    continue
            
            # Timeout
            print(f"Action {action_id} timed out")
            return False
            
        except Exception as e:
            print(f"Error waiting for action result: {e}")
            return False
        
        try:
            description = kwargs.get('description', '')
            task_name = kwargs.get('task_name', '')
            self.current_action = f"{action_type}: {description}"
            
            # Emit action start with detailed description
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_start',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'action_type': action_type,
                    'description': description,
                    'task_name': task_name,
                    'timestamp': time.time()
                })
            
            # Execute action based on type with smart locators and self-healing
            if action_type == 'click':
                # Build element info for smart locator
                selector = kwargs.get('selector', '')
                element_info = {
                    'selector': selector,
                    'text': kwargs.get('text') or description,
                    'description': description,
                    'attributes': kwargs.get('attributes', {})
                }
                
                # Extract attributes from selector if it's an attribute selector
                if selector.startswith('[') and selector.endswith(']'):
                    # Parse attribute selector
                    attr_part = selector[1:-1]
                    if '=' in attr_part:
                        attr_name, attr_value = attr_part.split('=', 1)
                        attr_value = attr_value.strip('"\'')
                        element_info['attributes'][attr_name.strip()] = attr_value
                
                # Execute with self-healing
                success, metadata = self.self_healing_executor.execute_click(
                    element_info,
                    timeout=10000
                )
                
                if not success:
                    # All strategies failed - create detailed error
                    error_msg = self._create_failure_explanation(metadata, 'click')
                    raise Exception(error_msg)
                
                # Store execution metadata
                self.execution_metadata.append({
                    'action': 'click',
                    'description': description,
                    'metadata': metadata,
                    'timestamp': time.time()
                })
                
                # Emit execution metadata for UI
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'execution_metadata',
                        'action': 'click',
                        'metadata': metadata,
                        'description': description
                    })
                    
                    # Emit button clicked event for visual feedback
                    self.on_update_callback({
                        'type': 'button_clicked',
                        'session_id': self.session_id,
                        'description': description,
                        'task_name': task_name,
                        'locator_used': metadata.get('locator_used'),
                        'locator_strategy': metadata.get('locator_strategy'),
                        'confidence': metadata.get('confidence'),
                        'healing_used': metadata.get('healing_successful', False),
                        'timestamp': time.time()
                    })
                
                # Stream URL update after click (page may have navigated)
                time.sleep(0.8)  # Allow navigation to start
                # Store URL after action for travel path tracking
                url_after = self.page.url if self.page else None
                if url_after and url_after != self.current_url:
                    metadata['url_after_action'] = url_after
                self.capture_and_stream(f"Clicked: {description}", task_name)
                time.sleep(0.5)
                    
            elif action_type == 'fill':
                selector = kwargs.get('selector', '')
                text = kwargs.get('text', '')
                
                # Build element info for smart locator
                element_info = {
                    'selector': selector,
                    'text': kwargs.get('label_text') or description,
                    'description': description,
                    'attributes': kwargs.get('attributes', {})
                }
                
                # Extract attributes from selector
                if selector.startswith('[') and selector.endswith(']'):
                    attr_part = selector[1:-1]
                    if '=' in attr_part:
                        attr_name, attr_value = attr_part.split('=', 1)
                        attr_value = attr_value.strip('"\'')
                        element_info['attributes'][attr_name.strip()] = attr_value
                
                # Execute with self-healing
                success, metadata = self.self_healing_executor.execute_fill(
                    element_info,
                    text,
                    timeout=10000
                )
                
                if not success:
                    error_msg = self._create_failure_explanation(metadata, 'fill')
                    raise Exception(error_msg)
                
                # Store execution metadata
                self.execution_metadata.append({
                    'action': 'fill',
                    'description': description,
                    'metadata': metadata,
                    'timestamp': time.time()
                })
                
                # Emit execution metadata
                if self.on_update_callback:
                    self.on_update_callback({
                        'type': 'execution_metadata',
                        'action': 'fill',
                        'metadata': metadata,
                        'description': description
                    })
                
                # Stream update after fill
                time.sleep(0.3)
                self.capture_and_stream(f"Filled: {description}", task_name)
                    
            elif action_type == 'navigate':
                url = kwargs.get('url')
                if url:
                    self.capture_and_stream(f"Navigating to: {url}", task_name)
                    self._navigate_to_url(url)
                    self.current_url = url
                    # Stream URL after navigation
                    self.capture_and_stream(f"Navigated to: {url}", task_name)
                    
            elif action_type == 'wait':
                duration = kwargs.get('duration', 1)
                self.capture_and_stream(f"Waiting: {description}", task_name)
                time.sleep(duration)
                self.capture_and_stream(f"Wait complete: {description}", task_name)
                
            elif action_type == 'scroll':
                direction = kwargs.get('direction', 'down')
                if direction == 'down':
                    self.page.evaluate("window.scrollBy(0, 500)")
                    self.capture_and_stream(f"Scrolled down: {description}", task_name)
                elif direction == 'up':
                    self.page.evaluate("window.scrollTo(0, 0)")
                    self.capture_and_stream(f"Scrolled to top: {description}", task_name)
                time.sleep(0.5)
            
            # Emit action complete
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_complete',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'action_type': action_type,
                    'description': description,
                    'task_name': task_name,
                    'timestamp': time.time()
                })
            
            return True
            
        except Exception as e:
            print(f"Error executing action {action_type}: {e}")
            import traceback
            traceback.print_exc()
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'error',
                    'session_id': self.session_id,
                    'message': f'Action error: {str(e)}',
                    'action': self.current_action,
                    'action_type': action_type,
                    'timestamp': time.time()
                })
            return False
    
    def _on_healing_update(self, update_data):
        """Callback for healing updates"""
        if self.on_update_callback:
            self.on_update_callback({
                'type': 'healing_update',
                'session_id': self.session_id,
                **update_data,
                'timestamp': time.time()
            })
    
    def _on_capability_update(self, update):
        """Callback for capability module updates"""
        if self.on_update_callback:
            # Transform capability update to match existing update format
            update['session_id'] = self.session_id
            self.on_update_callback(update)
    
    def _create_failure_explanation(self, metadata: Dict, action_type: str) -> str:
        """Create detailed failure explanation for debugging"""
        explanation = f"Failed to {action_type} element.\n"
        explanation += f"Attempted {len(metadata.get('healing_steps', []))} locator strategies.\n"
        
        if metadata.get('healing_attempted'):
            explanation += "Self-healing was attempted but failed.\n"
            if metadata.get('healing_steps'):
                last_step = metadata['healing_steps'][-1]
                explanation += f"Final healing attempt: {last_step.get('reason', 'Unknown')}\n"
        
        explanation += "\nLocator strategies tried:\n"
        for i, step in enumerate(metadata.get('healing_steps', [])[:5], 1):
            strategy = step.get('strategy', 'unknown')
            locator = step.get('locator', 'N/A')
            error = step.get('error', 'N/A')
            explanation += f"  {i}. {strategy}: {locator[:50]}... (Error: {error[:50]})\n"
        
        return explanation
    
    def stop(self):
        """Stop the browser session"""
        self.is_running = False
        self._stop_event.set()
        
        # Send poison pill to stop browser thread
        try:
            self.action_queue.put(None)
        except:
            pass
        
        # Wait for browser thread to finish
        if self.browser_thread and self.browser_thread.is_alive():
            self.browser_thread.join(timeout=5)
        
        # Cleanup will happen in browser thread, but try here too
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"Error stopping browser: {e}")

