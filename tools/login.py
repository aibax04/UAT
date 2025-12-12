from db import get_db
import time

def get_credentials(app_name):
    """Fetch login credentials from database"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT login_url, username, password FROM credentials WHERE app_name=?",
            (app_name,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "login_url": row[0],
                "username": row[1],
                "password": row[2]
            }
        return None
    except Exception as e:
        print(f"Error fetching credentials: {e}")
        return None


def login_to_app(page, app_name: str):
    """
    Attempt to login to the application if credentials exist
    
    Args:
        page: Playwright page object
        app_name: Name of the app to login to
        
    Returns:
        bool: True if login successful or no credentials needed, False otherwise
    """
    creds = get_credentials(app_name)
    
    if not creds or not creds.get("login_url"):
        print(f"No credentials found for {app_name}, skipping login")
        return True
    
    try:
        print(f"Attempting login to {creds['login_url']}")
        # Navigate with optimized fallback for faster loading
        try:
            page.goto(creds["login_url"], wait_until="domcontentloaded", timeout=20000)  # Faster than networkidle
            time.sleep(1)  # Reduced from 2s
        except Exception as e:
            print(f"   Domcontentloaded timeout, trying load state...")
            try:
                page.goto(creds["login_url"], wait_until="load", timeout=15000)
                time.sleep(1)  # Reduced from 2s
            except Exception as e2:
                print(f"   Navigation error: {str(e2)[:100]}")
                # Last resort: try networkidle
                try:
                    page.goto(creds["login_url"], wait_until="networkidle", timeout=20000)
                    time.sleep(1)
                except:
                    print(f"   Failed to load login page, continuing anyway...")
        time.sleep(1)  # Reduced from 2s
        
        
        username_selectors = [
            "input[name='username']",
            "input[name='email']", 
            "input[type='email']",
            "input[id*='user']",
            "input[id*='email']",
            "#username",
            "#email"
        ]
        
        username_filled = False
        for selector in username_selectors:
            try:
                if page.is_visible(selector):
                    page.fill(selector, creds["username"])
                    username_filled = True
                    print(f"  ✓ Username filled using selector: {selector}")
                    break
            except:
                continue
        
        
        password_selectors = [
            "input[name='password']",
            "input[type='password']",
            "input[id*='pass']",
            "#password"
        ]
        
        password_filled = False
        for selector in password_selectors:
            try:
                if page.is_visible(selector):
                    page.fill(selector, creds["password"])
                    password_filled = True
                    print(f"  ✓ Password filled using selector: {selector}")
                    break
            except:
                continue
        
        
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "#login-button",
            ".login-button"
        ]
        
        if username_filled and password_filled:
            for selector in submit_selectors:
                try:
                    if page.is_visible(selector):
                        page.click(selector)
                        print(f"   Login button clicked")
                        time.sleep(3)
                        return True
                except:
                    continue
            
            
            try:
                page.press("input[type='password']", "Enter")
                print(f"  ✓ Submitted via Enter key")
                time.sleep(3)
                return True
            except:
                pass
        
        print("   Could not complete login form")
        return False
        
    except Exception as e:
        print(f"  Login error: {str(e)}")
        return False