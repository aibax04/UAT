"""
Payment Gateway Handler Module
===============================

Detects and handles common payment gateways (Stripe, Razorpay, PayPal, etc.)
in test/sandbox mode using known test credentials.
"""

import os
import time
from typing import Dict, Any, Optional, Callable
from playwright.sync_api import Page
from dotenv import load_dotenv

from .base_module import BaseCapabilityModule

load_dotenv()

# Test card credentials for common gateways
TEST_CARDS = {
    'stripe': {
        'number': '4242424242424242',
        'cvc': '123',
        'expiry_month': '12',
        'expiry_year': '2025',
        'zip': '12345'
    },
    'razorpay': {
        'number': '4111111111111111',
        'cvc': '123',
        'expiry_month': '12',
        'expiry_year': '2025',
        'name': 'Test User'
    },
    'paypal': {
        'sandbox_email': os.getenv('PAYPAL_SANDBOX_EMAIL', 'test@example.com'),
        'sandbox_password': os.getenv('PAYPAL_SANDBOX_PASSWORD', 'test123')
    },
    'square': {
        'number': '4111111111111111',
        'cvc': '123',
        'expiry_month': '12',
        'expiry_year': '2025',
        'zip': '94103'
    }
}


class PaymentGatewayHandler(BaseCapabilityModule):
    """Handle payment gateway flows in test mode"""
    
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """Check if this is a payment-related task"""
        action_type = intent_data.get('action_type', '')
        description = intent_data.get('description', '').lower()
        task_name = intent_data.get('task_name', '').lower()
        url = intent_data.get('url', '').lower()
        
        payment_keywords = ['payment', 'pay', 'checkout', 'stripe', 'razorpay', 'paypal', 'card', 'billing']
        gateway_type = intent_data.get('gateway_type', '').lower()
        
        return (action_type == 'payment' or
                gateway_type or
                any(keyword in description or keyword in task_name or keyword in url 
                    for keyword in payment_keywords) or
                intent_data.get('capability') == 'payment')
    
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute payment flow in test mode
        
        Args:
            intent_data: Must contain 'gateway_type' (stripe/razorpay/paypal/etc)
                        and optional 'test_card' to override defaults
            
        Returns:
            Result dict with payment completion status
        """
        try:
            gateway_type = intent_data.get('gateway_type', '').lower()
            if not gateway_type:
                # Auto-detect gateway
                gateway_type = self._detect_gateway()
            
            if not gateway_type:
                return self._create_result(
                    False,
                    error="Could not detect payment gateway type"
                )
            
            self._emit_update('capability_start', {
                'message': f'Processing payment via {gateway_type}',
                'gateway': gateway_type
            })
            
            # Switch to test/sandbox mode if possible
            self._enable_test_mode(gateway_type)
            
            # Handle payment flow based on gateway type
            result = None
            if gateway_type == 'stripe':
                result = self._handle_stripe(intent_data)
            elif gateway_type == 'razorpay':
                result = self._handle_razorpay(intent_data)
            elif gateway_type == 'paypal':
                result = self._handle_paypal(intent_data)
            elif gateway_type == 'square':
                result = self._handle_square(intent_data)
            else:
                result = self._handle_generic(intent_data)
            
            screenshot = self._capture_screenshot("After payment processing")
            
            metadata = {
                'gateway_type': gateway_type,
                'test_mode': True,
                'timestamp': time.time()
            }
            
            if result and result.get('success'):
                self._emit_update('capability_complete', {
                    'message': f'Payment processed successfully via {gateway_type}',
                    'result': result
                })
            
            return self._create_result(
                result.get('success', False) if result else False,
                result=result,
                metadata=metadata,
                error=result.get('error') if result else None
            )
            
        except Exception as e:
            error_msg = f"Payment processing error: {str(e)}"
            self._emit_update('capability_error', {'error': error_msg})
            return self._create_result(False, error=error_msg)
    
    def _detect_gateway(self) -> Optional[str]:
        """Auto-detect payment gateway from page content"""
        try:
            page_content = self.page.content().lower()
            page_url = self.page.url.lower()
            
            if 'stripe.com' in page_url or 'js.stripe.com' in page_content:
                return 'stripe'
            elif 'razorpay.com' in page_url or 'razorpay' in page_content:
                return 'razorpay'
            elif 'paypal.com' in page_url or 'paypal' in page_content:
                return 'paypal'
            elif 'square.com' in page_url or 'square' in page_content:
                return 'square'
            
            return None
        except:
            return None
    
    def _enable_test_mode(self, gateway_type: str):
        """Attempt to enable test/sandbox mode"""
        try:
            # Some gateways have test mode switches in UI or URL params
            current_url = self.page.url
            if 'test' not in current_url.lower() and 'sandbox' not in current_url.lower():
                # Try to add test mode parameter (varies by gateway)
                if gateway_type == 'stripe':
                    # Stripe test mode is usually automatic with test keys
                    pass
                elif gateway_type == 'razorpay':
                    # Razorpay test mode handled via API keys
                    pass
        except:
            pass
    
    def _handle_stripe(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe payment flow"""
        try:
            card_data = intent_data.get('test_card') or TEST_CARDS['stripe']
            
            # Stripe Elements are typically in iframes
            # Try to fill Stripe card fields
            stripe_selectors = {
                'card_number': ['input[name="cardnumber"]', '[data-stripe="number"]', '#cardnumber'],
                'expiry': ['input[name="exp-date"]', '[data-stripe="exp"]', '#exp-date'],
                'cvc': ['input[name="cvc"]', '[data-stripe="cvc"]', '#cvc'],
                'zip': ['input[name="postal"]', '[data-stripe="postal"]', '#postal']
            }
            
            # Fill card number (usually in iframe)
            self._fill_in_iframe(stripe_selectors['card_number'], card_data['number'])
            time.sleep(0.5)
            
            # Fill expiry
            self._fill_in_iframe(stripe_selectors['expiry'], 
                                f"{card_data['expiry_month']}{card_data['expiry_year'][-2:]}")
            time.sleep(0.5)
            
            # Fill CVC
            self._fill_in_iframe(stripe_selectors['cvc'], card_data['cvc'])
            time.sleep(0.5)
            
            # Fill ZIP if present
            if 'zip' in card_data:
                self._fill_in_iframe(stripe_selectors['zip'], card_data['zip'])
            
            return {'success': True, 'gateway': 'stripe', 'method': 'test_card'}
            
        except Exception as e:
            return {'success': False, 'error': f"Stripe handling failed: {str(e)}"}
    
    def _handle_razorpay(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Razorpay payment flow"""
        try:
            card_data = intent_data.get('test_card') or TEST_CARDS['razorpay']
            
            # Razorpay fields (may be in iframe)
            self._fill_in_iframe(['input[name="cardnumber"]', '#card-number'], card_data['number'])
            time.sleep(0.5)
            
            self._fill_in_iframe(['input[name="expiry"]', '#expiry'], 
                                f"{card_data['expiry_month']}/{card_data['expiry_year']}")
            time.sleep(0.5)
            
            self._fill_in_iframe(['input[name="cvv"]', '#cvv'], card_data['cvc'])
            
            return {'success': True, 'gateway': 'razorpay', 'method': 'test_card'}
            
        except Exception as e:
            return {'success': False, 'error': f"Razorpay handling failed: {str(e)}"}
    
    def _handle_paypal(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PayPal payment flow"""
        try:
            # PayPal sandbox credentials
            email = intent_data.get('paypal_email') or TEST_CARDS['paypal']['sandbox_email']
            password = intent_data.get('paypal_password') or TEST_CARDS['paypal']['sandbox_password']
            
            # Fill PayPal login if present
            email_selector = self.page.locator('input[type="email"], input[name="email"], #email').first
            if email_selector.is_visible():
                email_selector.fill(email)
                time.sleep(0.5)
                
                password_selector = self.page.locator('input[type="password"], input[name="password"], #password').first
                if password_selector.is_visible():
                    password_selector.fill(password)
                    time.sleep(0.5)
                    
                    # Click login/continue
                    submit = self.page.locator('button:has-text("Log In"), button:has-text("Continue"), #btnLogin').first
                    if submit.is_visible():
                        submit.click()
                        time.sleep(2)  # Wait for PayPal redirect
            
            return {'success': True, 'gateway': 'paypal', 'method': 'sandbox_login'}
            
        except Exception as e:
            return {'success': False, 'error': f"PayPal handling failed: {str(e)}"}
    
    def _handle_square(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Square payment flow"""
        try:
            card_data = intent_data.get('test_card') or TEST_CARDS['square']
            
            # Square uses similar iframe structure
            self._fill_in_iframe(['input[name="sq-card-number"]'], card_data['number'])
            time.sleep(0.5)
            
            self._fill_in_iframe(['input[name="sq-expiration-date"]'], 
                                f"{card_data['expiry_month']}{card_data['expiry_year'][-2:]}")
            time.sleep(0.5)
            
            self._fill_in_iframe(['input[name="sq-cvv"]'], card_data['cvc'])
            time.sleep(0.5)
            
            self._fill_in_iframe(['input[name="sq-postal-code"]'], card_data['zip'])
            
            return {'success': True, 'gateway': 'square', 'method': 'test_card'}
            
        except Exception as e:
            return {'success': False, 'error': f"Square handling failed: {str(e)}"}
    
    def _handle_generic(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic payment form"""
        try:
            card_data = intent_data.get('test_card') or TEST_CARDS['stripe']
            
            # Try common field patterns
            card_number_selectors = [
                'input[name*="card"][name*="number"]',
                'input[id*="card"][id*="number"]',
                '#card-number',
                'input[placeholder*="card"]'
            ]
            
            for selector in card_number_selectors:
                try:
                    if self.page.locator(selector).first.is_visible():
                        self.page.fill(selector, card_data['number'])
                        break
                except:
                    continue
            
            return {'success': True, 'gateway': 'generic', 'method': 'generic_fill'}
            
        except Exception as e:
            return {'success': False, 'error': f"Generic payment handling failed: {str(e)}"}
    
    def _fill_in_iframe(self, selectors: list, value: str):
        """Fill a field that may be inside an iframe"""
        # Try main page first
        for selector in selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible():
                    element.fill(value)
                    return
            except:
                continue
        
        # Try iframes
        try:
            iframes = self.page.frames
            for iframe in iframes:
                for selector in selectors:
                    try:
                        element = iframe.locator(selector).first
                        if element.is_visible():
                            element.fill(value)
                            return
                    except:
                        continue
        except:
            pass


def execute_test_payment(page: Page, gateway_type: str, 
                         test_card: Optional[Dict[str, Any]] = None,
                         on_update_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to execute test payment
    
    Args:
        page: Playwright page object
        gateway_type: 'stripe', 'razorpay', 'paypal', 'square', or None for auto-detect
        test_card: Optional custom test card data
        on_update_callback: Optional callback for updates
        
    Returns:
        Result dict with payment status
    """
    module = PaymentGatewayHandler(page, on_update_callback)
    return module.execute({
        'gateway_type': gateway_type,
        'test_card': test_card
    })

