from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import shutil
import statistics
import time

from contextsift_agent.agent import Agent
from contextsift_agent.artifact_store import ArtifactStore
from contextsift_agent.config import Settings
from contextsift_agent.context_builder import ContextBuilder
from contextsift_agent.history_store import HistoryStore
from contextsift_agent.models import Message, ModelResponse, estimate_tokens, utc_now
from contextsift_agent.provider import ChatCompletionsProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = PROJECT_ROOT / "benchmarks" / "results"
HISTORICAL_CALLS = 20

TASKS = (
    {
        "id": "main_fact",
        "prompt": "What is the project charter code recorded in our main conversation? Reply with only the code.",
        "expected": "PROJECT-ATLAS-91",
    },
    {
        "id": "tool_summary",
        "prompt": "What summary seal was reported by historical tool call call-hist-003? Reply with only the seal.",
        "expected": "SUMMARY-SEAL-440",
    },
    {
        "id": "tool_deep_detail",
        "prompt": (
            "Find the exact deep checksum in historical tool call call-hist-005. "
            "If the raw result is external, use its ledger artifact with artifact_search. "
            "Reply with only the checksum."
        ),
        "expected": "DEEP-CHECKSUM-7729",
    },
    {
        "id": "filesystem_tool",
        "prompt": "Use filesystem_read_file to read BENCHMARK_FACTS.md. Reply with only the file probe code.",
        "expected": "FILE-PROBE-7391",
        "required_tool": "filesystem_read_file",
    },
    {
        "id": "code_tool",
        "prompt": (
            "Use code_execute_python to calculate the sum of the squares of integers 1 through 20. "
            "Reply with only the integer result."
        ),
        "expected": "2870",
        "required_tool": "code_execute_python",
    },
)


class RecordingProvider:
    def __init__(self, settings):
        self.inner = ChatCompletionsProvider(settings)
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelResponse:
        started = time.perf_counter()
        response = self.inner.complete(messages, tools)
        elapsed = time.perf_counter() - started
        raw = response.raw or {}
        usage = raw.get("usage") or {}
        role_counts: dict[str, int] = {}
        for message in messages:
            role = str(message.get("role", "unknown"))
            role_counts[role] = role_counts.get(role, 0) + 1
        self.calls.append(
            {
                "elapsed_seconds": round(elapsed, 4),
                "message_count": len(messages),
                "role_counts": role_counts,
                "estimated_message_tokens": sum(
                    estimate_tokens(json.dumps(item, ensure_ascii=False)) for item in messages
                ),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                "requested_tools": [call.name for call in response.tool_calls],
                "finish_reason": ((raw.get("choices") or [{}])[0]).get("finish_reason"),
            }
        )
        return response


def historical_user(index: int) -> str:
    prefix = (
        "The project charter code is PROJECT-ATLAS-91. Keep this exact code in the main conversation. "
        if index == 0
        else ""
    )
    return prefix + (
        f"Historical request {index:03d}: inspect diagnostic batch {index:03d}, record the useful summary, "
        "and preserve the detailed output for later evidence. This is an ordinary completed task in a "
        "long-running agent session."
    )


def historical_assistant(index: int) -> str:
    return (
        f"Diagnostic batch {index:03d} completed successfully. The detailed tool evidence was preserved "
        "and this main response intentionally avoids repeating the raw output."
    )


def historical_summary(index: int) -> str:
    if index == 3:
        return "Diagnostic batch 003 completed; summary seal SUMMARY-SEAL-440"
    if index == 5:
        return "Diagnostic batch 005 completed; exact values are available in its artifact"
    return f"Diagnostic batch {index:03d} completed with no actionable failures"


def historical_raw_output(index: int) -> str:
    lines = [
        f"diagnostic={index:03d} line={line:03d} status=ok component=service-{(index + line) % 11:02d} "
        f"latency_ms={20 + ((index * 17 + line * 13) % 180):03d} note=archived-observation-{index:03d}-{line:03d}"
        for line in range(34)
    ]
    if index == 3:
        lines.insert(9, "summary_seal=SUMMARY-SEAL-440")
    if index == 5:
        lines.insert(31, "deep_checksum=DEEP-CHECKSUM-7729")
    return "\n".join(lines)


def prepare_root(run_dir: Path, arm: str) -> Path:
    root = run_dir / arm
    root.mkdir(parents=True)
    shutil.copytree(PROJECT_ROOT / "prompts", root / "prompts")
    (root / "BENCHMARK_FACTS.md").write_text(
        "# Benchmark facts\n\nThe file probe code is FILE-PROBE-7391.\n",
        encoding="utf-8",
    )
    return root


