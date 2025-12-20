# Scheduled Testing Feature

## Overview

The Scheduled Testing feature allows users to automate test execution on a schedule without modifying existing agent logic. Tests run automatically based on configured schedules (daily, weekly, interval, or one-time).

## Architecture

### Components

1. **Scheduler Service** (`scheduler_service.py`)
   - Uses APScheduler for job scheduling
   - SQLite jobstore for persistence across server restarts
   - Integrates with existing `workflow.invoke()` function
   - Manages schedule CRUD operations

2. **Database Schema** (`migrate_db_scheduler.py`)
   - `scheduled_tests` table stores schedule configurations
   - Fields: site_url, frequency, time, status, etc.

3. **API Routes** (`app.py`)
   - `GET /api/scheduled-tests` - List all schedules
   - `POST /api/scheduled-tests` - Create new schedule
   - `PUT /api/scheduled-tests/<id>` - Update schedule
   - `DELETE /api/scheduled-tests/<id>` - Delete schedule
   - `POST /api/scheduled-tests/<id>/toggle` - Enable/disable schedule

4. **Frontend** (`scheduled_testing.js`, `index.html`)
   - UI for creating and managing schedules
   - List view with status, last run time, etc.
   - Enable/disable and delete functionality

## Usage

### Creating a Schedule

1. Click "Scheduled Testing" button on landing page
2. Fill in the form:
   - Website URL (required)
   - Task Description (optional)
   - Frequency: Daily, Weekly, Interval, or One Time
   - Time/Date based on frequency
   - Enable/disable toggle
3. Click "Create Schedule"

### Frequency Types

- **Daily**: Runs every day at specified time
- **Weekly**: Runs on selected days of week at specified time
- **Interval**: Runs every X hours/minutes
- **One Time**: Runs once at specified date/time

### Schedule Management

- View all schedules in the "Active Schedules" list
- Toggle enable/disable for any schedule
- Delete schedules you no longer need
- View status (pending, running, success, failed)
- View last run time and error messages (if any)

## Technical Details

### Execution Flow

1. When a scheduled job fires:
   - Scheduler calls `_execute_scheduled_test(schedule_id)`
   - Status updated to 'running'
   - Calls `workflow.invoke()` with `mode="scheduled"`
   - Status updated to 'success' or 'failed' based on result

### Persistence

- Schedules stored in SQLite database (`uat.db`)
- Jobs stored in SQLite jobstore (`jobs.db`)
- Survives server restarts - schedules automatically reloaded on startup

### Error Handling

- Failed runs update status to 'failed'
- Error messages stored in `last_error` field
- Scheduler continues running even if individual jobs fail
- All errors logged for debugging

### Integration Points

- **Non-intrusive**: Only calls existing `workflow.invoke()` function
- **No modifications**: Existing agent execution logic unchanged
- **Headless execution**: Scheduled tests run without browser preview
- **Same results**: Uses same report/history system as manual runs

## Setup

1. Run database migration:
   ```bash
   python migrate_db_scheduler.py
   ```

2. Install dependencies:
   ```bash
   pip install APScheduler==3.10.4
   ```

3. Start the application:
   ```bash
   python app.py
   ```

The scheduler automatically starts and loads existing schedules from the database.

## Database Schema

```sql
CREATE TABLE scheduled_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_url TEXT NOT NULL,
    task_description TEXT,
    frequency TEXT NOT NULL,  -- 'daily', 'weekly', 'interval', 'once'
    schedule_time TEXT,  -- HH:MM format
    interval_hours INTEGER,
    interval_minutes INTEGER,
    days_of_week TEXT,  -- Comma-separated
    schedule_date TEXT,  -- ISO format
    enabled INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    last_run_time TEXT,
    last_error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    app_name TEXT
);
```

## API Examples

### Create Daily Schedule
```json
POST /api/scheduled-tests
{
  "site_url": "https://example.com",
  "task_description": "Run full site analysis",
  "frequency": "daily",
  "time": "02:00",
  "enabled": true
}
```

### Create Weekly Schedule
```json
POST /api/scheduled-tests
{
  "site_url": "https://example.com",
  "frequency": "weekly",
  "time": "09:00",
  "days_of_week": ["monday", "wednesday", "friday"],
  "enabled": true
}
```

### Create Interval Schedule
```json
POST /api/scheduled-tests
{
  "site_url": "https://example.com",
  "frequency": "interval",
  "interval_hours": 0,
  "interval_minutes": 30,
  "enabled": true
}
```

## Notes

- All times are in UTC
- Schedules are loaded on server startup
- Disabled schedules don't run but remain in database
- One-time schedules are automatically disabled after execution
- Error messages truncated to 500 characters in database

