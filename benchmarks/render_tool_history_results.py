from __future__ import annotations

from html import escape
from pathlib import Path
import argparse
import json
import shutil
import subprocess


BASELINE = "#475569"
SIFT = "#0f766e"


def start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff" rx="18"/>',
        '<style>text{font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;fill:#0f172a}.title{font-size:25px;font-weight:750}.sub{font-size:13px;fill:#64748b}.label{font-size:14px;font-weight:650}.value{font-size:16px;font-weight:750}.small{font-size:12px;fill:#64748b}</style>',
        f'<text x="38" y="44" class="title">{escape(title)}</text>',
        f'<text x="38" y="69" class="sub">{escape(subtitle)}</text>',
    ]


def token_chart(data: dict, path: Path) -> None:
    baseline, sift = data["arms"]
    b = baseline["summary"]["actual_prompt_tokens"]
    s = sift["summary"]["actual_prompt_tokens"]
    reduction = 100 * (b - s) / b
    lines = start(840, 390, "Completed tool history dominated repeated input", "All main messages remained active in both arms.")
    for index, (label, value, color) in enumerate(
        (("Full-history baseline", b, BASELINE), ("ContextSift", s, SIFT))
    ):
        y = 115 + index * 105
        bar = 570 * value / b
        lines.extend(
            [
                f'<text x="38" y="{y + 28}" class="label">{label}</text>',
                f'<rect x="215" y="{y}" width="570" height="45" rx="9" fill="#f1f5f9"/>',
                f'<rect x="215" y="{y}" width="{bar:.1f}" height="45" rx="9" fill="{color}"/>',
                f'<text x="230" y="{y + 29}" fill="#ffffff" style="font:750 15px Inter,system-ui">{value:,}</text>',
            ]
        )
    lines.extend(
        [
            f'<text x="785" y="333" text-anchor="end" class="value">{reduction:.1f}% fewer prompt tokens</text>',
            '<text x="38" y="362" class="small">Provider-reported total across five tasks and eight model calls per arm.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def active_context_chart(data: dict, path: Path) -> None:
    calls = data["historical_completed_tool_calls"]
    main = data["main_message_count"]
    lines = start(900, 430, "Same main history, different active baggage", "Initial request composition before the first benchmark task.")
    categories = (
        ("System", 2, "#cbd5e1"),
        ("Main user/assistant", main, "#0f766e"),
        ("Assistant tool calls", calls, "#f59e0b"),
        ("Raw tool results", calls, "#dc2626"),
    )
    scale = 680 / (2 + main + calls * 2)
    for row, (label, values) in enumerate(
        (("Full-history baseline", [2, main, calls, calls]), ("ContextSift", [2, main, 0, 0]))
    ):
        y = 115 + row * 100
        lines.append(f'<text x="38" y="{y + 31}" class="label">{label}</text>')
        x = 190
        for (_, _, color), value in zip(categories, values):
            if not value:
                continue
            width = value * scale
            lines.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="48" fill="{color}" rx="6"/>')
            if width > 45:
                lines.append(f'<text x="{x + width / 2:.1f}" y="{y + 30}" text-anchor="middle" fill="#ffffff" style="font:700 13px Inter,system-ui">{value}</text>')
            x += width
    x, y = 38, 330
    for label, _, color in categories:
        lines.extend(
            [
                f'<rect x="{x}" y="{y}" width="14" height="14" rx="3" fill="{color}"/>',
                f'<text x="{x + 21}" y="{y + 12}" class="small">{label}</text>',
            ]
        )
        x += 200
    lines.extend(
        [
            '<text x="38" y="395" class="small">ContextSift represents all 20 completed exchanges as compact ledger lines inside a system message; full outputs remain artifacts.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def outcome_chart(data: dict, path: Path) -> None:
    baseline, sift = data["arms"]
    bq, sq = baseline["summary"]["quality_percent"], sift["summary"]["quality_percent"]
    bt, st = baseline["summary"]["total_wall_seconds"], sift["summary"]["total_wall_seconds"]
    time_reduction = 100 * (bt - st) / bt
    lines = start(900, 455, "Quality held; latency improved in this run", "Latency is a single-run observation, not yet a stable performance claim.")
    for panel, (heading, values, maximum, suffix) in enumerate(
        (("Task success", [(bq, BASELINE), (sq, SIFT)], 100, "%"), ("Total wall time", [(bt, BASELINE), (st, SIFT)], bt, "s"))
    ):
        x0 = 55 + panel * 430
        lines.append(f'<text x="{x0}" y="102" class="label">{heading}</text>')
        for row, ((value, color), label) in enumerate(zip(values, ("Baseline", "ContextSift"))):
            y = 135 + row * 105
            lines.extend(
                [
                    f'<text x="{x0}" y="{y}" class="small">{label}</text>',
                    f'<text x="{x0 + 350}" y="{y}" text-anchor="end" class="value">{value:.2f}{suffix}</text>',
                    f'<rect x="{x0}" y="{y + 18}" width="350" height="43" rx="8" fill="#f1f5f9"/>',
                    f'<rect x="{x0}" y="{y + 18}" width="{350 * value / maximum:.1f}" height="43" rx="8" fill="{color}"/>',
                ]
            )
    lines.extend(
        [
            f'<text x="845" y="390" text-anchor="end" class="value">{time_reduction:.1f}% lower wall time</text>',
            '<text x="38" y="423" class="small">Both arms passed 5/5 tasks, including exact recovery of a deep historical tool detail.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def make_report(data: dict) -> str:
    baseline, sift = data["arms"]
    bs, ss = baseline["summary"], sift["summary"]
    token_reduction = 100 * (bs["actual_prompt_tokens"] - ss["actual_prompt_tokens"]) / bs["actual_prompt_tokens"]
    initial_reduction = 100 * (
        baseline["initial_context"]["estimated_tokens_with_schemas"]
        - sift["initial_context"]["estimated_tokens_with_schemas"]
    ) / baseline["initial_context"]["estimated_tokens_with_schemas"]
    time_reduction = 100 * (bs["total_wall_seconds"] - ss["total_wall_seconds"]) / bs["total_wall_seconds"]
    first_baseline = baseline["tasks"][0]["model_calls"][0]["prompt_tokens"]
    first_sift = sift["tasks"][0]["model_calls"][0]["prompt_tokens"]
    first_reduction = 100 * (first_baseline - first_sift) / first_baseline
    rows = []
    for arm, label in ((baseline, "Full-history baseline"), (sift, "ContextSift")):
        summary = arm["summary"]
        initial = arm["initial_context"]
        rows.append(
            f"| {label} | {initial['message_count']} | {initial['estimated_tokens_with_schemas']:,} | "
            f"{summary['actual_prompt_tokens']:,} | {summary['passed']}/{summary['task_count']} | "
            f"{summary['total_wall_seconds']:.2f}s |"
        )
    return f"""# ContextSift: completed-tool-history benchmark

Run: `{data['run_id']}`
Model: `{data['model']}` through {data['provider']}
Comparison: all {data['main_message_count']} main messages in both arms; {data['historical_completed_tool_calls']} completed tool exchanges retained raw versus externalized

## Result

ContextSift used **{ss['actual_prompt_tokens']:,} prompt tokens**, versus **{bs['actual_prompt_tokens']:,}** for the non-eliminating full-history baseline: an **{token_reduction:.1f}% reduction**. Both arms passed **5/5 tasks**.

The first live request was **{first_baseline:,} tokens** with raw tool history and **{first_sift:,} tokens** with ContextSift, a **{first_reduction:.1f}% reduction** before repeated calls compounded the difference.

| Arm | Initial active messages | Initial estimated tokens | Actual prompt tokens across run | Quality | Wall time |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

![Prompt tokens](charts/prompt_tokens.png)

![Initial active context](charts/active_context.png)

![Quality and latency](charts/outcomes.png)

## What changed—and what did not

- Both arms kept all 40 main user/assistant messages.
- Both received the same identity, memory, state prompts, model, ten tool schemas, task order, and current tools.
- The baseline began with 20 assistant tool-call messages and 20 raw tool-result messages in addition to main history.
- ContextSift replaced those completed exchanges with 20 compact ledger receipts and stored **{sift['initial_context']['raw_tool_output_bytes']:,} bytes** of full output in artifacts.
- The baseline retained new filesystem, artifact, and Python tool exchanges in later requests. ContextSift removed each completed exchange after the model consumed it.

## Exact historical evidence

The difficult task asked for `DEEP-CHECKSUM-7729`, which existed deep inside historical call `call-hist-005` and was intentionally absent from the compact receipt.

- The baseline had the raw result in active context and ultimately answered correctly. It also attempted `artifact_search` without a valid artifact and received an error.
- ContextSift saw the receipt and artifact ID, called `artifact_search` successfully, loaded one matching line, and answered correctly.

This demonstrates the intended distinction: remove raw completed output from routine context without making exact evidence unrecoverable.

## Latency and caching

Wall time was **{bs['total_wall_seconds']:.2f}s** for the baseline and **{ss['total_wall_seconds']:.2f}s** for ContextSift, a **{time_reduction:.1f}% reduction in this run**. This is encouraging but not a stable latency claim: it is one run against a cloud model, and repeated trials are required.

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
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    out = args.results.parent
    charts = out / "charts"
    charts.mkdir(exist_ok=True)
    token_chart(data, charts / "prompt_tokens.svg")
    active_context_chart(data, charts / "active_context.svg")
    outcome_chart(data, charts / "outcomes.svg")
    converter = shutil.which("rsvg-convert")
    if converter:
        for name, width in (("prompt_tokens", 1680), ("active_context", 1800), ("outcomes", 1800)):
            subprocess.run(
                [converter, "-w", str(width), "-o", str(charts / f"{name}.png"), str(charts / f"{name}.svg")],
                check=True,
            )
    (out / "REPORT.md").write_text(make_report(data), encoding="utf-8")
    print(out / "REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
