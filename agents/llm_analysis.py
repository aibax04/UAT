import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv
import os
import time

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

FREE_MODELS = [
    {
        "name": "gemini-2.5-flash",
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "enabled": bool(GEMINI_API_KEY),
        "priority": 1
    },
    {
        "name": "Gemini 1.5 Flash",
        "provider": "gemini",
        "model": "gemini-1.5-flash-latest",
        "enabled": bool(GEMINI_API_KEY),
        "priority": 2
    },
    {
        "name": "GPT-OSS-120B",
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "enabled": bool(GROQ_API_KEY),
        "priority": 3
    },
    {
        "name": "Llama 3.3 70B",
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "enabled": bool(GROQ_API_KEY),
        "priority": 4
    },
    {
        "name": "Llama 3.1 70B",
        "provider": "groq",
        "model": "llama-3.1-70b-versatile",
        "enabled": bool(GROQ_API_KEY),
        "priority": 5
    },
    {
        "name": "Mixtral 8x7B",
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "enabled": bool(GROQ_API_KEY),
        "priority": 6
    },
    {
        "name": "Llama 3.1 8B Instant",
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "enabled": bool(GROQ_API_KEY),
        "priority": 7
    }
]

def analyze_with_gemini(prompt, model_name="gemini-1.5-pro-latest"):
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                top_p=0.95,
                max_output_tokens=8192,
            )
        )
        return response.text
    except Exception as e:
        error_msg = str(e).lower()
        error_str = str(e)
        # Check for rate limit/quota errors
        if any(keyword in error_msg for keyword in ["429", "quota", "rate limit", "resource_exhausted", "quota exceeded"]):
            raise Exception("RATE_LIMIT")
        # Re-raise with original message for other errors
        raise Exception(f"Gemini Error: {error_str}")


def analyze_with_groq(prompt, model_name="llama-3.3-70b-versatile"):
    try:
        # Initialize Groq client - updated to version 0.37.1+ which fixes proxies issue
        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY is not set")
        
        # Use basic Groq initialization - newer versions (0.37.1+) handle proxies correctly
        client = Groq(api_key=GROQ_API_KEY)
        
        # Create chat completion with only supported parameters
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert UX/QA analyst conducting comprehensive website audits. Provide detailed, actionable insights."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.4,
            max_tokens=8000,
            top_p=0.95
        )
        return response.choices[0].message.content
    except TypeError as e:
        # Handle TypeError for unsupported arguments (like proxies in older versions)
        error_msg = str(e)
        if "proxies" in error_msg.lower() or "unexpected keyword" in error_msg.lower():
            raise Exception(f"Groq client error: {error_msg}. Please ensure you have groq>=0.37.1 installed. Try: pip install --upgrade groq")
        raise Exception(f"Groq TypeError: {error_msg}")
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "rate_limit" in error_msg:
            raise Exception("RATE_LIMIT")
        raise Exception(f"Groq Error: {str(e)}")


