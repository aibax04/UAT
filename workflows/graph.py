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
            args=['--start-maximized']
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
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
                # Wait for redirect after login
                time.sleep(3)
            else:
                print(f"⚠ Login may have failed, continuing anyway...")
        else:
            # No login required, go directly to start URL
            print(f"🌐 No login required, navigating to {state['start_url']}")
            page.goto(state["start_url"], wait_until="networkidle", timeout=15000)
            time.sleep(2)
        
        # Get the current URL after login (in case of redirect)
        current_url = page.url
        print(f"📍 Current page: {current_url}")
        
        # Run the crawler from current page
        state["crawl_data"], state["transitions"] = crawl_app(
            page, 
            state["run_id"],
            start_url=current_url,
            depth_limit=2,  # Crawl 2 levels deep
            max_pages=25    # Visit up to 25 pages
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
    
    # Extract score from report (basic extraction)
    score = 0.0
    try:
        report_lower = state["report"].lower()
        if "score:" in report_lower or "ux score" in report_lower:
            # Try to extract numerical score
            import re
            score_match = re.search(r'score[:\s]*(\d+(?:\.\d+)?)\s*/?\s*10', report_lower)
            if score_match:
                score = float(score_match.group(1))
    except:
        pass
    
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

# Build the workflow graph
graph = StateGraph(State)

graph.add_node("start_run", start_run)
graph.add_node("run_crawl", run_crawl)
graph.add_node("run_analysis", run_analysis)

graph.set_entry_point("start_run")
graph.add_edge("start_run", "run_crawl")
graph.add_edge("run_crawl", "run_analysis")
graph.add_edge("run_analysis", END)

workflow = graph.compile()