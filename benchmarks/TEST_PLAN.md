# ContextSift tool-history benchmark plan

## Primary question

When both agents keep **all main user/assistant messages**, how much context does ContextSift save by externalizing completed tool calls and raw tool results instead of resending them forever?

This benchmark isolates completed tool-history elimination. Main conversation history is held constant.

## Arms

### Full-history baseline

- Keeps every main user and assistant message.
- Keeps every historical assistant tool-call message.
- Keeps every historical raw tool-result message.
- Keeps completed tool exchanges from new benchmark tasks in subsequent requests.

### ContextSift

- Keeps every main user and completed assistant message (`recent_main_messages = 0`).
- Removes completed tool-call/result messages from subsequent requests.
- Keeps all compact historical tool receipts in the active ledger for this test.
- Preserves full historical tool outputs as retrievable artifacts.

## Fixed inputs

- Model: `glm-5.2:cloud` through Ollama.
- Main history: 40 messages (20 user/assistant turns), identical in both arms.
- Historical completed tool exchanges: 20, identical in both arms.
- Historical raw tool output: approximately 4 KB per call.
- System prompts and ten tool schemas: identical.
- Task order and deterministic pass conditions: identical.
- No Tavily key is required; the comparison uses local artifact, filesystem, and Python tools.

## Tasks

| ID | Purpose | Pass condition |
|---|---|---|
| main_fact | Verify that both arms retain all main messages | Contains `PROJECT-ATLAS-91` |
| tool_summary | Verify compact receipts retain a useful historical summary | Contains `SUMMARY-SEAL-440` |
| tool_deep_detail | Verify an exact detail removed from context can be recovered from an artifact | Contains `DEEP-CHECKSUM-7729` |
| filesystem_tool | Verify a current real tool sequence works | Calls `filesystem_read_file` successfully and contains `FILE-PROBE-7391` |
| code_tool | Verify a second current tool sequence works | Calls `code_execute_python` successfully and contains `2870` |

## Metrics

- Provider-reported prompt and completion tokens.
- Prompt-token reduction relative to the non-eliminating baseline.
- Deterministic task success.
- Total and per-task wall time.
- Model-call count and requested tool calls.
- Initial active message counts by role.
- Framework-estimated initial context tokens.
- Tool-result bytes kept externally by ContextSift.
- Cached prompt tokens if Ollama reports them; otherwise explicitly unavailable.

## Interpretation

- A token reduction is meaningful only if task quality is retained.
- The baseline intentionally models the behavior under investigation: retaining completed tool exchanges. It is not a claim that every existing framework behaves identically.
- The synthetic tool outputs test containment and repeat-transmission directly; they do not represent every real workload.
- One run per task is sufficient for a POC token comparison, but not for a stable latency claim.

## Run

```bash
PYTHONPATH=src python3 benchmarks/run_tool_history_benchmark.py
python3 benchmarks/render_tool_history_results.py benchmarks/results/<run-id>/results.json
```

Every run gets a new timestamped directory and never overwrites prior evidence.
