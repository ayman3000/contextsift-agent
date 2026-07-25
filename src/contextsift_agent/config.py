from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass(slots=True)
class AgentSettings:
    model: str = "glm-5.2:cloud"
    base_url: str = "http://127.0.0.1:11434/v1"
    api_key_env: str = ""
    api_key_required: bool = False
    request_timeout_seconds: int = 300
    max_tool_calls_per_turn: int = 20


@dataclass(slots=True)
class ContextSettings:
    recent_main_messages: int = 0
    max_input_tokens: int = 32_000
    retrieved_history_results: int = 5
    tool_ledger_entries: int = 20


@dataclass(slots=True)
class ToolSettings:
    default_timeout_seconds: int = 60
    max_preview_bytes: int = 12_000


@dataclass(slots=True)
class WebSettings:
    api_key_env: str = "TAVILY_API_KEY"
    max_results: int = 5


@dataclass(slots=True)
class Settings:
    root: Path
    agent: AgentSettings = field(default_factory=AgentSettings)
    context: ContextSettings = field(default_factory=ContextSettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    web: WebSettings = field(default_factory=WebSettings)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"


def _section(cls, values: dict | None):
    return cls(**(values or {}))


def load_settings(path: str | Path = "config.toml") -> Settings:
    config_path = Path(path).resolve()
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    settings = Settings(
        root=config_path.parent,
        agent=_section(AgentSettings, raw.get("agent")),
        context=_section(ContextSettings, raw.get("context")),
        tools=_section(ToolSettings, raw.get("tools")),
        web=_section(WebSettings, raw.get("web")),
    )
    if settings.context.recent_main_messages < 0:
        raise ValueError("context.recent_main_messages must be 0 or a positive integer")
    if settings.context.max_input_tokens <= 0:
        raise ValueError("context.max_input_tokens must be positive")
    if settings.agent.max_tool_calls_per_turn <= 0:
        raise ValueError("agent.max_tool_calls_per_turn must be positive")
    if settings.agent.request_timeout_seconds <= 0:
        raise ValueError("agent.request_timeout_seconds must be positive")
    return settings
