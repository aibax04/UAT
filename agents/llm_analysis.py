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

---

## YOUR ROLE AS A SENIOR UX RESEARCHER

When evaluating this UI and user flow, follow these principles:

1. **Think like a real user encountering the interface for the first time** - Put yourself in their shoes. What would confuse, frustrate, or delight them?

2. **Highlight emotional impact** - Identify places where users may feel confused, anxious, overloaded, uncertain, frustrated, or satisfied. Judge elements not just functionally, but emotionally.

3. **Consider discoverability, readability, and accessibility** - Point out where typical users might struggle to find things, read content, or access features.

4. **Use human-centered reasoning** - Prefer intuition, empathy, and behavioral patterns over rigid technical logic. If something "feels off" or "looks confusing," call it out explicitly.

5. **Consider multiple user personas** - Evaluate how different users might react:
   - **Novice user**: First-time visitor, unfamiliar with the site
   - **Busy user**: Wants to accomplish tasks quickly
   - **Frustrated user**: Already experiencing issues, low patience
   - **Distracted user**: Multi-tasking, limited attention span

6. **Be direct and honest** - Provide constructive, critical feedback. If something doesn't guide the eye, creates cognitive overload, or breaks user expectations, say so clearly.

7. **Apply UX principles** - Reference modern UI principles when relevant:
   - **Gestalt principles**: Proximity, similarity, closure, continuity
   - **Fitts's Law**: Target size and distance for interactive elements
   - **Hick's Law**: Choice complexity and decision time
   - **Nielsen's heuristics**: Visibility, feedback, error prevention, etc.

8. **Provide actionable improvements** - Suggest specific design changes, microcopy rewrites, visual hierarchy improvements, or alternative layouts that would enhance the user experience.

9. **Explain the "why"** - Always explain WHY something might confuse or frustrate a real human. Connect issues to human psychology and behavior.

10. **Avoid being overly positive** - Give balanced, honest feedback. Highlight both strengths and areas for improvement.

## REPORT STRUCTURE (Follow This Exact Format)

Generate a comprehensive UX RESEARCH REPORT using this exact structure. Be detailed, specific, and human-centered in each section:

### 1. First Impressions & Emotional Response

Start with: "A first-time visitor will likely feel: [emotion]."

Then provide:
- **Why:** Explain the positive signals (what builds trust/curiosity) and negative signals (what creates confusion/anxiety)
- **Emotional barriers:** List specific emotions users might experience (confusion, anxiety, mistrust, delight, etc.)
- Be specific about what elements trigger these emotions

### 2. Navigation & Wayfinding

Structure as:
- **What works:** List navigation strengths
- **Problems:** Detail navigation issues with specific examples
- **Dead-ends/confusing paths:** Identify broken routes or confusing navigation flows from the crawl data
- **Persona view:** Evaluate navigation for each persona (Novice, Busy, Frustrated, Distracted)

### 3. Cognitive Load & Information Architecture

Cover:
- Overall flow assessment (top-to-bottom structure)
- Content repetition issues (if any)
- Hick's Law violations (too many choices)
- **Where users might feel lost:** Specific areas that would confuse users
- IA improvement suggestions

### 4. Interactive Elements & Affordances

Evaluate:
- **Buttons/links:** Affordance clarity, Fitts's Law compliance
- **Feedback:** Quality of interaction feedback
- **Clickability:** Whether users understand what's interactive
- Reference specific elements from the crawl data

### 5. Visual Hierarchy & Readability

Include:
- **Strengths:** What works well visually
- **Weaknesses:** Competing focal points, whitespace issues, Gestalt principle violations
- **Result:** How visual issues impact user experience

### 6. Error States & Recovery

Analyze:
- Specific error examples from crawl data
- How errors make users feel
- Recovery mechanisms (or lack thereof)
- Error tone and messaging quality

### 7. Accessibility & Inclusivity

From crawl output, assess:
- Alt text presence/quality
- Keyboard navigation indicators
- Cognitive load for users with disabilities
- Mobile/responsive considerations (if observable)

### 8. Trust & Credibility

Evaluate:
- **Positive:** Trust signals (logos, metrics, testimonials)
- **Negative:** Elements that reduce trust (errors, inconsistencies, broken features)

### 9. Specific Pain Points (concrete & prioritized)

List each pain point with:
- **Severity rating:** (High/Medium/Low severity)
- **Emotional impact:** How it makes users feel
- **Practical impact:** What users can't do or struggle with
- Reference specific examples from crawl data

