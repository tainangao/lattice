# AGENTS.md - Development Guide for Lattice

## Overview

This is a Python project using FastAPI, Pydantic, and Streamlit. The project follows functional programming principles with a focus on modularity, testability, and maintainability.

---

## Build, Lint, and Test Commands

### Python Environment

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e .
pip install fastapi pydantic streamlit pytest pytest-asyncio ruff black mypy
```

### Running the Application

```bash
# Run FastAPI server
uvicorn main:app --reload

# Run Streamlit app
streamlit run app.py
```

### Linting and Formatting

```bash
# Run ruff linter
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format with ruff
ruff format .

# Type checking with mypy
mypy .
```

### Testing

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_api.py

# Run a single test function
pytest tests/test_api.py::test_get_user

# Run tests matching a pattern
pytest -k "test_user"

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html
```

---

## Code Style Guidelines

### General Principles

- **Modular**: Single responsibility per module, small focused components (< 50 lines)
- **Functional**: Pure functions, immutability, composition over inheritance
- **Maintainable**: Self-documenting, testable, predictable

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `user_service.py`, `api_utils.py` |
| Functions | verbPhrase | `get_user`, `validate_email`, `calculate_total` |
| Variables | descriptive | `user_count`, `active_users` (not `uc`, `au`) |
| Classes | PascalCase | `UserService`, `ApiResponse` |
| Constants | UPPER_SNAKE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| Predicates | is/has/can | `is_valid`, `has_permission`, `can_access` |

### Python-Specific Guidelines

- Follow **PEP 8** style guide
- Use **type hints** for function signatures
- Prefer **list comprehensions** for simple transformations
- Use **context managers** (`with` statements)
- Use **dataclasses** or **Pydantic models** for data structures

### Imports

```python
# Standard library first
import os
import sys
from typing import Optional, List

# Third-party imports
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local imports
from .utils import helper_function
from .models import User
```

### Type Annotations

```python
# Use type hints always
def process_user(user_id: int, name: str) -> User:
    ...

def get_users(limit: Optional[int] = None) -> List[User]:
    ...

# Use Pydantic for data validation
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., pattern=r"^[a-z]+@[a-z]+\.[a-z]+$")
    age: int | None = None
```

### Error Handling

```python
# ✅ Explicit error handling
def parse_data(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

# ✅ Validate at boundaries
def create_user(user_data: dict) -> User:
    validation = validate_user_data(user_data)
    if not validation.is_valid:
        raise ValidationError(validation.errors)
    return save_user(user_data)

# ✅ FastAPI error handling
from fastapi import HTTPException

@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### Functions

```python
# ✅ Pure function - same input = same output
def calculate_total(items: List[PriceItem]) -> float:
    return sum(item.price for item in items)

# ✅ Small functions
def process_order(order: Order) -> OrderResult:
    validated = validate_order(order)
    if not validated.is_valid:
        return OrderResult(success=False, errors=validated.errors)
    
    charged = charge_customer(validated)
    return OrderResult(success=True, order=charged)
```

### Pydantic Models

```python
from pydantic import BaseModel, Field, validator
from datetime import datetime

class UserBase(BaseModel):
    email: str
    name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @validator('email')
    def email_lowercase(cls, v):
        return v.lower()

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
```

---

## Testing Guidelines

### Test Structure (AAA Pattern)

```python
def test_calculate_total_returns_sum():
    # Arrange
    items = [PriceItem(price=10), PriceItem(price=20), PriceItem(price=30)]
    
    # Act
    result = calculate_total(items)
    
    # Assert
    assert result == 60
```

### What to Test

- ✅ Happy path (normal usage)
- ✅ Edge cases (empty, null, boundaries)
- ✅ Error cases (invalid input, failures)
- ✅ Business logic
- ✅ Public APIs

### What NOT to Test

- ❌ Third-party libraries
- ❌ Framework internals
- ❌ Simple getters/setters
- ❌ Private implementation details

### Coverage Goals

- **Critical**: Business logic (100%)
- **High**: Public APIs (90%+)
- **Medium**: Utilities (80%+)

---

## Anti-Patterns to Avoid

- ❌ **Mutation**: Modifying data in place
- ❌ **Deep nesting**: Use early returns instead
- ❌ **God modules**: Split into focused modules
- ❌ **Global state**: Pass dependencies explicitly
- ❌ **Large functions**: Keep < 50 lines
- ❌ **Magic numbers**: Use named constants
- ❌ **Silent errors**: Always handle explicitly

---

## Best Practices Summary

1. Write **pure functions** whenever possible
2. Use **immutable data structures**
3. Keep functions **small and focused** (< 50 lines)
4. **Compose** small functions into larger ones
5. Use **dependency injection** for testability
6. **Validate at boundaries**
7. Write **self-documenting code**
8. Use **type hints** throughout
9. Test in **isolation**
10. Follow **PEP 8**

**Golden Rule**: If you can't easily test it, refactor it.
