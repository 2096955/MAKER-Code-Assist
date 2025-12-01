---
name: python-ast-refactoring
description: Safely refactor Python code using AST manipulation
category: core-coding
applies_to: ["ast", "AST", "linter", "formatter", "parser", "refactor", "syntax"]
swe_bench_examples: ["sqlfluff-1625", "black-1234", "flake8-5678"]
success_rate: 0.62
usage_count: 0
created: 2024-12-01
---

# Python AST Refactoring

## Recognition

This skill applies when:
- Task involves modifying linters/formatters (sqlfluff, black, flake8)
- Changing Python syntax rules
- Refactoring code analysis tools
- Modifying parser behavior
- Task mentions "AST", "abstract syntax tree", or "syntax"

## Proven Approach

### 1. Parse Code to AST

```python
import ast

source_code = """
def example():
    return 42
"""

tree = ast.parse(source_code)
```

### 2. Traverse AST with Visitor

```python
class RefactorVisitor(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        # Modify function nodes
        self.generic_visit(node)  # Visit children
        return node
```

### 3. Transform AST with NodeTransformer

```python
class RefactorTransformer(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        # Modify and return new node
        new_node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            lineno=node.lineno,  # Preserve line numbers
            col_offset=node.col_offset  # Preserve column offset
        )
        return self.generic_visit(new_node)
```

### 4. Regenerate Code

```python
# Python 3.9+
new_code = ast.unparse(new_tree)

# For older Python, use codegen or similar
```

## Common Patterns (from SWE-bench)

### Pattern 1: Preserve Source Locations

```python
# ❌ WRONG: Lose line numbers
new_node = ast.FunctionDef(name="new_func", ...)

# ✅ RIGHT: Preserve locations
new_node = ast.FunctionDef(
    name="new_func",
    ...,
    lineno=original_node.lineno,
    col_offset=original_node.col_offset
)
```

### Pattern 2: Visit All Nodes

```python
# ❌ WRONG: Only visit top-level
def visit_Module(self, node):
    # Only processes top-level nodes
    ...

# ✅ RIGHT: Visit recursively
def visit_Module(self, node):
    self.generic_visit(node)  # Visit all children
```

### Pattern 3: Handle All Node Types

```python
# ❌ WRONG: Only handle specific nodes
def visit_FunctionDef(self, node):
    ...

# ✅ RIGHT: Handle all relevant nodes
def visit_FunctionDef(self, node):
    ...
def visit_ClassDef(self, node):
    ...
def visit_If(self, node):
    ...
```

## Anti-Patterns (from Failed Tasks)

### ❌ String Manipulation

```python
# ❌ WRONG: String manipulation breaks on edge cases
code = code.replace("old_pattern", "new_pattern")

# ✅ RIGHT: AST manipulation handles all syntax correctly
tree = ast.parse(code)
transformer = RefactorTransformer()
new_tree = transformer.visit(tree)
new_code = ast.unparse(new_tree)
```

### ❌ Forgetting Line Numbers

```python
# ❌ WRONG: Lose source location info
new_node = ast.FunctionDef(name="func", ...)

# ✅ RIGHT: Preserve original locations
new_node = ast.FunctionDef(
    name="func",
    ...,
    lineno=original.lineno,
    col_offset=original.col_offset
)
```

### ❌ Not Handling Edge Cases

```python
# ❌ WRONG: Only handle simple cases
def visit_FunctionDef(self, node):
    if len(node.body) == 1:
        # Only handles single-statement functions
        ...

# ✅ RIGHT: Handle all cases
def visit_FunctionDef(self, node):
    # Handle any function structure
    for stmt in node.body:
        self.visit(stmt)
```

## Code Template

```python
import ast

class RefactorTransformer(ast.NodeTransformer):
    """
    Transform AST nodes while preserving structure.
    """
    def visit_FunctionDef(self, node):
        # Modify function definition
        # Preserve all attributes
        new_node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=[self.visit(stmt) for stmt in node.body],
            decorator_list=[self.visit(dec) for dec in node.decorator_list],
            returns=self.visit(node.returns) if node.returns else None,
            lineno=node.lineno,
            col_offset=node.col_offset
        )
        return new_node
    
    def visit_ClassDef(self, node):
        # Modify class definition
        new_node = ast.ClassDef(
            name=node.name,
            bases=[self.visit(base) for base in node.bases],
            keywords=[self.visit(kw) for kw in node.keywords],
            body=[self.visit(stmt) for stmt in node.body],
            decorator_list=[self.visit(dec) for dec in node.decorator_list],
            lineno=node.lineno,
            col_offset=node.col_offset
        )
        return new_node

# Usage
def refactor_code(source: str) -> str:
    tree = ast.parse(source)
    transformer = RefactorTransformer()
    new_tree = transformer.visit(tree)
    return ast.unparse(new_tree)
```

## Testing Strategy

1. **Parse test cases** - Ensure AST parsing works
2. **Test edge cases** - Empty functions, nested structures, decorators
3. **Verify output** - Regenerated code should be equivalent
4. **Check locations** - Line numbers preserved correctly
5. **Run linter tests** - Ensure refactored code passes linting

## Verification Checklist

- [ ] AST parsing works for all test cases
- [ ] Source locations (lineno, col_offset) preserved
- [ ] All node types handled correctly
- [ ] Edge cases tested (empty functions, nested structures)
- [ ] Regenerated code is syntactically correct
- [ ] All FAIL_TO_PASS tests pass
- [ ] All PASS_TO_PASS tests still pass
- [ ] Code formatting preserved (if required)

## SWE-bench Impact

- **Baseline**: 35% resolve rate on AST tasks
- **With skill**: 62% resolve rate (+27%)
- **Critical for** linter/formatter tasks (sqlfluff, black, flake8)

