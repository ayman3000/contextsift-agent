# ContextSift architecture

## Core invariant

The model receives a complete tool result while the corresponding turn is active. After the model consumes that result and produces a completed response, later turns receive a compact receipt instead of the raw exchange.

Main user messages and completed assistant responses have a separate retention policy. The default `recent_main_messages = 0` keeps all of them.

## Request lifecycle

1. Append the current user message to `conversation.jsonl`.
2. Build stable context from `agent.md` and `user.md`.
3. Build volatile context from `memory.md`, `state.md`, retrieved excerpts, and the compact tool ledger.
4. Append configured main conversation history.
5. Send the request with all registered tool schemas.
6. If the model calls a tool, keep the assistant tool call and bounded result in the active in-memory sequence.
7. Before a later tool step, compact already-consumed result previews to receipts within the active sequence.
8. When the model returns a completed assistant response, persist that response as a main message and discard the in-memory tool protocol sequence.
9. Persist tool receipts and full artifacts independently so later turns can recover evidence.

## Persistent stores

| Store | Purpose | Sent automatically to the model? |
|---|---|---|
| `conversation.jsonl` | Main user and completed assistant messages | According to `recent_main_messages` |
| `tool_calls.jsonl` | Compact completed tool receipts | Recent/configured ledger lines only |
| `artifacts.jsonl` | Artifact metadata | No |
| `artifacts/` | Full large tool output | No; accessed with artifact tools |
| `search.sqlite` | Lexical index over messages and receipt previews | Only selected excerpts |
| `context_manifests.jsonl` | Per-request estimated context composition | No |
| `executions/` | Python execution working directories | No |

## Stable and volatile prompt ordering

The builder orders identity before changing state:

```text
agent.md + user.md
memory.md + state.md + retrieved excerpts + tool ledger
main conversation messages
unfinished current tool sequence
```

This ordering is intended to keep stable material at the front for providers that support prefix caching. Cache effectiveness has not yet been measured in the reference Ollama run.

## Current limitations

- The token limit is observed but not enforced.
- Search is lexical FTS5, not semantic retrieval.
- Every tool schema is sent on every request.
- Memory and state files are not updated automatically.
- Duplicate tool calls are not blocked deterministically.
- Execution tools are not isolated by an OS sandbox.

See [ROADMAP.md](../ROADMAP.md) for planned work and [SECURITY.md](../SECURITY.md) for operational risks.