def settings_for(root: Path) -> Settings:
    settings = Settings(root=root)
    settings.agent.model = "glm-5.2:cloud"
    settings.agent.base_url = "http://127.0.0.1:11434/v1"
    settings.agent.api_key_env = ""
    settings.agent.api_key_required = False
    settings.agent.request_timeout_seconds = 300
    settings.context.recent_main_messages = 0
    settings.context.tool_ledger_entries = 0
    settings.context.max_input_tokens = 96_000
    return settings


def seed_contextsift(root: Path) -> dict[str, Any]:
    history = HistoryStore(root / "data")
    artifacts = ArtifactStore(root / "data")
    raw_bytes = 0
    for index in range(HISTORICAL_CALLS):
        turn_id = f"turn-hist-{index:03d}"
        history.append_message(Message(role="user", content=historical_user(index), turn_id=turn_id))
        raw = historical_raw_output(index)
        raw_bytes += len(raw.encode("utf-8"))
        artifact = artifacts.save_text(
            raw,
            suffix=".log",
            description=f"Full historical terminal output {index:03d}",
            call_id=f"call-hist-{index:03d}",
        )
        history.append_tool_receipt(
            {
                "call_id": f"call-hist-{index:03d}",
                "tool": "terminal_run",
                "status": "success",
                "summary": historical_summary(index),
                "preview": raw[:240],
                "artifact_ids": [artifact["id"]],
                "truncated": True,
                "duration_ms": 10 + index,
                "error": None,
                "metadata": {"historical": True, "total_bytes": len(raw.encode("utf-8"))},
                "timestamp": utc_now(),
                "arguments": {"command": ["diagnostic", str(index)]},
                "turn_id": turn_id,
            }
        )
        history.append_message(Message(role="assistant", content=historical_assistant(index), turn_id=turn_id))
    return {"raw_tool_output_bytes": raw_bytes, "artifact_count": HISTORICAL_CALLS}


def canonical_baseline_transcript() -> tuple[list[dict[str, Any]], int]:
    transcript: list[dict[str, Any]] = []
    raw_bytes = 0
    for index in range(HISTORICAL_CALLS):
        call_id = f"call-hist-{index:03d}"
        raw = historical_raw_output(index)
        raw_bytes += len(raw.encode("utf-8"))
        transcript.extend(
            [
                {"role": "user", "content": historical_user(index)},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "terminal_run",
                                "arguments": json.dumps({"command": ["diagnostic", str(index)]}),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(
                        {
                            "call_id": call_id,
                            "tool": "terminal_run",
                            "status": "success",
                            "summary": historical_summary(index),
                            "preview": raw,
                            "artifact_ids": [],
                            "truncated": False,
                            "error": None,
                        },
                        ensure_ascii=False,
                    ),
                },
                {"role": "assistant", "content": historical_assistant(index)},
            ]
        )
    return transcript, raw_bytes


def task_result(
    task: dict[str, Any], answer: str, error: str | None, calls: list[dict[str, Any]],
    receipts: list[dict[str, Any]], wall_seconds: float,
) -> dict[str, Any]:
    requested = [name for call in calls for name in call["requested_tools"]]
    required = task.get("required_tool")
    tool_ok = True if not required else required in requested and any(
        item.get("tool") == required and item.get("status") == "success" for item in receipts
    )
    expected_ok = task["expected"].casefold() in answer.casefold()
    return {
        **task,
        "answer": answer,
        "error": error,
        "passed": bool(not error and expected_ok and tool_ok),
        "expected_found": expected_ok,
        "required_tool_succeeded": tool_ok,
        "requested_tools": requested,
        "tool_receipts": receipts,
        "wall_seconds": round(wall_seconds, 4),
        "model_calls": calls,
    }


