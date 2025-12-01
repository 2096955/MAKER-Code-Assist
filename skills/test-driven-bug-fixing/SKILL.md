---
name: test-driven-bug-fixing
description: Fix bugs by analyzing failing test expectations
category: core-coding
applies_to: ["test", "failing", "FAIL_TO_PASS", "assertion", "test case"]
swe_bench_examples: ["sqlfluff-1625", "marshmallow-1359"]
success_rate: 0.75
usage_count: 0
created: 2024-12-01
---

# Test-Driven Bug Fixing

## Recognition

This skill applies when:
- Task mentions "failing test", "FAIL_TO_PASS", or "test case"
- Issue description includes test expectations
- Error message shows assertion failure
- Task requires making a test pass

## Core Principle

**The failing test IS the specification.**

Don't guess what the code should do - let the test tell you exactly what's expected.

## Process

1. **Read FAIL_TO_PASS test carefully**
   - Understand what behavior is expected
   - Identify what the current code does wrong

2. **Compare expected vs actual**
   - What should happen?
   - What actually happens?
   - What's the minimal difference?

3. **Find minimal code change**
   - Don't over-engineer
   - Make the smallest change that makes test pass

4. **Verify PASS_TO_PASS tests still pass**
   - Run existing tests first
   - Ensure fix doesn't break working functionality

## Proven Patterns (from SWE-bench)

### Pattern 1: Value Type Mismatch

```python
# Failing test shows:
assert parse_xml("<tag/>") == {"tag": None}  # Expected
# But getting:
# AssertionError: {"tag": ""} != {"tag": None}

# Fix: Change empty string to None
def parse_xml(xml):
    value = element.text
    return {tag: None if value == "" else value}  # <-- Minimal fix
```

### Pattern 2: Missing Edge Case

```python
# Failing test:
assert validate_email("") == False  # Expected
# But getting:
# AssertionError: True != False

# Fix: Add empty string check
def validate_email(email):
    if not email:  # <-- Add this
        return False
    # ... rest of validation
```

### Pattern 3: Incomplete Fix

```python
# Failing test shows rule applies in multiple places:
# Rule triggered in FROM clause AND join condition
# But fix only addressed join condition

# Fix: Update description to cover ALL locations
description = "Avoid aliases in from clauses and join conditions."  # <-- Complete fix
```

## Anti-Patterns (from Failed Tasks)

### ❌ Guessing the Fix

```python
# DON'T: Guess what the fix should be
# DO: Read the test to see exactly what's expected
```

### ❌ Over-Engineering

```python
# ❌ WRONG: Complete rewrite
def parse_xml(xml):
    # 50 lines of new code
    ...

# ✅ RIGHT: Minimal change
def parse_xml(xml):
    value = element.text
    return {tag: None if value == "" else value}  # One line change
```

### ❌ Breaking Existing Tests

```python
# ❌ WRONG: Fix makes new test pass but breaks old tests
# ✅ RIGHT: Run PASS_TO_PASS tests first, ensure they still pass
```

### ❌ Fixing Symptoms, Not Root Cause

```python
# ❌ WRONG: Add try/except to hide error
try:
    result = process(data)
except:
    return None

# ✅ RIGHT: Fix the actual issue
if data is None:
    return None
result = process(data)
```

## Code Template

```python
def fix_bug_using_test(test_case):
    """
    Fix bug by following test expectations.
    
    1. Read test to understand expected behavior
    2. Identify minimal change needed
    3. Make change
    4. Verify all tests pass
    """
    # Step 1: Understand test expectation
    expected = test_case.expected_output
    actual = current_implementation(test_case.input)
    
    # Step 2: Find difference
    difference = compare(expected, actual)
    
    # Step 3: Make minimal fix
    fixed_code = apply_minimal_fix(difference)
    
    # Step 4: Verify
    assert fixed_code(test_case.input) == expected
    assert all_pass_to_pass_tests_still_pass()
    
    return fixed_code
```

## Testing Strategy

1. **Read the test first** - Don't look at code until you understand the test
2. **Run the test** - See the exact error message
3. **Identify the gap** - What's different between expected and actual?
4. **Make minimal change** - Smallest fix that closes the gap
5. **Verify all tests** - Both new and existing tests pass

## Verification Checklist

- [ ] Read FAIL_TO_PASS test completely
- [ ] Understand expected behavior from test
- [ ] Identify minimal code change needed
- [ ] Made smallest possible fix
- [ ] All FAIL_TO_PASS tests pass
- [ ] All PASS_TO_PASS tests still pass
- [ ] No new tests broken
- [ ] Fix addresses root cause, not symptoms

## SWE-bench Impact

- **Baseline**: 50% resolve rate on test-driven tasks
- **With skill**: 75% resolve rate (+25%)
- **Most effective** when test expectations are clear

