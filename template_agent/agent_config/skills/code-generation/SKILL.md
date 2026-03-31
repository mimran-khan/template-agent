---
name: code-generation
description: Guidelines for generating clean, secure, and efficient Python code in a sandboxed environment
---

# Code Generation Skill

This skill provides guidelines for generating Python code that runs safely in a restricted sandbox environment.

## Code Quality Standards

### Readability
- Use descriptive variable names that convey meaning
- Keep functions focused and single-purpose
- Add comments only for non-obvious logic
- Follow PEP 8 style guidelines

### Efficiency
- Choose appropriate data structures
- Avoid unnecessary loops or redundant operations
- Use built-in functions when available
- Consider memory usage for large datasets

### Robustness
- Validate inputs before processing
- Handle edge cases (empty lists, zero values, etc.)
- Use try-except for operations that might fail
- Provide meaningful error messages

## Available Standard Library Modules

```python
# Safe to use
import math
import datetime
import json
import re
import collections
import itertools
import functools
import statistics
import random
import decimal
import fractions
import operator
import string
```

## Available Third-Party Libraries

```python
# Data science (if installed)
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
```

## Blocked Operations

The following are NOT allowed in the sandbox:

### File System
```python
# BLOCKED
open()
with open('file.txt') as f: ...
pathlib.Path().read_text()
```

### Network
```python
# BLOCKED
import requests
import urllib
import socket
import http.client
```

### System Access
```python
# BLOCKED
import os
import sys
import subprocess
import shutil
os.system()
subprocess.run()
```

### Code Execution
```python
# BLOCKED
eval()
exec()
compile()
__import__()
```

### Dangerous Attributes
```python
# BLOCKED
obj.__class__
obj.__globals__
obj.__code__
obj.__dict__
```

## Code Patterns

### Safe Input Handling
```python
def process_numbers(numbers):
    if not numbers:
        return "No numbers provided"
    if not all(isinstance(n, (int, float)) for n in numbers):
        return "All values must be numbers"
    return sum(numbers) / len(numbers)
```

### Using Statistics
```python
import statistics

def analyze_data(values):
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }
```

### Working with Dates
```python
from datetime import datetime, timedelta

def days_between(date1_str, date2_str, fmt="%Y-%m-%d"):
    d1 = datetime.strptime(date1_str, fmt)
    d2 = datetime.strptime(date2_str, fmt)
    return abs((d2 - d1).days)
```

### List Comprehensions
```python
# Filter and transform
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
even_squares = [x**2 for x in numbers if x % 2 == 0]
```

### Dictionary Operations
```python
from collections import Counter

def word_frequency(text):
    words = text.lower().split()
    return dict(Counter(words).most_common(10))
```

## Output Guidelines

### Print Results Clearly
```python
# Good
print(f"Result: {value}")
print(f"The average is {avg:.2f}")

# Avoid
print(value)  # No context
```

### Format Numbers Appropriately
```python
# Currency
print(f"Total: ${amount:,.2f}")

# Percentages
print(f"Growth: {rate:.1%}")

# Large numbers
print(f"Population: {count:,}")
```

### Structure Complex Output
```python
results = {
    "input": data,
    "calculations": {
        "sum": total,
        "average": avg,
    },
    "summary": f"Processed {len(data)} items"
}
print(json.dumps(results, indent=2))
```

## Timeout Considerations

- Code has a 30-second execution limit
- Avoid infinite loops
- For large iterations, consider sampling or limiting

```python
# Safe iteration with limit
MAX_ITERATIONS = 100000
for i, item in enumerate(large_list):
    if i >= MAX_ITERATIONS:
        print(f"Processed first {MAX_ITERATIONS} items")
        break
    process(item)
```

## Output Size Limits

- Maximum output: 100,000 characters
- Truncate large outputs proactively

```python
MAX_OUTPUT = 1000
result = some_large_output()
if len(str(result)) > MAX_OUTPUT:
    print(str(result)[:MAX_OUTPUT] + "... [truncated]")
else:
    print(result)
```
