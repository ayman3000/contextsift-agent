from unittest.mock import patch
import json
import os
import unittest

from contextsift_agent.config import AgentSettings
from contextsift_agent.provider import ChatCompletionsProvider


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-local",
                                    "type": "function",
                                    "function": {
                                        "name": "filesystem_stat",
                                        "arguments": '{"path":"README.md"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ).encode()


class ProviderTests(unittest.TestCase):
    def test_chat_completions_adapter_serializes_and_parses_tool_calls(self):
        captured = {}

        def fake_urlopen(http_request, timeout):
            captured["request"] = http_request
            captured["timeout"] = timeout
            return _Response()

        os.environ["CONTEXTSIFT_PROVIDER_TEST_KEY"] = "local-test-key"
        try:
            settings = AgentSettings(
                model="test-model",
                base_url="https://provider.invalid/v1",
                api_key_env="CONTEXTSIFT_PROVIDER_TEST_KEY",
                api_key_required=True,
            )
            with patch("contextsift_agent.provider.request.urlopen", side_effect=fake_urlopen):
                response = ChatCompletionsProvider(settings).complete(
                    [{"role": "user", "content": "inspect"}],
                    [
                        {
                            "type": "function",
                            "function": {
                                "name": "filesystem_stat",
                                "description": "Stat a file",
                                "parameters": {"type": "object", "properties": {}},
                            },
                        }
                    ],
                )
        finally:
            os.environ.pop("CONTEXTSIFT_PROVIDER_TEST_KEY", None)

        payload = json.loads(captured["request"].data)
        self.assertEqual(response.tool_calls[0].name, "filesystem_stat")
        self.assertEqual(response.tool_calls[0].arguments, {"path": "README.md"})
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertEqual(captured["request"].get_header("Authorization"), "Bearer local-test-key")
        self.assertEqual(captured["timeout"], 300)

    def test_api_key_is_optional_for_local_ollama(self):
        captured = {}

        def fake_urlopen(http_request, timeout):
            captured["request"] = http_request
            return _Response()

        settings = AgentSettings(
            model="glm-5.2:cloud",
            base_url="http://127.0.0.1:11434/v1",
            api_key_env="",
            api_key_required=False,
        )
        with patch("contextsift_agent.provider.request.urlopen", side_effect=fake_urlopen):
            ChatCompletionsProvider(settings).complete([{"role": "user", "content": "inspect"}], [])

        self.assertIsNone(captured["request"].get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
