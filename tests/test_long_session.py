from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contextsift_agent.config import Settings
from contextsift_agent.context_builder import ContextBuilder
from contextsift_agent.history_store import HistoryStore
from contextsift_agent.models import Message


class LongSessionTests(unittest.TestCase):
    def test_configured_window_stays_constant_while_unlimited_grows(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = HistoryStore(root / "data")
            for number in range(100):
                history.append_message(Message(role="user" if number % 2 == 0 else "assistant", content=f"turn {number} " + "x" * 100))

            bounded = Settings(root=root)
            bounded.context.recent_main_messages = 10
            bounded_context = ContextBuilder(bounded, history).build()

            unlimited = Settings(root=root)
            unlimited.context.recent_main_messages = 0
            unlimited_context = ContextBuilder(unlimited, history).build()

            self.assertEqual(bounded_context.manifest["sources"][-1]["message_count"], 10)
            self.assertEqual(unlimited_context.manifest["sources"][-1]["message_count"], 100)
            self.assertGreater(
                unlimited_context.manifest["estimated_input_tokens"],
                bounded_context.manifest["estimated_input_tokens"] * 5,
            )


if __name__ == "__main__":
    unittest.main()
