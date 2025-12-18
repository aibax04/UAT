"""
TaskPlanner: Converts natural language instructions into structured task lists.
Uses AI (Gemini) to break down user instructions into executable tasks.
"""
import os
import google.generativeai as genai
import json


class TaskPlanner:
    """Plans tasks from natural language instructions"""
    
    def __init__(self):
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.model = None
            print("Warning: GEMINI_API_KEY not found. Task planning will use fallback.")
    
    def plan_tasks(self, instruction, current_url=None):
        """Convert natural language instruction into task list"""
        if not instruction or not instruction.strip():
            return []
        
        # If no AI model, use simple fallback
        if not self.model:
            return self._fallback_plan(instruction)
        
        try:
            # Build prompt for task planning
            prompt = f"""You are a task planning agent. Break down the following user instruction into a sequential list of executable browser tasks.

User Instruction: {instruction}
Current URL: {current_url or 'Not specified'}

For each task, provide:
- id: unique number (1, 2, 3...)
- name: short descriptive name
- description: detailed description of what to do
- action_type: one of [click, fill, navigate, wait, scroll]
- selector: CSS selector or description of element (if applicable)
- text: text to fill (if action_type is 'fill')
- url: URL to navigate to (if action_type is 'navigate')

Return ONLY a valid JSON array of tasks. Example:
[
  {{
    "id": 1,
    "name": "Click login button",
    "description": "Find and click the login button on the page",
    "action_type": "click",
    "selector": "button[type='submit'], a[href*='login'], .login-btn"
  }},
  {{
    "id": 2,
    "name": "Fill username",
    "description": "Enter username in the username field",
    "action_type": "fill",
    "selector": "input[name='username'], input[type='text']#username",
    "text": "testuser"
  }}
]

Important:
- Tasks must be sequential and executable
- Use common CSS selectors
- For clicks, provide multiple selector options
- Keep task names concise (max 50 chars)
- Return valid JSON only, no markdown formatting"""

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean response (remove markdown code blocks if present)
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            if response_text.endswith('```'):
                response_text = response_text.rsplit('```', 1)[0].strip()
            
            # Parse JSON
            tasks = json.loads(response_text)
            
            # Validate and add status
            for task in tasks:
                if 'status' not in task:
                    task['status'] = 'pending'
                if 'id' not in task:
                    task['id'] = len(tasks) + 1
            
            return tasks
            
        except Exception as e:
            print(f"Error in AI task planning: {e}")
            # Fallback to simple planning
            return self._fallback_plan(instruction)
    
    def _fallback_plan(self, instruction):
        """Simple fallback task planning without AI"""
        instruction_lower = instruction.lower()
        tasks = []
        
        # Simple keyword-based task generation
        if 'click' in instruction_lower:
            tasks.append({
                'id': 1,
                'name': 'Click element',
                'description': instruction,
                'action_type': 'click',
                'selector': 'button, a, [role="button"]',
                'status': 'pending'
            })
        
        if 'fill' in instruction_lower or 'enter' in instruction_lower or 'type' in instruction_lower:
            tasks.append({
                'id': len(tasks) + 1,
                'name': 'Fill input field',
                'description': instruction,
                'action_type': 'fill',
                'selector': 'input[type="text"], input[type="email"], textarea',
                'text': 'test',
                'status': 'pending'
            })
        
        if 'navigate' in instruction_lower or 'go to' in instruction_lower:
            tasks.append({
                'id': len(tasks) + 1,
                'name': 'Navigate to URL',
                'description': instruction,
                'action_type': 'navigate',
                'url': 'https://example.com',
                'status': 'pending'
            })
        
        if not tasks:
            # Default task
            tasks.append({
                'id': 1,
                'name': 'Execute instruction',
                'description': instruction,
                'action_type': 'wait',
                'duration': 1,
                'status': 'pending'
            })
        
        return tasks

