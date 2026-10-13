"""2FA regression tests: safe classification, immutable UID ownership, admin-only fallback.

No Discord connection, Gmail credentials or actual codes are used by this suite.
"""
import ast
import asyncio
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_codes():
    stub = types.ModuleType("discord")
    class DynamicItem:
        @classmethod
        def __class_getitem__(cls, _):
            return cls
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()
    stub.ui = types.SimpleNamespace(DynamicItem=DynamicItem, Button=type("Button", (), {}))
    previous = sys.modules.get("discord")
    sys.modules["discord"] = stub
    try:
        spec = importlib.util.spec_from_file_location("test_gm_codes_v2", ROOT / "codes_2fa.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("discord", None)
        else:
            sys.modules["discord"] = previous


class CodeDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = load_codes()
        cls.code.SECURITES = True

    def test_normal_instagram_login_survives_footer_noise(self):
        c = self.code.classer(
            "Instagram <security@mail.instagram.com>",
            "422902 is your Instagram code",
            "Use this code to log in to your Instagram account: 422902.\n"
            "This email was sent to you by Meta Platforms, Facebook support.",
            )
        self.assertEqual(c["decision"], "donner")
        self.assertEqual(c["code"], "422902")
        self.assertEqual(c["type"], "connexion")

    def test_icloud_instagram_relay_uses_same_logic(self):
        c = self.code.classer(
            "Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>",
            "422902 is your Instagram code",
            "Your Instagram code is 422902. This email was sent to you.")
        self.assertEqual(c["decision"], "donner")

    def test_no_email_change_code(self):
        c = self.code.classer(
            "Instagram <security@mail.instagram.com>",
            "422902 is your Instagram code",
            "Enter 422902 to change the email address on your account.")
        self.assertEqual(c["decision"], "garder")

    def test_no_reset_password_code(self):
        c = self.code.classer(
            "Instagram <security@mail.instagram.com>",
            "422902 is your Instagram code",
            "Enter 422902 to reset your password.")
        self.assertEqual(c["decision"], "garder")

    def test_no_fake_instagram_sender(self):
        c = self.code.classer("Instagram <fraud@example.net>",
                              "422902 is your Instagram code", "Code 422902")
        self.assertNotEqual(c["decision"], "donner")

    def test_no_facebook_code(self):
        c = self.code.classer("Facebook <security@facebookmail.com>",
                              "422902 is your Instagram code", "Code 422902")
        self.assertNotEqual(c["decision"], "donner")

    def test_only_admin_can_see_last_unassigned_code(self):
        now = datetime.now(timezone.utc).isoformat()
        self.code._etat = lambda: {"codes": [
            {"code": "111111", "date": now, "alias": "one@icloud.com", "decision": "donner", "mid": "m1"},
            {"code": "222222", "date": now, "alias": "two@icloud.com", "decision": "garder", "mid": "m2"},
        ]}
        self.code._lire = lambda: {}
        self.assertEqual(self.code.codes_pour(set(), minutes=10), [])
        admin = self.code.codes_pour(set(), minutes=10, tout=True)
        self.assertEqual([c["code"] for c in admin], ["111111"])


class OwnershipTests(unittest.TestCase):
    def _functions(self):
        tree = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ("_adresses_codes_fiche", "adresses_codes_de")]
        ns = {}
        code = compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                       "extract_ownership.py", "exec")
        return ns, code

    def test_same_name_cannot_receive_someone_elses_alias(self):
        ns, code = self._functions()
        records = {
            "clippers": {
                "100": {"comptes": ["sophie.one"], "acces": [{"handle": "sophie.one", "mail": "own@icloud.com"},
                                                              {"handle": "sophie.stolen", "mail": "stolen@icloud.com"}]},
                "200": {"comptes": ["sophie.stolen"], "acces": [{"handle": "sophie.stolen", "mail": "stolen@icloud.com"}]},
            },
            "livres": {"sophie.one": {"uid": "100"}, "sophie.stolen": {"uid": "200"}}
        }
        ns.update(
            lire_json=lambda path, default: records,
            FICHIER_ONBOARDING="mock",
            onboarding=types.SimpleNamespace(_cle_handle=lambda t: str(t or "").strip().lower()),
            membre_par_id=lambda uid: types.SimpleNamespace(id=int(uid), display_name="Sophie"),
            salon_perso_de=lambda uid: types.SimpleNamespace(id="12345"),
            _autres_occupants=lambda salon, user: ["a team leader"],
            codes_2fa=types.SimpleNamespace(_salon_prive=lambda s: False,
                                             signaler=lambda *args: None),
        )
        exec(code, ns)
        own = ns["adresses_codes_de"]("100")
        self.assertEqual(own, {"own@icloud.com"})
        self.assertNotIn("stolen@icloud.com", own)
        self.assertEqual(ns["adresses_codes_de"]("200"), {"stolen@icloud.com"})

    def test_no_fallback_for_shared_channel_without_verified_uid(self):
        ns, code = self._functions()
        ns.update(
            lire_json=lambda path, default: {"clippers": {}}, FICHIER_ONBOARDING="mock",
            onboarding=types.SimpleNamespace(_cle_handle=lambda t: str(t or "").lower()),
            membre_par_id=lambda uid: types.SimpleNamespace(id=int(uid), display_name="No fiche"),
            salon_perso_de=lambda uid: types.SimpleNamespace(id="12345"),
            _autres_occupants=lambda salon, user: ["TL"],
            codes_2fa=types.SimpleNamespace(_salon_prive=lambda s: False,
                                             signaler=lambda *args: None,
                                             adresses_de=lambda sid: {"someone-else@icloud.com"}),
        )
        exec(code, ns)
        self.assertEqual(ns["adresses_codes_de"]("100"), set())


if __name__ == "__main__":
    unittest.main()
