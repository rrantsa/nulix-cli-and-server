import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_provider import ModelProviderConfigError, generate_command_from_model, generate_text_from_model


class ModelProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [
            "NULIX_MODEL_PROVIDER",
            "NULIX_MODEL_NAME",
            "NULIX_MODEL_TIMEOUT_SECONDS",
            "OLLAMA_URL",
            "NULIX_EXTERNAL_API_BASE_URL",
            "NULIX_EXTERNAL_API_KEY",
            "NULIX_EXTERNAL_API_PATH",
        ]:
            os.environ.pop(key, None)

    @patch("model_provider.requests.post")
    def test_ollama_provider_uses_local_api(self, mock_post: Mock) -> None:
        os.environ["NULIX_MODEL_PROVIDER"] = "ollama"
        mock_response = Mock()
        mock_response.json.return_value = {"response": "mkdir photos"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        command = generate_command_from_model("create a photos folder")

        self.assertEqual(command, "mkdir photos")
        self.assertIn("/api/generate", mock_post.call_args.kwargs["url"] if "url" in mock_post.call_args.kwargs else mock_post.call_args.args[0])

    @patch("model_provider.requests.post")
    def test_openai_compatible_provider_uses_external_api(self, mock_post: Mock) -> None:
        os.environ["NULIX_MODEL_PROVIDER"] = "openai_compatible"
        os.environ["NULIX_EXTERNAL_API_BASE_URL"] = "https://example.com/v1"
        os.environ["NULIX_EXTERNAL_API_KEY"] = "secret"
        os.environ["NULIX_MODEL_NAME"] = "gpt-4.1-mini"
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "find . -type f | wc -l",
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        command = generate_command_from_model("count files")

        self.assertEqual(command, "find . -type f | wc -l")
        url = mock_post.call_args.kwargs["url"] if "url" in mock_post.call_args.kwargs else mock_post.call_args.args[0]
        self.assertEqual(url, "https://example.com/v1/chat/completions")
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer secret")

    @patch("model_provider.requests.post")
    def test_generic_provider_call_accepts_custom_system_and_prompt(self, mock_post: Mock) -> None:
        os.environ["NULIX_MODEL_PROVIDER"] = "ollama"
        mock_response = Mock()
        mock_response.json.return_value = {"response": "chmod +x script.sh"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        command = generate_text_from_model("system text", "prompt text")

        self.assertEqual(command, "chmod +x script.sh")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["system"], "system text")
        self.assertEqual(payload["prompt"], "prompt text")

    def test_unsupported_provider_raises(self) -> None:
        os.environ["NULIX_MODEL_PROVIDER"] = "unknown"
        with self.assertRaises(ModelProviderConfigError):
            generate_command_from_model("anything")
