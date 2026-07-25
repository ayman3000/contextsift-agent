from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from contextsift_agent.artifact_store import ArtifactStore
from contextsift_agent.tools.code_execution import CodeExecutionTools
from contextsift_agent.tools.filesystem import FilesystemTools
from contextsift_agent.tools.terminal import TerminalTools


class ArtifactAndToolTests(unittest.TestCase):
    def test_artifact_slice_and_search(self):
        with TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            artifact = store.save_text("alpha\nbeta target\ngamma\n")
            self.assertEqual(store.read(artifact["id"], 0, 5)["content"], "alpha")
            self.assertEqual(store.search(artifact["id"], "target")[0]["line"], 2)

    def test_filesystem_rejects_escape(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            store = ArtifactStore(root / "data")
            tools = FilesystemTools([root], store, 100)
            with self.assertRaises(PermissionError):
                tools.read_file("../outside.txt", call_id="call-1")

    def test_terminal_spills_large_output_to_artifact(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root / "data")
            tools = TerminalTools(root, store, 10, 100)
            result = tools.run("python3 -c 'print(\"x\" * 1000)'", call_id="call-2")
            self.assertEqual(result.status, "success")
            self.assertTrue(result.truncated)
            self.assertEqual(len(result.artifact_ids), 1)

    def test_code_execution_does_not_inherit_secret(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStore(root / "data")
            tools = CodeExecutionTools(root / "data", store, 1000)
            os.environ["CONTEXTSIFT_TEST_SECRET"] = "do-not-leak"
            try:
                result = tools.execute_python(
                    "import os; print(os.environ.get('CONTEXTSIFT_TEST_SECRET'))",
                    call_id="call-3",
                )
            finally:
                os.environ.pop("CONTEXTSIFT_TEST_SECRET", None)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.preview.strip(), "None")


if __name__ == "__main__":
    unittest.main()
