# ContextSift Agent — Proof-of-Concept Specification

**Status:** Implemented and benchmarked POC; broader trace evaluation remains
**Version:** 0.2
**Date:** 2026-07-25

> This document describes the target POC architecture, including planned capabilities. For the exact implemented/tested/partial status, use [README.md](README.md) and [ROADMAP.md](ROADMAP.md) as the current source of truth.

## Executive summary: Why, What, and How Much?

ContextSift Agent exists to answer three questions.

### Why do agent frameworks keep carrying annoying history?

Most agent loops resend the conversation transcript, completed tool calls, and tool results to the model on every step. Keeping this history preserves causality and makes old information immediately available, but it also causes several problems:

- The same information is repeatedly transmitted after it has already been understood.
- Large terminal, filesystem, web, and code-execution results remain in context after their useful moment has passed.
- Context length grows with session age instead of current task complexity.
- Old and irrelevant text competes with the current request for model attention.
- Token consumption and latency increase throughout a long-running session.
- Eventually, the framework must truncate or summarize history under pressure, risking the loss of important constraints.

Complete history is useful as a record, but it does not need to remain inside the model's active working context.

### What is the ContextSift Agent proposal?

ContextSift Agent separates **active context** from **external memory**:

- Keep agent identity, user profile, durable memory, and current task state in small purpose-specific files.
- Keep a configurable number of recent main messages: user requests and completed assistant responses. `0` means all messages and is the default.
- Keep the current unfinished tool sequence only while it is active.
- Remove completed tool exchanges from subsequent model requests.
- Store the complete conversation and compact tool receipts in append-only logs.
- Store large raw outputs as artifacts.
- Retrieve old conversation excerpts or artifact slices only when the current request needs them.
- Build every model request under an explicit token budget and record exactly what was included.

The result is a bounded working context backed by lossless, searchable history.

### How much context did it reduce?

Reduction is calculated as:

```text
context reduction % = (baseline input tokens - lean input tokens)
                      / baseline input tokens × 100
```

The reference screenshot contains approximately 199.9k tokens in its counted active categories:

```text
Messages       171.2k
System tools    14.6k
MCP tools        7.2k
System prompt    3.4k
Skills           2.3k
Memory files     1.2k
--------------- ------
Counted total  199.9k
```

With a hypothetical 32k-token input cap, the equivalent maximum payload would be:

```text
(199.9k - 32k) / 199.9k × 100 ≈ 84.0% reduction
```

That 84% value is useful for capacity planning but is not an experimental result: it follows directly from choosing a 32k cap. Any truncation strategy with the same cap can produce the same arithmetic.

The primary live POC benchmark used `glm-5.2:cloud` through Ollama. Both arms kept all 40 main messages and ran the same five tasks. The baseline also retained 20 completed assistant tool-call messages and 20 raw tool-result messages; ContextSift replaced them with compact receipts and artifacts. Provider-reported totals were:

```text
Full tool history   222,274 prompt tokens   5/5 tasks
ContextSift          25,015 prompt tokens   5/5 tasks   88.7% reduction
```

ContextSift also recovered an exact value removed from active context through its artifact reference. The measured 88.7% reduction describes this deliberately tool-heavy synthetic workload, not a universal rate. The important result is that it isolates the framework's main claim: completed tool exchanges can leave active history without dropping main user/assistant messages or losing tested evidence.

## 1. Purpose

ContextSift Agent is a local-first agent framework designed to keep the model's active context small and predictable during long-running conversations.

The framework stores complete conversation and tool history outside the model context, maintains a small set of durable memory and task-state files, and retrieves older information only when it is relevant to the current request.

The proof of concept must compare against a full-history baseline that retains completed tool exchanges while keeping the same main messages in both arms. Token reduction and task quality must be reported together.

## 2. Core principles

1. **Bounded active context:** Conversation length must not cause unbounded context growth.
2. **Lossless external history:** The full conversation, tool receipts, and raw artifacts remain available outside the active context.
3. **Selective retrieval:** Only relevant historical excerpts enter the context.
4. **Main-turn retention:** The recent window counts completed user requests and completed assistant responses, not intermediate tool messages.
5. **Tool-output containment:** Large tool output is stored as an artifact. The model receives a summary and bounded preview.
6. **Explicit durable state:** Identity, user information, durable memory, and current task state have separate responsibilities.
7. **Traceability:** Every retrieved excerpt, tool result, and memory update has a source identifier.
8. **Safe execution:** Filesystem, terminal, web, and code tools operate under explicit limits and policies.
9. **Observable token usage:** Every model request records which context sources were included and their estimated token cost.

