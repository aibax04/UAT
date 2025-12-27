"""
WorkspaceSessionManager: Central coordinator for workspace sessions.
Manages browser sessions, task planning, and task execution per user session.
"""
import uuid
import threading
import time
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
                'created_at': threading.current_thread().name,
                'execution_metrics': {
                    'start_time': None,
                    'end_time': None,
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'failed_tasks': 0,
                    'total_duration': 0,
                    'average_task_time': 0,
                    'tasks': []
                }
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
        
        # Enhanced: Scan page for forms first
        form_schema = None
        try:
            # Lazy import to avoid circular dependency issues if any
            from capabilities.form_intelligence import FormIntelligenceModule
            if browser_session.page:
                form_module = FormIntelligenceModule(browser_session.page)
                scan_result = form_module._detect_forms()
                if scan_result and scan_result.get('forms'):
                    form_schema = scan_result
                    print(f"Task Planning: Detected {len(form_schema['forms'])} forms with {form_schema['total_fields']} fields")
        except Exception as e:
            print(f"Warning: Form detection failed during planning: {e}")

        # Plan tasks with form context
        tasks = task_planner.plan_tasks(instruction, current_url, form_schema)
        
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
        
        # Initialize execution metrics
        session['execution_metrics']['start_time'] = time.time()
        session['execution_metrics']['total_tasks'] = len(session['task_executor'].task_queue.get_all_tasks())
        
        task_executor = session['task_executor']
        return task_executor.start_execution()
    
    def get_execution_report(self, session_id):
        """Get execution report with metrics"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Start with session metrics
        metrics = session.get('execution_metrics', {}).copy()
        task_executor = session['task_executor']
        
        # Get latest metrics from executor if available (executor has more up-to-date data)
        if hasattr(task_executor, 'execution_metrics') and task_executor.execution_metrics:
            # Merge executor metrics (they take precedence)
            executor_metrics = task_executor.execution_metrics
            metrics.update({
                'start_time': executor_metrics.get('start_time') or metrics.get('start_time'),
                'end_time': executor_metrics.get('end_time') or metrics.get('end_time'),
                'total_duration': executor_metrics.get('total_duration') or metrics.get('total_duration'),
                'total_tasks': executor_metrics.get('total_tasks') or metrics.get('total_tasks'),
                'completed_tasks': executor_metrics.get('completed_tasks') or metrics.get('completed_tasks'),
                'failed_tasks': executor_metrics.get('failed_tasks') or metrics.get('failed_tasks'),
                'average_task_time': executor_metrics.get('average_task_time') or metrics.get('average_task_time'),
                'tasks': executor_metrics.get('tasks') or metrics.get('tasks', [])
            })
        
        # Ensure we have task list from executor if metrics don't have it
        if not metrics.get('tasks') or len(metrics.get('tasks', [])) == 0:
            # Try to get tasks from queue
            try:
                all_tasks = task_executor.task_queue.get_all_tasks()
                if all_tasks:
                    metrics['tasks'] = all_tasks
                    if not metrics.get('total_tasks'):
                        metrics['total_tasks'] = len(all_tasks)
                    if not metrics.get('completed_tasks'):
                        metrics['completed_tasks'] = sum(1 for t in all_tasks if t.get('status') == 'done')
                    if not metrics.get('failed_tasks'):
                        metrics['failed_tasks'] = sum(1 for t in all_tasks if t.get('status') == 'failed')
            except Exception as e:
                print(f"Error getting tasks from queue: {e}")
                # Fallback to empty list
                if not metrics.get('tasks'):
                    metrics['tasks'] = []
        
        # Calculate score out of 10
        score = self._calculate_score(metrics)
        
        # Get travel path from browser session (URLs visited)
        travel_path = []
        browser_session = session.get('browser_session')
        if browser_session and hasattr(browser_session, 'current_url') and browser_session.current_url:
            # Add initial URL
            travel_path.append(session['url'])
            # Add current URL if different
            if browser_session.current_url != session['url']:
                travel_path.append(browser_session.current_url)
        
        # Also extract URLs from tasks that navigated
        if metrics.get('tasks'):
            for task in metrics['tasks']:
                if task.get('action_type') == 'navigate' and task.get('url'):
                    if task['url'] not in travel_path:
                        travel_path.append(task['url'])
                # Track URL changes from task metadata
                if task.get('metadata') and task.get('metadata', {}).get('url_after_action'):
                    url_after = task['metadata']['url_after_action']
                    if url_after not in travel_path:
                        travel_path.append(url_after)
        
        return {
            'session_id': session_id,
            'url': session['url'],
            'metrics': metrics,
            'travel_path': travel_path,
            'score': score,
            'timestamp': time.time()
        }
    
    def _calculate_score(self, metrics):
        """Calculate execution score out of 10"""
        total_tasks = metrics.get('total_tasks', 0)
        if total_tasks == 0:
            return 0.0
        
        completed = metrics.get('completed_tasks', 0)
        failed = metrics.get('failed_tasks', 0)
        
        # Base score: completion rate (0-7 points)
        completion_rate = completed / total_tasks if total_tasks > 0 else 0
        base_score = completion_rate * 7
        
        # Speed bonus: average task time (0-2 points)
        avg_time = metrics.get('average_task_time', 0)
        # Faster tasks get more points (assuming < 5 seconds per task is good)
        speed_score = max(0, 2 - (avg_time / 5) * 2) if avg_time > 0 else 0
        
        # Reliability bonus: no failures (0-1 point)
        reliability_score = 1.0 if failed == 0 else max(0, 1 - (failed / total_tasks))
        
        total_score = base_score + speed_score + reliability_score
        return min(10.0, round(total_score, 1))
    
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
    
    def provide_input(self, session_id, value):
        """Provide user input for a waiting session"""
        session = self.get_session(session_id)
        if session:
            return session['task_executor'].provide_input(value)
        return False

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

