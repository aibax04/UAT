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
        seen_elements = set()  # Track by element handle to avoid duplicates
        
        # Find all links (including those without href but with onclick)
        links = page.query_selector_all("a[href], a[onclick], a[data-href]")
        for link in links:
            try:
                if link.is_visible():
                    # Get href from various attributes
                    href = (link.get_attribute("href") or 
                           link.get_attribute("data-href") or
                           link.get_attribute("data-url"))
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        elem_id = id(link)
                        if elem_id not in seen_elements:
                            seen_elements.add(elem_id)
                            elements.append({
                                'element': link,
                                'type': 'link',
                                'href': href
                            })
            except:
                continue
        
        # Find all buttons and form inputs
        buttons = page.query_selector_all(
            "button, input[type='button'], input[type='submit'], input[type='reset'], [role='button'], [type='button']"
        )
        for btn in buttons:
            try:
                if btn.is_visible() and btn.is_enabled():
                    elem_id = id(btn)
                    if elem_id not in seen_elements:
                        seen_elements.add(elem_id)
                        elements.append({
                            'element': btn,
                            'type': 'button',
                            'href': None
                        })
            except:
                continue
        
        # Find clickable divs/spans with onclick or data attributes
        clickable_divs = page.query_selector_all(
            "[onclick], [data-href], [data-url], [data-link], [data-action], [data-target], .clickable, [class*='click'], [class*='link'], [class*='button'], [tabindex='0']"
        )
        for div in clickable_divs:
            try:
                if div.is_visible():
                    href = (div.get_attribute("data-href") or 
                           div.get_attribute("data-url") or 
                           div.get_attribute("data-link") or
                           div.get_attribute("data-action"))
                    elem_id = id(div)
                    if elem_id not in seen_elements:
                        seen_elements.add(elem_id)
                        elements.append({
                            'element': div,
                            'type': 'div',
                            'href': href
                        })
            except:
                continue
        
        # Find select dropdowns
        selects = page.query_selector_all("select")
        for sel in selects:
            try:
                if sel.is_visible() and sel.is_enabled():
                    elem_id = id(sel)
                    if elem_id not in seen_elements:
                        seen_elements.add(elem_id)
                        elements.append({
                            'element': sel,
                            'type': 'select',
                            'href': None
                        })
            except:
                continue
        
        # Find checkboxes and radio buttons
        checkboxes = page.query_selector_all("input[type='checkbox'], input[type='radio']")
        for cb in checkboxes:
            try:
                if cb.is_visible() and cb.is_enabled():
                    elem_id = id(cb)
                    if elem_id not in seen_elements:
                        seen_elements.add(elem_id)
                        elements.append({
                            'element': cb,
                            'type': 'checkbox',
                            'href': None
                        })
            except:
                continue
        
        print(f"    Discovered {len(elements)} total clickable elements")
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
            
            # Click ALL elements on the page - no limit
            click_count = 0
            page_transitions = []  # Track transitions for this page
            processed_elements = set()  # Track processed elements to avoid duplicates
            
            # Initialize log entry (will be updated with click_count later)
            log_entry = {
                "url": url,
                "buttons": element_labels,
                "screenshot": screenshot_path,
                "element_count": len(clickable_elements),
                "click_count": 0,
                "transitions_count": 0
            }
            logs.append(log_entry)
            
            # Sort elements: prioritize links with unique URLs, but process ALL elements
            elements_with_urls = []
            elements_without_urls = []
            seen_urls = set()
            
            for elem_data in clickable_elements:
                # Create unique identifier for element
                try:
                    elem_id = f"{elem_data['type']}_{get_element_label(elem_data['element'])}"
                    if elem_id in processed_elements:
                        continue
                    processed_elements.add(elem_id)
                except:
                    pass
                
                if elem_data['type'] == 'link' and elem_data['href']:
                    full_href = urljoin(url, elem_data['href'])
                    normalized_href = normalize_url(full_href)
                    if normalized_href not in seen_urls and is_same_domain(full_href):
                        elements_with_urls.append(elem_data)
                        seen_urls.add(normalized_href)
                else:
                    elements_without_urls.append(elem_data)
            
            # Prioritize elements with unique URLs first, but process ALL
            prioritized_elements = elements_with_urls + elements_without_urls
            
            print(f"    Found {len(prioritized_elements)} clickable elements, processing all...")
            
            # Process ALL elements, not just a limited subset
            elements_processed = 0
            for elem_data in prioritized_elements:
                elements_processed += 1
                if elements_processed % 10 == 0:
                    print(f"    Processed {elements_processed}/{len(prioritized_elements)} elements...")
                # Check max_pages limit if set (only for new page navigation)
                if max_pages and len(visited) >= max_pages:
                    # Still process buttons that don't navigate, just don't add new pages
                    if elem_data['type'] != 'link' or not elem_data.get('href'):
                        pass  # Continue processing non-navigation elements
                    else:
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
                        
                        # Skip external links
                        if not is_same_domain(full_href):
                            continue
                        
                        # Still click and record even if visited (for interaction tracking)
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
                                # Still record the attempt - ALWAYS record transitions
                                transition_data = {
                                    "from": current_url,
                                    "clicked": label,
                                    "to": current_url,
                                    "screenshot": None,
                                    "error": "Navigation failed"
                                }
                                transitions.append(transition_data)
                                page_transitions.append(transition_data)
                                click_count += 1
                                continue
                        
                        new_url = page.url
                        normalized_new = normalize_url(new_url)
                        
                        # Take screenshot of transition
                        trans_screenshot = f"screenshots/run_{run_id}_trans_{len(transitions)}.png"
                        try:
                            page.screenshot(path=trans_screenshot, full_page=True)
                        except:
                            trans_screenshot = None
                        
                        transition_data = {
                            "from": current_url,
                            "clicked": label,
                            "to": new_url,
                            "screenshot": trans_screenshot,
                            "error": None
                        }
                        transitions.append(transition_data)
                        page_transitions.append(transition_data)
                        
                        # Add to queue if not visited (for new page exploration)
                        if normalized_new not in visited and is_same_domain(new_url):
                            url_queue.append((new_url, depth + 1))
                        
                        click_count += 1
                        
                        # If we navigated to a new page, go back to continue processing original page elements
                        if normalized_new != normalize_url(current_url):
                            try:
                                # Go back to original page to continue clicking remaining elements
                                page.goto(current_url, wait_until="domcontentloaded", timeout=10000)
                                wait_for_page_load()
                            except:
                                # If navigation back fails, continue with current page
                                pass
                    
                    # Handle buttons and other clickable elements - ALWAYS click and record
                    elif elem_type in ['button', 'div', 'select', 'checkbox']:
                        current_url = page.url
                        
                        try:
                            # Scroll element into view
                            element.scroll_into_view_if_needed()
                            time.sleep(0.2)  # Reduced wait time
                            
                            # Handle different element types
                            if elem_type == 'select':
                                # For select dropdowns, try to select first option
                                try:
                                    options = element.query_selector_all("option")
                                    if options and len(options) > 1:
                                        element.select_option(value=options[1].get_attribute("value"))
                                    else:
                                        element.click(timeout=5000)
                                except:
                                    element.click(timeout=5000)
                            elif elem_type == 'checkbox':
                                # For checkboxes, toggle them
                                element.click(timeout=5000)
                            else:
                                # Click the element - always record the interaction
                                element.click(timeout=5000)
                            
                            wait_for_page_load(timeout=6000)  # Reduced timeout
                            
                            new_url = page.url
                            normalized_new = normalize_url(new_url)
                            
                            # ALWAYS record the interaction, even if URL didn't change
                            trans_screenshot = f"screenshots/run_{run_id}_trans_{len(transitions)}.png"
                            try:
                                page.screenshot(path=trans_screenshot, full_page=True)
                            except:
                                trans_screenshot = None
                            
                            transition_data = {
                                "from": current_url,
                                "clicked": label,
                                "to": new_url,
                                "screenshot": trans_screenshot,
                                "error": None
                            }
                            transitions.append(transition_data)
                            page_transitions.append(transition_data)
                            
                            # Add to queue if new page discovered
                            if normalized_new not in visited and is_same_domain(new_url) and new_url != current_url:
                                url_queue.append((new_url, depth + 1))
                            
                            click_count += 1
                            
                            # Small delay before next click
                            time.sleep(0.2)
                            
                        except Exception as e:
                            error_msg = str(e)[:200]
                            # Still record the failed attempt - ALWAYS record
                            transition_data = {
                                "from": current_url,
                                "clicked": label,
                                "to": current_url,
                                "screenshot": None,
                                "error": error_msg
                            }
                            transitions.append(transition_data)
                            page_transitions.append(transition_data)
                            click_count += 1  # Count failed attempts too
                            continue
                
                except Exception as e:
                    error_msg = str(e)[:200]
                    print(f"    Error interacting with element: {error_msg[:50]}")
                    # Still record the error as a transition
                    try:
                        current_url = page.url
                        transition_data = {
                            "from": current_url,
                            "clicked": label if 'label' in locals() else "Unknown",
                            "to": current_url,
                            "screenshot": None,
                            "error": error_msg
                        }
                        transitions.append(transition_data)
                        page_transitions.append(transition_data)
                        click_count += 1
                    except:
                        pass
                    continue
            
            # Update log with click count for this page
            log_entry["click_count"] = click_count
            log_entry["transitions_count"] = len(page_transitions)
            
            print(f"    ✓ Page complete: {click_count} clicks, {len(page_transitions)} transitions recorded")
            return True
            
        except Exception as e:
            print(f"    Error visiting {url}: {str(e)[:100]}")
            return False
    
    # Start crawling
    start = start_url or page.url
    url_queue.append((start, 0))
    
    # Process queue - continue until queue is empty or no new pages found
    consecutive_no_new = 0
    max_consecutive_no_new = 10  # Increased: Stop if no new pages found after 10 attempts
    
    while url_queue:
        # Check if we should stop (max_pages limit)
        if max_pages and len(visited) >= max_pages:
            print(f"  Reached max_pages limit ({max_pages})")
            break
        
        url, depth = url_queue.popleft()
        pages_before = len(visited)
        interactions_before = len(transitions)
        
        if visit_url(url, depth):
            # Small delay between pages
            time.sleep(0.3)  # Reduced delay
            
            # Reset counter if we found a new page or new interactions
            if len(visited) > pages_before or len(transitions) > interactions_before:
                consecutive_no_new = 0
            else:
                consecutive_no_new += 1
        else:
            consecutive_no_new += 1
        
        # Stop if we haven't found new pages in a while AND queue is empty
        if consecutive_no_new >= max_consecutive_no_new and not url_queue:
            print(f"  No new pages found after {max_consecutive_no_new} attempts, stopping crawl")
            break
        
        # Safety check: if queue is getting too large, we might be in a loop
        if len(url_queue) > 2000:  # Increased limit
            print(f"  ⚠ Queue size exceeded 2000, stopping to prevent infinite loop")
            break
    
    print(f"\n✓ Crawl summary: {len(visited)} pages, {len(transitions)} interactions")
    if skipped_loops:
        print(f"  ⚠ Skipped {len(skipped_loops)} URLs due to potential loops")
    return logs, transitions
