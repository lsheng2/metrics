# Code Comment Policy

Status: active BKM.

This repo prefers readable names and simple structure over comments. Root `CLAUDE.md` says not to add production code comments by default; this BKM defines the rare exceptions.

## Add A Comment Only When It Explains

1. A non-obvious domain invariant.
2. A tracker API or `sd-metrics-lib` constraint.
3. A cross-module boundary rule that is easy to break.
4. A fallback or compatibility behavior with a known removal trigger.
5. A security or secret-handling constraint.

## Do Not Add Comments For

1. Simple assignments, getters, loops, or mappings.
2. Restating a function or variable name.
3. Explaining obvious Django, dataclass, or template mechanics.
4. Narrating every step of a test.

## Style

Use one or two factual lines before the relevant block. Do not add license or copyright headers unless explicitly requested.
