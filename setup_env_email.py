"""
Helper script to add SMTP email configuration to .env file
"""

import os
import sys

def setup_email_config():
    env_file = '.env'
    
    # Check if .env exists
    if not os.path.exists(env_file):
        print(f"Creating {env_file} file...")
        with open(env_file, 'w') as f:
            f.write('')
    
    # Read existing content
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Check if SMTP config already exists
    if 'SMTP_HOST' in content:
        print("SMTP configuration already exists in .env file")
        print("\nCurrent SMTP configuration:")
        for line in content.split('\n'):
            if line.strip().startswith('SMTP_'):
                print(f"  {line.strip()}")
        
        response = input("\nDo you want to update it? (y/n): ").strip().lower()
        if response != 'y':
            print("Exiting...")
            return
        
        # Remove existing SMTP lines
        lines = content.split('\n')
        lines = [line for line in lines if not line.strip().startswith('SMTP_')]
        content = '\n'.join(lines)
    
    print("\n" + "=" * 60)
    print("SMTP Email Configuration Setup")
    print("=" * 60)
    print("\nEnter your SMTP configuration:")
    print("(Press Enter to use default values shown in brackets)")
    
    smtp_host = input("\nSMTP Host [smtp.gmail.com]: ").strip() or 'smtp.gmail.com'
    smtp_port = input("SMTP Port [587]: ").strip() or '587'
    smtp_user = input("SMTP Username (your email): ").strip()
    smtp_password = input("SMTP Password/App Password: ").strip()
    smtp_from = input(f"From Email Address [{smtp_user}]: ").strip() or smtp_user
    smtp_use_tls = input("Use TLS? (yes/no) [yes]: ").strip().lower() or 'yes'
    
    if not smtp_user or not smtp_password:
        print("\n❌ Error: SMTP Username and Password are required!")
        sys.exit(1)
    
    # Add SMTP configuration
    smtp_config = f"""
# Email Notification Configuration
SMTP_HOST={smtp_host}
SMTP_PORT={smtp_port}
SMTP_USER={smtp_user}
SMTP_PASSWORD={smtp_password}
SMTP_FROM={smtp_from}
SMTP_USE_TLS={smtp_use_tls}
"""
    
    # Append to .env file
    with open(env_file, 'a') as f:
        f.write(smtp_config)
    
    print("\n✅ SMTP configuration added to .env file!")
    print("\n" + "=" * 60)
    print("Configuration Summary:")
    print("=" * 60)
    print(f"  SMTP_HOST={smtp_host}")
    print(f"  SMTP_PORT={smtp_port}")
    print(f"  SMTP_USER={smtp_user}")
    print(f"  SMTP_PASSWORD={'***' * len(smtp_password)}")
    print(f"  SMTP_FROM={smtp_from}")
    print(f"  SMTP_USE_TLS={smtp_use_tls}")
    print("\n⚠️  Important: Restart your Flask app for changes to take effect!")
    print("\n📧 To test email configuration, run: python check_email_config.py")

if __name__ == '__main__':
    try:
        setup_email_config()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

