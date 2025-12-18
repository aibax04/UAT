"""
BrowserSessionManager: Manages a single Playwright headless browser session.
Handles navigation, action execution, and screenshot streaming.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import threading


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
        
    def start(self, url):
        """Start the browser session and navigate to URL"""
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
            
            # Navigate to URL
            self._navigate_to_url(url)
            self.current_url = url
            
            # Capture initial screenshot
            self.capture_and_stream("Initial page load", "setup")
            
            return True
        except Exception as e:
            print(f"Error starting browser session: {e}")
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'error',
                    'session_id': self.session_id,
                    'message': str(e),
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
        """Stream current URL for live website preview"""
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
                'timestamp': time.time()
            }
            
            # Emit via callback
            if self.on_update_callback:
                self.on_update_callback(update_data)
                print(f"URL update sent: {current_url}")
                
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
        """Execute a browser action"""
        if not self.page or not self.is_running:
            return False
        
        try:
            self.current_action = f"{action_type}: {kwargs.get('description', '')}"
            
            # Emit action start
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_start',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'timestamp': time.time()
                })
            
            # Execute action based on type
            if action_type == 'click':
                selector = kwargs.get('selector')
                if selector:
                    self.page.click(selector, timeout=10000)
                    time.sleep(0.5)
                    
            elif action_type == 'fill':
                selector = kwargs.get('selector')
                text = kwargs.get('text', '')
                if selector:
                    self.page.fill(selector, text, timeout=10000)
                    time.sleep(0.3)
                    
            elif action_type == 'navigate':
                url = kwargs.get('url')
                if url:
                    self._navigate_to_url(url)
                    self.current_url = url
                    
            elif action_type == 'wait':
                duration = kwargs.get('duration', 1)
                time.sleep(duration)
                
            elif action_type == 'scroll':
                direction = kwargs.get('direction', 'down')
                if direction == 'down':
                    self.page.evaluate("window.scrollBy(0, 500)")
                elif direction == 'up':
                    self.page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.5)
            
            # Capture screenshot after action
            self.capture_and_stream(self.current_action, kwargs.get('task_name'))
            
            # Emit action complete
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'action_complete',
                    'session_id': self.session_id,
                    'action': self.current_action,
                    'timestamp': time.time()
                })
            
            return True
            
        except Exception as e:
            print(f"Error executing action {action_type}: {e}")
            if self.on_update_callback:
                self.on_update_callback({
                    'type': 'error',
                    'session_id': self.session_id,
                    'message': f'Action error: {str(e)}',
                    'action': self.current_action,
                    'timestamp': time.time()
                })
            return False
    
    def stop(self):
        """Stop the browser session"""
        self.is_running = False
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

