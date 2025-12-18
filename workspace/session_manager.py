"""
WorkspaceSessionManager: Central coordinator for workspace sessions.
Manages browser sessions, task planning, and task execution per user session.
"""
import uuid
import threading
from workspace.browser_session import BrowserSessionManager
from workspace.task_planner import TaskPlanner
from workspace.task_executor import TaskExecutor


class WorkspaceSessionManager:
    """Manages workspace sessions for multiple users"""
    
    def __init__(self):
        self.sessions = {}  # session_id -> session_data
        self.lock = threading.Lock()
    
    def create_session(self, url, socketio, socket_id):
        """Create a new workspace session"""
        session_id = str(uuid.uuid4())
        
        # Callbacks for WebSocket emission
        def on_browser_update(update_data):
            socketio.emit('browser_update', update_data, room=session_id)
            socketio.emit('browser_update', update_data, room=socket_id)
        
        def on_task_update(update_data):
            socketio.emit('task_update', update_data, room=session_id)
            socketio.emit('task_update', update_data, room=socket_id)
        
        # Create browser session
        browser_session = BrowserSessionManager(session_id, on_browser_update)
        
        # Create task executor
        task_executor = TaskExecutor(browser_session, on_task_update)
        
        # Create task planner
        task_planner = TaskPlanner()
        
        # Start browser (it will create its own thread internally)
        browser_session.start(url)
        
        # Store session data
        with self.lock:
            self.sessions[session_id] = {
                'browser_session': browser_session,
                'task_executor': task_executor,
                'task_planner': task_planner,
                'url': url,
                'created_at': threading.current_thread().name
            }
        
        return session_id
    
    def get_session(self, session_id):
        """Get session data"""
        with self.lock:
            return self.sessions.get(session_id)
    
    def plan_tasks(self, session_id, instruction, auto_start=False):
        """Plan tasks for a session"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        browser_session = session['browser_session']
        task_planner = session['task_planner']
        
        current_url = browser_session.current_url if browser_session.current_url else None
        tasks = task_planner.plan_tasks(instruction, current_url)
        
        # Set tasks in executor
        task_executor = session['task_executor']
        task_executor.set_tasks(tasks)
        
        # Auto-start execution if requested
        if auto_start and tasks:
            task_executor.start_execution()
        
        return tasks
    
    def start_execution(self, session_id):
        """Start task execution for a session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        task_executor = session['task_executor']
        return task_executor.start_execution()
    
    def pause_execution(self, session_id):
        """Pause task execution"""
        session = self.get_session(session_id)
        if session:
            session['task_executor'].pause_execution()
    
    def resume_execution(self, session_id):
        """Resume task execution"""
        session = self.get_session(session_id)
        if session:
            session['task_executor'].resume_execution()
    
    def stop_execution(self, session_id):
        """Stop task execution"""
        session = self.get_session(session_id)
        if session:
            session['task_executor'].stop_execution()
    
    def stop_session(self, session_id):
        """Stop and cleanup a session"""
        session = self.get_session(session_id)
        if session:
            # Stop execution if running
            session['task_executor'].stop_execution()
            # Stop browser
            session['browser_session'].stop()
            # Remove from sessions
            with self.lock:
                del self.sessions[session_id]


# Global workspace manager instance
workspace_manager = WorkspaceSessionManager()

