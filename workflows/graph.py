from langgraph.graph import StateGraph, END
from playwright.sync_api import sync_playwright
from db import get_db
from tools.login import login_to_app, get_credentials
from tools.crawler import crawl_app
from agents.llm_analysis import analyze_crawl
from typing import TypedDict
import json
import time

class State(TypedDict):
    app_name: str
    start_url: str
    run_id: int
    crawl_data: list
    transitions: list
    report: str
    status: str
    login_success: bool

def start_run(state: State) -> State:
    """Initialize a new test run in the database"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO test_runs (app_name, status) VALUES (?, ?)", 
        (state["app_name"], "started")
    )
    state["run_id"] = cursor.lastrowid
    state["status"] = "started"
    state["login_success"] = False

    conn.commit()
    conn.close()
    
    print(f"✓ Started test run #{state['run_id']} for {state['app_name']}")
    return state

def run_crawl(state: State) -> State:
    """Launch browser, login if needed, and crawl the application"""
    print(f" Starting crawl of {state['start_url']}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--start-maximized', '--force-device-scale-factor=1']
        )
        # Responsive viewport that fits in popup window
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            device_scale_factor=1,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        
        creds = get_credentials(state["app_name"])
        
        if creds and creds.get("login_url"):
            print(f" Login required for {state['app_name']}")
            print(f"   Navigating to: {creds['login_url']}")
            
            
            page.goto(creds["login_url"], wait_until="networkidle", timeout=15000)
            time.sleep(2)
            
            
            state["login_success"] = login_to_app(page, state["app_name"])
            
            if state["login_success"]:
                print(f"✓ Login successful!")
                
                time.sleep(3)
            else:
                print(f"⚠ Login may have failed, continuing anyway...")
        else:
            
            print(f" No login required, navigating to {state['start_url']}")
            page.goto(state["start_url"], wait_until="networkidle", timeout=15000)
            time.sleep(2)
        
        
        current_url = page.url
        print(f" Current page: {current_url}")
        
        # Run the crawler from current page - crawl all pages until done
        state["crawl_data"], state["transitions"] = crawl_app(
            page, 
            state["run_id"],
            start_url=current_url,
            depth_limit=10,  # Increased depth limit
            max_pages=None   # No limit - crawl until all pages found
        )

        # Save crawl data to database
        conn = get_db()
        cursor = conn.cursor()
        
        for log in state["crawl_data"]:
            cursor.execute(
                """INSERT INTO crawl_logs (run_id, url, buttons, screenshot_path)
                   VALUES (?, ?, ?, ?)""",
                (state["run_id"], log["url"], json.dumps(log["buttons"]), log["screenshot"])
            )
        
        for trans in state["transitions"]:
            cursor.execute(
                """INSERT INTO transitions (run_id, from_url, clicked_element, to_url, screenshot_path, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (state["run_id"], trans["from"], trans["clicked"], trans["to"], 
                 trans.get("screenshot", ""), trans.get("error", ""))
            )
        
        conn.commit()
        conn.close()

        browser.close()
    
    print(f"✓ Crawl complete: {len(state['crawl_data'])} pages, {len(state['transitions'])} transitions")
    return state

