# Email Notifications for Scheduled Tests

## Overview

Automatic email notifications are sent after scheduled test completion (success or failure). The system is designed to be non-blocking, configurable, and failure-tolerant.

## Features

- ✅ **Automatic Notifications**: Emails sent immediately after test completion
- ✅ **Configurable Per Schedule**: Each schedule can have different notification settings
- ✅ **Success/Failure Toggles**: Choose to be notified on success, failure, or both
- ✅ **Multiple Recipients**: Support for comma-separated email addresses
- ✅ **Professional Templates**: HTML and plain text email templates
- ✅ **Non-Blocking**: Email sending doesn't delay test execution
- ✅ **Failure Tolerant**: Email failures don't crash the scheduler

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true
```

### Email Provider Examples

#### Gmail
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password, not regular password
SMTP_USE_TLS=true
```

#### SendGrid
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_USE_TLS=true
```

#### Mailtrap (Testing)
```env
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_USER=your-mailtrap-username
SMTP_PASSWORD=your-mailtrap-password
SMTP_USE_TLS=false
```

#### AWS SES
```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-ses-smtp-username
SMTP_PASSWORD=your-ses-smtp-password
SMTP_USE_TLS=true
```

## Usage

### Via UI

1. Go to **Scheduled Testing** section
2. Create or edit a schedule
3. In the **Email Notifications** section:
   - Enter email address(es) (comma-separated for multiple)
   - Check "Notify on success" to receive emails when tests pass
   - Check "Notify on failure" to receive emails when tests fail
4. Save the schedule

### Via API

```json
POST /api/scheduled-tests
{
  "site_url": "https://example.com",
  "frequency": "daily",
  "time": "02:00",
  "notify_email": "team@example.com, manager@example.com",
  "notify_on_success": true,
  "notify_on_failure": true
}
```

## Email Content

### Subject Lines
- ✅ **Success**: `✅ Scheduled Test Passed – <site_url>`
- ❌ **Failure**: `❌ Scheduled Test Failed – <site_url>`

### Email Body Includes
- Test status (Success/Failed)
- Website URL (clickable)
- Task description
- Execution time
- Duration
- Error details (if failed)
- Professional HTML formatting

## Technical Details

### Architecture

1. **Email Notifier Module** (`email_notifier.py`)
   - Handles SMTP connection and email sending
   - Supports HTML and plain text emails
   - Singleton pattern for reuse

2. **Scheduler Integration** (`scheduler_service.py`)
   - Calls notification function after test completion
   - Uses background thread for non-blocking delivery
   - Updates notification status in database

3. **Database Schema**
   - `notify_email`: Comma-separated email addresses
   - `notify_on_success`: Boolean flag
   - `notify_on_failure`: Boolean flag
   - `last_notification_sent`: Timestamp
   - `last_notification_status`: Status (sent/failed/partial_failed)

### Execution Flow

1. Scheduled test completes (success or failure)
2. Status updated in database
3. Background thread spawned for notification
4. Notification settings checked
5. If configured, email sent to recipient(s)
6. Notification status updated in database

### Error Handling

- Email failures are logged but don't interrupt scheduler
- Notification status tracked in database
- Supports partial failures (some emails succeed, others fail)
- Graceful degradation if email notifier not configured

## Setup

1. **Run migration** (if not already done):
   ```bash
   python migrate_db_email_notifications.py
   ```

2. **Configure SMTP** in `.env` file

3. **Restart application** to load new configuration

## Notes

- Notifications are **OFF by default** - must be explicitly enabled per schedule
- Multiple email addresses supported (comma-separated)
- Email sending is **asynchronous** - doesn't block test execution
- Notification status visible in schedule list
- System works even if email notifier is not configured (graceful degradation)

