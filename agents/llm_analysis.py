import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv
import os
import time

load_dotenv()

# Load and clean API keys (remove any whitespace)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Debug: Print to verify keys are loaded (first 10 chars only for security)
print(f"DEBUG: GEMINI_API_KEY loaded: {GEMINI_API_KEY[:10]}..." if GEMINI_API_KEY else "DEBUG: GEMINI_API_KEY not found")
print(f"DEBUG: GROQ_API_KEY loaded: {GROQ_API_KEY[:10]}..." if GROQ_API_KEY else "DEBUG: GROQ_API_KEY not found")

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
                max_output_tokens=16384,  # Increased for comprehensive reports
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
        # Validate API key format and existence
        if not GROQ_API_KEY:
            raise Exception("GROQ_API_KEY is not set in .env file")
        
        # Check if key has proper format (Groq keys typically start with 'gsk_')
        if not GROQ_API_KEY.startswith('gsk_'):
            print(f"WARNING: Groq API key should start with 'gsk_', current key starts with: {GROQ_API_KEY[:4]}")
            print(f"WARNING: Key length: {len(GROQ_API_KEY)} (should be around 100+ characters)")
        
        # Initialize Groq client with minimal configuration
        # DO NOT pass any extra parameters like proxies, timeout, etc.
        try:
            client = Groq(api_key=GROQ_API_KEY)
        except TypeError as te:
            raise Exception(f"Groq client initialization error: {str(te)}. Try: pip install --upgrade groq")
        
        # Create chat completion
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
            max_tokens=16000,  # Increased for comprehensive reports
            top_p=0.95
        )
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = str(e).lower()
        error_str = str(e)
        
        # Check for rate limit errors
        if "429" in error_msg or "rate_limit" in error_msg:
            raise Exception("RATE_LIMIT")
        
        # Check for authentication errors - provide detailed info
        if "401" in error_msg or "invalid api key" in error_msg or "unauthorized" in error_msg:
            print(f"\n=== GROQ API KEY DEBUG INFO ===")
            print(f"Key starts with: {GROQ_API_KEY[:4]}...")
            print(f"Key length: {len(GROQ_API_KEY)}")
            print(f"Key ends with: ...{GROQ_API_KEY[-4:]}")
            print(f"Expected format: gsk_xxxxx (100+ chars)")
            print(f"================================\n")
            raise Exception(f"Invalid GROQ_API_KEY (401 Error). Please check:\n"
                          f"1. Copy the FULL API key from https://console.groq.com/keys\n"
                          f"2. Make sure there are NO spaces or quotes in .env\n"
                          f"3. Format in .env should be: GROQ_API_KEY=gsk_yourkey\n"
                          f"4. Restart your app after changing .env\n"
                          f"Current key format: starts with '{GROQ_API_KEY[:4]}' (length: {len(GROQ_API_KEY)})")
        
        # Re-raise other errors
        raise Exception(f"Groq Error: {error_str}")


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
You are a senior UX Researcher with deep experience in human psychology, cognitive load theory, visual hierarchy, and emotional design. You are conducting a comprehensive website audit from a human-centered perspective.

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

## YOUR ROLE AS A SENIOR UX RESEARCHER

When evaluating this UI and user flow, follow these principles:

1. Think like a real user encountering the interface for the first time. Evaluate confusion, frustration, delight, trust, clarity, and emotional responses.
2. Highlight emotional impact at every stage. Identify where users may feel anxious, overloaded, uncertain, frustrated, or satisfied.
3. Consider discoverability, readability, and accessibility. Point out where users might struggle.
4. Use human-centered reasoning. Trust intuition and behavior patterns over technical logic.
5. Consider multiple personas: Novice, Busy, Frustrated, Distracted.
6. Be direct and honest. Call out anything confusing or poorly structured.
7. Apply UX principles: Gestalt, Fitts’s Law, Hick’s Law, Nielsen’s heuristics.
8. Provide actionable improvements with microcopy and layout recommendations.
9. Always explain WHY something is an issue—tie it to human psychology.
10. Avoid being overly positive; provide balanced, critical insights.

---------------------------------------------------

## REPORT STRUCTURE (FOLLOW EXACTLY)

### 1. First Impressions & Emotional Response
Start with: “A first-time visitor will likely feel: [emotion].”
Explain positive/negative signals, emotional barriers, and specific triggers.

### 2. Navigation & Wayfinding
Include:
- What works
- Problems
- Dead-ends or confusing paths
- Persona analysis: Novice, Busy, Frustrated, Distracted

