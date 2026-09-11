# Architecture — What "good work" means in <YOUR_PROJECT>

> **This file is a template: fill it in before writing the first feature.**
> It is the document the reviewer agent evaluates the code against. If a
> requirement is not here, it is not a requirement — and the reviewer will not
> enforce it. Be concrete: "clear layers" is useless, "only these three layers,
> with these names" works.

## Principles

1. **Clear layers.** The project has these layers and only these:
   - `<module_1>.py` — <responsibility>
   - `<module_2>.py` — <responsibility>
   - `<module_3>.py` — <responsibility>

   Do not introduce extra layers (services, repositories, ORMs) until there is
   a concrete reason documented as a feature in `feature_list.json`.

2. **No external dependencies.** Python stdlib only. If a feature needs a
   dependency, it is not installed on anyone's own initiative: the feature goes
   to `blocked` and it gets discussed.

3. **Explicit errors.** Functions that can fail raise named domain exceptions;
   they do not return `None` or a sentinel value.

4. **Immutability by default.** Domain data structures are
   `@dataclass(frozen=True)`. Modifying = creating a new instance.

5. **Atomic writes.** Every write of a state file goes to a temporary file
   first and then `os.replace()`. Never leave a half-written file behind.

<!-- Principles 2-5 are cross-cutting and usually hold as they are. Principle 1
     and the data flow are specific to your project: rewrite them. -->

## Data flow

```
<input>  ─→  <module_3>.py (interface)
               │
               ├─ builds <entity> with <module_2>.<constructor>(...)
               │
               └─→  <module_1>.load() / <module_1>.save()
                        │
                        └─→  <state file>
```

## What NOT to do

- Do not use `print()` for errors. Use `sys.stderr` and a non-zero exit code.
- Do not mix IO with domain logic.
- Do not read/write the state file inside a loop: load at the start, modify in
  memory, save at the end.
- Do not add a configuration system. Paths are passed explicitly or use a
  default constant from the module.
- <add your domain's concrete antipatterns here>
