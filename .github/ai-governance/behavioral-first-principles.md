# Behavioral First Principles

Status: active BKM.

## Principles

1. Think before coding: state assumptions and resolve critical ambiguity before editing.
2. Architecture before patching: prefer the owner boundary over local bypasses.
3. Reuse before reinvention: search existing module APIs, facades, utilities, and `sd-metrics-lib` before adding custom machinery.
4. Simplicity first: implement the smallest complete behavior the request needs.
5. Surgical changes: touch only the files required by the task and preserve surrounding style.
6. Goal-driven execution: define success criteria and run a check that can reject the change.
7. Single authority before convenience: name the module, API, facade, or config object that owns the truth being changed.
8. Validate transitions: for regressions, test the boundary where data moves between tracker adapter, domain service, facade, view, template, and htmx partial.

## Practical Interpretation

For small fixes, keep this lightweight. For multi-owner work, use the DAG skill and custom agents.