def analyze_crawl(crawl_data, transitions):
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
            errors.append(f"Error on '{trans['clicked']}': {trans['error']}")
        transition_summary.append(f"""
Transition {i+1}:
- From: {trans['from']}
- Clicked: "{trans['clicked']}"
- To: {trans['to']}
- Status: {'ERROR' if trans.get('error') else 'Success'}
""")
    
    # Calculate base metrics for scoring
    total_pages = len(crawl_data)
    total_interactions = len(transitions)
    error_count = len(errors)
    success_rate = ((total_interactions - error_count) / total_interactions * 100) if total_interactions > 0 else 100
    avg_elements_per_page = sum(len(log.get('buttons', [])) for log in crawl_data) / total_pages if total_pages > 0 else 0
    
    prompt = f"""
You are an expert UX/QA analyst conducting a comprehensive website audit. Provide a fair and realistic assessment based on the actual crawled data.

## CRAWL SUMMARY
Total Pages Crawled: {total_pages}
Total Interactions Tested: {total_interactions}
Errors Encountered: {error_count}
Success Rate: {success_rate:.1f}%
Average Interactive Elements per Page: {avg_elements_per_page:.1f}

## PAGES ANALYZED
{''.join(crawl_summary)}

## NAVIGATION TRANSITIONS
{''.join(transition_summary)}

## ERRORS FOUND
{chr(10).join(errors) if errors else 'No errors detected'}

---

## SCORING INSTRUCTIONS

Please provide a detailed UX/QA analysis report covering:

1. **Navigation and Structure** - How easy is it to navigate? Are pages well-organized?
2. **Interactive Elements** - Are buttons, links, and forms working properly?
3. **User Experience** - Is the flow logical and intuitive?
4. **Visual Design** - Is the UI clean and professional?
5. **Technical Issues** - Any broken links, errors, or functionality problems?
6. **Recommendations** - Specific, actionable improvements

## SCORING CRITERIA (Be Fair and Realistic)

Calculate the **UI/UX Score** (out of 10) based on these factors:

**Base Score Calculation:**
- **Pages Found (0-2 points)**: 
  - 2 points: 10+ pages discovered
  - 1.5 points: 5-9 pages
  - 1 point: 2-4 pages
  - 0.5 points: 1 page
- **Interactivity (0-2 points)**:
  - 2 points: 20+ successful interactions
  - 1.5 points: 10-19 interactions
  - 1 point: 5-9 interactions
  - 0.5 points: 1-4 interactions
- **Error Rate (0-2 points)**:
  - 2 points: 0-10% errors (excellent)
  - 1.5 points: 11-25% errors (good)
  - 1 point: 26-50% errors (fair)
  - 0.5 points: 51-75% errors (poor)
  - 0 points: 76%+ errors (very poor)
- **Element Discovery (0-2 points)**:
  - 2 points: 5+ elements per page average
  - 1.5 points: 3-4 elements per page
  - 1 point: 2 elements per page
  - 0.5 points: 1 element per page
- **Navigation Quality (0-2 points)**:
  - 2 points: Clear navigation, logical flow
  - 1.5 points: Mostly clear navigation
  - 1 point: Some navigation issues
  - 0.5 points: Poor navigation structure

**IMPORTANT SCORING RULES:**
- Start with the base calculation above
- Add 0.5-1 point if the site has good UX patterns (clear CTAs, good layout)
- Subtract 0.5-1 point if there are major UX issues (confusing navigation, broken flows)
- **Final score should be realistic**: Most functional websites should score 6-8/10
- **Be generous**: If the site works reasonably well, don't penalize heavily for minor issues
- **Consider the data available**: If we only crawled a few pages, don't assume the whole site is bad

**Output Format:**
At the end of your report, include:
```
## FINAL SCORES

**UI/UX Score: X.X/10**

Breakdown:
- Pages Found: X.X/2
- Interactivity: X.X/2
- Error Rate: X.X/2
- Element Discovery: X.X/2
- Navigation Quality: X.X/2
```

Make sure to provide the score in the format: "UI/UX Score: X.X/10" where X.X is a number between 0 and 10.
"""

    enabled_models = [m for m in FREE_MODELS if m["enabled"]]
    
    if not enabled_models:
        return """
No AI Models Available

Add at least one API key in .env:
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
"""

    # Sort models by priority (Gemini first, then Groq)
    sorted_models = sorted(enabled_models, key=lambda x: x.get("priority", 999))
    
    last_error = None
    for model_config in sorted_models:
        if not model_config["enabled"]:
            continue
        
        try:
            provider = model_config["provider"]
            model_name = model_config["model"]
            start_time = time.time()
            
            if provider == "gemini":
                report = analyze_with_gemini(prompt, model_name)
            elif provider == "groq":
                report = analyze_with_groq(prompt, model_name)
            else:
                continue
            
            elapsed = time.time() - start_time
            
            model_info = f"""
---
Analysis Generated By: {model_config['name']} ({provider.upper()})
Model: {model_name}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Processing Time: {elapsed:.2f} seconds
Status: FREE Model
---

"""
            
            report = model_info + report
            
            os.makedirs("reports", exist_ok=True)
            report_file = f"reports/ux_analysis_{len(crawl_data)}pages_{int(time.time())}.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)
            
            return report
            
        except Exception as e:
            error_msg = str(e)
            last_error = error_msg
            error_lower = error_msg.lower()
            # If it's a rate limit error, try next model
            if "RATE_LIMIT" in error_msg or "429" in error_msg or "quota" in error_lower or "rate limit" in error_lower or "resource_exhausted" in error_lower:
                print(f"Rate limit/quota exceeded on {model_config['name']}, trying next model...")
                continue
            # For other errors, also try next model (fallback behavior)
            else:
                print(f"Error with {model_config['name']}: {error_msg}, trying next model...")
                continue
    
    error_report = f"""
All AI Models Failed

Pages Crawled: {len(crawl_data)}
Transitions: {len(transitions)}
Errors: {len(errors)}

Solutions:
Add Groq API Key (Free)
Retry later
"""

    return error_report
