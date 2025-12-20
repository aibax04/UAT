"""
Quick script to check email notification configuration and test email sending.
Run this to diagnose email notification issues.
"""

import os
from dotenv import load_dotenv
from email_notifier import get_email_notifier

load_dotenv()

def main():
    print("=" * 60)
    print("Email Notification Configuration Check")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Environment Variables:")
    smtp_host = os.getenv('SMTP_HOST', '')
    smtp_port = os.getenv('SMTP_PORT', '')
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    smtp_from = os.getenv('SMTP_FROM', '')
    
    print(f"  SMTP_HOST: {smtp_host or 'NOT SET (default: smtp.gmail.com)'}")
    print(f"  SMTP_PORT: {smtp_port or 'NOT SET (default: 587)'}")
    print(f"  SMTP_USER: {smtp_user or 'NOT SET ❌ REQUIRED'}")
    print(f"  SMTP_PASSWORD: {'***SET***' if smtp_password else 'NOT SET ❌ REQUIRED'}")
    print(f"  SMTP_FROM: {smtp_from or smtp_user or 'NOT SET (will use SMTP_USER)'}")
    print(f"  SMTP_USE_TLS: {os.getenv('SMTP_USE_TLS', 'true (default)')}")
    
    # Check notifier
    print("\n2. Email Notifier Status:")
    notifier = get_email_notifier()
    print(f"  Configured: {notifier.is_configured}")
    
    if not notifier.is_configured:
        print("\n⚠️  Email notifier is NOT configured!")
        print("\nTo fix this, add to your .env file:")
        print("  SMTP_HOST=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USER=your-email@gmail.com")
        print("  SMTP_PASSWORD=your-app-password")
        print("  SMTP_FROM=your-email@gmail.com")
        print("  SMTP_USE_TLS=true")
        return
    
    # Test email sending
    print("\n3. Test Email Sending:")
    test_email = input("  Enter test email address: ").strip()
    
    if not test_email:
        print("  No email provided, skipping test")
        return
    
    print(f"  Sending test email to {test_email}...")
    
    summary = {
        'site_url': 'https://example.com',
        'task_description': 'Test email notification from configuration checker',
        'status': 'success',
        'execution_time': '2024-01-01T12:00:00Z',
        'duration': '1m 23s'
    }
    
    success = notifier.send_test_notification(test_email, summary, 'success')
    
    if success:
        print("  ✅ Test email sent successfully!")
        print(f"  Check {test_email} inbox for the test email")
    else:
        print("  ❌ Failed to send test email")
        print("  Check server logs for detailed error messages")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()

