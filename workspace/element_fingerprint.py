"""
Element Fingerprinting: Creates lightweight signatures for elements.
Enables re-identification when selectors fail.
"""
from playwright.sync_api import ElementHandle, Page
from typing import Dict, Optional
import hashlib
import json


class ElementFingerprint:
    """Creates and manages element fingerprints for resilient identification"""
    
    @staticmethod
    def create_fingerprint(element: ElementHandle, page: Page) -> Dict:
        """
        Create a fingerprint for an element.
        
        Args:
            element: Playwright ElementHandle
            page: Playwright Page
        
        Returns:
            Dict containing fingerprint data
        """
        try:
            # Get element properties
            tag = element.evaluate('el => el.tagName.toLowerCase()')
            text = element.evaluate('el => (el.textContent || "").trim()')
            visible_text = element.evaluate('''
                el => {
                    const style = window.getComputedStyle(el);
                    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
                        return "";
                    }
                    return (el.textContent || "").trim();
                }
            ''')
            
            # Get key attributes
            attributes = {}
            key_attrs = ['id', 'name', 'data-testid', 'data-cy', 'data-test', 
                        'aria-label', 'aria-labelledby', 'role', 'type', 'class']
            
            for attr in key_attrs:
                try:
                    value = element.get_attribute(attr)
                    if value:
                        attributes[attr] = value
                except:
                    pass
            
            # Get bounding box
            box = element.bounding_box()
            position = {
                'x': box['x'] if box else None,
                'y': box['y'] if box else None,
                'width': box['width'] if box else None,
                'height': box['height'] if box else None
            }
            
            # Get parent context (first parent with ID or class)
            parent_context = element.evaluate('''
                el => {
                    let parent = el.parentElement;
                    let depth = 0;
                    while (parent && depth < 3) {
                        if (parent.id) return `#${parent.id}`;
                        if (parent.className && typeof parent.className === 'string') {
                            const classes = parent.className.split(' ').filter(c => c);
                            if (classes.length > 0) return `.${classes[0]}`;
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                    return null;
                }
            ''')
            
            # Create fingerprint hash
            fingerprint_data = {
                'tag': tag,
                'text': visible_text[:100] if visible_text else '',  # Limit text length
                'attributes': attributes,
                'position': position,
                'parent_context': parent_context
            }
            
            fingerprint_hash = hashlib.md5(
                json.dumps(fingerprint_data, sort_keys=True).encode()
            ).hexdigest()
            
            return {
                'hash': fingerprint_hash,
                'tag': tag,
                'text': visible_text[:100] if visible_text else '',
                'full_text': text[:200] if text else '',
                'attributes': attributes,
                'position': position,
                'parent_context': parent_context,
                'fingerprint_data': fingerprint_data
            }
            
        except Exception as e:
            print(f"Error creating fingerprint: {e}")
            return {
                'hash': '',
                'tag': '',
                'text': '',
                'attributes': {},
                'position': {},
                'parent_context': None
            }
    
    @staticmethod
    def fingerprint_from_info(element_info: Dict) -> str:
        """
        Create fingerprint hash from element info (when element not yet found).
        
        Args:
            element_info: Dict with selector, text, attributes, etc.
        
        Returns:
            Fingerprint hash string
        """
        fingerprint_data = {
            'text': element_info.get('text', ''),
            'attributes': element_info.get('attributes', {}),
            'selector': element_info.get('selector', '')
        }
        
        return hashlib.md5(
            json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()