## 3. Scope

The POC includes:

- A single local agent and a single user.
- A bounded context builder.
- Persistent identity, user, memory, and task-state files.
- Complete conversation and tool-call archives.
- Keyword and full-text retrieval.
- Filesystem tools.
- Terminal tools.
- Tavily-backed web search.
- Isolated Python code execution.
- Artifact storage for large outputs.
- Token and retrieval observability.
- A baseline-versus-lean evaluation.

The POC does not require:

- Multi-agent orchestration.
- Cloud deployment.
- Distributed storage.
- A production-grade permission system.
- Embedding-based retrieval.
- Support for multiple code-execution languages.
- Perfect operating-system sandboxing.
- Automatic long-term memory extraction without reviewable rules.

## 4. Proposed repository layout

```text
contextsift-agent/
├── CONTEXTSIFT_AGENT_SPEC.md
├── README.md
├── pyproject.toml
├── config.toml
├── prompts/
│   ├── agent.md
│   ├── user.md
│   ├── memory.md
│   └── state.md
├── src/contextsift_agent/
│   ├── agent.py
│   ├── models.py
│   ├── context_builder.py
│   ├── token_budget.py
│   ├── memory_manager.py
│   ├── retrieval.py
│   ├── history_store.py
│   ├── artifact_store.py
│   ├── policy.py
│   ├── tool_registry.py
│   ├── tool_executor.py
│   └── tools/
│       ├── filesystem.py
│       ├── terminal.py
│       ├── web_search.py
│       └── code_execution.py
├── data/
│   ├── conversation.jsonl
│   ├── tool_calls.jsonl
│   ├── search.sqlite
│   ├── artifacts/
│   └── executions/
└── tests/
    ├── test_context_builder.py
    ├── test_retrieval.py
    ├── test_memory_manager.py
    ├── test_tool_limits.py
    └── test_long_session.py
```

Generated runtime data under `data/` should be excluded from version control except for small fixtures.

## 5. Persistent knowledge model

### 5.1 `agent.md`

Defines who the agent is:

- Identity and role.
- General behavior.
- Operating principles.
- Communication style.
- Stable capability boundaries.

It is always loaded and changes rarely.

### 5.2 `user.md`

Defines who the user is:

- Name and role, when known.
- Stable preferences.
- Expertise and typical workflows.
- Preferred communication style.

It is always loaded and changes only when the understanding of the user materially changes.

### 5.3 `memory.md`

Contains durable, user-relevant facts learned over time:

- Persistent preferences.
- Long-lived projects and goals.
- Reusable facts explicitly provided by the user.
- Decisions likely to matter across future tasks.

It must not become a transcript or contain temporary task progress. Each memory should have an identifier, creation date, optional source-turn identifier, and status.

Recommended format:

```md
## M-0001

- Fact: The user prefers local-first agent architectures.
- Created: 2026-07-25
- Source: turn-0007
- Status: active
```

When `memory.md` exceeds its configured budget, its headings are indexed and only relevant memories are retrieved.

### 5.4 `state.md`

Contains the current task state:

- Active objective.
- Current constraints.
- Decisions and rationale.
- Completed work.
- Open work.
- Important artifact and tool-call references.
- Known blockers.

It is always loaded. It is updated at checkpoints and must remain compact. Completed task details should be moved to history rather than accumulated indefinitely.

### 5.5 Authority and precedence

When information conflicts, the framework uses this precedence:

1. System and safety instructions.
2. Explicit current user request.
3. Applicable agent instructions from `agent.md`.
4. Current task constraints from `state.md`.
5. Stable user profile from `user.md`.
6. Durable facts from `memory.md`.
7. Retrieved historical conversation or tool records.

New explicit user information supersedes conflicting older memory. Conflicts must be surfaced and corrected rather than silently merged.

## 6. History storage

### 6.1 Canonical conversation log

`conversation.jsonl` is the canonical append-only conversation history. Markdown may be generated from it for human inspection but is not the source of truth.

