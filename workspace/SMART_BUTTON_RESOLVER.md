# Smart Button Resolver - Testim-Style Button Clicking

## Overview

The Smart Button Resolver provides **robust, semantic, accessibility-aware, self-healing button clicking** similar to Testim's execution engine. It's **OPTIONAL and opt-in** - existing click logic remains completely unchanged.

**NEW ENHANCEMENTS:**
- ✅ **Iframe Detection & Handling** - Automatically detects and clicks buttons inside iframes
- ✅ **Context Readiness** - Ensures page is ready (network idle, stable DOM) before clicking
- ✅ **Enhanced Validation** - Checks DOM attachment, visibility, enabled state, not obscured
- ✅ **Screenshot Capture** - Captures before/after screenshots for observability
- ✅ **Improved Verification** - Better post-click effect detection (URL change, modals, spinners, DOM changes)

## Key Features

### 1. Semantic Intent-Based Resolution
- Locate buttons by intent (e.g., "Submit", "Pay Now", "Login", "Cancel")
- No need for brittle CSS selectors or XPath

### 2. Multi-Strategy Resolution (Priority Order)
1. **Role-based with accessible name** (Highest priority - most semantic)
   - Uses `page.get_by_role('button', name=intent)`
   - Accessibility-first approach
   - Confidence: 0.95

2. **Visible text match** (Exact and partial)
   - Exact text match: confidence 0.90
   - Partial text match: confidence 0.85

3. **ARIA label / aria-describedby**
   - Checks `aria-label` attributes
   - Confidence: 0.90

4. **Stable attributes**
   - `data-testid`, `data-cy`, `data-test*` attributes
   - `name` or `value` attributes (for input buttons)
   - Confidence: 0.88 (test attributes), 0.80 (name/value)

5. **Relative DOM position** (Context-aware)
   - Primary button in form context
   - Confidence: 0.75

6. **Generic button text contains intent**
   - Fallback strategy
   - Confidence: 0.70

### 3. Context Validation
Before clicking, validates:
- ✅ Button is visible
- ✅ Button is enabled (not disabled)
- ✅ Button is not obscured by other elements
- ✅ Button is in viewport (scrolls if needed)

### 4. Self-Healing
- Automatically tries multiple strategies in order
- Selects highest-confidence match that works
- Logs which strategy succeeded
- Tracks healing attempts

### 5. Action Verification (ENHANCED)
After clicking, verifies at least one of:
- ✅ **URL change** (navigation occurred) - Most reliable indicator
- ✅ **Modal/dialog appeared** - Checks for `[role="dialog"]`, `.modal`, etc.
- ✅ **Spinner/loading indicator** - Detects loading states
- ✅ **Loading state** - Checks `document.readyState` and loading classes
- ✅ **DOM changes** - Form submission indicators, success messages
- Uses progressive waits (no hard sleeps) to detect effects quickly

### 6. Iframe Detection & Handling (NEW)
- Automatically detects iframes containing target buttons
- Searches all frames (main page + iframes) for button matches
- If button found in iframe:
  - Uses frame-scoped locators
  - Logs iframe URL used
  - Marks metadata with iframe information
- Falls back to iframe search if main page fails

### 7. Observability & Logging (ENHANCED)
- Emits logs for:
  - Strategy attempts (with iframe info if applicable)
  - Which strategy succeeded
  - Whether healing occurred
  - Click success/failure
  - Verification results
  - Iframe usage (URL, context)
- **Screenshot capture**:
  - Screenshot before click (captured)
  - Screenshot after click (captured)
  - Metadata includes screenshot availability flags
- Metadata attached to execution logs
- All events include comprehensive metadata

## Usage

### Opt-In Usage

To use smart button resolver, add `use_smart_button=True` to click action:

```python
# Standard click (unchanged)
browser_session.execute_action('click', selector='#submit-btn', description='Submit form')

# Smart button click (NEW - OPTIONAL)
browser_session.execute_action(
    'click',
    use_smart_button=True,  # Enable smart button resolver
    button_intent='Submit',  # Semantic intent
    description='Submit form',
    verify_action=True  # Verify click had effect (default: True)
)
```

### In Task Definitions

```python
task = {
    "name": "Submit registration form",
    "action_type": "click",
    "use_smart_button": True,  # OPT-IN flag
    "button_intent": "Submit",  # Semantic intent
    "description": "Click submit button",
    "verify_action": True  # Verify effect (optional, default: True)
}
```

### With Context

