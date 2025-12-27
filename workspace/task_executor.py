"""
TaskExecutor: Executes tasks sequentially on the browser session.
Manages task status and coordinates with BrowserSessionManager.
Implements persistent agent execution loop with real-time updates.
"""
import time
import threading
from workspace.task_queue import TaskQueue
try:
    from db import get_db
except ImportError:
    import sqlite3
    def get_db():
        return sqlite3.connect('user_data.db')


class TaskExecutor:
    """Executes tasks sequentially on a browser session with real-time updates"""
    
    def __init__(self, browser_session, on_task_update_callback):
        self.browser_session = browser_session
        self.on_task_update_callback = on_task_update_callback
        self.task_queue = TaskQueue()
        self.current_task = None
        self.current_step = None
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.execution_thread = None
        self.lock = threading.Lock()
        
        # User Interaction & Memory
        self.input_event = threading.Event()
        self.waiting_for_input = False
        self.provided_input = None
    
    def set_tasks(self, tasks):
        """Set the task list to execute (adds to queue)"""
        self.task_queue.clear()
        self.task_queue.add_tasks(tasks)
        
        # Emit initial task list for UI
        if self.on_task_update_callback:
            for task in tasks:
                self.on_task_update_callback({
                    'type': 'task_update',
                    'task': task
                })
    
    def start_execution(self):
        """Start executing tasks in a separate thread (agent execution loop)"""
        with self.lock:
            if self.is_running:
                return False
            
            if self.task_queue.get_queue_size() == 0 and not self.current_task:
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'error',
                        'message': 'No tasks to execute'
                    })
                return False
            
            self.is_running = True
            self.is_paused = False
            self.should_stop = False
        
        # Start persistent agent execution loop in background thread
        self.execution_thread = threading.Thread(target=self._agent_execution_loop, daemon=True)
        self.execution_thread.start()
        
        # Emit execution started
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'execution_started',
                'message': 'Agent execution started'
            })
        
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
        with self.lock:
            self.should_stop = True
            self.is_paused = False
            self.is_running = False
            
            # Mark current task as failed if stopped mid-execution
            if self.current_task and self.current_task['status'] == 'running':
                self.current_task['status'] = 'failed'
                self.task_queue.mark_task_complete(self.current_task, success=False)
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': self.current_task
                    })
                self.current_task = None
        
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'execution_stopped',
                'message': 'Execution stopped'
            })
    
    def _agent_execution_loop(self):
        """Persistent agent execution loop - runs continuously until stopped"""
        execution_start_time = time.time()
        
        try:
            while not self.should_stop:
                # Wait if paused
                while self.is_paused and not self.should_stop:
                    time.sleep(0.5)
                
                if self.should_stop:
                    break
                
                # Get next task from queue
                task = self.task_queue.get_next_task()
                if not task:
                    # No more tasks, but keep loop running for future tasks
                    time.sleep(1)
                    continue
                
                # Set as current task
                with self.lock:
                    self.current_task = task
                
                # Emit task started
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': task,
                        'message': f'Starting: {task.get("name", "Task")}'
                    })
                
                # Execute task with step-by-step updates
                success = self._execute_task_with_steps(task)
                
                # Mark task complete
                self.task_queue.mark_task_complete(task, success)
                
                # Emit task completion
                if self.on_task_update_callback:
                    self.on_task_update_callback({
                        'type': 'task_update',
                        'task': task,
                        'message': f'Completed: {task.get("name", "Task")}'
                    })
                
                # Stop on critical failure
                if not success and task.get('critical', False):
                    self.should_stop = True
                    break
                
                # Small delay between tasks
                if not self.should_stop:
                    time.sleep(0.3)
            
            # Calculate execution metrics
            execution_end_time = time.time()
            total_duration = execution_end_time - execution_start_time
            all_tasks = self.task_queue.get_all_tasks()
            completed_count = sum(1 for t in all_tasks if t.get('status') == 'done')
            failed_count = sum(1 for t in all_tasks if t.get('status') == 'failed')
            
            # Calculate average task time
            task_times = [t.get('execution_time', 0) for t in all_tasks if t.get('execution_time')]
            avg_task_time = sum(task_times) / len(task_times) if task_times else 0
            
            # Execution stopped
            with self.lock:
                self.is_running = False
                self.current_task = None
                self.execution_metrics = {
                    'start_time': execution_start_time,
                    'end_time': execution_end_time,
                    'total_duration': total_duration,
                    'total_tasks': len(all_tasks),
                    'completed_tasks': completed_count,
                    'failed_tasks': failed_count,
                    'average_task_time': avg_task_time,
                    'tasks': all_tasks
                }
            
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'execution_complete',
                    'message': 'All tasks completed',
                    'tasks': all_tasks,
                    'metrics': self.execution_metrics
                })
                
        except Exception as e:
            print(f"Error in agent execution loop: {e}")
            import traceback
            traceback.print_exc()
            with self.lock:
                self.is_running = False
                self.current_task = None
            
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'execution_error',
                    'error': str(e),
                    'message': f'Execution error: {str(e)}'
                })
    
    def _execute_task_with_steps(self, task):
        """Execute a single task with granular step updates"""
        import time
        task_start_time = time.time()
        
        try:
            action_type = task.get('action_type', 'wait')
            task_name = task.get('name', 'Task')
            description = task.get('description', task_name)
            
            # Emit step start
            step_description = f"{task_name}: {description}"
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'step_start',
                    'task': task,
                    'step': step_description,
                    'message': step_description
                })
            
            # INTELLIGENT FILL PRE-PROCESSING
            if action_type == 'fill':
                text = task.get('text', '')
                field_key = task.get('field_id') or description.replace('Fill ', '').replace('Enter ', '').lower()
                
                # If value matches "ASK_USER" placeholder or is missing/placeholder-like for a required field
                # Heuristic: if text is uppercase "ASK_USER" or empty
                if text == 'ASK_USER' or not text:
                    # 1. Check Knowledge Base
                    found_value = self._get_from_knowledge_base(field_key)
                    
                    if found_value:
                        task['text'] = found_value
                        if self.on_task_update_callback:
                            self.on_task_update_callback({
                                'type': 'task_update',
                                'task': task,
                                'message': f"Auto-filled '{field_key}' from memory"
                            })
                    else:
                        # 2. Ask User
                        if self.on_task_update_callback:
                            self.on_task_update_callback({
                                'type': 'request_input',
                                'session_id': self.browser_session.session_id,
                                'task_id': task.get('id'),
                                'field': field_key,
                                'description': description,
                                'message': f"Please provide value for: {field_key}"
                            })
                        
                        # Wait for input
                        self.waiting_for_input = True
                        self.input_event.clear()
                        self.is_paused = True # Pause loop
                        
                        print(f"Waiting for input for {field_key}...")
                        self.input_event.wait()
                        
                        # Input received
                        text = self.provided_input
                        self.waiting_for_input = False
                        self.is_paused = False
                        
                        # 3. Store in Knowledge Base (Learning)
                        if text:
                            self._save_to_knowledge_base(field_key, text)
                            task['text'] = text

            # Execute action with detailed description
            success = self.browser_session.execute_action(
                action_type,
                selector=task.get('selector'),
                text=task.get('text'), # Updated text
                url=task.get('url'),
                duration=task.get('duration', 1),
                description=description,
                task_name=task_name,
                attributes=task.get('attributes', {})
            )
            
            # Calculate execution time
            task_duration = time.time() - task_start_time
            task['execution_time'] = task_duration
            task['start_time'] = task_start_time
            task['end_time'] = time.time()
            
            # Store execution metadata in task if available
            if hasattr(self.browser_session, 'execution_metadata') and self.browser_session.execution_metadata:
                last_metadata = self.browser_session.execution_metadata[-1]
                if last_metadata.get('action') == action_type:
                    task['metadata'] = last_metadata.get('metadata', {})
            
            # Emit step complete
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'step_complete',
                    'task': task,
                    'step': step_description,
                    'success': success,
                    'message': f'Completed: {step_description}' if success else f'Failed: {step_description}'
                })
            
            return success
            
        except Exception as e:
            print(f"Error executing task {task.get('name')}: {e}")
            if self.on_task_update_callback:
                self.on_task_update_callback({
                    'type': 'step_error',
                    'task': task,
                    'error': str(e),
                    'message': f'Error: {str(e)}'
                })
            return False

    def provide_input(self, value):
        """Provide input for a waiting task"""
        if self.waiting_for_input:
            self.provided_input = value
            self.input_event.set()
            return True
        return False

    def _get_from_knowledge_base(self, key):
        """Retrieve value from user knowledge base (context=default for now)"""
        try:
            # Connect to user_data.db (assuming it's in root)
            conn = sqlite3.connect('user_data.db')
            cursor = conn.cursor()
            # Try exact match on key
            cursor.execute("SELECT value FROM user_knowledge WHERE key = ? ORDER BY last_updated DESC LIMIT 1", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
            
            # TODO: Fuzzy matching could be added here
            return None
        except Exception as e:
            print(f"DB Read Error: {e}")
            return None

    def _save_to_knowledge_base(self, key, value):
        """Save value to user knowledge base"""
        try:
            conn = sqlite3.connect('user_data.db')
            cursor = conn.cursor()
            # Upsert
            cursor.execute("""
                INSERT OR REPLACE INTO user_knowledge (key, value, type, last_updated)
                VALUES (?, ?, 'user_input', CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Write Error: {e}")
    
    def add_task(self, task):
        """Add a single task to the queue (for dynamic task addition)"""
        queue_size = self.task_queue.add_task(task)
        if self.on_task_update_callback:
            self.on_task_update_callback({
                'type': 'task_update',
                'task': task
            })
        return queue_size

