"""
TaskExecutor: Executes tasks sequentially on the browser session.
Manages task status and coordinates with BrowserSessionManager.
"""
import time
import threading


class TaskExecutor:
    """Executes tasks sequentially on a browser session"""
    
    def __init__(self, browser_session, on_task_update_callback):
        self.browser_session = browser_session
        self.on_task_update_callback = on_task_update_callback
        self.tasks = []
        self.current_task_index = 0
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.execution_thread = None
    
    def set_tasks(self, tasks):
        """Set the task list to execute"""
        self.tasks = tasks
        self.current_task_index = 0
        # Initialize all tasks as pending
        for task in self.tasks:
            if 'status' not in task:
                task['status'] = 'pending'
    
    def start_execution(self):
        """Start executing tasks in a separate thread"""
        if self.is_running:
            return False
        
        if not self.tasks:
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'error',
                    'message': 'No tasks to execute'
                })
            return False
        
        self.is_running = True
        self.is_paused = False
        self.should_stop = False
        self.current_task_index = 0
        
        # Start execution in background thread
        self.execution_thread = threading.Thread(target=self._execute_tasks, daemon=True)
        self.execution_thread.start()
        
        return True
    
    def pause_execution(self):
        """Pause task execution"""
        self.is_paused = True
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'execution_paused',
                'message': 'Execution paused'
            })
    
    def resume_execution(self):
        """Resume task execution"""
        self.is_paused = False
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'execution_resumed',
                'message': 'Execution resumed'
            })
    
    def stop_execution(self):
        """Stop task execution"""
        self.should_stop = True
        self.is_paused = False
        self.is_running = False
        
        # Mark current task as failed if stopped mid-execution
        if 0 <= self.current_task_index < len(self.tasks):
            task = self.tasks[self.current_task_index]
            if task['status'] == 'running':
                task['status'] = 'failed'
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': task
                    })
        
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'execution_stopped',
                'message': 'Execution stopped'
            })
    
    def _execute_tasks(self):
        """Execute tasks sequentially"""
        try:
            for i, task in enumerate(self.tasks):
                # Check if should stop
                if self.should_stop:
                    break
                
                # Wait if paused
                while self.is_paused and not self.should_stop:
                    time.sleep(0.5)
                
                if self.should_stop:
                    break
                
                self.current_task_index = i
                
                # Update task status to running
                task['status'] = 'running'
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': task
                    })
                
                # Execute task action
                action_type = task.get('action_type', 'wait')
                success = self.browser_session.execute_action(
                    action_type,
                    selector=task.get('selector'),
                    text=task.get('text'),
                    url=task.get('url'),
                    duration=task.get('duration', 1),
                    description=task.get('description', task.get('name')),
                    task_name=task.get('name')
                )
                
                # Update task status based on result
                if success:
                    task['status'] = 'done'
                else:
                    task['status'] = 'failed'
                    # Stop on critical failure
                    if task.get('critical', False):
                        self.should_stop = True
                
                # Emit task update
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': task
                    })
                
                # Small delay between tasks
                if not self.should_stop:
                    time.sleep(0.5)
            
            # Execution complete
            self.is_running = False
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'execution_complete',
                    'message': 'All tasks completed',
                    'tasks': self.tasks
                })
                
        except Exception as e:
            print(f"Error in task execution: {e}")
            self.is_running = False
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'execution_error',
                    'error': str(e),
                    'message': f'Execution error: {str(e)}'
                })

