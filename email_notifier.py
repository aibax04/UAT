"""
Email Notification Service
==========================

Handles sending email notifications after scheduled test completion.
Uses SMTP with support for multiple email providers.
Designed to be non-blocking and failure-tolerant.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Handles email notification delivery for scheduled test results.
    Supports SMTP with multiple provider configurations.
    """
    
    def __init__(self):
        """Initialize email notifier with configuration from environment"""
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_from = os.getenv('SMTP_FROM', self.smtp_user)
        smtp_use_tls_val = os.getenv('SMTP_USE_TLS', 'true').lower()
        self.smtp_use_tls = smtp_use_tls_val in ('true', 'yes', '1', 'on')
        
        # Check if email is configured
        self.is_configured = bool(self.smtp_user and self.smtp_password)
        
        if not self.is_configured:
            logger.warning("Email notifier not configured - SMTP_USER and SMTP_PASSWORD required")
    
    def send_test_notification(
        self,
        email: str,
        summary: Dict[str, Any],
        notify_type: str = 'completion'
    ) -> bool:
        """
        Send email notification for test completion.
        
        Args:
            email: Recipient email address
            summary: Test execution summary with keys:
                - site_url: str
                - task_description: str (optional)
                - status: str ('success' or 'failed')
                - execution_time: str (ISO format)
                - duration: str (optional)
                - error: str (optional)
                - schedule_id: int (optional)
            notify_type: Type of notification ('success', 'failure', 'completion')
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("Cannot send email: Email notifier not configured")
            logger.warning(f"SMTP_USER: {'Set' if self.smtp_user else 'NOT SET'}")
            logger.warning(f"SMTP_PASSWORD: {'Set' if self.smtp_password else 'NOT SET'}")
            logger.warning(f"SMTP_HOST: {self.smtp_host}")
            logger.warning(f"SMTP_PORT: {self.smtp_port}")
            return False
        
        try:
            logger.info(f"Preparing to send email to {email}")
            subject, body_text, body_html = self._build_email_content(summary, notify_type)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_from
            msg['To'] = email
            
            # Add text and HTML parts
            part1 = MIMEText(body_text, 'plain')
            part2 = MIMEText(body_html, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            try:
                # Enable debug for troubleshooting (optional, can be removed)
                # server.set_debuglevel(1)
                
                # Send EHLO to identify ourselves
                code, message = server.ehlo()
                logger.debug(f"EHLO response: {code} {message}")
                
                if self.smtp_use_tls:
                    logger.info("Starting TLS connection")
                    # Check if server supports TLS
                    if server.has_extn('STARTTLS'):
                        server.starttls()
                        # CRITICAL: Re-identify after TLS to get updated capabilities
                        code, message = server.ehlo()
                        logger.debug(f"EHLO after TLS: {code} {message}")
                    else:
                        logger.warning("Server does not support STARTTLS")
                
                logger.info(f"Logging in as {self.smtp_user}")
                # Gmail and most servers require AUTH after TLS
                # Try login directly - it will raise an exception if not supported
                server.login(self.smtp_user, self.smtp_password)
                
                logger.info(f"Sending email to {email}")
                server.send_message(msg)
                logger.info(f"Email sent successfully to {email}")
            finally:
                try:
                    server.quit()
                except:
                    server.close()
            
            logger.info(f"Email notification sent successfully to {email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error(f"Check SMTP_USER and SMTP_PASSWORD in .env file")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email notification to {email}: {e}")
            logger.exception("Full error traceback:")
            return False
    
    def send_batch_notifications(
        self,
        emails: List[str],
        summary: Dict[str, Any],
        notify_type: str = 'completion'
    ) -> Dict[str, bool]:
        """
        Send notifications to multiple email addresses.
        
        Returns:
            Dict mapping email addresses to success status
        """
        results = {}
        for email in emails:
            results[email] = self.send_test_notification(email, summary, notify_type)
        return results
    
    def _build_email_content(
        self,
        summary: Dict[str, Any],
        notify_type: str
    ) -> tuple:
        """
        Build email subject, text body, and HTML body from summary.
        
        Returns:
            (subject, text_body, html_body)
        """
        site_url = summary.get('site_url', 'Unknown Site')
        status = summary.get('status', 'unknown')
        task_description = summary.get('task_description', 'Scheduled test execution')
        execution_time = summary.get('execution_time', 'Unknown')
        duration = summary.get('duration', 'N/A')
        error = summary.get('error', '')
        
        # Format execution time
        try:
            exec_dt = datetime.fromisoformat(execution_time.replace('Z', '+00:00'))
            formatted_time = exec_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            formatted_time = execution_time
        
        # Subject
        if status == 'success':
            emoji = '✅'
            status_text = 'Passed'
        else:
            emoji = '❌'
            status_text = 'Failed'
        
        subject = f"{emoji} Scheduled Test {status_text} – {site_url}"
        
        # Text body
        text_body = f"""
