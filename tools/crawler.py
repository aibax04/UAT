import time
import os
from urllib.parse import urlparse, urljoin
from collections import deque
import random

def crawl_app(page, run_id, start_url=None, depth_limit=10, max_pages=None):
    """
    Enhanced crawler for web applications with better navigation and element discovery
    
    Args:
        page: Playwright page object
        run_id: Database run ID for this crawl
        start_url: URL to start crawling from
        depth_limit: Maximum depth to crawl (default: 10)
        max_pages: Maximum number of pages to visit (None = unlimited)
    """
    visited = set()
    logs = []
    transitions = []
    url_queue = deque()  # Queue-based approach for better crawling
    url_visit_count = {}  # Track how many times we've seen similar URLs (loop detection)
    skipped_loops = set()  # URLs we've skipped due to loops
    
    if start_url:
        base_domain = urlparse(start_url).netloc
    else:
        base_domain = urlparse(page.url).netloc
    
    print(f"Crawling domain: {base_domain}")
    
    def is_same_domain(url):
        """Check if URL belongs to the same domain"""
        parsed = urlparse(url)
        return parsed.netloc == base_domain or parsed.netloc == ""
    
    def normalize_url(url):
        """Normalize URL by removing fragments and query params for comparison"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def wait_for_page_load(timeout=15000):
        """Wait for page to be fully loaded"""
        try:
            # Wait for network to be idle
            page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            try:
                # Fallback to domcontentloaded
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass
        # Additional wait for dynamic content
        time.sleep(0.5)
    
    def find_clickable_elements():
        """Find all clickable elements on the page"""
        elements = []
        
        # Find all links
        links = page.query_selector_all("a[href]")
        for link in links:
            try:
                if link.is_visible():
                    href = link.get_attribute("href")
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        elements.append({
                            'element': link,
                            'type': 'link',
                            'href': href
                        })
            except:
                continue
        
        # Find all buttons
        buttons = page.query_selector_all(
            "button, input[type='button'], input[type='submit'], [role='button']"
        )
        for btn in buttons:
            try:
                if btn.is_visible() and btn.is_enabled():
                    elements.append({
                        'element': btn,
                        'type': 'button',
                        'href': None
                    })
            except:
                continue
        
        # Find clickable divs/spans with onclick or data attributes
        clickable_divs = page.query_selector_all(
            "[onclick], [data-href], [data-url], [data-link], .clickable, [class*='click'], [class*='link']"
        )
        for div in clickable_divs:
            try:
                if div.is_visible():
                    href = (div.get_attribute("data-href") or 
                           div.get_attribute("data-url") or 
                           div.get_attribute("data-link"))
                    elements.append({
                        'element': div,
                        'type': 'div',
                        'href': href
                    })
            except:
                continue
        
        # Shuffle to explore different paths
        random.shuffle(elements)
        return elements
    
    def get_element_label(element):
        """Extract label/text from an element"""
        try:
            # Try multiple methods to get label
            label = (element.inner_text() or 
                    element.get_attribute("aria-label") or 
                    element.get_attribute("title") or 
                    element.get_attribute("alt") or
                    element.get_attribute("data-label") or
                    element.get_attribute("href") or
                    element.get_attribute("name") or
                    element.get_attribute("value") or
                    "Unnamed")
            return label.strip()[:100] if label else "Unnamed"
        except:
            return "Unnamed"
    
    def visit_url(url, depth):
        """Visit a URL and collect data"""
        if depth > depth_limit:
            return False
        
        # Check max_pages limit if set
        if max_pages and len(visited) >= max_pages:
            return False
        
        normalized = normalize_url(url)
        
        # Loop detection: if we've visited this URL pattern too many times, skip it
        if normalized in url_visit_count:
            url_visit_count[normalized] += 1
            if url_visit_count[normalized] > 3:  # Skip if visited more than 3 times
                if normalized not in skipped_loops:
                    print(f"    ⚠ Skipping potential loop: {url} (visited {url_visit_count[normalized]} times)")
                    skipped_loops.add(normalized)
                return False
        else:
            url_visit_count[normalized] = 1
        
        if normalized in visited:
            return False
        
        try:
            visited.add(normalized)
            print(f"  {'  ' * depth}Visiting [{depth}]: {url}")
            
            # Navigate to URL with better error handling
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                wait_for_page_load()
            except Exception as e:
                print(f"    Navigation error: {str(e)[:100]}")
                return False
            
            # Take screenshot
            screenshot_path = f"screenshots/run_{run_id}_page_{len(visited)}.png"
            os.makedirs("screenshots", exist_ok=True)
            try:
                page.screenshot(path=screenshot_path, full_page=True)
            except:
                pass
            
            # Find all clickable elements
            clickable_elements = find_clickable_elements()
            
            # Extract button/link labels
            element_labels = [get_element_label(elem['element']) for elem in clickable_elements]
            
            logs.append({
                "url": url,
                "buttons": element_labels,
                "screenshot": screenshot_path,
                "element_count": len(clickable_elements)
            })
            
            # Try to click/interact with elements - prioritize unique URLs
            click_count = 0
            # Higher limit to crawl more elements, but not unlimited to avoid issues
            max_clicks_per_page = min(50, len(clickable_elements))  # Up to 50 clicks per page
            
            # Sort elements: prioritize links with unique URLs
            elements_with_urls = []
            elements_without_urls = []
            seen_urls = set()
            
            for elem_data in clickable_elements:
                if elem_data['type'] == 'link' and elem_data['href']:
                    full_href = urljoin(url, elem_data['href'])
                    normalized_href = normalize_url(full_href)
                    if normalized_href not in seen_urls and is_same_domain(full_href):
                        elements_with_urls.append(elem_data)
                        seen_urls.add(normalized_href)
                else:
                    elements_without_urls.append(elem_data)
            
            # Prioritize elements with unique URLs first
            prioritized_elements = elements_with_urls + elements_without_urls
            
            for elem_data in prioritized_elements[:max_clicks_per_page]:
                # Check max_pages limit if set
                if max_pages and len(visited) >= max_pages:
                    break
                
                try:
                    element = elem_data['element']
                    elem_type = elem_data['type']
                    href = elem_data['href']
                    label = get_element_label(element)
                    
                    # Skip if element is no longer visible
                    if not element.is_visible():
                        continue
                    
                    # Handle links differently
                    if elem_type == 'link' and href:
                        full_href = urljoin(url, href)
                        normalized_href = normalize_url(full_href)
                        
                        # Skip external links and already visited
                        if not is_same_domain(full_href) or normalized_href in visited:
                            continue
                        
                        current_url = page.url
                        
                        # Click the link
                        try:
                            element.click(timeout=5000)
                            wait_for_page_load(timeout=10000)
                        except:
                            # Try programmatic navigation
                            try:
                                page.goto(full_href, wait_until="domcontentloaded", timeout=15000)
                                wait_for_page_load()
                            except:
                                continue
                        
                        new_url = page.url
                        normalized_new = normalize_url(new_url)
                        
                        # Take screenshot of transition
                        trans_screenshot = f"screenshots/run_{run_id}_trans_{len(transitions)}.png"
                        try:
                            page.screenshot(path=trans_screenshot, full_page=True)
                        except:
                            trans_screenshot = None
                        
                        transitions.append({
                            "from": current_url,
                            "clicked": label,
                            "to": new_url,
                            "screenshot": trans_screenshot,
                            "error": None
                        })
                        
                        # Add to queue if not visited
                        if normalized_new not in visited and is_same_domain(new_url):
                            url_queue.append((new_url, depth + 1))
                            click_count += 1
                    
                    # Handle buttons and other clickable elements
                    elif elem_type in ['button', 'div']:
                        current_url = page.url
                        
                        try:
                            # Scroll element into view
                            element.scroll_into_view_if_needed()
                            time.sleep(0.3)
                            
                            # Click the element
                            element.click(timeout=5000)
                            wait_for_page_load(timeout=8000)
                            
                            new_url = page.url
                            normalized_new = normalize_url(new_url)
                            
                            # Only count if URL changed or significant interaction
                            if new_url != current_url or normalized_new not in visited:
                                trans_screenshot = f"screenshots/run_{run_id}_trans_{len(transitions)}.png"
                                try:
                                    page.screenshot(path=trans_screenshot, full_page=True)
                                except:
                                    trans_screenshot = None
                                
                                transitions.append({
                                    "from": current_url,
                                    "clicked": label,
                                    "to": new_url,
                                    "screenshot": trans_screenshot,
                                    "error": None
                                })
                                
                                # Add to queue if new page
                                if normalized_new not in visited and is_same_domain(new_url) and new_url != current_url:
                                    url_queue.append((new_url, depth + 1))
                                    click_count += 1
                        except Exception as e:
                            error_msg = str(e)[:200]
                            transitions.append({
                                "from": current_url,
                                "clicked": label,
                                "to": current_url,
                                "screenshot": None,
                                "error": error_msg
                            })
                            continue
                
                except Exception as e:
                    error_msg = str(e)[:200]
                    print(f"    Error interacting with element: {error_msg[:50]}")
                    continue
            
            return True
            
        except Exception as e:
            print(f"    Error visiting {url}: {str(e)[:100]}")
            return False
    
    # Start crawling
    start = start_url or page.url
    url_queue.append((start, 0))
    
    # Process queue - continue until queue is empty or no new pages found
    consecutive_no_new = 0
    max_consecutive_no_new = 5  # Stop if no new pages found after 5 attempts
    
    while url_queue:
        # Check if we should stop (max_pages limit)
        if max_pages and len(visited) >= max_pages:
            print(f"  Reached max_pages limit ({max_pages})")
            break
        
        url, depth = url_queue.popleft()
        pages_before = len(visited)
        
        if visit_url(url, depth):
            # Small delay between pages
            time.sleep(0.5)
            
            # Reset counter if we found a new page
            if len(visited) > pages_before:
                consecutive_no_new = 0
            else:
                consecutive_no_new += 1
        else:
            consecutive_no_new += 1
        
        # Stop if we haven't found new pages in a while
        if consecutive_no_new >= max_consecutive_no_new and not url_queue:
            print(f"  No new pages found after {max_consecutive_no_new} attempts, stopping crawl")
            break
        
        # Safety check: if queue is getting too large, we might be in a loop
        if len(url_queue) > 1000:
            print(f"  ⚠ Queue size exceeded 1000, stopping to prevent infinite loop")
            break
    
    print(f"\n✓ Crawl summary: {len(visited)} pages, {len(transitions)} interactions")
    if skipped_loops:
        print(f"  ⚠ Skipped {len(skipped_loops)} URLs due to potential loops")
    return logs, transitions