Each record contains:

```json
{
  "id": "msg-0042",
  "turn_id": "turn-0021",
  "timestamp": "2026-07-25T06:30:00+03:00",
  "role": "user",
  "kind": "main",
  "content": "What did we decide about retrieval?",
  "token_count": 11,
  "tags": ["retrieval", "context"]
}
```

`kind` is one of:

- `main`: user request or completed assistant response.
- `commentary`: optional intermediate assistant update.
- `system_event`: framework-generated event.

Tool calls and tool results are stored separately and do not count toward the recent main-message window.

### 6.2 Tool-call log

`tool_calls.jsonl` stores compact, append-only tool receipts. Raw output is stored in artifacts.

```json
{
  "call_id": "call-0104",
  "turn_id": "turn-0021",
  "timestamp": "2026-07-25T06:31:00+03:00",
  "tool": "terminal.run",
  "arguments": {"command": "pytest", "cwd": "/workspace"},
  "status": "success",
  "summary": "97 tests passed and 2 failed",
  "preview": "FAILED tests/test_memory.py ...",
  "artifact_ids": ["artifact-0192"],
  "truncated": true,
  "duration_ms": 2410,
  "exit_code": 1
}
```

Secrets and sensitive environment values must be redacted before arguments or output are persisted.

### 6.3 Artifacts

Large output is stored under `data/artifacts/`. Each artifact has:

- Stable identifier.
- Originating turn and tool call.
- Relative path.
- MIME type.
- Byte length.
- Content hash.
- Creation timestamp.
- Optional short description.

The model receives artifact metadata and a bounded preview, never an unlimited artifact by default.

## 7. Active context policy

### 7.1 Always-loaded content

Each model request includes:

- System and safety prompt.
- `agent.md`.
- `user.md`.
- Compact `memory.md`, or retrieved memory entries when it is large.
- `state.md`.
- Current user request.
- Recent main-message window.
- Tool schemas currently available to the agent.
- Active tool sequence for the unfinished current turn.

The framework may pin one or more foundational user messages when their exact wording remains essential. Otherwise their durable requirements belong in `state.md` or `memory.md`.

### 7.2 Recent main-message window

The main-message window is configurable. Its default value is `0`, meaning all `main` messages across user and assistant roles are included. Any positive value includes only that many most-recent main messages.

Unlimited mode can exceed the configured token budget as history grows. It is useful for short sessions and as the full-history evaluation baseline; bounded ContextSift behavior requires a positive value.

Intermediate assistant tool requests, tool results, and commentary do not consume these ten positions.

Once the assistant completes a response:

1. The main response is appended to `conversation.jsonl`.
2. Completed tool exchanges are removed from future active contexts.
3. Tool receipts and artifacts remain externally available.
4. Durable decisions or progress are written to `state.md`.
5. Durable user-relevant facts may be promoted to `memory.md`.

### 7.3 Context budget

An initial configurable budget:

```yaml
context:
  max_input_tokens: 32000
  response_reserve_tokens: 8000
  recent_main_messages: 0
  budgets:
    agent: 1000
    user: 1000
    memory: 2000
    state: 3000
    recent_messages: 8000
    retrieved_history: 5000
    active_tools: 5000
```

The context builder must enforce the total budget. If content exceeds its section budget, it is trimmed by explicit priority rules rather than arbitrary character truncation.

### 7.4 Context manifest

Every model request records a manifest:

```json
{
  "request_id": "request-0088",
  "estimated_input_tokens": 18400,
  "sources": [
    {"source": "agent.md", "tokens": 430, "reason": "agent identity"},
    {"source": "state.md", "tokens": 920, "reason": "active task"},
    {"source": "turns:0017-0021", "tokens": 6100, "reason": "recent main messages"},
    {"source": "msg-0009", "tokens": 380, "reason": "retrieval match"}
  ]
}
```

This manifest is required for evaluation and debugging.

## 8. Retrieval

### 8.1 Retrieval order

When older information may be relevant, the agent searches in this order:

1. `state.md`.
2. `memory.md`.
3. Recent main messages.
4. Archived conversation records.
5. Tool-call summaries.
6. Raw artifacts.

### 8.2 POC retrieval engine

The POC uses SQLite FTS5 for full-text search over:

- Conversation content.
- Memory entries.
- Task-state sections.
- Tool names, arguments, summaries, and previews.
- Text artifacts when their size permits indexing.

The model or retrieval layer generates a small group of keyword queries from the current request. Results include source IDs, timestamps, snippets, and relevance scores.

Only the highest-value excerpts are loaded, subject to the retrieved-history token budget. The agent may request surrounding records or an artifact slice if the excerpt is insufficient.

### 8.3 Artifact retrieval operations

The framework provides:

- `artifact.read(artifact_id, offset, limit)`.
- `artifact.search(artifact_id, query, max_matches)`.
- `artifact.metadata(artifact_id)`.

Reads are bounded and return whether more content is available.

### 8.4 Semantic retrieval

Embedding-based semantic retrieval is an optional future enhancement. It should be added only after tests demonstrate that full-text search regularly misses relevant paraphrased information.

## 9. Agent loop

For each user request:

1. Append the user main message.
2. Load persistent identity and current state.
3. Determine whether historical retrieval is needed.
4. Retrieve only relevant excerpts.
5. Build a budgeted context and record its manifest.
6. Call the model.
7. If the model requests tools, validate each request against policy.
8. Execute the tool and persist its full receipt and artifacts.
9. Send the bounded tool result back to the model.
10. Repeat until the model produces a completed assistant response or reaches a loop limit.
11. Append the completed assistant response as a main message.
12. Update `state.md` and, when justified, `memory.md`.
13. Drop completed tool exchanges from the next active context.

The framework must reject or pause on invalid tool arguments, disallowed operations, exceeded limits, and requests requiring approval.

## 10. Common tool contract

All tools use JSON-schema-compatible input definitions and return a shared envelope:

```json
{
  "call_id": "call-0105",
  "tool": "code.execute_python",
  "status": "success",
  "summary": "Execution completed successfully",
  "preview": "4950\n",
  "artifact_ids": [],
  "truncated": false,
  "duration_ms": 83,
  "error": null,
  "metadata": {"exit_code": 0}
}
```

Required behaviors:

- Validate arguments before execution.
- Assign stable call and artifact identifiers.
- Enforce timeout and output limits.
- Persist raw output before returning.
- Return a concise summary and bounded preview.
- Redact known secrets.
- Record failure and cancellation explicitly.
- Never claim success solely because output text appears successful.

Default result limits:

```yaml
tools:
  max_preview_bytes: 12000
  default_timeout_seconds: 60
  max_calls_per_turn: 20
  duplicate_call_window: 10
```

The framework detects recently repeated calls with equivalent normalized arguments and unchanged dependencies. It may return a cached receipt or ask the model to justify repetition.

## 11. Filesystem tools

Initial operations:

- `filesystem.list_directory(path)`.
- `filesystem.stat(path)`.
- `filesystem.find_files(path, pattern, limit)`.
- `filesystem.search_text(path, query, limit)`.
- `filesystem.read_file(path, start_line, line_count)`.
- `filesystem.apply_patch(patch)`.
- `filesystem.create_file(path, content)`.

Requirements:

- All paths are resolved and checked against configured workspace roots.
- Path traversal and symlink escape are rejected.
- Binary files are detected before text reading.
- Large files are read in numbered slices.
- Search results are capped and include file paths and line numbers.
- Edits use patches where practical.
- Existing unrelated modifications are preserved.
- Destructive operations are excluded from the initial POC.

## 12. Terminal tool

Operation:

```json
{
  "tool": "terminal.run",
  "arguments": {
    "command": "pytest",
    "cwd": "/workspace",
    "timeout_seconds": 60,
    "max_preview_bytes": 12000
  }
}
```

Requirements:

- Working directory must remain inside an allowed root.
- Commands run in a child process, never the agent process.
- Capture stdout, stderr, exit code, duration, and termination reason.
- Store complete output as artifacts when it exceeds the preview limit.
- Terminate the process tree on timeout or cancellation.
- Use a sanitized environment and never expose secrets in receipts.
- Classify commands as read-only, workspace-writing, external/networked, or destructive.
- Apply configured approval policy before execution.

The POC may permit read-only and workspace-writing commands while rejecting destructive commands by default.

## 13. Web search tool

The web integration uses Tavily through two logical operations:

- `web.search(query, max_results)`.
- `web.fetch(url)` when supported or through an equivalent content-retrieval path.

