from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contextsift_agent.agent import Agent
from contextsift_agent.config import Settings
from contextsift_agent.history_store import HistoryStore
from contextsift_agent.models import Message, ModelResponse, ToolCall, ToolResult
from contextsift_agent.tool_registry import ToolRegistry


class FakeProvider:
    def __init__(self):
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return ModelResponse(None, [ToolCall("call-demo", "demo.echo", {"text": "hello"})])
        self.tool_content = messages[-1]["content"]
        return ModelResponse("Finished")


class MultiToolProvider:
    def __init__(self):
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return ModelResponse(None, [ToolCall("call-1", "demo_large", {})])
        if len(self.calls) == 2:
            self.asserted_full_first_result = "UNIQUE-LARGE-PREVIEW" in messages[-1]["content"]
            return ModelResponse(None, [ToolCall("call-2", "demo_small", {})])
        first_tool = next(item for item in messages if item.get("tool_call_id") == "call-1")
        second_tool = next(item for item in messages if item.get("tool_call_id") == "call-2")
        self.first_was_compacted = "UNIQUE-LARGE-PREVIEW" not in first_tool["content"] and '"compacted": true' in first_tool["content"]
        self.second_was_still_full = '"preview": "second-result"' in second_tool["content"]
        return ModelResponse("Done")


class AgentLoopTests(unittest.TestCase):
    def test_completed_tool_exchange_is_externalized(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(root=root)
            settings.context.recent_main_messages = 0
            registry = ToolRegistry()

            def echo(text: str, *, call_id: str):
                return ToolResult(call_id, "demo.echo", "success", "Echo complete", text)

            registry.register(
                "demo.echo",
                "Echo text",
                {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                echo,
            )
            provider = FakeProvider()
            agent = Agent(settings, provider=provider, registry=registry)
            self.assertEqual(agent.ask("Run the demo"), "Finished")
            self.assertIn("Echo complete", provider.tool_content)
            messages = agent.history.main_messages(0)
            self.assertEqual([(item.role, item.content) for item in messages], [("user", "Run the demo"), ("assistant", "Finished")])
            receipts = agent.history.recent_tool_receipts()
            self.assertEqual(receipts[0]["call_id"], "call-demo")
            preview = agent.preview_context()
            system_text = "\n".join(
                item["content"] for item in preview["messages"] if item["role"] == "system"
            )
            self.assertIn("call-demo demo.echo", system_text)
            manifest_sources = {item["source"] for item in preview["manifest"]["sources"]}
            self.assertIn("tool-schemas", manifest_sources)
            manifest_lines = (root / "data" / "context_manifests.jsonl").read_text().splitlines()
            self.assertEqual(len(manifest_lines), 2)

    def test_consumed_tool_previews_are_compacted_before_later_steps(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(root=root)
            registry = ToolRegistry()

            registry.register(
                "demo_large",
                "Large output",
                {"type": "object", "properties": {}},
                lambda *, call_id: ToolResult(call_id, "demo_large", "success", "large complete", "UNIQUE-LARGE-PREVIEW" * 100),
            )
            registry.register(
                "demo_small",
                "Small output",
                {"type": "object", "properties": {}},
                lambda *, call_id: ToolResult(call_id, "demo_small", "success", "small complete", "second-result"),
            )
            provider = MultiToolProvider()
            agent = Agent(settings, provider=provider, registry=registry)
            self.assertEqual(agent.ask("Use two tools"), "Done")
            self.assertTrue(provider.asserted_full_first_result)
            self.assertTrue(provider.first_was_compacted)
            self.assertTrue(provider.second_was_still_full)
            manifest_lines = (root / "data" / "context_manifests.jsonl").read_text().splitlines()
            self.assertEqual(len(manifest_lines), 3)

    def test_existing_jsonl_history_is_reindexed_on_startup(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = HistoryStore(root / "data")
            history.append_message(Message(role="user", content="The cobalt constraint is permanent"))
            agent = Agent(Settings(root=root), provider=FakeProvider(), registry=ToolRegistry())
            results = agent.search_index.search("cobalt constraint")
            self.assertEqual(results[0]["source"], "conversation:user")

    def test_doctor_reports_missing_keys_without_exposing_values(self):
        with TemporaryDirectory() as directory:
            agent = Agent(Settings(root=Path(directory)), provider=FakeProvider(), registry=ToolRegistry())
            report = agent.doctor()
            self.assertIn(report["status"], {"ready", "needs_api_key"})
            self.assertNotIn("api_key", report)


if __name__ == "__main__":
    unittest.main()