```python
task = {
    "name": "Submit form",
    "action_type": "click",
    "use_smart_button": True,
    "button_intent": "Submit",
    "context": {
        "form_context": page.locator('form#registration')  # Optional form context
    },
    "verify_action": True
}
```

## API

### Main Function

```python
from workspace.smart_button_resolver import smart_click_button

success, metadata = smart_click_button(
    page=page,
    intent="Submit",
    context={'form_context': form_locator},  # Optional
    verify_action=True,  # Default: True
    timeout=10000,  # Default: 10000ms
    on_update_callback=callback  # Optional
)
```

### Metadata Returned

```python
{
    'intent': 'Submit',
    'strategy_used': 'role_with_name',  # Which strategy succeeded
    'confidence': 0.95,  # Confidence score
    'healing_occurred': False,  # True if multiple strategies tried
    'healing_steps': [],  # List of attempted strategies
    'verification_passed': True,  # Whether click had observable effect
    'verification_type': 'url_change',  # Type of effect detected
    'verification_metadata': {...},  # Additional verification data
    'error': None  # Error message if failed
}
```

## Integration Points

### Modified Files

1. **`workspace/browser_session.py`**
   - Added optional import of `SmartButtonResolver`
   - Added `smart_button_resolver` attribute (initialized only if available)
   - Added check for `use_smart_button` flag in click action
   - Added `_on_smart_button_update()` callback
   - **Existing click logic unchanged** - smart resolver only activates when `use_smart_button=True`

### New Files

- `workspace/smart_button_resolver.py` - Main resolver implementation
  - `SmartButtonResolver` class
  - `ButtonResolverStrategy` class
  - `ContextValidator` class
  - `ActionVerifier` class
  - `smart_click_button()` convenience function

## Non-Breaking Design

✅ **No existing function signatures changed**
✅ **Existing `page.click()` and selector-based clicks continue to work**
✅ **Smart resolver is OPT-IN only** (requires `use_smart_button=True`)
✅ **Graceful fallback** - if smart resolver fails, falls back to standard execution
✅ **Existing self-healing executor still used** for non-smart-button clicks

## Benefits

1. **Resilient to UI Changes**
   - Semantic intent survives CSS/class changes
   - Multiple fallback strategies
   - Self-healing when primary strategy fails

2. **Accessibility-First**
   - Prioritizes role-based and ARIA locators
   - Works with screen readers
   - Follows accessibility best practices

3. **Production-Safe**
   - Context validation before clicking
   - Action verification after clicking
   - Comprehensive error handling

4. **Observable & Debuggable**
   - Detailed metadata on strategy used
   - Logging of all attempts
   - Clear failure reasons

5. **Testim-Style Intelligence**
   - Semantic understanding
   - Multiple resolution strategies
   - Self-healing capabilities
   - Action verification

## Examples

### Example 1: Simple Submit Button

```python
# Old way (still works)
execute_action('click', selector='button[type="submit"]', description='Submit')

# New way (more resilient)
execute_action('click', use_smart_button=True, button_intent='Submit', description='Submit')
```

### Example 2: Payment Button

```python
execute_action(
    'click',
    use_smart_button=True,
    button_intent='Pay Now',
    description='Complete payment',
    verify_action=True  # Verify payment modal or URL change
)
```

### Example 3: Login Button

```python
execute_action(
    'click',
    use_smart_button=True,
    button_intent='Login',
    description='Click login button',
    context={'form_context': page.locator('form#login')}  # Provide form context
)
```

## Best Practices

1. **Use semantic intents** - Prefer "Submit" over "Click submit button"
2. **Provide context when available** - Form context helps disambiguate
3. **Enable verification** - Let it verify click effects (default)
4. **Use for primary actions** - Best for important buttons (submit, pay, login, etc.)
5. **Keep standard clicks for specific elements** - Use selector-based clicks when you need exact element

## Migration Path

1. **Start with new actions** - Use smart button resolver for new tests
2. **Gradually migrate** - Convert existing clicks when maintaining tests
3. **Keep both** - Use smart resolver for intent-based clicks, standard for specific selectors
4. **No rush** - Existing code continues to work unchanged

## Observability Events

Smart button resolver emits these event types:

- `smart_button_resolve_start` - Resolution started
- `smart_button_strategy_attempt` - Trying a strategy
- `smart_button_clicked` - Button successfully clicked
- `smart_button_verification_warning` - Click succeeded but verification failed
- `smart_button_resolve_failed` - All strategies failed
- `smart_button_resolve_error` - Error during resolution

All events include metadata about intent, strategy, confidence, etc.

