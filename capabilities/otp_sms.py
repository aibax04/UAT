"""
OTP/SMS Module
==============

Integrates with virtual OTP providers (Twilio test, Firebase emulator)
to fetch latest OTP programmatically.
"""

import os
import time
import re
import requests
from typing import Dict, Any, Optional, Callable
from playwright.sync_api import Page
from dotenv import load_dotenv

from .base_module import BaseCapabilityModule

load_dotenv()


class OTPSMSModule(BaseCapabilityModule):
    """Fetch OTP from SMS/OTP providers"""
    
    def __init__(self, page: Page, on_update_callback: Optional[Callable] = None):
        super().__init__(page, on_update_callback)
        # OTP provider configuration
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.twilio_test_number = os.getenv('TWILIO_TEST_NUMBER', '')
        self.firebase_emulator_url = os.getenv('FIREBASE_EMULATOR_URL', 'http://localhost:9099')
        self.poll_timeout = int(os.getenv('OTP_POLL_TIMEOUT', '60'))  # seconds
        self.poll_interval = int(os.getenv('OTP_POLL_INTERVAL', '2'))  # seconds
    
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """Check if this is an OTP/SMS-related task"""
        action_type = intent_data.get('action_type', '')
        description = intent_data.get('description', '').lower()
        task_name = intent_data.get('task_name', '').lower()
        
        otp_keywords = ['otp', 'sms', 'verification code', 'text message', 'phone code']
        return (action_type in ['otp', 'sms', 'verify_otp'] or
                any(keyword in description or keyword in task_name for keyword in otp_keywords) or
                intent_data.get('capability') == 'otp_sms')
    
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch OTP for a phone number
        
        Args:
            intent_data: Must contain:
                - 'phone_number': Phone number to check
                - 'provider': Optional provider ('twilio', 'firebase', or None for auto-detect)
                - 'max_wait': Maximum seconds to wait (defaults to poll_timeout)
        
        Returns:
            Result dict with OTP code
        """
        try:
            phone_number = intent_data.get('phone_number', '')
            provider = intent_data.get('provider', '').lower()
            max_wait = intent_data.get('max_wait', self.poll_timeout)
            
            if not phone_number:
                phone_number = self.twilio_test_number or os.getenv('TEST_PHONE_NUMBER', '')
            
            if not phone_number:
                return self._create_result(
                    False,
                    error="Phone number not provided and no default configured"
                )
            
            self._emit_update('capability_start', {
                'message': f'Fetching OTP for {phone_number}',
                'phone_number': phone_number
            })
            
            # Auto-detect provider if not specified
            if not provider:
                provider = self._detect_provider()
            
            # Fetch OTP
            otp = self._fetch_otp(provider, phone_number, max_wait)
            
            if not otp:
                return self._create_result(
                    False,
                    error=f"No OTP found within {max_wait} seconds"
                )
            
            result = {
                'otp': otp,
                'phone_number': phone_number,
                'provider': provider
            }
            
            metadata = {
                'provider': provider,
                'poll_duration': max_wait,
                'timestamp': time.time()
            }
            
            self._emit_update('capability_complete', {
                'message': f'OTP retrieved: {otp}',
                'result': result
            })
            
            return self._create_result(True, result=result, metadata=metadata)
            
        except Exception as e:
            error_msg = f"OTP/SMS error: {str(e)}"
            self._emit_update('capability_error', {'error': error_msg})
            return self._create_result(False, error=error_msg)
    
    def _detect_provider(self) -> str:
        """Auto-detect OTP provider from configuration"""
        if self.twilio_account_sid and self.twilio_auth_token:
            return 'twilio'
        elif self.firebase_emulator_url:
            return 'firebase'
        else:
            return 'mock'
    
    def _fetch_otp(self, provider: str, phone_number: str, max_wait: int) -> Optional[str]:
        """Fetch OTP from provider"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                if provider == 'twilio':
                    otp = self._fetch_twilio_otp(phone_number)
                elif provider == 'firebase':
                    otp = self._fetch_firebase_otp(phone_number)
                else:
                    # Mock OTP for testing
                    otp = '123456'
                
                if otp:
                    return otp
                
            except Exception as e:
                print(f"Error fetching OTP: {e}")
            
            time.sleep(self.poll_interval)
            self._emit_update('capability_progress', {
                'message': f'Waiting for OTP... ({int(time.time() - start_time)}s)'
            })
        
        return None
    
    def _fetch_twilio_otp(self, phone_number: str) -> Optional[str]:
        """Fetch latest OTP from Twilio test account"""
        try:
            # Twilio API to fetch messages
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
            auth = (self.twilio_account_sid, self.twilio_auth_token)
            params = {
                'To': phone_number,
                'PageSize': 1  # Get most recent message
            }
            
            response = requests.get(url, auth=auth, params=params, timeout=5)
            if response.status_code == 200:
                messages = response.json().get('messages', [])
                if messages:
                    message_body = messages[0].get('body', '')
                    # Extract OTP (typically 4-8 digits)
                    otp_match = re.search(r'\b(\d{4,8})\b', message_body)
                    if otp_match:
                        return otp_match.group(1)
        except Exception as e:
            print(f"Twilio OTP fetch error: {e}")
        
        return None
    
    def _fetch_firebase_otp(self, phone_number: str) -> Optional[str]:
        """Fetch OTP from Firebase Auth Emulator"""
        try:
            # Firebase Auth Emulator stores verification codes in emulator UI
            # This would typically require querying the emulator's internal state
            # or using Firebase Admin SDK
            
            # For now, check if there's an API endpoint (varies by emulator version)
            response = requests.get(
                f"{self.firebase_emulator_url}/emulator/v1/projects/default/verificationCodes",
                timeout=5
            )
            if response.status_code == 200:
                codes = response.json()
                # Find code for this phone number
                for code_data in codes:
                    if code_data.get('phoneNumber') == phone_number:
                        return code_data.get('code')
        except Exception as e:
            print(f"Firebase OTP fetch error: {e}")
        
        return None


def fetch_otp(phone_number: str, provider: Optional[str] = None,
              max_wait: int = 60,
              on_update_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to fetch OTP
    
    Args:
        phone_number: Phone number to check
        provider: 'twilio', 'firebase', or None for auto-detect
        max_wait: Maximum seconds to wait
        on_update_callback: Optional callback for updates
        
    Returns:
        Result dict with OTP code
    """
    module = OTPSMSModule(None, on_update_callback)
    return module.execute({
        'phone_number': phone_number,
        'provider': provider,
        'max_wait': max_wait
    })

