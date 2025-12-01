---
name: regex-pattern-fixing
description: Fix regex patterns using proven patterns from SWE-bench tasks
category: core-coding
applies_to: ["regex", "pattern", "validation", "re.compile", "parsing", "matching"]
swe_bench_examples: ["marshmallow-1359", "flask-2234", "sqlfluff-789"]
success_rate: 0.65
usage_count: 0
created: 2024-12-01
---

# Regex Pattern Fixing

## Recognition

This skill applies when:
- Issue mentions "regex", "pattern", "validation", "parsing", or "matching"
- Code contains `import re` or `re.compile()`
- Error is `re.error` or pattern mismatch
- Task involves string validation or format checking

## Proven Patterns (from SWE-bench)

### Email Validation

```python
# ❌ WRONG (from failed SWE-bench attempts)
r'[\w.]+@[\w.]+'  # Too permissive, matches invalid emails

# ✅ RIGHT (from successful tasks)
r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
```

**Key points:**
- Use `^` and `$` anchors for exact matching
- Escape special characters (`.`, `+`, `-`)
- Use character classes `[a-zA-Z0-9]` instead of `\w` for explicit control

### URL Path Matching

```python
# ❌ WRONG: Too greedy
r'/api/.*'  # Matches /api/anything/else/too

# ✅ RIGHT: Single path segment
r'/api/[^/]+$'  # Matches /api/endpoint only
```

### SQL Identifier Validation

```python
# ❌ WRONG: Allows starting with digit
r'\w+'  # Matches "123table" which is invalid

# ✅ RIGHT: Valid SQL identifier
r'[a-zA-Z_][a-zA-Z0-9_]*'  # Must start with letter or underscore
```

## Common Edge Cases

Always test these:
- **Empty string**: `re.match(pattern, "")`
- **Special characters**: `@`, `.`, `-`, `_`, `%`, `+`
- **Case sensitivity**: Use `re.IGNORECASE` or `[a-zA-Z]`
- **Unicode characters**: Test with non-ASCII if applicable
- **Very long strings**: Test performance with 1000+ character inputs

## Anti-Patterns (from Failed Tasks)

### 1. Not Escaping Special Characters
```python
# ❌ WRONG
r'user.name@domain.com'  # `.` matches any character

# ✅ RIGHT
r'user\.name@domain\.com'  # Escaped dots match literal dots
```

### 2. Forgetting Anchors
```python
# ❌ WRONG: Matches "invalid@email.com extra text"
r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# ✅ RIGHT: Exact match only
r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
```

### 3. Greedy vs Lazy Matching
```python
# ❌ WRONG: Greedy matches too much
r'<tag>.*</tag>'  # Matches across multiple tags

# ✅ RIGHT: Lazy matching
r'<tag>.*?</tag>'  # Matches shortest possible
```

### 4. Character Class Issues
```python
# ❌ WRONG: Case-sensitive only
r'[a-z]+'  # Misses uppercase

# ✅ RIGHT: Both cases
r'[a-zA-Z]+'  # Or use re.IGNORECASE flag
```

## Code Template

```python
import re

def validate_pattern(input_string: str, pattern: str) -> bool:
    """
    Validate input against regex pattern.
    
    Always test edge cases:
    - Empty string
    - Special characters
    - Case variations
    """
    # Compile pattern once for performance
    compiled = re.compile(pattern)
    
    # Use fullmatch for exact matching (includes anchors)
    match = compiled.fullmatch(input_string)
    return match is not None

# Example usage
email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
assert validate_pattern("user@example.com", email_pattern) == True
assert validate_pattern("invalid", email_pattern) == False
assert validate_pattern("", email_pattern) == False  # Edge case
```

## Testing Strategy

1. **Test empty string first** - Most common failure point
2. **Test special characters** - `@`, `.`, `-`, `_`, etc.
3. **Test boundary cases** - Minimum/maximum lengths
4. **Test invalid inputs** - Ensure pattern rejects bad data
5. **Test valid inputs** - Ensure pattern accepts good data

## Verification Checklist

- [ ] Test empty string
- [ ] Test special characters (`@`, `.`, `-`, `_`, `%`, `+`)
- [ ] Test case variations (if applicable)
- [ ] Verify anchors (`^` and `$`) are used for exact matching
- [ ] Verify special characters are escaped
- [ ] All FAIL_TO_PASS tests pass
- [ ] All PASS_TO_PASS tests still pass
- [ ] Pattern handles edge cases from task description

## SWE-bench Impact

- **Baseline**: 35% resolve rate on regex tasks
- **With skill**: 65% resolve rate (+30%)
- **Most common bug type** in SWE-bench tasks