### 10. Actionable Recommendations (specific, prioritized)

Organize as:
- **Immediate (must-fix):** Critical issues with specific fixes
- **High-impact UX improvements:** Important enhancements
- **Microcopy examples:** Provide exact rewritten text for buttons, messages, etc.
- **QUICK DESIGN SKETCH:** Textual blueprint for improved layout/hierarchy

For each recommendation:
- Be specific (not generic)
- Provide exact microcopy when relevant
- Explain the "why" behind each suggestion
- Reference UX principles (Gestalt, Fitts's Law, etc.) when applicable

## SCORING CRITERIA (Human-Centered Evaluation)

Calculate the **UI/UX Score** (out of 10) based on human experience:

**Base Score Calculation:**
- **Pages Found (0-2 points)**: 
  - 2 points: 10+ pages discovered (comprehensive site)
  - 1.5 points: 5-9 pages (good coverage)
  - 1 point: 2-4 pages (limited but functional)
  - 0.5 points: 1 page (minimal)
- **Interactivity (0-2 points)**:
  - 2 points: 20+ successful interactions (rich, engaging)
  - 1.5 points: 10-19 interactions (good interactivity)
  - 1 point: 5-9 interactions (basic functionality)
  - 0.5 points: 1-4 interactions (minimal)
- **Error Rate (0-2 points)**:
  - 2 points: 0-10% errors (smooth, frustration-free)
  - 1.5 points: 11-25% errors (mostly smooth with minor hiccups)
  - 1 point: 26-50% errors (noticeable friction)
  - 0.5 points: 51-75% errors (frustrating experience)
  - 0 points: 76%+ errors (highly frustrating)
- **Element Discovery (0-2 points)**:
  - 2 points: 5+ elements per page (rich, discoverable)
  - 1.5 points: 3-4 elements per page (adequate)
  - 1 point: 2 elements per page (sparse)
  - 0.5 points: 1 element per page (very limited)
- **Navigation Quality (0-2 points)**:
  - 2 points: Clear, intuitive navigation (users feel confident)
  - 1.5 points: Mostly clear (minor confusion possible)
  - 1 point: Some navigation issues (users may get lost)
  - 0.5 points: Poor navigation (users feel lost or frustrated)

**IMPORTANT SCORING RULES:**
- Start with the base calculation above
- **Add 0.5-1 point** if the site demonstrates excellent UX patterns:
  - Clear visual hierarchy
  - Intuitive navigation
  - Empathetic error handling
  - Good use of whitespace and typography
  - Strong affordances and feedback
- **Subtract 0.5-1 point** if there are major UX issues:
  - Confusing navigation that would frustrate users
  - High cognitive load
  - Poor visual hierarchy
  - Lack of clear feedback
  - Accessibility barriers
- **Final score should reflect real user experience**: Most functional websites should score 6-8/10
- **Be fair but honest**: If the site works but feels confusing or frustrating, reflect that in the score
- **Consider the data available**: If we only crawled a few pages, focus on what you observed, but note limitations

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

Adjustments applied:
[Explain any points added or subtracted based on UX patterns observed]

**Human Experience Summary:**
[2-4 sentences describing the overall user experience from a human perspective. Be specific about the emotional journey and key friction points. Match the style of the demo report.]
```

## CRITICAL REQUIREMENTS

1. **Be as detailed as the demo report** - Include specific examples, emotional impacts, and concrete recommendations
2. **Reference crawl data** - Use specific pages, errors, and interactions from the crawl data in your analysis
3. **Provide exact microcopy** - When suggesting text changes, provide the exact rewritten copy
4. **Include severity ratings** - Rate pain points as High/Medium/Low severity
5. **Be specific, not generic** - Avoid vague statements like "improve navigation." Instead, say "consolidate the 8 top-level nav items into 5 with an 'Initiatives' dropdown"
6. **Match demo quality** - Your report should be as comprehensive, insightful, and actionable as the demo report provided

## TOKEN EFFICIENCY

While being comprehensive, be concise where possible:
- Use bullet points for lists
- Be specific but not verbose
- Focus on actionable insights over lengthy descriptions
- Prioritize quality over quantity

Remember: Your goal is to evaluate this interface as a senior UX researcher would—with empathy, human psychology in mind, and a focus on how real people would actually experience and feel about using this interface. Generate a report that matches the depth, specificity, and actionable nature of the demo report.
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