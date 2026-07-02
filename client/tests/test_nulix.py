import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nulix


class ClientCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {key: os.environ.get(key) for key in self._managed_env_keys()}
        os.environ["NULIX_API_URL"] = "https://nulix.example.com"
        os.environ["NULIX_API_KEY"] = "user-key"
        os.environ["NULIX_ADMIN_API_KEY"] = "admin-key"

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _managed_env_keys(self) -> list[str]:
        return [
            "NULIX_API_URL",
            "NULIX_API_KEY",
            "NULIX_ADMIN_API_KEY",
            "NULIX_CLIENT_TIMEOUT_SECONDS",
        ]

    @patch("nulix.requests.post")
    def test_generate_uses_normal_endpoint_and_key(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"command": "ls -l", "dangerous": False}
        mock_post.return_value = response

        stdout = io.StringIO()
        with patch.object(sys, "argv", ["nulix", "list", "files"]), redirect_stdout(stdout):
            exit_code = nulix.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "ls -l")
        self.assertEqual(mock_post.call_args.kwargs["headers"]["X-API-Key"], "user-key")
        self.assertTrue(mock_post.call_args.args[0].endswith("/generate"))

    @patch("nulix.requests.post")
    def test_memorize_uses_admin_endpoint_and_aliases(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"created": 2, "duplicates": 0, "category": "user-added"}
        mock_post.return_value = response

        stdout = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "nulix",
                "memorize",
                "restart nginx",
                "systemctl restart nginx",
                "--alias",
                "nginx restart",
            ],
        ), redirect_stdout(stdout):
            exit_code = nulix.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("memorized created=2 duplicates=0 category=user-added", stdout.getvalue().strip())
        self.assertEqual(mock_post.call_args.kwargs["headers"]["X-API-Key"], "admin-key")
        self.assertTrue(mock_post.call_args.args[0].endswith("/rules"))
        self.assertEqual(
            mock_post.call_args.kwargs["json"],
            {
                "intent": "restart nginx",
                "command": "systemctl restart nginx",
                "aliases": ["nginx restart"],
            },
        )


if __name__ == "__main__":
    unittest.main()