def run_analysis(state: State) -> State:
    """Analyze crawl data using Gemini AI"""
    print("Running Ai analysis on crawled data...")
    
    # Add login context to analysis
    login_context = ""
    if state.get("login_success"):
        login_context = "\n**Note**: This analysis includes authenticated pages (user logged in successfully).\n"
    
    state["report"] = login_context + analyze_crawl(state["crawl_data"], state["transitions"])
    
    # Extract score from report (improved extraction)
    score = 0.0
    try:
        report_lower = state["report"].lower()
        # Try multiple patterns to find the score
        import re
        
        # Pattern 1: "UI/UX Score: X.X/10"
        score_match = re.search(r'ui/ux\s*score[:\s]*(\d+(?:\.\d+)?)\s*/?\s*10', report_lower)
        if not score_match:
            # Pattern 2: "UX Score: X.X/10"
            score_match = re.search(r'ux\s*score[:\s]*(\d+(?:\.\d+)?)\s*/?\s*10', report_lower)
        if not score_match:
            # Pattern 3: "Score: X.X/10"
            score_match = re.search(r'score[:\s]*(\d+(?:\.\d+)?)\s*/?\s*10', report_lower)
        if not score_match:
            # Pattern 4: Just a number between 0-10
            score_match = re.search(r'\b([0-9](?:\.[0-9])?)\s*(?:out\s*of|/)\s*10\b', report_lower)
        
        if score_match:
            score = float(score_match.group(1))
            # Ensure score is between 0 and 10
            score = max(0.0, min(10.0, score))
        else:
            # Fallback: Calculate a fair score from crawl data (matching LLM criteria)
            total_pages = len(state["crawl_data"])
            total_interactions = len(state["transitions"])
            errors = sum(1 for t in state["transitions"] if t.get("error"))
            success_rate = ((total_interactions - errors) / total_interactions * 100) if total_interactions > 0 else 100
            avg_elements = sum(len(log.get('buttons', [])) for log in state["crawl_data"]) / total_pages if total_pages > 0 else 0
            
            # Calculate score based on the same criteria as LLM prompt (fair and realistic)
            score = 0.0
            
            # Pages Found (0-2 points)
            if total_pages >= 10:
                score += 2.0
            elif total_pages >= 5:
                score += 1.5
            elif total_pages >= 2:
                score += 1.0
            elif total_pages >= 1:
                score += 0.5
            
            # Interactivity (0-2 points)
            if total_interactions >= 20:
                score += 2.0
            elif total_interactions >= 10:
                score += 1.5
            elif total_interactions >= 5:
                score += 1.0
            elif total_interactions >= 1:
                score += 0.5
            
            # Error Rate (0-2 points)
            error_rate = (errors / total_interactions * 100) if total_interactions > 0 else 0
            if error_rate <= 10:
                score += 2.0
            elif error_rate <= 25:
                score += 1.5
            elif error_rate <= 50:
                score += 1.0
            elif error_rate <= 75:
                score += 0.5
            
            # Element Discovery (0-2 points)
            if avg_elements >= 5:
                score += 2.0
            elif avg_elements >= 3:
                score += 1.5
            elif avg_elements >= 2:
                score += 1.0
            elif avg_elements >= 1:
                score += 0.5
            
            # Navigation Quality (0-2 points) - assume good if we found multiple pages
            if total_pages >= 5 and success_rate >= 70:
                score += 2.0
            elif total_pages >= 3 and success_rate >= 60:
                score += 1.5
            elif total_pages >= 2:
                score += 1.0
            else:
                score += 0.5
            
            # Ensure score is realistic (most functional sites should be 6-8)
            # If score is too low but site has basic functionality, boost it
            if score < 5.0 and total_pages >= 1 and success_rate >= 50:
                score = 5.5  # Minimum for functional sites
            
            # Cap at 10
            score = min(10.0, score)
    except Exception as e:
        print(f"Error extracting score: {e}")
        # Default score if extraction fails
        score = 6.0
    
    # Save report to database
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """INSERT INTO reports (run_id, report_text, score)
           VALUES (?, ?, ?)""",
        (state["run_id"], state["report"], score)
    )
    
    cursor.execute(
        """UPDATE test_runs 
           SET status = ?, finished_at = CURRENT_TIMESTAMP, 
               total_pages = ?, total_clicks = ?
           WHERE id = ?""",
        ("completed", len(state["crawl_data"]), len(state["transitions"]), state["run_id"])
    )
    
    conn.commit()
    conn.close()
    
    print("✓ Analysis complete!")
    print(f"✓ UX Score: {score}/10")
    return state

graph = StateGraph(State)

graph.add_node("start_run", start_run)
graph.add_node("run_crawl", run_crawl)
graph.add_node("run_analysis", run_analysis)

graph.set_entry_point("start_run")
graph.add_edge("start_run", "run_crawl")
graph.add_edge("run_crawl", "run_analysis")
graph.add_edge("run_analysis", END)

workflow = graph.compile()