Search returns structured results:

```json
{
  "title": "Example title",
  "url": "https://example.com/page",
  "snippet": "Relevant excerpt...",
  "published_at": "2026-07-20",
  "score": 0.91
}
```

Requirements:

- API credentials come from the runtime environment and are never stored in history.
- Result count and content length are capped.
- Search result URLs and titles are preserved for citation.
- Full fetched content is stored as an artifact.
- Only selected excerpts enter model context.
- The final response can map claims to source URLs.
- Network errors, unavailable pages, and incomplete publication dates are represented explicitly.

## 14. Code-execution tool

The POC supports Python through:

- `code.execute_python(code, input_artifact_ids, timeout_seconds)`.
- `code.read_output(call_id, offset, limit)`.
- `code.list_artifacts(call_id)`.

Example input:

```json
{
  "code": "print(sum(range(100)))",
  "input_artifact_ids": [],
  "timeout_seconds": 10
}
```

Requirements:

- Model-generated code never runs inside the agent process.
- Each call uses an isolated temporary working directory.
- The child process receives a sanitized environment.
- Network access is disabled by default where the execution environment permits.
- Filesystem visibility is restricted to declared inputs and the execution directory.
- Enforce time, output, generated-file-count, and generated-file-size limits.
- Capture stdout, stderr, exit code, and produced files.
- Store produced files as artifacts with MIME type and content hash.
- Terminate the complete process tree on timeout.

The local subprocess isolation used by the POC must be documented as weaker than a disposable container or virtual machine. Production use should adopt stronger isolation.

Execution caching may use a hash of:

```text
language + code + input hashes + interpreter version + dependency versions
```

## 15. Tool caching and duplicate prevention

The framework records enough dependency information to determine whether reuse is safe:

- Normalized tool arguments.
- Relevant file hashes or modification times.
- Search query and freshness policy.
- Interpreter and dependency versions for code execution.

Caching rules:

- Pure computations may be reused when all inputs are unchanged.
- Filesystem reads may be reused while the target metadata is unchanged.
- Terminal commands are not assumed deterministic unless explicitly classified.
- Web results require a configurable freshness window.
- Writes and externally mutating actions are never automatically replayed from cache as if executed.

## 16. Memory update policy

A fact may be promoted to `memory.md` when it is:

- About the user or a durable cross-task preference.
- Likely to matter in future sessions.
- Supported by an explicit user statement or strong evidence.
- Not a secret that should be excluded from persistent storage.

The following should not be promoted:

- Temporary task details.
- Tool output that can be retrieved by ID.
- Speculation about the user.
- Short-lived status information.
- Redundant paraphrases of existing memories.

Memory updates must be visible in logs. The framework should support correction, supersession, and deletion by memory ID.

## 17. State checkpoint policy

`state.md` is updated when:

- The objective changes.
- A material decision is made.
- A constraint is added or removed.
- A meaningful implementation phase completes.
- A blocker is discovered or resolved.
- The assistant finishes a response that changes task state.

The checkpoint records facts and references, not a prose retelling of the entire conversation.

## 18. Safety and permissions

The POC must implement:

- Explicit workspace roots.
- Path normalization and validation.
- Secret redaction.
- Tool argument validation.
- Per-tool time and output limits.
- Per-turn tool-call limit.
- Repeated-call detection.
- Destructive-operation rejection by default.
- Network disabled for code execution by default.
- Audit logs for tool calls and memory changes.
- No implicit expansion of authority from one tool to another.

The POC is not a hardened security boundary. Its limitations must be stated clearly in the README.

## 19. Configuration

Illustrative configuration:

```yaml
agent:
  model: glm-5.2:cloud
  base_url: http://127.0.0.1:11434/v1
  api_key_required: false
  request_timeout_seconds: 300
  max_tool_calls_per_turn: 20

context:
  max_input_tokens: 32000
  response_reserve_tokens: 8000
  recent_main_messages: 0
  budgets:
    agent: 1000
    user: 1000
    memory: 2000
    state: 3000
    recent_messages: 8000
    retrieved_history: 5000
    active_tools: 5000

retrieval:
  engine: sqlite_fts5
  max_results: 8
  max_excerpt_tokens: 800

tools:
  default_timeout_seconds: 60
  max_preview_bytes: 12000
  duplicate_call_window: 10
  workspace_roots:
    - .

code_execution:
  language: python
  default_timeout_seconds: 10
  max_output_bytes: 12000
  max_generated_files: 20
  max_generated_file_bytes: 10000000
  network: disabled

web:
  provider: tavily
  max_results: 5
  freshness_seconds: 3600
```

