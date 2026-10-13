"""Read-through Gmail tests: no credentials, no Discord activity, no real OTPs."""
from datetime import datetime, timezone, timedelta
import asyncio
import types
import unittest
from test_codes_reliable import load_codes


class OnDemandOtpTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime.now(timezone.utc)
        self.original = {k: getattr(self.c, k) for k in (
            "Lecteur", "classer_mail", "_maintenant")}

    def tearDown(self):
        for k, v in self.original.items():
            setattr(self.c, k, v)

    def _reader(self, returned):
        class Reader:
            closed = False

            def __init__(self):
                self.boite = types.SimpleNamespace(uid=lambda *a: ("OK", [b"1 2 3"]))
            def _connecter(self):
                pass
            def dossiers(self):
                return ["INBOX", "[Gmail]/Tous les messages", "[Gmail]/Spam"]
            def _selectionner(self, dossier):
                self.dossier = dossier
            def _lire(self, dossier, uids, amorce):
                return [{"mid": str(i), "msg": {"id": i}} for i in (1, 2, 3)]
            def fermer(self):
                Reader.closed = True
        self.c.Lecteur = Reader
        self.c._maintenant = lambda: self.now
        self.c.classer_mail = lambda x: returned[x["id"]]
        return Reader

    def test_only_owned_last_ten_minute_signin_or_signup(self):
        mock = {
            1: dict(mid="m1", alias="mine@icloud.com", code="123456",
                    type="connexion", decision="donner", date=self.now,
                    compte="sophie"),
            2: dict(mid="m2", alias="other@icloud.com", code="222222",
                    type="creation", decision="donner", date=self.now,
                    compte="other"),
            3: dict(mid="m3", alias="mine@icloud.com", code="333333",
                    type="connexion", decision="donner",
                    date=self.now - timedelta(minutes=12), compte="sophie"),
        }
        r = self._reader(mock)
        result = self.c._scan_recent_sync({"mine@icloud.com"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "123456")
        self.assertTrue(r.closed)

    def test_rejected_account_change_never_returned(self):
        mock = {
            1: dict(mid="m1", alias="mine@icloud.com", code="111111",
                    type="changement", decision="garder", date=self.now),
            2: dict(mid="m2", alias="mine@icloud.com", code="222222",
                    type="creation", decision="donner", date=self.now),
            3: dict(mid="m3", alias="mine@icloud.com", code="333333",
                    type="connexion", decision="alerte", date=self.now),
        }
        self._reader(mock)
        result = self.c._scan_recent_sync({"mine@icloud.com"}, 10)
        self.assertEqual({x["code"] for x in result}, {"222222"})

    def test_without_account_alias_never_scans_entire_mailbox(self):
        class NoReader:
            def __init__(self):
                raise AssertionError("Unexpected IMAP scan")
        self.c.Lecteur = NoReader
        self.assertEqual(self.c._scan_recent_sync(set()), [])

    def test_direct_request_wakes_existing_wait(self):
        self.c._SCAN_LAST.clear()
        self.c._etat = lambda: {"codes": [], "n": 0}
        messages = []
        async def awaken(): messages.append("wake")
        self.c._reveiller = awaken
        self.c._sauver = lambda: messages.append("save")
        self.c.actif = lambda: True
        self.c._scan_recent_sync = lambda aliases, minutes: [{
            "mid": "new-m", "alias": "mine@icloud.com", "code": "333333",
            "decision": "donner", "type": "connexion", "compte": "",
            "date": self.now.isoformat(),
        }]
        asyncio.run(self.c._scanner_sur_demande({"mine@icloud.com"}, "member-100"))
        self.assertIn("wake", messages)
        self.assertIn("save", messages)


if __name__ == "__main__":
    unittest.main()
