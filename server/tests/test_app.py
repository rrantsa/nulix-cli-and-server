import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module
from knowledge import KnowledgeBase


class AppEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {key: os.environ.get(key) for key in self._managed_env_keys()}
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmpdir.name)

        self.user_keys_path = tmp_path / "api_keys.txt"
        self.admin_keys_path = tmp_path / "admin_api_keys.txt"
        self.db_path = tmp_path / "knowledge.db"

        self.user_keys_path.write_text("user-key\n", encoding="utf-8")
        self.admin_keys_path.write_text("admin-key\n", encoding="utf-8")

        os.environ["NULIX_API_KEYS_FILE"] = str(self.user_keys_path)
        os.environ["NULIX_ADMIN_API_KEYS_FILE"] = str(self.admin_keys_path)
        os.environ["NULIX_KB_PATH"] = str(self.db_path)
        os.environ["NULIX_KB_ENABLED"] = "true"

        if app_module._kb is not None:
            app_module._kb.close()
        app_module._kb = None

    def tearDown(self) -> None:
        if app_module._kb is not None:
            app_module._kb.close()
        app_module._kb = None

        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        self._tmpdir.cleanup()

    def _managed_env_keys(self) -> list[str]:
        return [
            "NULIX_API_KEYS_FILE",
            "NULIX_ADMIN_API_KEYS_FILE",
            "NULIX_KB_PATH",
            "NULIX_KB_ENABLED",
        ]

    def test_admin_key_can_use_generate_endpoint(self) -> None:
        os.environ["NULIX_KB_ENABLED"] = "false"
        with patch("app.generate_command_from_provider", return_value="mkdir photos"):
            response = app_module.generate(
                app_module.GenerateRequest(text="create a photos folder"),
                x_api_key="admin-key",
            )

        self.assertEqual(response.command, "mkdir photos")
        self.assertFalse(response.dangerous)

    def test_normal_key_cannot_create_rule(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            app_module.create_rule(
                app_module.RuleCreateRequest(
                    intent="restart nginx",
                    command="systemctl restart nginx",
                ),
                x_api_key="user-key",
            )

        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_can_create_rule_with_aliases_and_search_immediately(self) -> None:
        response = app_module.create_rule(
            app_module.RuleCreateRequest(
                intent="restart nginx",
                command="systemctl restart nginx",
                aliases=["restart nginx service", "nginx restart"],
            ),
            x_api_key="admin-key",
        )

        self.assertEqual(response.created, 3)
        self.assertEqual(response.duplicates, 0)
        self.assertEqual(response.category, "user-added")

        kb = KnowledgeBase(str(self.db_path))
        try:
            direct_matches = kb.search("restart nginx", limit=3)
            matches = kb.search("nginx restart", limit=3)
        finally:
            kb.close()

        self.assertTrue(any(match["command"] == "systemctl restart nginx" for match in direct_matches))
        self.assertTrue(any(match["command"] == "systemctl restart nginx" for match in matches))

    def test_duplicate_rule_submission_is_idempotent(self) -> None:
        request = app_module.RuleCreateRequest(
            intent="restart nginx",
            command="systemctl restart nginx",
            aliases=["nginx restart"],
        )

        first = app_module.create_rule(request, x_api_key="admin-key")
        second = app_module.create_rule(request, x_api_key="admin-key")

        self.assertEqual(first.created, 2)
        self.assertEqual(first.duplicates, 0)
        self.assertEqual(second.created, 0)
        self.assertEqual(second.duplicates, 2)

        kb = KnowledgeBase(str(self.db_path))
        try:
            count = kb.conn.execute(
                "SELECT COUNT(*) FROM rules WHERE command = ? AND category = ?",
                ("systemctl restart nginx", "user-added"),
            ).fetchone()[0]
        finally:
            kb.close()

        self.assertEqual(count, 2)

    def test_dangerous_command_is_rejected_and_not_inserted(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            app_module.create_rule(
                app_module.RuleCreateRequest(
                    intent="delete everything",
                    command="rm -rf /",
                ),
                x_api_key="admin-key",
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("dangerous", str(ctx.exception.detail).lower())

        kb = KnowledgeBase(str(self.db_path))
        try:
            count = kb.conn.execute(
                "SELECT COUNT(*) FROM rules WHERE category = ?",
                ("user-added",),
            ).fetchone()[0]
        finally:
            kb.close()

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