### 3. Cognitive Load & Information Architecture
Include flow clarity, repetition, Hick’s Law issues, confusing points, improvement suggestions.

### 4. Interactive Elements & Affordances
Evaluate clarity, clickability, Fitts’s Law issues, and interaction feedback.

### 5. Visual Hierarchy & Readability
Include strengths, weaknesses, Gestalt issues, and how they affect comprehension.

### 6. Error States & Recovery
Analyze specific errors found, emotional impact, tone, and ability to recover.

### 7. Accessibility & Inclusivity
Include alt text findings, ARIA issues, keyboard navigation, cognitive load, mobile considerations.

### 8. Trust & Credibility
Identify trust-building and trust-damaging elements, consistency issues.

### 9. Specific Pain Points (Prioritized)
Each pain point must include:
- Severity (High/Medium/Low)
- Emotional impact
- Practical impact
- Specific example from crawl data

### 10. Actionable Recommendations (Prioritized)
Organize into:
- Immediate (must-fix)
- High-impact UX improvements
- Microcopy examples
- QUICK DESIGN SKETCH (a text-based layout improvement)

Each recommendation must include:
- What to fix
- Why it matters
- UX principle reference
- Exact rewritten microcopy

---------------------------------------------------

## SCORING CRITERIA (MANDATORY)

Compute UI/UX Score out of 10:

- Pages Found (0–2 points)
- Interactivity (0–2 points)
- Error Rate (0–2 points)
- Element Discovery (0–2 points)
- Navigation Quality (0–2 points)

Apply:
+0.5 to +1 for excellent UX patterns  
-0.5 to -1 for major UX issues  

Final Output Format:

## FINAL SCORES
UI/UX Score: X.X/10

Breakdown:
- Pages Found: X.X/2
- Interactivity: X.X/2
- Error Rate: X.X/2
- Element Discovery: X.X/2
- Navigation Quality: X.X/2

Adjustments:
[Explain additions or subtractions]

Human Experience Summary:
[2–4 sentences summarizing emotional experience and key friction points]

---------------------------------------------------

## OUTPUT QUALITY & READABILITY REQUIREMENTS (IMPORTANT)

1. Use clean formatting: short paragraphs, bullet points, numbered lists, bold headings.
2. Use simple, direct language. No vague statements.
3. Every insight must reference a specific example (page, button, error, label, etc.).
4. All recommendations must include: the issue, why it matters, how to fix it, exact microcopy rewrite.
5. Bullet points MUST be used for emotions, strengths, weaknesses, pain points, navigation issues, and recommendations.
6. Avoid walls of text. Break long explanations into readable chunks.
7. The report must be skimmable. A PM or designer should quickly understand key issues.
8. Tone: professional, empathetic, honest, human-centered.
9. EVERY issue must include:

Severity: High / Medium / Low  
Emotional Impact: [emotion]  
Practical Impact: [effect on task]

10. NEVER guess. If data is missing: “Data not available in crawl output.”

---------------------------------------------------

## FINAL INSTRUCTION
Generate a complete, polished, human-centered UX Research Report following ALL rules above. The report must be clear, readable, structured, bullet-pointed, actionable, emotionally aware, and grounded in UX psychology.
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
            
            print(f"\nTrying model: {model_config['name']} ({provider})...")
            
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
            
            print(f"✓ Successfully generated report with {model_config['name']}")
            return report
            
        except Exception as e:
            error_msg = str(e)
            last_error = error_msg
            error_lower = error_msg.lower()
            # If it's a rate limit error, try next model
            if "RATE_LIMIT" in error_msg or "429" in error_msg or "quota" in error_lower or "rate limit" in error_lower or "resource_exhausted" in error_lower:
                print(f"⚠ Rate limit/quota exceeded on {model_config['name']}, trying next model...")
                continue
            # For other errors, also try next model (fallback behavior)
            else:
                print(f"⚠ Error with {model_config['name']}: {error_msg}")
                print(f"  Trying next model...")
                continue
    
    error_report = f"""
All AI Models Failed

Last Error: {last_error}

Pages Crawled: {len(crawl_data)}
Transitions: {len(transitions)}
Errors: {len(errors)}

Solutions:
1. Check your API keys in .env file
2. For Groq: Get a new key from https://console.groq.com/keys
3. Make sure .env format is: GROQ_API_KEY=gsk_yourkey (no spaces, no quotes)
4. Restart your application after changing .env
"""

    return error_report