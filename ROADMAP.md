# ContextSift roadmap

ContextSift is an experimental proof of concept. This roadmap distinguishes validated behavior from design targets so that repository visitors can evaluate the current code without reading planned features as completed work.

## Validated in the current POC

- All-main-message mode and optional last-N main-message selection.
- Completed tool calls/results excluded from subsequent main conversation context.
- Compact tool receipt ledger.
- Append-only conversation and tool receipt logs.
- Artifact storage, bounded reads, and exact text search.
- Filesystem root containment.
- Non-shell terminal execution with bounded output.
- Child-process Python execution with a sanitized environment.
- Tavily web search.
- SQLite FTS5 indexing and lexical retrieval.
- OpenAI-compatible provider adapter, tested with Ollama and `glm-5.2:cloud`.
- Per-request context manifests and estimated token accounting.
- Reproducible completed-tool-history benchmark.

## Partially implemented

### Context budget

The builder estimates request size and marks a manifest `over_budget`. It does not yet apply deterministic trimming, reject the request, or reserve response tokens.

### Memory and task state

`agent.md`, `user.md`, `memory.md`, and `state.md` are loaded into context. The agent does not yet promote memories, resolve conflicts, or checkpoint task state automatically.

### Duplicate-call awareness

Compact receipts help the model see recent completed work. There is no deterministic duplicate-call detector, cache, or challenge step.

### Execution safety

Filesystem roots, subprocess timeouts, a terminal denylist, and a sanitized Python environment reduce accidental exposure. They do not form an OS-enforced sandbox.

## Next milestones

1. Enforce a deterministic context budget with explicit source-priority rules.
2. Add automatic, auditable state checkpoints and memory promotion/correction.
3. Add deterministic duplicate-call detection and safe result reuse.
4. Add progressive tool-schema disclosure.
5. Add hybrid lexical and embedding retrieval for older receipts and conversation history.
6. Add container-backed execution profiles with network, memory, and filesystem controls.
7. Replay sanitized real agent traces and repeat runs for latency distributions.
8. Measure prompt-cache behavior with providers that expose cached-token metrics.
9. Add more provider adapters and model compatibility tests.

## Non-goals for the POC

- Claiming a universal token-reduction percentage.
- Treating the execution tools as a secure multi-tenant sandbox.
- Automatically publishing or sending data to third parties.
- Hiding benchmark inputs, failures, or model responses needed for reproduction.
