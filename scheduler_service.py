"""
Scheduler Service: Manages scheduled test execution using APScheduler.
Integrates with existing agent execution pipeline without modifying it.
"""

import logging
from datetime import datetime, time as dt_time
from typing import Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from db import get_db
from workflows.graph import workflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance (singleton)
_scheduler = None


class SchedulerService:
    """
    Manages scheduled test execution.
    Uses APScheduler with SQLite jobstore for persistence across restarts.
    """
    
    def __init__(self):
        """Initialize the scheduler with SQLite jobstore for persistence"""
        # Use SQLite for job persistence (survives restarts)
        jobstore_url = 'sqlite:///jobs.db'
        jobstores = {
            'default': SQLAlchemyJobStore(url=jobstore_url)
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone='UTC'  # Use UTC for consistency
        )
        
        # Add event listeners for job execution tracking
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler service started")
    
    def shutdown(self):
        """Shutdown the scheduler gracefully"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler service shut down")
    
    def _on_job_executed(self, event):
        """Handle job execution events (for logging and status updates)"""
        schedule_id = event.job_id
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            if event.exception:
                # Job failed
                logger.error(f"Scheduled test {schedule_id} failed: {event.exception}")
                cursor.execute("""
                    UPDATE scheduled_tests 
                    SET status = ?, last_run_time = ?, last_error = ?
                    WHERE id = ?
                """, ('failed', datetime.utcnow().isoformat(), str(event.exception), schedule_id))
            else:
                # Job succeeded
                logger.info(f"Scheduled test {schedule_id} executed successfully")
                cursor.execute("""
                    UPDATE scheduled_tests 
                    SET status = ?, last_run_time = ?
                    WHERE id = ?
                """, ('success', datetime.utcnow().isoformat(), schedule_id))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating scheduled test status: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    @staticmethod
    def _execute_scheduled_test(schedule_id: int):
        """
        Execute a scheduled test by calling the existing workflow.
        This is a static method to avoid scheduler serialization issues.
        """
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Get schedule details
            cursor.execute("""
                SELECT site_url, task_description, app_name
                FROM scheduled_tests
                WHERE id = ?
            """, (schedule_id,))
            
            schedule = cursor.fetchone()
            if not schedule:
                logger.error(f"Scheduled test {schedule_id} not found")
                return
            
            site_url, task_description, app_name = schedule
            
            # Update status to running
            cursor.execute("""
                UPDATE scheduled_tests 
                SET status = 'running', last_run_time = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), schedule_id))
            conn.commit()
            
            logger.info(f"Executing scheduled test {schedule_id}: {site_url}")
            
            # Extract app_name helper (static version)
            try:
                extracted_app_name = site_url.split('//')[1].split('/')[0].replace('.', '_')
            except:
                extracted_app_name = 'unknown_app'
            
            # Call the existing workflow - this is the key integration point
            # We're NOT modifying workflow, just calling it with mode="scheduled"
            result = workflow.invoke({
                "app_name": app_name or extracted_app_name,
                "start_url": site_url,
                "mode": "scheduled",  # Pass mode flag for tracking
                "task_description": task_description  # Optional task hint
            })
            
            # Update status to success
            cursor.execute("""
                UPDATE scheduled_tests 
                SET status = 'success', last_run_time = ?, last_error = NULL
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), schedule_id))
            conn.commit()
            
            logger.info(f"Scheduled test {schedule_id} completed successfully")
            
        except Exception as e:
            # Update status to failed
            error_msg = str(e)
            logger.error(f"Scheduled test {schedule_id} failed: {error_msg}")
            
            try:
                cursor.execute("""
                    UPDATE scheduled_tests 
                    SET status = 'failed', last_run_time = ?, last_error = ?
                    WHERE id = ?
                """, (datetime.utcnow().isoformat(), error_msg[:500], schedule_id))
                conn.commit()
            except Exception as update_error:
                logger.error(f"Error updating failed status: {update_error}")
        
        finally:
            conn.close()
    
    def _extract_app_name(self, url: str) -> str:
        """Extract app name from URL (same logic as existing code)"""
        try:
            return url.split('//')[1].split('/')[0].replace('.', '_')
        except:
            return 'unknown_app'
    
    def add_schedule(self, schedule_data: Dict[str, Any]) -> int:
        """
        Add a new scheduled test.
        
        Args:
            schedule_data: Dict with keys:
                - site_url: str (required)
                - task_description: str (optional)
                - frequency: str ('daily', 'weekly', 'interval', 'once')
                - time: str (HH:MM format for daily/weekly)
                - interval_hours: int (for interval frequency)
                - interval_minutes: int (for interval frequency)
                - days_of_week: list (for weekly, e.g. ['monday', 'wednesday'])
                - date: str (ISO format for one-time schedules)
                - enabled: bool (default True)
        
        Returns:
            schedule_id: int
        """
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Extract app_name if provided, otherwise derive from URL
            app_name = schedule_data.get('app_name') or self._extract_app_name(schedule_data['site_url'])
            
            # Insert schedule into database
            cursor.execute("""
                INSERT INTO scheduled_tests (
                    site_url, task_description, frequency, schedule_time,
                    interval_hours, interval_minutes, days_of_week,
                    schedule_date, enabled, status, created_at, app_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                schedule_data['site_url'],
                schedule_data.get('task_description', ''),
                schedule_data['frequency'],
                schedule_data.get('time'),
                schedule_data.get('interval_hours'),
                schedule_data.get('interval_minutes'),
                ','.join(schedule_data.get('days_of_week', [])) if schedule_data.get('days_of_week') else None,
                schedule_data.get('date'),
                schedule_data.get('enabled', True),
                'pending',
                datetime.utcnow().isoformat(),
                app_name
            ))
            
            schedule_id = cursor.lastrowid
            conn.commit()
            
            # Add job to scheduler if enabled
            if schedule_data.get('enabled', True):
                self._schedule_job(schedule_id, schedule_data)
            
            logger.info(f"Added scheduled test {schedule_id}")
            return schedule_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error adding schedule: {e}")
            raise
        finally:
            conn.close()
    
    def _schedule_job(self, schedule_id: int, schedule_data: Dict[str, Any]):
        """Add a job to the scheduler based on frequency type"""
        frequency = schedule_data['frequency']
        job_id = str(schedule_id)
        
        try:
            if frequency == 'daily':
                # Daily schedule at specified time
                time_str = schedule_data.get('time', '00:00')
                hour, minute = map(int, time_str.split(':'))
                trigger = CronTrigger(hour=hour, minute=minute)
                
            elif frequency == 'weekly':
                # Weekly schedule on specified days at specified time
                time_str = schedule_data.get('time', '00:00')
                hour, minute = map(int, time_str.split(':'))
                days_of_week = schedule_data.get('days_of_week', [])
                
                # Map day names to cron day numbers (0=Monday, 6=Sunday)
                day_map = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2,
                    'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
                }
                day_list = [str(day_map.get(day.lower(), 0)) for day in days_of_week]
                day_of_week = ','.join(day_list) if day_list else None
                
                trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
                
            elif frequency == 'interval':
                # Interval schedule (every X hours/minutes)
                hours = schedule_data.get('interval_hours', 0)
                minutes = schedule_data.get('interval_minutes', 0)
                if hours == 0 and minutes == 0:
                    minutes = 60  # Default to 1 hour if not specified
                trigger = IntervalTrigger(hours=hours, minutes=minutes)
                
            elif frequency == 'once':
                # One-time schedule at specified date/time
                date_str = schedule_data.get('date')
                if date_str:
                    schedule_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    trigger = DateTrigger(run_date=schedule_datetime)
                else:
                    raise ValueError("date is required for 'once' frequency")
            else:
                raise ValueError(f"Invalid frequency: {frequency}")
            
            # Add job to scheduler
            # Use the class method directly, not self, to avoid serialization issues
            self.scheduler.add_job(
                func=SchedulerService._execute_scheduled_test,  # Use class method reference
                trigger=trigger,
                args=[schedule_id],
                id=job_id,
                replace_existing=True,
                max_instances=1  # Don't run duplicate jobs
            )
            
            logger.info(f"Scheduled job {job_id} with trigger: {trigger}")
            
        except Exception as e:
            logger.error(f"Error scheduling job {job_id}: {e}")
            raise
    
    def update_schedule(self, schedule_id: int, schedule_data: Dict[str, Any]) -> bool:
        """Update an existing scheduled test"""
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Update database
            cursor.execute("""
                UPDATE scheduled_tests 
                SET site_url = ?, task_description = ?, frequency = ?,
                    schedule_time = ?, interval_hours = ?, interval_minutes = ?,
                    days_of_week = ?, schedule_date = ?, enabled = ?
                WHERE id = ?
            """, (
                schedule_data['site_url'],
                schedule_data.get('task_description', ''),
                schedule_data['frequency'],
                schedule_data.get('time'),
                schedule_data.get('interval_hours'),
                schedule_data.get('interval_minutes'),
                ','.join(schedule_data.get('days_of_week', [])) if schedule_data.get('days_of_week') else None,
                schedule_data.get('date'),
                schedule_data.get('enabled', True),
                schedule_id
            ))
            
            conn.commit()
            
            # Remove old job if it exists
            job_id = str(schedule_id)
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass  # Job might not exist
            
            # Re-add job if enabled
            if schedule_data.get('enabled', True):
                self._schedule_job(schedule_id, schedule_data)
            
            logger.info(f"Updated scheduled test {schedule_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating schedule: {e}")
            raise
        finally:
            conn.close()
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a scheduled test"""
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Remove job from scheduler
            job_id = str(schedule_id)
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass  # Job might not exist
            
            # Delete from database
            cursor.execute("DELETE FROM scheduled_tests WHERE id = ?", (schedule_id,))
            conn.commit()
            
            logger.info(f"Deleted scheduled test {schedule_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting schedule: {e}")
            raise
        finally:
            conn.close()
    
    def toggle_schedule(self, schedule_id: int, enabled: bool) -> bool:
        """Enable or disable a scheduled test"""
        conn = get_db()
        cursor = conn.cursor()
        job_id = str(schedule_id)
        
        try:
            # Update database
            cursor.execute("""
                UPDATE scheduled_tests SET enabled = ? WHERE id = ?
            """, (enabled, schedule_id))
            conn.commit()
            
            # Update scheduler
            if enabled:
                # Get schedule data and re-add job
                cursor.execute("""
                    SELECT site_url, task_description, frequency, schedule_time,
                           interval_hours, interval_minutes, days_of_week, schedule_date
                    FROM scheduled_tests WHERE id = ?
                """, (schedule_id,))
                row = cursor.fetchone()
                if row:
                    schedule_data = {
                        'site_url': row[0],
                        'task_description': row[1],
                        'frequency': row[2],
                        'time': row[3],
                        'interval_hours': row[4],
                        'interval_minutes': row[5],
                        'days_of_week': row[6].split(',') if row[6] else [],
                        'date': row[7]
                    }
                    self._schedule_job(schedule_id, schedule_data)
            else:
                # Remove job from scheduler
                try:
                    self.scheduler.remove_job(job_id)
                except:
                    pass
            
            logger.info(f"Toggled schedule {schedule_id} to {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error toggling schedule: {e}")
            raise
        finally:
            conn.close()
    
    def get_all_schedules(self) -> list:
        """Get all scheduled tests"""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, site_url, task_description, frequency, schedule_time,
                   interval_hours, interval_minutes, days_of_week, schedule_date,
                   enabled, status, last_run_time, last_error, created_at
            FROM scheduled_tests
            ORDER BY created_at DESC
        """)
        
        schedules = []
        for row in cursor.fetchall():
            schedules.append({
                'id': row[0],
                'site_url': row[1],
                'task_description': row[2],
                'frequency': row[3],
                'time': row[4],
                'interval_hours': row[5],
                'interval_minutes': row[6],
                'days_of_week': row[7].split(',') if row[7] else [],
                'date': row[8],
                'enabled': bool(row[9]),
                'status': row[10],
                'last_run_time': row[11],
                'last_error': row[12],
                'created_at': row[13]
            })
        
        conn.close()
        return schedules
    
    def load_existing_schedules(self):
        """Load all enabled schedules from database on startup"""
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, site_url, task_description, frequency, schedule_time,
                   interval_hours, interval_minutes, days_of_week, schedule_date
            FROM scheduled_tests
            WHERE enabled = 1
        """)
        
        for row in cursor.fetchall():
            schedule_id = row[0]
            schedule_data = {
                'site_url': row[1],
                'task_description': row[2],
                'frequency': row[3],
                'time': row[4],
                'interval_hours': row[5],
                'interval_minutes': row[6],
                'days_of_week': row[7].split(',') if row[7] else [],
                'date': row[8]
            }
            try:
                self._schedule_job(schedule_id, schedule_data)
                logger.info(f"Loaded existing schedule {schedule_id}")
            except Exception as e:
                logger.error(f"Error loading schedule {schedule_id}: {e}")
        
        conn.close()


def get_scheduler_service() -> SchedulerService:
    """Get or create the global scheduler service instance (singleton)"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler

