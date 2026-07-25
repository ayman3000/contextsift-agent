from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contextsift_agent.config import Settings, load_settings
from contextsift_agent.context_builder import ContextBuilder
from contextsift_agent.history_store import HistoryStore
from contextsift_agent.models import Message


class ContextBuilderTests(unittest.TestCase):
    def _settings(self, root: Path, limit: int) -> Settings:
        settings = Settings(root=root)
        settings.context.recent_main_messages = limit
        prompts = root / "prompts"
        prompts.mkdir()
        for name in ("agent.md", "user.md", "memory.md", "state.md"):
            (prompts / name).write_text(name, encoding="utf-8")
        return settings

    def _history(self, root: Path, count: int = 8) -> HistoryStore:
        history = HistoryStore(root / "data")
        for number in range(count):
            history.append_message(
                Message(role="user" if number % 2 == 0 else "assistant", content=f"message-{number}")
            )
        return history

    def test_zero_includes_all_main_messages(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self._settings(root, 0)
            built = ContextBuilder(settings, self._history(root)).build()
            conversation = [item for item in built.messages if item["role"] != "system"]
            self.assertEqual([item["content"] for item in conversation], [f"message-{n}" for n in range(8)])
            self.assertEqual(built.manifest["recent_main_messages_setting"], 0)
            self.assertEqual(built.manifest["sources"][-1]["source"], "conversation:all")

    def test_positive_limit_keeps_only_newest_main_messages(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self._settings(root, 3)
            built = ContextBuilder(settings, self._history(root)).build()
            conversation = [item for item in built.messages if item["role"] != "system"]
            self.assertEqual([item["content"] for item in conversation], ["message-5", "message-6", "message-7"])

    def test_limit_counts_neither_tool_receipts_nor_non_main_messages(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self._settings(root, 2)
            history = self._history(root, 4)
            history.append_tool_receipt(
                {"call_id": "call-1", "tool": "demo", "summary": "done", "artifact_ids": []}
            )
            built = ContextBuilder(settings, history).build()
            conversation = [item for item in built.messages if item["role"] != "system"]
            self.assertEqual([item["content"] for item in conversation], ["message-2", "message-3"])
            self.assertIn("call-1 demo", built.messages[1]["content"])

    def test_project_configuration_defaults_to_all(self):
        settings = load_settings(Path(__file__).parents[1] / "config.toml")
        self.assertEqual(settings.context.recent_main_messages, 0)


if __name__ == "__main__":
    unittest.main()
