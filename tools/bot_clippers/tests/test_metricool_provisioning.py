import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metricool_onboarding as m


class Api:
    uid = "7"

    def __init__(self, total=19, uncertain=False):
        self.items = [{"id": i+1, "ownerUserId": 7, "label": f"Existing {i}"} for i in range(total)]
        self.creates = 0
        self.uncertain = uncertain

    async def brands(self):
        return list(self.items)

    async def capacity(self):
        return 25

    async def call(self, method, route, brand=None, **kwargs):
        if route == "v2/settings/brands":
            self.creates += 1
            if self.uncertain:
                raise TimeoutError("unknown outcome")
            self.items.append({"id": 100, "ownerUserId": 7, "label": "created"})
            return self.items[-1]
        return {"link": "https://mtr.cool/test", "expiresAt": {"dateTime": "2099-10-17T10:00:00", "timezone": "Europe/Paris"}}


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_creation_owned_and_idempotent(self):
        api = Api()
        state = {}
        row = ["", "clipper", "1", "talent"]
        now = datetime.now(timezone.utc)
        out = await m.provision(api, row, state, lambda: None, now)
        self.assertEqual(["prêt", "100", "oui", "oui", "20"], out[:5])
        await m.provision(api, row, state, lambda: None, now)
        self.assertEqual(1, api.creates)

    async def test_capacity_never_creates_26th(self):
        api = Api(25)
        with self.assertRaisesRegex(RuntimeError, "plafond"):
            await m.provision(api, ["", "clipper", "1", "talent"], {}, lambda: None, datetime.now(timezone.utc))
        self.assertEqual(0, api.creates)

    async def test_uncertain_creation_is_not_retried(self):
        api = Api(uncertain=True)
        state = {}
        args = (api, ["", "clipper", "1", "talent"], state, lambda: None, datetime.now(timezone.utc))
        with self.assertRaises(TimeoutError):
            await m.provision(*args)
        with self.assertRaisesRegex(RuntimeError, "incertaine"):
            await m.provision(*args)
        self.assertEqual(1, api.creates)

    async def test_existing_instagram_reuses_brand(self):
        api = Api(25)
        api.items[0]["networksData"] = {"instagramData": "talent"}
        out = await m.provision(api, ["", "clipper", "1", "talent"], {}, lambda: None, datetime.now(timezone.utc))
        self.assertEqual("connecté", out[0])
        self.assertEqual(0, api.creates)

    def test_threshold_freshness_and_urls(self):
        now = datetime.now(timezone.utc)
        row = [""]*12
        row[6] = "499"
        row[11] = now.isoformat()
        self.assertFalse(m.eligible(row, now))
        row[6] = "500"
        self.assertTrue(m.eligible(row, now))
        row[11] = (now-timedelta(hours=49)).isoformat()
        self.assertFalse(m.eligible(row, now))
        self.assertTrue(m.url_valide("https://mtr.cool/abc"))
        self.assertFalse(m.url_valide("https://mtr.cool.evil.example/abc"))
