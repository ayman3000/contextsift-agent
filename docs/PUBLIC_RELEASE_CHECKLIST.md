# Public release checklist

Complete these repository-owner steps before making the repository public.

## Required

- [ ] Choose the final GitHub owner/repository name.
- [ ] Confirm the copyright holder wording in `LICENSE`.
- [ ] Enable GitHub private vulnerability reporting.
- [ ] Rotate any API key previously pasted into a prompt, log, screenshot, or terminal transcript.
- [ ] Confirm `git status` contains no `data/`, `benchmarks/results/`, `.env`, database, or execution files.
- [ ] Run the publishable path/secret scan described below.
- [ ] Run the offline test suite on Python 3.11 and 3.12.
- [ ] Verify editable installation in a clean virtual environment.
- [ ] Review the reference benchmark answers and report one final time.
- [ ] Confirm the README status table matches the current implementation.

## Suggested scan

Inspect tracked files before the first push:

```bash
git ls-files -z | xargs -0 rg -n "/Users/|/home/|tvly-|sk-[A-Za-z0-9]|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY"
```

Review every match; do not assume all secrets follow a known prefix.

## Recommended repository settings

- Require CI before merging.
- Enable secret scanning and push protection when available.
- Enable Dependabot alerts.
- Disable force pushes to the default branch.
- Add repository topics such as `llm`, `agents`, `ollama`, and `context-management`.
- Add a short description that labels the project experimental.

## Release wording

Use workload-qualified language:

> In the published synthetic tool-history benchmark, ContextSift used 88.7% fewer provider-reported prompt tokens while both arms retained all main messages and passed 5/5 tasks.

Do not present 88.7% as a universal reduction, cost saving, or stable latency improvement.
