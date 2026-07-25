# Contributing to ContextSift

ContextSift is a proof of concept exploring completed-tool-history externalization. Contributions should preserve that focus and make claims that can be reproduced.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[web]"
```

Run the offline suite before submitting a change:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Check local readiness without a model call:

```bash
PYTHONPATH=src python3 -m contextsift_agent doctor
```

## Pull request expectations

- Explain the user-visible behavior and why it belongs in the POC.
- Add or update tests for behavior changes.
- Keep generated runtime data, secrets, and machine-specific paths out of the commit.
- Separate measured results from projections or hypotheses.
- Do not describe planned features as implemented.
- Document new tools, permissions, environment variables, and failure modes.
- Preserve append-only evidence and bounded model previews where practical.

## Benchmark contributions

The primary benchmark holds all main messages constant and varies only completed tool-history handling. Changes to that comparison should explain every changed variable.

Run it with:

```bash
PYTHONPATH=src python3 benchmarks/run_tool_history_benchmark.py
python3 benchmarks/render_tool_history_results.py benchmarks/results/<run-id>/results.json
```

Generated `benchmarks/results/` directories are intentionally ignored. To propose a new reference result:

1. State the model, provider, date, and benchmark commit.
2. Include the fixed test plan and raw provider token metrics.
3. Remove secrets, absolute paths, databases, execution directories, and unrelated tool output.
4. Report task failures and infrastructure failures, not only successful runs.
5. Label single-run latency as observational.

## Reporting problems

Use a public issue for ordinary bugs and reproducible compatibility problems. Follow [SECURITY.md](SECURITY.md) for vulnerabilities or findings that could expose data or execute unintended commands.
