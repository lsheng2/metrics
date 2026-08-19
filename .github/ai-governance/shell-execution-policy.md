# Shell Execution Policy

Status: active BKM.

## Windows Default

This repository is currently being developed from Windows VS Code. Use PowerShell syntax for terminal commands unless a repo document or tool requires another shell.

## Rules

1. Prefer direct commands such as `python -m pytest ...`, `python manage.py check`, `python scripts/check_file_size_limits.py --include-untracked`, and `python scripts/check_diff_whitespace.py --include-untracked`.
2. Do not mix PowerShell, CMD, bash, and WSL syntax in one command.
3. Use PowerShell environment syntax when needed: `$env:NAME = 'value'`.
4. Do not use WSL unless the task is explicitly Linux-only or the repo documentation requires it.
5. Do not print secrets from `.env`, PATs, cookies, or Authorization headers.
6. If a command fails, first check whether the failure is shell syntax or path syntax before changing code.
7. Use focused validation before broad test runs.

## Common Commands

```powershell
python manage.py check
python -m pytest path\to\test_file.py::TestClass::test_method -q
python scripts/check_file_size_limits.py --include-untracked
python scripts/check_diff_whitespace.py --include-untracked
```
