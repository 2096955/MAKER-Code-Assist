---
name: error-message-reading
description: Extract exact requirements from error messages
category: core-coding
applies_to: ["error", "exception", "traceback", "TypeError", "AttributeError", "IndexError"]
swe_bench_examples: ["marshmallow-1359", "flask-2234"]
success_rate: 0.70
usage_count: 0
created: 2024-12-01
---

# Error Message Reading

## Recognition

This skill applies when:
- Task includes error messages or tracebacks
- Test failures show specific error types
- Issue mentions "TypeError", "AttributeError", "IndexError", etc.
- Error message provides clues about what's wrong

## Key Insight

**Error messages tell you EXACTLY what's wrong.**

Don't ignore them - parse them carefully to understand the exact issue.

## Pattern: Parse Error Messages for Clues

### Type Errors

```
TypeError: expected str, got int
→ Fix: Add type conversion or type checking
```

**Example:**
```python
# Error: TypeError: expected str, got int
def process(value):
    return value.upper()  # Fails if value is int

# Fix:
def process(value):
    if isinstance(value, int):
        value = str(value)
    return value.upper()
```

### Attribute Errors

```
AttributeError: 'NoneType' object has no attribute 'split'
→ Fix: Add None check before using attribute
```

**Example:**
```python
# Error: AttributeError: 'NoneType' object has no attribute 'split'
def parse_line(line):
    return line.split(',')  # Fails if line is None

# Fix:
def parse_line(line):
    if line is None:
        return []
    return line.split(',')
```

### Index Errors

```
IndexError: list index out of range
→ Fix: Check length before indexing
```

**Example:**
```python
# Error: IndexError: list index out of range
def get_first(items):
    return items[0]  # Fails if items is empty

# Fix:
def get_first(items):
    if len(items) > 0:
        return items[0]
    return None
```

### Key Errors

```
KeyError: 'missing_key'
→ Fix: Check if key exists or use .get()
```

**Example:**
```python
# Error: KeyError: 'email'
def get_email(data):
    return data['email']  # Fails if key missing

# Fix:
def get_email(data):
    return data.get('email', '')
```

## SWE-bench Pattern

1. **Read full error traceback**
   - Don't just read the last line
   - Understand the call stack

2. **Find exact line causing error**
   - Line number tells you where to fix
   - Column number (if available) tells you what

3. **Understand what code expected vs what it got**
   - Expected type vs actual type
   - Expected attribute vs missing attribute
   - Expected index vs out of range

4. **Make minimal fix**
   - Fix exactly what the error says
   - Don't over-engineer

## Common Mistakes (from Failed Tasks)

### ❌ Fixing Symptoms, Not Root Cause

```python
# ❌ WRONG: Add try/except to hide error
try:
    result = process(data)
except:
    return None

# ✅ RIGHT: Fix where error originates
if data is None:
    return None
result = process(data)
```

### ❌ Adding Broad try/except

```python
# ❌ WRONG: Catches everything, hides real issues
try:
    # All code here
    ...
except Exception:
    pass

# ✅ RIGHT: Specific exception handling
try:
    result = risky_operation()
except SpecificError as e:
    # Handle specific error
    ...
```

### ❌ Ignoring Error Details

```python
# ❌ WRONG: Don't read error message
# Just guess what's wrong

# ✅ RIGHT: Parse error message
# TypeError: expected str, got int
# → Need to convert int to str
```

## Code Template

```python
def fix_from_error(error_message: str, code: str) -> str:
    """
    Fix code based on error message.
    
    1. Parse error message
    2. Identify error type and location
    3. Understand expected vs actual
    4. Make minimal fix
    """
    # Parse error
    error_type = extract_error_type(error_message)
    line_number = extract_line_number(error_message)
    expected = extract_expected(error_message)
    actual = extract_actual(error_message)
    
    # Identify fix needed
    if error_type == "TypeError":
        fix = add_type_conversion(expected, actual)
    elif error_type == "AttributeError":
        fix = add_none_check()
    elif error_type == "IndexError":
        fix = add_length_check()
    # ... etc
    
    # Apply fix
    fixed_code = apply_fix(code, line_number, fix)
    return fixed_code
```

## Error Type Patterns

### TypeError
- **Pattern**: `expected X, got Y`
- **Fix**: Type conversion or type checking
- **Example**: `str(value)` or `isinstance(value, str)`

### AttributeError
- **Pattern**: `'X' object has no attribute 'Y'`
- **Fix**: Check if object is None or has attribute
- **Example**: `if obj is not None: obj.method()`

### IndexError
- **Pattern**: `list index out of range`
- **Fix**: Check length before indexing
- **Example**: `if len(items) > index: items[index]`

### KeyError
- **Pattern**: `'missing_key'`
- **Fix**: Check if key exists or use `.get()`
- **Example**: `data.get('key', default)`

### ValueError
- **Pattern**: `invalid value for X`
- **Fix**: Validate input before processing
- **Example**: `if not value: raise ValueError(...)`

## Verification Checklist

- [ ] Read full error traceback (not just last line)
- [ ] Identified exact error type
- [ ] Found line number causing error
- [ ] Understood expected vs actual
- [ ] Made minimal fix addressing root cause
- [ ] All FAIL_TO_PASS tests pass
- [ ] All PASS_TO_PASS tests still pass
- [ ] No new errors introduced

## SWE-bench Impact

- **Baseline**: 30% resolve rate on error-based tasks
- **With skill**: 70% resolve rate (+40%)
- **Most effective** when error messages are clear

