from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contextsift_agent.retrieval import SearchIndex


class RetrievalTests(unittest.TestCase):
    def test_full_text_search_returns_source_and_excerpt(self):
        with TemporaryDirectory() as directory:
            index = SearchIndex(Path(directory) / "search.sqlite")
            index.add(record_id="m1", source="conversation:user", content="Use a bounded working context")
            index.add(record_id="m2", source="conversation:user", content="The weather is warm")
            results = index.search("working context", limit=3)
            self.assertEqual(results[0]["id"], "m1")
            self.assertIn("[working]", results[0]["excerpt"].casefold())

    def test_search_can_exclude_recent_ids(self):
        with TemporaryDirectory() as directory:
            index = SearchIndex(Path(directory) / "search.sqlite")
            index.add(record_id="old", source="conversation:user", content="context retrieval decision")
            index.add(record_id="new", source="conversation:user", content="context retrieval followup")
            results = index.search("context retrieval", exclude_ids={"new"})
            self.assertEqual([item["id"] for item in results], ["old"])


if __name__ == "__main__":
    unittest.main()