Scheduled Test Notification

Status: {status.upper()}
Website: {site_url}
Task: {task_description}
Execution Time: {formatted_time}
Duration: {duration}

"""
        
        if status == 'success':
            text_body += "✅ Test completed successfully!\n\n"
        else:
            text_body += f"❌ Test failed.\n\n"
            if error:
                text_body += f"Error Details:\n{error}\n\n"
        
        text_body += "---\n"
        text_body += "This is an automated notification from your testing platform.\n"
        
        # HTML body
        status_color = '#4ade80' if status == 'success' else '#f5576c'
        status_bg = '#10b981' if status == 'success' else '#ef4444'
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 3px solid {status_bg};
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .status-badge {{
            display: inline-block;
            background: {status_bg};
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 15px;
        }}
        .info-row {{
            margin: 15px 0;
            padding: 12px;
            background: #f9fafb;
            border-left: 3px solid #667eea;
            border-radius: 4px;
        }}
        .info-label {{
            font-weight: 600;
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .info-value {{
            color: #111;
            font-size: 16px;
        }}
        .error-box {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
            color: #991b1b;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #6b7280;
            text-align: center;
        }}
        .url-link {{
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
        }}
        .url-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="status-badge">{emoji} {status.upper()}</span>
            <h1 style="margin: 10px 0; color: #111;">Scheduled Test {status_text}</h1>
        </div>
        
        <div class="info-row">
            <div class="info-label">Website URL</div>
            <div class="info-value">
                <a href="{site_url}" class="url-link" target="_blank">{site_url}</a>
            </div>
        </div>
        
        <div class="info-row">
            <div class="info-label">Task Description</div>
            <div class="info-value">{task_description or 'No description provided'}</div>
        </div>
        
        <div class="info-row">
            <div class="info-label">Execution Time</div>
            <div class="info-value">{formatted_time}</div>
        </div>
        
        <div class="info-row">
            <div class="info-label">Duration</div>
            <div class="info-value">{duration}</div>
        </div>
        
"""
        
        if status == 'failed' and error:
            html_body += f"""
        <div class="error-box">
            <strong>❌ Error Details:</strong><br>
            <pre style="margin: 10px 0; white-space: pre-wrap; font-family: monospace; font-size: 12px;">{error[:500]}</pre>
        </div>
"""
        
        html_body += """
        <div class="footer">
            <p>This is an automated notification from your testing platform.</p>
            <p>You can manage your notification settings in the Scheduled Testing dashboard.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return subject, text_body, html_body


def send_test_notification(
    email: str,
    summary: Dict[str, Any],
    notify_type: str = 'completion'
) -> bool:
    """
    Convenience function to send test notification.
    
    Args:
        email: Recipient email address
        summary: Test execution summary dict
        notify_type: Type of notification ('success', 'failure', 'completion')
    
    Returns:
        bool: Success status
    """
    notifier = EmailNotifier()
    return notifier.send_test_notification(email, summary, notify_type)


# Global instance for reuse
_notifier_instance = None

def get_email_notifier() -> EmailNotifier:
    """Get or create global email notifier instance (singleton)"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = EmailNotifier()
    return _notifier_instance

