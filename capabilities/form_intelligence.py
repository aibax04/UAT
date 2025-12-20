"""
Form Intelligence Module
========================

Dynamically detects and analyzes forms, builds semantic schemas,
and fills fields contextually using LLM reasoning + Playwright DOM APIs.
"""

import os
import json
import re
from typing import Dict, Any, Optional, List
from playwright.sync_api import Page
import google.generativeai as genai
from dotenv import load_dotenv

from .base_module import BaseCapabilityModule

load_dotenv()


class FormIntelligenceModule(BaseCapabilityModule):
    """Intelligent form detection and contextual filling"""
    
    def __init__(self, page: Page, on_update_callback: Optional[callable] = None):
        super().__init__(page, on_update_callback)
        # Initialize Gemini for form analysis
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            self.llm = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.llm = None
            print("Warning: GEMINI_API_KEY not set, form intelligence will use rule-based filling only")
    
    def can_handle(self, intent_data: Dict[str, Any]) -> bool:
        """Check if this is a form-related task"""
        action_type = intent_data.get('action_type', '')
        description = intent_data.get('description', '').lower()
        task_name = intent_data.get('task_name', '').lower()
        
        # Check for form-related keywords
        form_keywords = ['form', 'fill', 'input', 'submit', 'register', 'signup', 'contact']
        return (action_type in ['fill', 'form'] or 
                any(keyword in description or keyword in task_name for keyword in form_keywords) or
                intent_data.get('capability') == 'form_intelligence')
    
    def execute(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect forms and fill them intelligently
        
        Args:
            intent_data: Must contain 'intent' (what to fill) and optional 'form_data'
            
        Returns:
            Result dict with success status and filled field details
        """
        try:
            self._emit_update('capability_start', {
                'message': 'Starting form intelligence analysis',
                'intent': intent_data.get('intent', 'fill form')
            })
            
            # Detect forms on the page
            form_schema = self._detect_forms()
            if not form_schema:
                return self._create_result(
                    False,
                    error="No forms detected on the page"
                )
            
            self._emit_update('capability_progress', {
                'message': f'Detected {len(form_schema.get("forms", []))} form(s)',
                'schema': form_schema
            })
            
            # Build intent data from task description or provided form_data
            form_data = intent_data.get('form_data') or self._extract_form_intent(
                intent_data.get('intent') or intent_data.get('description', ''),
                form_schema
            )
            
            # Fill forms intelligently
            fill_results = self._fill_forms(form_schema, form_data)
            
            # Capture screenshot
            screenshot = self._capture_screenshot("After form fill")
            
            result = {
                'forms_detected': len(form_schema.get('forms', [])),
                'fields_filled': fill_results.get('fields_filled', 0),
                'fill_results': fill_results.get('results', []),
                'screenshot': screenshot is not None
            }
            
            metadata = {
                'form_schema': form_schema,
                'form_data_used': form_data,
                'timestamp': self.page.evaluate('Date.now()')
            }
            
            self._emit_update('capability_complete', {
                'message': f'Successfully filled {fill_results.get("fields_filled", 0)} field(s)',
                'result': result
            })
            
            return self._create_result(True, result=result, metadata=metadata)
            
        except Exception as e:
            error_msg = f"Form intelligence error: {str(e)}"
            self._emit_update('capability_error', {'error': error_msg})
            return self._create_result(False, error=error_msg)
    
    def _detect_forms(self) -> Dict[str, Any]:
        """Detect all forms on the page and build semantic schema"""
        try:
            # Extract form structure using Playwright
            form_data = self.page.evaluate("""
                () => {
                    const forms = Array.from(document.querySelectorAll('form'));
                    return forms.map((form, idx) => {
                        const fields = Array.from(form.querySelectorAll('input, textarea, select'));
                        return {
                            index: idx,
                            id: form.id || null,
                            name: form.name || null,
                            action: form.action || null,
                            method: form.method || 'get',
                            fields: fields.map(field => ({
                                type: field.type || field.tagName.toLowerCase(),
                                name: field.name || null,
                                id: field.id || null,
                                label: (() => {
                                    const label = field.closest('label') || 
                                                  document.querySelector(`label[for="${field.id}"]`);
                                    return label ? label.textContent.trim() : null;
                                })(),
                                placeholder: field.placeholder || null,
                                required: field.required || false,
                                ariaLabel: field.getAttribute('aria-label') || null,
                                ariaLabelledBy: field.getAttribute('aria-labelledby') || null,
                                value: field.value || '',
                                options: field.tagName === 'SELECT' ? 
                                    Array.from(field.options).map(opt => ({
                                        value: opt.value,
                                        text: opt.text
                                    })) : null
                            }))
                        };
                    });
                }
            """)
            
            return {'forms': form_data, 'total_fields': sum(len(f['fields']) for f in form_data)}
            
        except Exception as e:
            print(f"Error detecting forms: {e}")
            return {}
    
    def _extract_form_intent(self, intent_text: str, form_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract form filling intent from natural language using LLM or rules"""
        
        # Rule-based extraction if LLM not available
        if not self.llm:
            return self._rule_based_extraction(intent_text, form_schema)
        
        # LLM-based extraction
        try:
            fields_summary = []
            for form in form_schema.get('forms', []):
                for field in form.get('fields', []):
                    field_desc = f"- {field.get('label') or field.get('placeholder') or field.get('name', 'unknown')} ({field.get('type', 'text')})"
                    fields_summary.append(field_desc)
            
            prompt = f"""Analyze this form filling request and extract structured data.

User Intent: {intent_text}

Available Form Fields:
{chr(10).join(fields_summary)}

Return a JSON object mapping field identifiers (name, id, label, or placeholder) to values.
Use contextual reasoning:
- Email fields → valid email format
- Password fields → test password
- Phone fields → valid phone format
- Name fields → realistic names
- Address fields → complete addresses

Return ONLY valid JSON, no markdown, no explanation.
Example: {{"email": "test@example.com", "password": "Test123!", "name": "John Doe"}}
"""
            
            response = self.llm.generate_content(prompt)
            json_text = response.text.strip()
            
            # Clean JSON (remove markdown code blocks if present)
            json_text = re.sub(r'^```json\n?', '', json_text)
            json_text = re.sub(r'\n?```$', '', json_text)
            
            return json.loads(json_text)
            
        except Exception as e:
            print(f"LLM extraction failed, falling back to rules: {e}")
            return self._rule_based_extraction(intent_text, form_schema)
    
    def _rule_based_extraction(self, intent_text: str, form_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based form data extraction (fallback)"""
        form_data = {}
        intent_lower = intent_text.lower()
        
        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', intent_text)
        if email_match:
            form_data['email'] = email_match.group(0)
        
        # Extract phone
        phone_match = re.search(r'[\d\s\-\+\(\)]{10,}', intent_text)
        if phone_match and 'phone' in intent_lower:
            form_data['phone'] = phone_match.group(0).strip()
        
        # Default test data for common fields
        for form in form_schema.get('forms', []):
            for field in form.get('fields', []):
                field_id = field.get('name') or field.get('id') or field.get('label', '').lower()
                field_type = field.get('type', '').lower()
                
                if not field_id:
                    continue
                
                # Map common field patterns to test data
                if 'email' in field_id or field_type == 'email':
                    form_data[field_id] = form_data.get('email', 'test@example.com')
                elif 'password' in field_id or field_type == 'password':
                    form_data[field_id] = 'Test123!@#'
                elif 'phone' in field_id:
                    form_data[field_id] = form_data.get('phone', '+1-555-123-4567')
                elif 'name' in field_id and 'first' in field_id:
                    form_data[field_id] = 'John'
                elif 'name' in field_id and 'last' in field_id:
                    form_data[field_id] = 'Doe'
                elif 'name' in field_id:
                    form_data[field_id] = 'John Doe'
                elif 'address' in field_id:
                    form_data[field_id] = '123 Test Street, City, State 12345'
        
        return form_data
    
    def _fill_forms(self, form_schema: Dict[str, Any], form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fill forms using detected schema and extracted data"""
        filled_count = 0
        fill_results = []
        
        for form in form_schema.get('forms', []):
            for field in form.get('fields', []):
                # Skip hidden fields and buttons
                if field.get('type') in ['hidden', 'submit', 'button']:
                    continue
                
                # Find matching data for this field
                field_value = None
                field_key = field.get('name') or field.get('id') or field.get('label', '').lower()
                
                # Try exact match
                if field_key in form_data:
                    field_value = form_data[field_key]
                else:
                    # Try fuzzy matching
                    for key, value in form_data.items():
                        if key.lower() in field_key or field_key in key.lower():
                            field_value = value
                            break
                
                if not field_value:
                    continue
                
                # Fill the field
                try:
                    selector = self._build_field_selector(field)
                    if selector:
                        if field.get('type') == 'select':
                            # Handle select dropdown
                            self.page.select_option(selector, str(field_value))
                        else:
                            # Handle input/textarea
                            self.page.fill(selector, str(field_value))
                        
                        filled_count += 1
                        fill_results.append({
                            'field': field_key,
                            'value': field_value,
                            'selector': selector,
                            'success': True
                        })
                except Exception as e:
                    fill_results.append({
                        'field': field_key,
                        'value': field_value,
                        'error': str(e),
                        'success': False
                    })
        
        return {'fields_filled': filled_count, 'results': fill_results}
    
    def _build_field_selector(self, field: Dict[str, Any]) -> Optional[str]:
        """Build a Playwright selector for a field"""
        if field.get('id'):
            return f"#{field['id']}"
        elif field.get('name'):
            return f"[name='{field['name']}']"
        else:
            # Fallback: try to find by label text
            label = field.get('label')
            if label:
                try:
                    # Find label element and get associated field
                    label_selector = f"//label[contains(text(), '{label}')]"
                    return f"{label_selector}/following-sibling::*[1]"
                except:
                    pass
        return None


def fill_form(page: Page, intent_data: Dict[str, Any], 
              on_update_callback: Optional[callable] = None) -> Dict[str, Any]:
    """
    Convenience function to fill forms intelligently
    
    Args:
        page: Playwright page object
        intent_data: Dict with 'intent' (description) and optional 'form_data'
        on_update_callback: Optional callback for updates
        
    Returns:
        Result dict with success status and details
    """
    module = FormIntelligenceModule(page, on_update_callback)
    return module.execute(intent_data)

