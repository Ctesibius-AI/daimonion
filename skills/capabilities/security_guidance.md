# Security Guidance

## When Active
When editing files that may introduce security vulnerabilities.

## Instructions
- GitHub Actions: never use untrusted input directly in `run:` commands; use `env:` with quoting instead
- Watch for injection-prone inputs: issue titles/bodies, PR descriptions, commit messages, head refs
- Avoid `child_process.exec()` — use `execFile` to prevent shell injection
- Flag `new Function()`, `eval()` as code injection risks; suggest alternatives
- Flag `dangerouslySetInnerHTML`, `document.write()`, `.innerHTML =` as XSS risks; suggest DOM methods or DOMPurify
- Python: avoid `pickle` with untrusted data (arbitrary code execution); prefer JSON
- Python: avoid `os.system` with dynamic arguments; use `subprocess` with argument lists
- Show warning once per file per session; allow operation to proceed after warning
- Only flag patterns in new/modified code, not pre-existing issues
