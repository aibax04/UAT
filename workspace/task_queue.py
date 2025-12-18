"""
TaskQueue: Manages task queue for sequential execution.
Ensures only one task runs at a time and preserves order.
"""
import threading
from collections import deque


class TaskQueue:
    """Thread-safe task queue for sequential execution"""
    
    def __init__(self):
        self.queue = deque()
        self.lock = threading.Lock()
        self.current_task = None
    
    def add_task(self, task):
        """Add a task to the queue"""
        with self.lock:
            # Initialize task status if not present
            if 'status' not in task:
                task['status'] = 'pending'
            self.queue.append(task)
            return len(self.queue)
    
    def add_tasks(self, tasks):
        """Add multiple tasks to the queue"""
        with self.lock:
            for task in tasks:
                if 'status' not in task:
                    task['status'] = 'pending'
                self.queue.append(task)
            return len(self.queue)
    
    def get_next_task(self):
        """Get and mark the next task as running"""
        with self.lock:
            if not self.queue:
                return None
            
            task = self.queue.popleft()
            task['status'] = 'running'
            self.current_task = task
            return task
    
    def mark_task_complete(self, task, success=True):
        """Mark a task as done or failed"""
        with self.lock:
            task['status'] = 'done' if success else 'failed'
            if self.current_task == task:
                self.current_task = None
    
    def clear(self):
        """Clear all tasks from queue"""
        with self.lock:
            self.queue.clear()
            self.current_task = None
    
    def get_queue_size(self):
        """Get current queue size"""
        with self.lock:
            return len(self.queue)
    
    def get_all_tasks(self):
        """Get all tasks (for UI display)"""
        with self.lock:
            tasks = list(self.queue)
            if self.current_task:
                tasks.insert(0, self.current_task)
            return tasks

