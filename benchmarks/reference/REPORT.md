# ContextSift: completed-tool-history benchmark

Run: `tool-history-20260725T090722Z`
Model: `glm-5.2:cloud` through Ollama OpenAI-compatible API
Comparison: all 40 main messages in both arms; 20 completed tool exchanges retained raw versus externalized

## Result

ContextSift used **25,015 prompt tokens**, versus **222,274** for the non-eliminating full-history baseline: an **88.7% reduction**. Both arms passed **5/5 tasks**.

The first live request was **27,529 tokens** with raw tool history and **2,960 tokens** with ContextSift, a **89.2% reduction** before repeated calls compounded the difference.

| Arm | Initial active messages | Initial estimated tokens | Actual prompt tokens across run | Quality | Wall time |
|---|---:|---:|---:|---:|---:|
| Full-history baseline | 82 | 23,763 | 222,274 | 5/5 | 22.05s |
| ContextSift | 42 | 3,466 | 25,015 | 5/5 | 12.66s |

![Prompt tokens](charts/prompt_tokens.png)

![Initial active context](charts/active_context.png)

![Quality and latency](charts/outcomes.png)

## What changed—and what did not

- Both arms kept all 40 main user/assistant messages.
- Both received the same identity, memory, state prompts, model, ten tool schemas, task order, and current tools.
- The baseline began with 20 assistant tool-call messages and 20 raw tool-result messages in addition to main history.
- ContextSift replaced those completed exchanges with 20 compact ledger receipts and stored **70,763 bytes** of full output in artifacts.
- The baseline retained new filesystem, artifact, and Python tool exchanges in later requests. ContextSift removed each completed exchange after the model consumed it.

## Exact historical evidence

The difficult task asked for `DEEP-CHECKSUM-7729`, which existed deep inside historical call `call-hist-005` and was intentionally absent from the compact receipt.

- The baseline had the raw result in active context and ultimately answered correctly. It also attempted `artifact_search` without a valid artifact and received an error.
- ContextSift saw the receipt and artifact ID, called `artifact_search` successfully, loaded one matching line, and answered correctly.

This demonstrates the intended distinction: remove raw completed output from routine context without making exact evidence unrecoverable.

## Latency and caching

Wall time was **22.05s** for the baseline and **12.66s** for ContextSift, a **42.6% reduction in this run**. This is encouraging but not a stable latency claim: it is one run against a cloud model, and repeated trials are required.

Ollama did not report cached prompt tokens, so this benchmark cannot quantify how provider-side prompt caching changes the economic result.

## Honest boundaries

- The historical outputs are synthetic, deliberately tool-heavy, and approximately 70 KB in total. Token savings will be smaller in conversation-heavy sessions with tiny tool results and larger in sessions with verbose terminal, filesystem, web, or code outputs.
- The baseline models the behavior under investigation—retaining completed tool exchanges—not every production framework.
- The benchmark demonstrates equal deterministic quality over five tasks, not universal quality equivalence.
- A future study should replay real agent traces, repeat each task, and report latency distributions and cache behavior.

## Reproduce

```bash
PYTHONPATH=src python3 benchmarks/run_tool_history_benchmark.py
python3 benchmarks/render_tool_history_results.py benchmarks/results/<run-id>/results.json
```

The fixed methodology is in `benchmarks/TEST_PLAN.md`; raw request metrics and answers are in `results.json`.