## 20. Observability

For every turn, record:

- Estimated and provider-reported input tokens.
- Output tokens.
- Cached tokens when reported.
- Tokens by context category.
- Retrieved source IDs and query terms.
- Tool calls, duration, status, and artifact sizes.
- Duplicate calls prevented or reused.
- Memory and state changes.
- Context trimming decisions.

A debug command should display why each context item was included.

## 21. Evaluation plan

Run the same scripted long-session workload in two modes:

1. **Baseline:** Complete conversation and completed tool messages are resent every turn.
2. **Lean:** This specification's bounded context and retrieval policies are used.

The workload should contain at least 50 turns and include:

- Early user constraints referenced much later.
- Large filesystem searches.
- Large terminal output.
- Web research with citations.
- Python computation producing an artifact.
- A repeated tool request.
- A corrected user preference.
- A follow-up requiring exact historical output.

Measure:

- Total and per-turn input tokens.
- Maximum active context size.
- Task success rate.
- Recall of early constraints.
- Retrieval precision and misses.
- Duplicate tool calls.
- Latency.
- Tool-output bytes kept outside context.
- Incorrect or stale memory usage.

## 22. POC acceptance criteria

The POC is successful when:

1. Active context stays within its configured token budget for the complete long-session test.
2. Completed tool exchanges disappear from subsequent active contexts.
3. A setting of `0` includes all main messages; a positive setting includes exactly that many most-recent main messages unless fewer exist.
4. Full conversation and tool history remain externally inspectable.
5. An old conversation fact can be found through full-text retrieval and cited by source ID.
6. Exact historical tool output can be recovered through its artifact reference.
7. Large file, terminal, web, and code outputs are truncated in context and preserved as artifacts.
8. Filesystem access cannot escape configured workspace roots.
9. Terminal and code execution stop at their configured timeouts.
10. Code execution does not inherit configured secret values.
11. Duplicate deterministic tool execution is detected and safely reused or challenged.
12. Memory correction supersedes an older conflicting memory.
13. Context manifests explain all included historical material.
14. Bounded modes report provider-measured token reduction and task quality together; token reduction alone is not a passing result.
15. With all main messages held constant, ContextSift matches the full-tool-history baseline on required evidence recovery and overall task success.

## 23. Implementation sequence

### Phase 1 — Core history and context

- Define record models and JSONL stores.
- Implement the recent main-message window.
- Implement token budgets and context manifests.
- Add `agent.md`, `user.md`, `memory.md`, and `state.md` loading.

### Phase 2 — Retrieval

- Add SQLite FTS5 indexing.
- Index conversations, memories, state sections, and tool receipts.
- Implement bounded excerpt retrieval and source references.

### Phase 3 — Tools and artifacts

- Implement the shared tool-result envelope.
- Implement artifact storage and bounded artifact reading.
- Add filesystem and terminal tools.
- Add Tavily web search.
- Add isolated Python execution.

### Phase 4 — Memory and checkpoints

- Add explicit memory-promotion rules.
- Add memory correction and supersession.
- Add state checkpoint updates.

### Phase 5 — Safety and evaluation

- Add permission, path, timeout, redaction, and duplicate-call checks.
- Build the long-session baseline-versus-lean test.
- Produce a token-use and correctness report.

## 24. Final architecture summary

```text
Current request
      │
      ▼
Persistent identity and state ── agent.md / user.md / memory.md / state.md
      │
      ▼
Recent main-message window ───── configurable; `0` includes all main messages
      │
      ▼
Selective retrieval ──────────── SQLite FTS5 over conversation and tool receipts
      │
      ▼
Budgeted context builder ─────── context manifest and strict token limits
      │
      ▼
Model ↔ bounded tool results ─── filesystem / terminal / Tavily / Python
      │
      ▼
Lossless external storage ────── JSONL logs and artifact files
```

The active model context is a bounded working set. The external history is the lossless source of recall. Retrieval connects the two only when older information is relevant.
