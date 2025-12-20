# Enterprise Automation Capabilities

This module provides **additive, modular capabilities** for advanced automation scenarios. All modules are **optional** and **non-breaking** - existing functionality continues to work unchanged.

## Architecture

- **Base Module Interface**: All capability modules extend `BaseCapabilityModule`
- **Capability Router**: Routes tasks to appropriate modules based on intent detection
- **Non-Intrusive Integration**: Only activates when a module can handle a task

## Modules

### 1. Form Intelligence Module
- **Purpose**: Dynamically detect and intelligently fill forms
- **Features**:
  - Semantic form schema detection (labels, placeholders, ARIA, names)
  - LLM-powered contextual field filling (email, password, phone, address)
  - Rule-based fallback when LLM unavailable
- **Usage**: Add `"capability": "form_intelligence"` to task or use form-related keywords

### 2. Payment Gateway Handler
- **Purpose**: Handle payment flows in test/sandbox mode
- **Features**:
  - Auto-detect payment gateways (Stripe, Razorpay, PayPal, Square)
  - Use known test credentials/cards
  - Safe iframe handling
- **Usage**: Add `"capability": "payment"` or use payment-related keywords

### 3. Email Verification Module
- **Purpose**: Fetch emails and extract OTPs, links, confirmation text
- **Features**:
  - Integration with MailHog, Mailtrap, AWS SES sandbox
  - Poll for new emails triggered by UI actions
  - Extract artifacts (OTP, verification links, confirmation messages)
- **Usage**: Add `"capability": "email_verification"` or use email-related keywords

### 4. OTP/SMS Module
- **Purpose**: Fetch OTPs from virtual providers
- **Features**:
  - Integration with Twilio test, Firebase Auth Emulator
  - Poll for OTP codes
- **Usage**: Add `"capability": "otp_sms"` or use OTP/SMS-related keywords

### 5. Backend Verification Module
- **Purpose**: API-level assertions after UI actions
- **Features**:
  - Verify order status, user creation, payment success
  - JSONPath-based assertions
  - Multiple assertion operators (equals, contains, exists, etc.)
- **Usage**: Add `"capability": "backend_verification"` with `assertion_config`

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Form Intelligence (optional - uses rule-based if not set)
GEMINI_API_KEY=your_gemini_api_key

# Email Verification (choose one service)
MAILHOG_URL=http://localhost:8025
# OR
MAILTRAP_API_TOKEN=your_token
MAILTRAP_INBOX_ID=your_inbox_id
# OR
AWS_SES_ENDPOINT=your_ses_endpoint

# OTP/SMS (choose one provider)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_TEST_NUMBER=+1234567890
# OR
FIREBASE_EMULATOR_URL=http://localhost:9099

# Payment Gateways (optional)
PAYPAL_SANDBOX_EMAIL=test@example.com
PAYPAL_SANDBOX_PASSWORD=test123

# Backend Verification
BACKEND_API_URL=https://api.example.com
BACKEND_API_KEY=your_api_key
```

## Usage Examples

### Form Filling
```python
task = {
    "name": "Fill registration form",
    "action_type": "form",
    "description": "Fill in user registration form with test data",
    "capability": "form_intelligence",
    "intent": "Register new user with email test@example.com and name John Doe"
}
```

### Payment Processing
```python
task = {
    "name": "Process test payment",
    "action_type": "payment",
    "description": "Complete checkout with test payment",
    "capability": "payment",
    "gateway_type": "stripe"  # or "razorpay", "paypal", etc.
}
```

### Email OTP Extraction
```python
task = {
    "name": "Get email verification code",
    "action_type": "email",
    "description": "Fetch OTP from email",
    "capability": "email_verification",
    "email_type": "otp",
    "recipient_email": "test@example.com",
    "subject_filter": "verification"
}
```

### OTP from SMS
```python
task = {
    "name": "Get SMS OTP",
    "action_type": "otp",
    "description": "Fetch OTP from SMS",
    "capability": "otp_sms",
    "phone_number": "+1234567890",
    "provider": "twilio"
}
```

### Backend Verification
```python
task = {
    "name": "Verify order creation",
    "action_type": "verify",
    "description": "Check that order was created in backend",
    "capability": "backend_verification",
    "assertion_config": {
        "endpoint": "/api/orders/latest",
        "method": "GET",
        "auth_type": "bearer",
        "auth_value": "token_here",
        "assertions": [
            {
                "path": "data.status",
                "operator": "equals",
                "expected": "confirmed"
            },
            {
                "path": "data.total",
                "operator": "greater_than",
                "expected": 0
            }
        ]
    }
}
```

## Integration Flow

1. Task arrives at `BrowserSessionManager.execute_action()`
2. Task is queued for browser thread execution
3. Capability router checks if any module can handle the task
4. If yes: Module executes and returns result
5. If no: Standard execution continues (existing logic unchanged)

## Observability

All capability modules:
- Emit real-time execution updates via callback
- Support screenshot capture
- Return structured success/failure results
- Include execution metadata in results

Update types emitted:
- `capability_start`: Module execution started
- `capability_progress`: Progress update
- `capability_complete`: Module execution completed successfully
- `capability_error`: Module execution failed

## Non-Breaking Design

✅ **No changes to existing function signatures**
✅ **Existing crawl and task execution continue unchanged**
✅ **Modules only activate when explicitly requested or detected**
✅ **Graceful fallback to standard execution if module unavailable**

