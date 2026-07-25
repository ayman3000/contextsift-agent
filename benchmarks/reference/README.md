# Reference benchmark bundle

This directory contains the sanitized, publishable output from the completed-tool-history benchmark run `tool-history-20260725T090722Z`.

Included:

- `REPORT.md`: interpretation, methodology summary, limitations, and reproduction command.
- `results.json`: provider-reported token metrics, deterministic task outcomes, answers, and tool statuses.
- `charts/`: PNG and SVG versions of the published figures.

Excluded from the reference bundle:

- SQLite databases.
- Python execution directories.
- Absolute local paths.
- Full generated artifact files.
- Runtime prompt copies.
- Secrets and environment values.

The benchmark generator writes complete local evidence under ignored `benchmarks/results/` directories. Run it yourself to inspect the full artifacts:

```bash
PYTHONPATH=src python3 benchmarks/run_tool_history_benchmark.py
python3 benchmarks/render_tool_history_results.py benchmarks/results/<run-id>/results.json
```

The reference run used one live pass with `glm-5.2:cloud` through Ollama. Treat latency as observational and the 88.7% prompt-token reduction as specific to the published synthetic, tool-heavy workload.
