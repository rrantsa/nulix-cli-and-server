import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator import validate_generated_command


class ValidatorTests(unittest.TestCase):
    def test_safe_command_passes_through(self) -> None:
        result = validate_generated_command("mkdir photos")
        self.assertEqual(result.command, "mkdir photos")
        self.assertFalse(result.dangerous)

    def test_model_unknown_becomes_echo(self) -> None:
        result = validate_generated_command("# UNKNOWN")
        self.assertEqual(result.command, "echo '#UNKNOWN'")
        self.assertFalse(result.dangerous)

    def test_dangerous_rm_is_blocked(self) -> None:
        result = validate_generated_command("rm -rf /")
        self.assertEqual(result.command, "echo '#DANGEROUS rm -rf /'")
        self.assertTrue(result.dangerous)

    def test_multiple_lines_become_unknown(self) -> None:
        result = validate_generated_command("mkdir photos\nls")
        self.assertEqual(result.command, "echo '#UNKNOWN'")
        self.assertFalse(result.dangerous)


if __name__ == "__main__":
    unittest.main()