def summarize(arm: str, tasks: list[dict[str, Any]], initial: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = [
        call["prompt_tokens"] for task in tasks for call in task["model_calls"]
        if call["prompt_tokens"] is not None
    ]
    completion_tokens = [
        call["completion_tokens"] for task in tasks for call in task["model_calls"]
        if call["completion_tokens"] is not None
    ]
    return {
        "arm": arm,
        "initial_context": initial,
        "tasks": tasks,
        "summary": {
            "passed": sum(task["passed"] for task in tasks),
            "task_count": len(tasks),
            "quality_percent": round(100 * sum(task["passed"] for task in tasks) / len(tasks), 2),
            "actual_prompt_tokens": sum(prompt_tokens) if prompt_tokens else None,
            "actual_completion_tokens": sum(completion_tokens) if completion_tokens else None,
            "model_call_count": sum(len(task["model_calls"]) for task in tasks),
            "total_wall_seconds": round(sum(task["wall_seconds"] for task in tasks), 4),
            "median_task_seconds": round(statistics.median(task["wall_seconds"] for task in tasks), 4),
        },
    }


def run_contextsift(run_dir: Path) -> dict[str, Any]:
    root = prepare_root(run_dir, "contextsift")
    storage = seed_contextsift(root)
    settings = settings_for(root)
    provider = RecordingProvider(settings.agent)
    agent = Agent(settings, provider=provider)
    preview = agent.preview_context()
    initial = {
        "message_count": len(preview["messages"]),
        "role_counts": {
            role: sum(message["role"] == role for message in preview["messages"])
            for role in ("system", "user", "assistant", "tool")
        },
        "estimated_tokens_with_schemas": preview["manifest"]["estimated_input_tokens"],
        **storage,
    }
    results = []
    for task in TASKS:
        call_start = len(provider.calls)
        receipt_start = len(agent.history.recent_tool_receipts(0))
        started = time.perf_counter()
        error = None
        try:
            answer = agent.ask(task["prompt"])
        except Exception as exc:
            answer = ""
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        calls = provider.calls[call_start:]
        receipts = agent.history.recent_tool_receipts(0)[receipt_start:]
        compact_receipts = [
            {key: item.get(key) for key in ("call_id", "tool", "status", "summary", "duration_ms")}
            for item in receipts
        ]
        result = task_result(task, answer, error, calls, compact_receipts, elapsed)
        results.append(result)
        print(f"contextsift {task['id']:<18} {'PASS' if result['passed'] else 'FAIL'} {elapsed:7.2f}s", flush=True)
    return summarize("contextsift", results, initial)


class FullHistoryAgent:
    def __init__(self, provider: RecordingProvider, registry, system_messages, transcript):
        self.provider = provider
        self.registry = registry
        self.system_messages = system_messages
        self.transcript = transcript

    def ask(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        self.transcript.append({"role": "user", "content": text})
        receipts = []
        calls_used = 0
        schemas = self.registry.schemas()
        while True:
            response = self.provider.complete(self.system_messages + self.transcript, schemas)
            if not response.tool_calls:
                answer = response.content or ""
                self.transcript.append({"role": "assistant", "content": answer})
                return answer, receipts
            calls_used += len(response.tool_calls)
            if calls_used > 20:
                raise RuntimeError("Tool-call limit exceeded")
            self.transcript.append(Agent._assistant_tool_message(response))
            for call in response.tool_calls:
                result = self.registry.execute(call.name, call.arguments, call.id)
                receipts.append(
                    {key: getattr(result, key) for key in ("call_id", "tool", "status", "summary", "duration_ms")}
                )
                self.transcript.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result.to_model_content()}
                )


def run_baseline(run_dir: Path) -> dict[str, Any]:
    root = prepare_root(run_dir, "full_history_baseline")
    settings = settings_for(root)
    provider = RecordingProvider(settings.agent)
    registry_host = Agent(settings, provider=provider)
    empty_context = ContextBuilder(settings, HistoryStore(root / "empty-data")).build()
    transcript, raw_bytes = canonical_baseline_transcript()
    initial_messages = empty_context.messages + transcript
    initial = {
        "message_count": len(initial_messages),
        "role_counts": {
            role: sum(message["role"] == role for message in initial_messages)
            for role in ("system", "user", "assistant", "tool")
        },
        "estimated_tokens_with_schemas": (
            sum(estimate_tokens(json.dumps(message, ensure_ascii=False)) for message in initial_messages)
            + estimate_tokens(json.dumps(registry_host.registry.schemas(), ensure_ascii=False))
        ),
        "raw_tool_output_bytes": raw_bytes,
        "artifact_count": 0,
    }
    agent = FullHistoryAgent(provider, registry_host.registry, empty_context.messages, transcript)
    results = []
    for task in TASKS:
        call_start = len(provider.calls)
        started = time.perf_counter()
        error = None
        receipts: list[dict[str, Any]] = []
        try:
            answer, receipts = agent.ask(task["prompt"])
        except Exception as exc:
            answer = ""
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        result = task_result(task, answer, error, provider.calls[call_start:], receipts, elapsed)
        results.append(result)
        print(f"baseline    {task['id']:<18} {'PASS' if result['passed'] else 'FAIL'} {elapsed:7.2f}s", flush=True)
    return summarize("full_history_baseline", results, initial)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("tool-history-%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_ROOT / stamp
    run_dir.mkdir(parents=True)
    payload = {
        "run_id": stamp,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": "all main messages in both arms; retain versus externalize completed tool exchanges",
        "model": "glm-5.2:cloud",
        "provider": "Ollama OpenAI-compatible API",
        "main_message_count": HISTORICAL_CALLS * 2,
        "historical_completed_tool_calls": HISTORICAL_CALLS,
        "tasks": list(TASKS),
        "arms": [],
    }
    payload["arms"].append(run_baseline(run_dir))
    (run_dir / "results.partial.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["arms"].append(run_contextsift(run_dir))
    (run_dir / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"RESULTS={run_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
