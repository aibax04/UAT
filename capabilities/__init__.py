"""
Enterprise Automation Capabilities Module
==========================================

Additive, modular capabilities for advanced automation scenarios.
All modules are optional and invoked only when relevant.

Modules:
- Form Intelligence: Dynamic form detection and filling
- Payment Gateway Handler: Payment flow automation
- Email Verification: Email artifact extraction
- OTP/SMS: OTP retrieval from virtual providers
- Backend Verification: API-level state validation
"""

from .form_intelligence import FormIntelligenceModule
from .payment_handler import PaymentGatewayHandler
from .email_verification import EmailVerificationModule
from .otp_sms import OTPSMSModule
from .backend_verification import BackendVerificationModule
from .capability_router import CapabilityRouter

__all__ = [
    'FormIntelligenceModule',
    'PaymentGatewayHandler',
    'EmailVerificationModule',
    'OTPSMSModule',
    'BackendVerificationModule',
    'CapabilityRouter'
]

