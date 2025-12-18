"""
Smart Locator Engine: Generates multiple locator strategies for elements.
Similar to Testim's AI-powered element identification.
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class LocatorCandidate:
    """Represents a locator candidate with confidence score"""
    strategy: str  # 'text', 'role', 'id', 'class', 'attribute', 'position', 'hierarchy'
    locator: str  # The actual locator string
    confidence: float  # 0.0 to 1.0
    metadata: Dict  # Additional context (e.g., text content, attributes)


class SmartLocatorEngine:
    """Generates and ranks multiple locator strategies for elements"""
    
    def __init__(self, page: Page):
        self.page = page
        self.locator_memory = {}  # Store successful locators: element_fingerprint -> best_locator
    
    def generate_locators(self, element_info: Dict) -> List[LocatorCandidate]:
        """
        Generate multiple locator candidates for an element.
        
        Args:
            element_info: Dict containing:
                - selector (optional): Original selector hint
                - text (optional): Visible text to find
                - role (optional): ARIA role
                - attributes (optional): Dict of attributes
                - description (optional): Human description
        
        Returns:
            List of LocatorCandidate objects, ranked by confidence
        """
        candidates = []
        
        # Strategy 1: Text-based locator (highest confidence for unique text)
        if element_info.get('text'):
            text = element_info['text'].strip()
            if text:
                # Exact text match
                candidates.append(LocatorCandidate(
                    strategy='text',
                    locator=f'text="{text}"',
                    confidence=0.95 if len(text) > 10 else 0.85,
                    metadata={'text': text}
                ))
                # Partial text match
                if len(text) > 5:
                    candidates.append(LocatorCandidate(
                        strategy='text_partial',
                        locator=f'text=/{text[:20]}/',
                        confidence=0.75,
                        metadata={'text': text}
                    ))
        
        # Strategy 2: Role-based locator (ARIA roles)
        if element_info.get('role'):
            role = element_info['role']
            candidates.append(LocatorCandidate(
                strategy='role',
                locator=f'role={role}',
                confidence=0.80,
                metadata={'role': role}
            ))
            # Role + name combination
            if element_info.get('text'):
                candidates.append(LocatorCandidate(
                    strategy='role_name',
                    locator=f'role={role}[name="{element_info["text"]}"]',
                    confidence=0.90,
                    metadata={'role': role, 'text': element_info['text']}
                ))
        
        # Strategy 3: ID-based locator (if provided)
        if element_info.get('selector'):
            selector = element_info['selector']
            # Try original selector first
            candidates.append(LocatorCandidate(
                strategy='original',
                locator=selector,
                confidence=0.70,  # Lower confidence - may be brittle
                metadata={'original': selector}
            ))
            
            # Extract ID if present
            if selector.startswith('#'):
                candidates.append(LocatorCandidate(
                    strategy='id',
                    locator=selector,
                    confidence=0.85,
                    metadata={'id': selector[1:]}
                ))
            # Extract class if present
            elif selector.startswith('.'):
                candidates.append(LocatorCandidate(
                    strategy='class',
                    locator=selector,
                    confidence=0.65,  # Classes can change
                    metadata={'class': selector[1:]}
                ))
        
        # Strategy 4: Attribute-based locators
        if element_info.get('attributes'):
            attrs = element_info['attributes']
            for attr_name, attr_value in attrs.items():
                if attr_name in ['data-testid', 'data-cy', 'data-test', 'name', 'aria-label']:
                    # High-value attributes
                    candidates.append(LocatorCandidate(
                        strategy='attribute',
                        locator=f'[{attr_name}="{attr_value}"]',
                        confidence=0.90,
                        metadata={attr_name: attr_value}
                    ))
                elif attr_name in ['id', 'name']:
                    candidates.append(LocatorCandidate(
                        strategy='attribute',
                        locator=f'[{attr_name}="{attr_value}"]',
                        confidence=0.85,
                        metadata={attr_name: attr_value}
                    ))
        
        # Strategy 5: DOM hierarchy context (if we have parent info)
        if element_info.get('parent_context'):
            parent = element_info['parent_context']
            if element_info.get('text'):
                candidates.append(LocatorCandidate(
                    strategy='hierarchy',
                    locator=f'{parent} >> text="{element_info["text"]}"',
                    confidence=0.80,
                    metadata={'parent': parent, 'text': element_info['text']}
                ))
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        return candidates
    
    def find_element_by_fingerprint(self, fingerprint: Dict) -> Optional[Dict]:
        """
        Find element in DOM using fingerprint similarity.
        Used for self-healing when selectors fail.
        
        Args:
            fingerprint: Element fingerprint dict
        
        Returns:
            Element handle dict or None
        """
        try:
            # Build search query from fingerprint
            tag = fingerprint.get('tag', '*')
            text = fingerprint.get('text', '')
            attributes = fingerprint.get('attributes', {})
            
            # Try to find by text first
            if text:
                try:
                    elements = self.page.query_selector_all(f'text="{text}"')
                    if elements:
                        for elem in elements:
                            if self._match_fingerprint(elem, fingerprint):
                                return {'element': elem, 'confidence': 0.85}
                except:
                    pass
            
            # Try by attributes
            for attr_name, attr_value in attributes.items():
                try:
                    selector = f'[{attr_name}="{attr_value}"]'
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        for elem in elements:
                            if self._match_fingerprint(elem, fingerprint):
                                return {'element': elem, 'confidence': 0.80}
                except:
                    pass
            
            # Try by tag + text combination
            if tag and text:
                try:
                    elements = self.page.query_selector_all(f'{tag}:has-text("{text}")')
                    if elements:
                        for elem in elements[:5]:  # Limit search
                            if self._match_fingerprint(elem, fingerprint):
                                return {'element': elem, 'confidence': 0.75}
                except:
                    pass
            
            return None
            
        except Exception as e:
            print(f"Error finding element by fingerprint: {e}")
            return None
    
    def _match_fingerprint(self, element, fingerprint: Dict) -> bool:
        """Check if element matches fingerprint"""
        try:
            # Check tag
            tag = fingerprint.get('tag')
            if tag and element.evaluate('el => el.tagName.toLowerCase()') != tag.lower():
                return False
            
            # Check text (partial match)
            text = fingerprint.get('text', '')
            if text:
                elem_text = element.evaluate('el => el.textContent || ""').strip()
                if text.lower() not in elem_text.lower() and elem_text.lower() not in text.lower():
                    return False
            
            # Check key attributes
            key_attrs = fingerprint.get('attributes', {})
            for attr_name, attr_value in key_attrs.items():
                if attr_name in ['data-testid', 'data-cy', 'id', 'name']:
                    elem_attr = element.get_attribute(attr_name)
                    if elem_attr != attr_value:
                        return False
            
            return True
            
        except:
            return False
    
    def record_successful_locator(self, element_fingerprint: str, locator: LocatorCandidate):
        """Store successful locator for future use"""
        if element_fingerprint not in self.locator_memory:
            self.locator_memory[element_fingerprint] = []
        
        # Add to memory with success count
        found = False
        for entry in self.locator_memory[element_fingerprint]:
            if entry['locator'].locator == locator.locator:
                entry['success_count'] += 1
                entry['locator'].confidence = min(1.0, entry['locator'].confidence + 0.05)
                found = True
                break
        
        if not found:
            self.locator_memory[element_fingerprint].append({
                'locator': locator,
                'success_count': 1
            })
        
        # Sort by success count
        self.locator_memory[element_fingerprint].sort(
            key=lambda x: (x['success_count'], x['locator'].confidence),
            reverse=True
        )
    
    def get_cached_locators(self, element_fingerprint: str) -> List[LocatorCandidate]:
        """Get previously successful locators for an element"""
        if element_fingerprint in self.locator_memory:
            return [entry['locator'] for entry in self.locator_memory[element_fingerprint]]
        return []

