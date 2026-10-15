"""Scénarios fictifs : disque temporaire, aucun connecteur ni droit réel."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_store import Store, Bloque
from process_liens import preparer, depart
from process_clippeur import pseudo_disponible


class TransactionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'process.sqlite3'
        self.store = Store(self.path)

    def test_historique_absent_ne_vaut_pas_zero(self):
        with self.assertRaisesRegex(Bloque, 'non rapproché'):
            self.store.reserve('42', ['test.a'])
        self.assertEqual({}, self.store.counts('42'))

    def test_reservation_creation_rejeu_annulation_depart(self):
        s = self.store
        s.reconcile('42', [], 'revue-fictive-complete')
        s.reserve('42', ['a', 'b', 'c'])
        self.assertEqual({'reserved': 3}, s.counts('42'))
        s.created('42', 'a', 'confirmation-fictive')
        s.created('42', 'a', 'confirmation-fictive')
        self.assertEqual({'created': 1, 'reserved': 2}, s.counts('42'))
        with self.assertRaises(Bloque):
            s.reserve('42', ['d'])
        with self.assertRaises(Bloque):
            s.cancel('42', 'a', 'ban ne vaut pas non-creation')
        with self.assertRaises(Bloque):
            s.cancel('42', 'b', '')
        s.cancel('42', 'b', 'preuve-fictive-non-creation')
        s.reserve('42', ['d'])
        s.created('42', 'c', 'confirmation-fictive')
        s.created('42', 'd', 'confirmation-fictive')
        s.put('sortie:42', {'phase': 'termine'})
        self.assertEqual(3, s.counts('42')['created'])
        with self.assertRaises(Bloque):
            s.reserve('42', ['e'])
        s.reconcile('42', [], 'nouvelle-revue-ne-supprime-rien')
        self.assertEqual(3, s.counts('42')['created'])

    def test_deux_connexions_concurrentes_reservent_une_seule_place(self):
        self.store.reconcile('42', [], 'fictif')
        self.store.reconcile('43', [], 'fictif')
        def reserve(uid):
            try:
                Store(self.path).reserve(uid, ['meme.pseudo'])
                return True
            except Bloque:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(1, sum(pool.map(reserve, ['42', '43'])))

    def test_course_quatrieme_place_et_lot_atomique(self):
        self.store.reconcile('42', [], 'fictif')
        self.store.reserve('42', ['a', 'b'])
        def reserve(h):
            try:
                Store(self.path).reserve('42', [h])
                return True
            except Bloque:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(1, sum(pool.map(reserve, ['c', 'd'])))
        self.assertEqual({'reserved': 3}, self.store.counts('42'))
        with self.assertRaises(Bloque):
            self.store.reserve('42', ['e', 'f'])
        self.assertEqual({'reserved': 3}, self.store.counts('42'))

    def test_renommage_et_interdiction_de_reemploi(self):
        s = self.store
        s.reconcile('42', [], 'fictif')
        s.reconcile('43', [], 'fictif')
        s.reserve('42', ['a'])
        s.rename('42', 'a', 'nouveau')
        s.created('42', 'nouveau', 'preuve')
        self.assertEqual({'created': 1}, s.counts('42'))
        for h in ('a', 'nouveau'):
            with self.assertRaises(Bloque):
                s.reserve('43', [h])

    def test_verrou_fichier_et_destinations_atomiques(self):
        with self.store.lock('operation'):
            with self.assertRaises(Bloque):
                with Store(self.path).lock('operation'):
                    pass
        self.store.claim('42', [('mym', 'm1'), ('of', 'o1')])
        with self.assertRaises(Bloque):
            self.store.claim('43', [('mym', 'm2'), ('of', 'o1')])
        self.assertIsNone(self.store.resource_owner('mym', 'm2'))

    def test_disponibilite_exige_preuve_reelle_recente(self):
        now = datetime.now(timezone.utc)
        base = {'disponible': True, 'date': now.isoformat(), 'source': 'instagram_formulaire',
                'reference': 'preuve-fictive', 'verifie_par': 'operateur-fictif'}
        self.assertTrue(pseudo_disponible(base, now))
        self.assertFalse(pseudo_disponible({'existe': False}, now))
        self.assertFalse(pseudo_disponible({**base, 'source': 'apify'}, now))
        self.assertFalse(pseudo_disponible({**base, 'date': (now-timedelta(days=2)).isoformat()}, now))
        self.assertFalse(pseudo_disponible({**base, 'date': (now+timedelta(days=1)).isoformat()}, now))


class FakeLiens:
    def __init__(self):
        self.clones = 0
        self.cartes = {}
        self.fail_of = False
        self.fail_clone = False
        self.fail_mark = False
        self.complete = True

    async def capacite(self, cr):
        return {'modele': 'modele-fictif', 'mym': 'mym-fictif', 'of': 'of-fictif'}

    async def preparer_clone(self, modele):
        pass

    async def cloner(self, modele):
        self.clones += 1
        if self.fail_clone:
            raise TimeoutError('réponse perdue')
        return {'id': 'clone-fictif', 'url': 'https://example.invalid/lien'}

    async def configurer(self, lid, uid):
        pass

    async def poser(self, lid, kind, value):
        if kind == 'of' and self.fail_of:
            raise RuntimeError('OF temporairement indisponible')
        self.cartes[kind] = value

    async def verifier(self, job):
        return self.complete and self.cartes == {'mym': job['mym'], 'of': job['of']}

    async def marquer_capacite(self, job):
        if self.fail_mark:
            raise RuntimeError('Sheets indisponible')


class FluxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'process.sqlite3')

    async def test_reprise_of_et_marqueur_sheets_sans_nouveau_clone(self):
        api = FakeLiens()
        api.fail_of = True
        with self.assertRaises(RuntimeError):
            await preparer(self.store, '42', 'Fictive', api)
        self.assertTrue(self.store.get('liens:42:fictive')['mym_pose'])
        api.fail_of, api.fail_mark = False, True
        with self.assertRaises(RuntimeError):
            await preparer(self.store, '42', 'Fictive', api)
        api.fail_mark = False
        job = await preparer(self.store, '42', 'Fictive', api)
        self.assertEqual('pret', job['phase'])
        await preparer(self.store, '42', 'Fictive', api)
        self.assertEqual(1, api.clones)

    async def test_timeout_clone_bloque_les_rejeux_et_conserve_reservation(self):
        api = FakeLiens()
        api.fail_clone = True
        with self.assertRaises(TimeoutError):
            await preparer(self.store, '42', 'Fictive', api)
        api.fail_clone = False
        with self.assertRaisesRegex(Bloque, 'inconnu'):
            await preparer(self.store, '42', 'Fictive', api)
        self.assertEqual(1, api.clones)
        with self.assertRaises(Bloque):
            await preparer(self.store, '43', 'Fictive', api)

    async def test_verification_distante_obligatoire(self):
        api = FakeLiens()
        api.complete = False
        with self.assertRaises(Bloque):
            await preparer(self.store, '42', 'Fictive', api)
        self.assertNotEqual('pret', self.store.get('liens:42:fictive')['phase'])

    async def test_depart_archive_avant_metricool_avant_kick_et_reprise(self):
        calls = []
        class API:
            fail_archive = True
            fail_metricool = True
            async def liens(self, uid): return ['lien-fictif']
            async def archiver_x(self, lid):
                calls.append('X')
                if self.fail_archive: raise RuntimeError('GAML indisponible')
            async def preparer_metricool(self, uid, liens):
                calls.append('Metricool')
                if self.fail_metricool: raise RuntimeError('Sheets indisponible')
            async def exclure(self, uid): calls.append('Discord')
        api = API()
        with self.assertRaises(RuntimeError): await depart(self.store, '42', api)
        self.assertEqual(['X'], calls)
        api.fail_archive = False
        with self.assertRaises(RuntimeError): await depart(self.store, '42', api)
        self.assertNotIn('Discord', calls)
        api.fail_metricool = False
        await depart(self.store, '42', api)
        await depart(self.store, '42', api)
        self.assertEqual(1, calls.count('Discord'))
        self.assertEqual(['X', 'Metricool', 'Discord'], calls[-3:])

    async def test_drive_aucun_partage_nouveau(self):
        import onboarding
        with patch.object(onboarding.google_api, 'drive_partages', AsyncMock(return_value=[])), \
             patch.object(onboarding.google_api, 'drive_partager_public', AsyncMock(side_effect=AssertionError('partage interdit'))):
            self.assertFalse(await onboarding._ouvert_par_lien('dossier-fictif'))
