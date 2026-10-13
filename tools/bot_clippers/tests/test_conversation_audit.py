"""Regression checks for private, read-only Discord conversation exports."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest

BASE = Path(__file__).resolve().parents[1]


class ConversationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Discord is intentionally not installed in CI; the tests exercise the
        # pure redactor and inspect the export path without using credentials.
        sys.modules.setdefault("discord", types.ModuleType("discord"))
        spec = importlib.util.spec_from_file_location(
            "gm_conversation_audit_for_test", BASE / "conversation_audit.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.mod = mod

    def test_exporter_compiles(self):
        compile((BASE / "conversation_audit.py").read_text(encoding="utf-8"),
                "conversation_audit.py", "exec")

    def test_redacts_credentials_and_emails(self):
        x = self.mod.sanitize_message(
            "Bonjour\n"
            "mon mdp: superprivate!\n"
            "email gaetan@example.com\n"
            "le code Instagram 582944\n"
            "visite https://example.com/?token=dont-share\n")
        self.assertNotIn("superprivate", x)
        self.assertNotIn("gaetan@example", x)
        self.assertNotIn("582944", x)
        self.assertNotIn("dont-share", x)
        self.assertIn("MASQU", x)

    def test_conversational_text_is_preserved(self):
        x = self.mod.sanitize_message("Quand publier mon Reel ?\nMon compte privé est prêt.")
        self.assertIn("Quand publier mon Reel", x)
        self.assertIn("Mon compte privé est prêt", x)

    def test_export_only_dm_and_never_posts_archive_to_channel(self):
        tree = ast.parse((BASE / "conversation_audit.py").read_text(encoding="utf-8"))
        node = next(x for x in tree.body
                    if isinstance(x, ast.AsyncFunctionDef)
                    and x.name == "export_to_admin_dm")
        code = ast.unparse(node)
        self.assertIn("message.author.send", code)
        self.assertNotIn("channel.send", code)
        self.assertNotIn("message.channel.send", code)
        self.assertIn("MAX_MESSAGES_PER_CHANNEL", code)


if __name__ == "__main__":
    unittest.main()
