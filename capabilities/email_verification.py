"""
Email Verification Module
=========================

Integrates with inbox APIs (MailHog, Mailtrap, SES sandbox) to poll for
emails triggered by UI actions and extract OTPs, links, or confirmation text.
"""

import os
import time
import re
import requests
from typing import Dict, Any, Optional, Callable, List
from playwright.sync_api import Page
from dotenv import load_dotenv

from .base_module import BaseCapabilityModule

load_dotenv()


class EmailVerificationModule(BaseCapabilityModule):
    """Fetch and extract artifacts from emails"""
    
    def __init__(self, page: Page, on_update_callback: Optional[Callable] = None):
        super().__init__(page, on_update_callback)
        # Email service configuration
        self.mailhog_url = os.getenv('MAILHOG_URL', 'http://localhost:8025')
        self.mailtrap_api_token = os.getenv('MAILTRAP_API_TOKEN', '')
        self.mailtrap_inbox_id = os.getenv('MAILTRAP_INBOX_ID', '')
        self.ses_endpoint = os.getenv('AWS_SES_ENDPOINT', '')
        self.poll_timeout = int(os.getenv('EMAIL_POLL_TIMEOUT', '30'))  # seconds
        self.poll_interval = int(os.getenv('EMAIL_POLL_INTERVAL', '2'))  # seconds
    
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """Check if this is an email-related task"""
        action_type = intent_data.get('action_type', '')
        description = intent_data.get('description', '').lower()
        task_name = intent_data.get('task_name', '').lower()
        
        email_keywords = ['email', 'mail', 'inbox', 'otp', 'verification', 'confirmation', 'link', 'activate']
        return (action_type in ['email', 'verify_email'] or
                any(keyword in description or keyword in task_name for keyword in email_keywords) or
                intent_data.get('capability') == 'email_verification')
    
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch email artifact (OTP, link, confirmation text)
        
        Args:
            intent_data: Must contain:
                - 'email_type': 'otp', 'link', 'confirmation', or 'all'
                - 'recipient_email': Email to check (optional, defaults to env)
                - 'subject_filter': Optional subject line filter
                - 'sender_filter': Optional sender filter
                - 'max_wait': Maximum seconds to wait (defaults to poll_timeout)
        
        Returns:
            Result dict with extracted artifact(s)
        """
        try:
            email_type = intent_data.get('email_type', 'all')
            recipient = intent_data.get('recipient_email') or os.getenv('TEST_EMAIL', 'test@example.com')
            subject_filter = intent_data.get('subject_filter', '')
            sender_filter = intent_data.get('sender_filter', '')
            max_wait = intent_data.get('max_wait', self.poll_timeout)
            
            self._emit_update('capability_start', {
                'message': f'Polling for {email_type} email',
                'recipient': recipient
            })
            
            # Determine which email service to use
            service = self._detect_email_service()
            
            # Poll for new email
            email_data = self._poll_for_email(
                service, recipient, subject_filter, sender_filter, max_wait
            )
            
            if not email_data:
                return self._create_result(
                    False,
                    error=f"No email found within {max_wait} seconds"
                )
            
            # Extract artifact based on type
            artifact = self._extract_artifact(email_data, email_type)
            
            result = {
                'email_found': True,
                'email_type': email_type,
                'artifact': artifact,
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('from', ''),
                'timestamp': email_data.get('timestamp')
            }
            
            metadata = {
                'service_used': service,
                'poll_duration': max_wait,
                'email_data': {
                    'subject': email_data.get('subject'),
                    'from': email_data.get('from'),
                    'to': email_data.get('to')
                }
            }
            
            self._emit_update('capability_complete', {
                'message': f'Email artifact extracted: {email_type}',
                'result': result
            })
            
            return self._create_result(True, result=result, metadata=metadata)
            
        except Exception as e:
            error_msg = f"Email verification error: {str(e)}"
            self._emit_update('capability_error', {'error': error_msg})
            return self._create_result(False, error=error_msg)
    
    def _detect_email_service(self) -> str:
        """Detect which email service is configured"""
        if self.mailtrap_api_token and self.mailtrap_inbox_id:
            return 'mailtrap'
        elif self.mailhog_url:
            return 'mailhog'
        elif self.ses_endpoint:
            return 'ses'
        else:
            return 'none'
    
    def _poll_for_email(self, service: str, recipient: str, 
                       subject_filter: str, sender_filter: str, 
                       max_wait: int) -> Optional[Dict[str, Any]]:
        """Poll email service for new messages"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                if service == 'mailhog':
                    email = self._fetch_mailhog_email(recipient, subject_filter, sender_filter)
                elif service == 'mailtrap':
                    email = self._fetch_mailtrap_email(subject_filter, sender_filter)
                elif service == 'ses':
                    email = self._fetch_ses_email(recipient, subject_filter, sender_filter)
                else:
                    # Mock email for testing when no service configured
                    self._emit_update('capability_progress', {
                        'message': 'No email service configured, using mock data'
                    })
                    return self._create_mock_email()
                
                if email:
                    return email
                
            except Exception as e:
                print(f"Error polling email: {e}")
            
            time.sleep(self.poll_interval)
            self._emit_update('capability_progress', {
                'message': f'Waiting for email... ({int(time.time() - start_time)}s)'
            })
        
        return None
    
    def _fetch_mailhog_email(self, recipient: str, subject_filter: str, 
                             sender_filter: str) -> Optional[Dict[str, Any]]:
        """Fetch latest email from MailHog"""
        try:
            # MailHog API v2
            response = requests.get(f"{self.mailhog_url}/api/v2/messages", timeout=5)
            if response.status_code == 200:
                messages = response.json().get('items', [])
                
                # Filter by recipient, subject, sender
                for msg in messages:
                    to_emails = [rcpt.get('Mailbox', '') + '@' + rcpt.get('Domain', '') 
                                for rcpt in msg.get('To', [])]
                    
                    if recipient not in ' '.join(to_emails):
                        continue
                    
                    subject = msg.get('Content', {}).get('Headers', {}).get('Subject', [''])[0]
                    if subject_filter and subject_filter.lower() not in subject.lower():
                        continue
                    
                    from_email = msg.get('Content', {}).get('Headers', {}).get('From', [''])[0]
                    if sender_filter and sender_filter.lower() not in from_email.lower():
                        continue
                    
                    # Get email body
                    body_parts = msg.get('Content', {}).get('Body', {})
                    text_body = body_parts.get('text', '')
                    html_body = body_parts.get('html', '')
                    
                    return {
                        'subject': subject,
                        'from': from_email,
                        'to': recipient,
                        'text_body': text_body,
                        'html_body': html_body,
                        'timestamp': msg.get('Created', '')
                    }
        except Exception as e:
            print(f"MailHog fetch error: {e}")
        
        return None
    
    def _fetch_mailtrap_email(self, subject_filter: str, 
                              sender_filter: str) -> Optional[Dict[str, Any]]:
        """Fetch latest email from Mailtrap"""
        try:
            headers = {'Api-Token': self.mailtrap_api_token}
            url = f"https://mailtrap.io/api/v1/inboxes/{self.mailtrap_inbox_id}/messages"
            
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                messages = response.json()
                
                for msg in messages:
                    subject = msg.get('subject', '')
                    if subject_filter and subject_filter.lower() not in subject.lower():
                        continue
                    
                    from_email = msg.get('from_email', '')
                    if sender_filter and sender_filter.lower() not in from_email.lower():
                        continue
                    
                    # Fetch full message
                    msg_id = msg.get('id')
                    msg_response = requests.get(f"{url}/{msg_id}", headers=headers, timeout=5)
                    if msg_response.status_code == 200:
                        full_msg = msg_response.json()
                        
                        return {
                            'subject': subject,
                            'from': from_email,
                            'to': msg.get('to_email', ''),
                            'text_body': full_msg.get('text_body', ''),
                            'html_body': full_msg.get('html_body', ''),
                            'timestamp': msg.get('created_at', '')
                        }
        except Exception as e:
            print(f"Mailtrap fetch error: {e}")
        
        return None
    
    def _fetch_ses_email(self, recipient: str, subject_filter: str, 
                        sender_filter: str) -> Optional[Dict[str, Any]]:
        """Fetch email from AWS SES sandbox (requires boto3)"""
        # Placeholder - would require boto3 and S3/SES setup
        # This is a simplified version
        try:
            # In a real implementation, you'd query S3 bucket or SES API
            # where SES sandbox stores emails
            pass
        except:
            pass
        
        return None
    
    def _create_mock_email(self) -> Dict[str, Any]:
        """Create mock email data for testing"""
        return {
            'subject': 'Verification Code',
            'from': 'noreply@example.com',
            'to': 'test@example.com',
            'text_body': 'Your verification code is 123456',
            'html_body': '<p>Your verification code is <strong>123456</strong></p>',
            'timestamp': time.time()
        }
    
    def _extract_artifact(self, email_data: Dict[str, Any], artifact_type: str) -> Any:
        """Extract specific artifact from email"""
        text_body = email_data.get('text_body', '')
        html_body = email_data.get('html_body', '')
        combined_text = text_body + ' ' + html_body
        
        if artifact_type == 'otp' or artifact_type == 'all':
            # Extract OTP (typically 4-8 digits)
            otp_patterns = [
                r'\b(\d{4,8})\b',  # 4-8 digit code
                r'code[:\s]+(\d{4,8})',
                r'OTP[:\s]+(\d{4,8})',
                r'verification[:\s]+code[:\s]+(\d{4,8})'
            ]
            
            for pattern in otp_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    return {'type': 'otp', 'value': match.group(1)}
        
        if artifact_type == 'link' or artifact_type == 'all':
            # Extract verification/activation links
            link_patterns = [
                r'(https?://[^\s<>"]+)',  # Any HTTP(S) URL
                r'href=["\']([^"\']+)["\']'  # HTML href
            ]
            
            for pattern in link_patterns:
                matches = re.findall(pattern, combined_text)
                # Filter for verification/activation links
                for link in matches:
                    if any(keyword in link.lower() for keyword in ['verify', 'activate', 'confirm', 'link']):
                        return {'type': 'link', 'value': link}
                # Return first link if no verification link found
                if matches:
                    return {'type': 'link', 'value': matches[0]}
        
        if artifact_type == 'confirmation' or artifact_type == 'all':
            # Extract confirmation text
            return {
                'type': 'confirmation',
                'value': text_body[:200]  # First 200 chars
            }
        
        return {'type': 'unknown', 'value': None}


def fetch_email_artifact(email_type: str, recipient_email: Optional[str] = None,
                        subject_filter: Optional[str] = None,
                        max_wait: int = 30,
                        on_update_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to fetch email artifact
    
    Note: This function doesn't require a page object but follows the module pattern.
    For full functionality, use EmailVerificationModule with a page context.
    
    Args:
        email_type: 'otp', 'link', 'confirmation', or 'all'
        recipient_email: Email to check (optional)
        subject_filter: Filter emails by subject
        max_wait: Maximum seconds to wait
        on_update_callback: Optional callback for updates
        
    Returns:
        Result dict with extracted artifact
    """
    # This is a simplified version - full implementation would require
    # page context for better integration
    module = EmailVerificationModule(None, on_update_callback)
    return module.execute({
        'email_type': email_type,
        'recipient_email': recipient_email,
        'subject_filter': subject_filter,
        'max_wait': max_wait
    })

