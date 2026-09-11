# Code conventions

> Extreme homogeneity. An AI predicts better when the repository looks like
> itself everywhere.

## Python style

- **Version:** Python 3.9+ (`list[str]` syntax allowed).
- **Formatting:** PEP 8. Lines of at most 100 characters.
- **Imports:** stdlib first, then local. One line per module.
- **Strings:** double quotes `"..."` always. Single quotes only to escape
  double quotes inside.
- **f-strings** for interpolation. No `.format()` and no `%`.

## Names

| Kind                    | Convention        | Example               |
|-------------------------|-------------------|-----------------------|
| Modules                 | `snake_case`      | `storage.py`          |
| Classes                 | `PascalCase`      | `Record`              |
| Functions / variables   | `snake_case`      | `load_records`        |
| Constants               | `UPPER_SNAKE`     | `DEFAULT_STATE_PATH`  |
| Private                 | `_` prefix        | `_atomic_write`       |

## File structure

Every file in `src/` starts with:

```python
"""One line describing the module's purpose."""
from __future__ import annotations

# stdlib imports
import json
import os

# local imports
from src.<module> import <Entity>
```

## Tests

- One test file per module in `src/`: `tests/test_<module>.py`.
- One `Test<Thing>(unittest.TestCase)` class per logical unit.
- Every test uses a `tempfile.TemporaryDirectory()` and cleans up after itself.
- Descriptive test names, written as assertions:
  `test_load_returns_empty_when_file_missing`.

## Error handling

Every project defines its exception hierarchy in the domain module, with its
own base class and subclasses per concrete case:

```python
class <Domain>Error(Exception):
    """Base class for domain errors."""

class <Thing>NotFound(<Domain>Error):
    """Raised when something that does not exist is looked up."""
```

The interface layer catches domain exceptions, prints the message to `stderr`
and exits with code 1. It never propagates stack traces to the user.

## Comments

By default they are **not** written. They are only allowed when they explain a
non-obvious *why* (a documented workaround, a subtle invariant). Names should
do the rest.
