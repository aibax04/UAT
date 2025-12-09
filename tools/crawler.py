import time
import os
from urllib.parse import urlparse, urljoin

def crawl_app(page, run_id, start_url=None, depth_limit=2, max_pages=20):
    """
    Crawl a web application starting from start_url
    
    Args:
        page: Playwright page object
        run_id: Database run ID for this crawl
        start_url: URL to start crawling from
        depth_limit: Maximum depth to crawl
        max_pages: Maximum number of pages to visit
    """
    visited = set()
    logs = []
    transitions = []
    
    
    if start_url:
        base_domain = urlparse(start_url).netloc
    else:
        base_domain = urlparse(page.url).netloc
    
    print(f"Crawling domain: {base_domain}")
    
    def is_same_domain(url):
        """Check if URL belongs to the same domain"""
        return urlparse(url).netloc == base_domain
    
    def crawl(url, depth):
        if depth > depth_limit or url in visited or len(visited) >= max_pages:
            return
        
        try:
            visited.add(url)
            print(f"  {'  ' * depth}Visiting [{depth}]: {url}")
            
            page.goto(url, wait_until="networkidle", timeout=10000)
            time.sleep(1.5)

            
            buttons = page.query_selector_all(
                "button, a, input[type='button'], input[type='submit'], [role='button']"
            )
            
            
            screenshot_path = f"screenshots/run_{run_id}_page_{len(visited)}.png"
            os.makedirs("screenshots", exist_ok=True)
            page.screenshot(path=screenshot_path, full_page=True)

            
            button_labels = []
            for b in buttons:
                try:
                    label = (b.inner_text() or 
                            b.get_attribute("aria-label") or 
                            b.get_attribute("title") or 
                            b.get_attribute("href") or 
                            "Unnamed")
                    button_labels.append(label.strip()[:50])  
                except:
                    button_labels.append("Unnamed")

            logs.append({
                "url": url,
                "buttons": button_labels,
                "screenshot": screenshot_path
            })

            
            click_count = 0
            max_clicks_per_page = 5
            
            for idx, btn in enumerate(buttons):
                if click_count >= max_clicks_per_page:
                    break
                    
                try:
                    label = button_labels[idx]
                    
                    
                    href = btn.get_attribute("href")
                    if href:
                        full_href = urljoin(url, href)
                        if not is_same_domain(full_href):
                            continue
                    
                    
                    if not btn.is_visible() or not btn.is_enabled():
                        continue
                    
                    current_url = page.url
                    
                    
                    btn.click(timeout=3000)
                    time.sleep(1)
                    click_count += 1

                    new_url = page.url
                    screenshot_path = f"screenshots/run_{run_id}_trans_{len(transitions)}.png"
                    page.screenshot(path=screenshot_path, full_page=True)

                    transitions.append({
                        "from": current_url,
                        "clicked": label,
                        "to": new_url,
                        "screenshot": screenshot_path,
                        "error": None
                    })

                    
                    if new_url not in visited and is_same_domain(new_url):
                        crawl(new_url, depth + 1)
                        
                        
                        try:
                            page.goto(current_url, timeout=5000)
                            time.sleep(1)
                        except:
                            break

                except Exception as e:
                    error_msg = str(e)[:200]
                    print(f"    Error clicking '{label}': {error_msg}")
                    transitions.append({
                        "from": url,
                        "clicked": label,
                        "to": url,
                        "screenshot": None,
                        "error": error_msg
                    })
                    
                    
                    try:
                        page.goto(url, timeout=5000)
                        time.sleep(1)
                    except:
                        break

        except Exception as e:
            print(f"    Error visiting {url}: {str(e)}")
    
    
    start = start_url or page.url
    crawl(start, 0)
    
    print(f"\n✓ Crawl summary: {len(visited)} pages, {len(transitions)} interactions")
    return logs, transitions