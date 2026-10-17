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
    def test_auto_discovery_threshold_freshness_changes_and_deduplication(self):
        now = datetime.now(timezone.utc)
        def account(n, followers, stamp=None):
            return ["clipper", "Test", "", str(n), f"talent{n}", "", str(followers), "", "", "", "", stamp or now.isoformat()]
        rows = [account(1, 500), account(2, 499), account(3, 700, (now-timedelta(hours=49)).isoformat())]
        requests = m.nouvelles_demandes(rows, [], [], now)
        self.assertEqual(["talent1"], [r[3] for r in requests])
        self.assertEqual([], m.nouvelles_demandes(rows, requests, [], now))
        self.assertEqual([], m.nouvelles_demandes(rows, [], [["", "clipper", "1", "changed", ""]], now))
        self.assertEqual([], m.nouvelles_demandes(rows + [rows[0]], [], [], now))
        self.assertEqual([], m.nouvelles_demandes(rows, [], [["", "clipper", "1", "changed"]], now))

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

    async def test_file_identite_modifiee_ou_en_attente_sans_effet(self):
        import tempfile
        from unittest.mock import AsyncMock, patch
        import onboarding
        import codes_2fa
        now=datetime.now(timezone.utc).isoformat()
        compte=['cle-fictive','','','1','ancien-fictif','','500','','','','',now]
        demande=['','cle-fictive','1','ancien-fictif','','','demandé','','','oui']
        for changement in ('attente','modifie','lecture_impossible'):
            async def lire(classeur,plage):
                if plage==f"'{m.TAB}'!A2:O":return [demande]
                if plage=="'Comptes app'!A2:L":
                    c=list(compte)
                    if changement=='modifie':c[4]='nouveau-fictif'
                    return [c]
                if changement=='lecture_impossible':raise OSError('lecture fictive impossible')
                return [['','cle-fictive','1','nouveau-fictif','']]
            with tempfile.TemporaryDirectory() as tmp, \
                 patch.dict(m.os.environ,{'DONNEES_DIR':tmp}), \
                 patch.object(m.google_api,'sheets_lire',side_effect=lire), \
                 patch.object(m.google_api,'sheets_ecrire',AsyncMock()) as ecrire, \
                 patch.object(onboarding,'lire_comptes',AsyncMock(return_value=[])), \
                 patch.object(codes_2fa,'_lire',return_value={}), \
                 patch.object(m,'provision',AsyncMock()) as provision:
                await m.traiter('classeur-fictif',[compte])
                provision.assert_not_awaited();ecrire.assert_not_awaited()
                self.assertFalse((Path(tmp)/'metricool_onboarding.json').exists())

    async def test_autoqueue_relit_identite_avant_provisioning(self):
        import tempfile
        from unittest.mock import AsyncMock, patch
        import onboarding
        import codes_2fa
        stamp = datetime.now(timezone.utc).isoformat()
        compte = ['cle-fictive', '', '', '1', 'ancien-fictif', '', '500', '', '', '', '', stamp]
        for cas in ('stable', 'pseudo_tardif', 'identite_modifiee', 'slot_ambigu', 'lecture_impossible'):
            demandes = []
            lectures_pseudos = 0
            async def ajouter(classeur, plage, valeurs):
                demandes.extend(valeurs)
            async def lire(classeur, plage):
                nonlocal lectures_pseudos
                if plage == f"'{m.TAB}'!A2:O":
                    return demandes
                if plage == "'Comptes app'!A2:L":
                    if cas == 'lecture_impossible':
                        raise OSError('lecture fictive impossible')
                    autre = list(compte)
                    autre[4] = 'nouveau-fictif'
                    if cas == 'slot_ambigu':
                        return [compte, autre]
                    return [autre if cas == 'identite_modifiee' else compte]
                lectures_pseudos += 1
                if lectures_pseudos > 1 and cas == 'pseudo_tardif':
                    # Sheets omet les cellules vides en fin de ligne.
                    return [['', 'cle-fictive', '1', 'nouveau-fictif']]
                return []
            with self.subTest(cas=cas), tempfile.TemporaryDirectory() as tmp, \
                 patch.dict(m.os.environ, {'DONNEES_DIR': tmp}), \
                 patch.object(m.google_api, 'sheets_lire', side_effect=lire), \
                 patch.object(m.google_api, 'sheets_ajouter', side_effect=ajouter) as ajout, \
                 patch.object(m.google_api, 'sheets_ecrire', AsyncMock()) as ecrire, \
                 patch.object(onboarding, 'lire_comptes', AsyncMock(return_value=[
                     {'handle': 'ancien-fictif', 'mdp': 'fictif', 'mail': 'test@example.invalid'}])), \
                 patch.object(codes_2fa, '_lire', return_value={'test@example.invalid': {}}), \
                 patch.object(codes_2fa, 'actif', return_value=True), \
                 patch.object(m, 'provision', AsyncMock(return_value=['prêt', 'marque-fictive'])) as provision:
                await m.traiter('classeur-fictif', [compte])
                ajout.assert_awaited_once()
                self.assertEqual(1, len(demandes))
                if cas == 'stable':
                    provision.assert_awaited_once()
                    ecrire.assert_awaited_once()
                else:
                    provision.assert_not_awaited()
                    ecrire.assert_not_awaited()
                self.assertFalse((Path(tmp) / 'metricool_onboarding.json').exists())
