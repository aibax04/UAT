import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


model = genai.GenerativeModel("gemini-2.5-flash")

def analyze_crawl(crawl_data, transitions):
    """
    Analyze website crawl data using Gemini AI
    
    Args:
        crawl_data: List of pages visited with buttons found
        transitions: List of button clicks and navigation results
    
    Returns:
        Detailed UX/QA analysis report
    """
    
    
    crawl_summary = []
    for i, log in enumerate(crawl_data):
        crawl_summary.append(f"""
Page {i+1}: {log['url']}
- Interactive Elements Found: {len(log['buttons'])}
- Elements: {', '.join(log['buttons'][:10])}{'...' if len(log['buttons']) > 10 else ''}
""")
    
    transition_summary = []
    errors = []
    
    for i, trans in enumerate(transitions):
        if trans.get('error'):
            errors.append(f" Error on '{trans['clicked']}': {trans['error']}")
        
        transition_summary.append(f"""
Transition {i+1}:
- From: {trans['from']}
- Clicked: "{trans['clicked']}"
- To: {trans['to']}
- Status: {' ERROR' if trans.get('error') else '✓ Success'}
""")
    
    prompt = f"""
You are an expert UX/QA analyst conducting a comprehensive website audit.

## CRAWL SUMMARY
Total Pages Crawled: {len(crawl_data)}
Total Interactions Tested: {len(transitions)}
Errors Encountered: {len(errors)}

## PAGES ANALYZED
{''.join(crawl_summary)}

## NAVIGATION TRANSITIONS
{''.join(transition_summary)}

## ERRORS FOUND
{chr(10).join(errors) if errors else 'No errors detected'}

---

Please provide a detailed UX/QA analysis report covering:

### 1. NAVIGATION & STRUCTURE
- Site navigation clarity and consistency
- URL structure and routing
- Breadcrumb trails and user orientation
- Navigation dead ends or loops

### 2. INTERACTIVE ELEMENTS
- Button/link functionality
- Missing or unclear labels
- Broken interactions
- Unresponsive elements

### 3. ACCESSIBILITY ISSUES
- Missing aria-labels
- Poor semantic HTML
- Keyboard navigation problems
- Screen reader compatibility

### 4. UX PATTERNS & DESIGN
- User flow clarity
- Information architecture
- Consistency in design patterns
- Call-to-action effectiveness

### 5. TECHNICAL ISSUES
- Broken links or buttons
- JavaScript errors
- Timeout issues
- Navigation failures

### 6. RECOMMENDATIONS
Provide 5-10 specific, actionable improvements prioritized by impact

### 7. UX SCORE
Rate the overall user experience from 0-10 with justification:
- 0-3: Critical issues, unusable
- 4-5: Major problems, poor UX
- 6-7: Functional but needs improvement
- 8-9: Good UX with minor issues
- 10: Exceptional UX

Format your response as a clear, professional report with markdown formatting.
"""

    try:
        print("Sending data to UAT agent for analysis")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.4, 
                top_p=0.95,
                max_output_tokens=8192,
            )
        )
        
        report = response.text
        
        
        os.makedirs("reports", exist_ok=True)
        report_file = f"reports/ux_analysis_{len(crawl_data)}pages.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"✓ Report saved to {report_file}")
        
        return report
        
    except Exception as e:
        error_report = f"""
# UX/QA Analysis Error

An error occurred during analysis:
{str(e)}

## Raw Data Summary
- Pages Crawled: {len(crawl_data)}
- Transitions: {len(transitions)}
- Errors: {len(errors)}

Please check your Gemini API key and try again.
"""
        return error_report