"""Régressions de coût et de fidélité, sans appel Apify réel."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache_apify import CacheCollecte
from historique_instagram import HistoriqueReleves
import etats_comptes as etats
import series

T = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)

def mesure():
    return {'lu': True, 'existe': True, 'followers': 100, 'serie_reels': [], 'reels_7j': 1}

class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_panne_refroidissement_sans_relecture_payante(self):
        cache = CacheCollecte()
        collecter = AsyncMock(return_value=None)
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T)
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T + timedelta(minutes=1))
        self.assertEqual(collecter.await_count, 1)
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T + timedelta(minutes=5))
        self.assertEqual(collecter.await_count, 2)

    async def test_chevauchement_simultane_ne_paie_chaque_compte_qu_une_fois(self):
        cache, demandes = CacheCollecte(), []
        async def collecter(cles):
            demandes.extend(cles)
            await asyncio.sleep(0)
            return {c: mesure() for c in cles}
        a, b = await asyncio.gather(cache.obtenir(['fiche_a', 'fiche_b'], 3, 'jour', collecter),
                                    cache.obtenir(['fiche_b', 'fiche_c'], 3, 'jour', collecter))
        self.assertEqual(demandes, ['fiche_a', 'fiche_b', 'fiche_c'])
        self.assertTrue(b['fiche_b']['cache_apify'])
        self.assertEqual(a['fiche_b']['collecte_iso'], b['fiche_b']['collecte_iso'])
        b['fiche_b']['followers'] = 999
        c = await cache.obtenir(['fiche_b'], 0, 'jour', collecter)
        self.assertEqual(c['fiche_b']['followers'], 100)

    async def test_ttl_scope_jour_et_forcage(self):
        cache, appels = CacheCollecte(), []
        async def collecter(cles):
            appels.append(cles)
            return {c: mesure() for c in cles}
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T)
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T + timedelta(minutes=1))
        self.assertEqual(len(appels), 1)
        await cache.obtenir(['fiche_a'], 10, 'jour', collecter, maintenant=T + timedelta(minutes=2))
        await cache.obtenir(['fiche_a'], 3, 'jour', collecter, maintenant=T + timedelta(minutes=3))
        self.assertEqual(len(appels), 2)
        await cache.obtenir(['fiche_a'], 3, 'autre-jour', collecter, maintenant=T + timedelta(minutes=4))
        await cache.obtenir(['fiche_a'], 3, 'autre-jour', collecter, maintenant=T + timedelta(minutes=19))
        await cache.obtenir(['fiche_a'], 3, 'autre-jour', collecter, forcer=True, maintenant=T + timedelta(minutes=20))
        self.assertEqual(len(appels), 5)

    async def test_introuvables_et_echecs_ne_sont_pas_mis_en_cache(self):
        cache = CacheCollecte()
        collecter = AsyncMock(return_value={'fiche_a': {'lu': True, 'existe': False}})
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T)
        await cache.obtenir(['fiche_a'], 0, 'jour', collecter, maintenant=T)
        self.assertEqual(collecter.await_count, 2)
        collecter.return_value = None
        self.assertIsNone(await cache.obtenir(['fiche_b'], 0, 'jour', collecter, maintenant=T))

    async def test_cache_persistant_et_horodatage_intact(self):
        donnees = {}
        def lire(_f, _d): return json.loads(json.dumps(donnees))
        def ecrire(_f, d): donnees.clear(); donnees.update(d)
        collecter = AsyncMock(return_value={'fiche_a': mesure()})
        await CacheCollecte(lire, ecrire, 'cache').obtenir(['fiche_a'], 3, 'jour', collecter, maintenant=T)
        r = await CacheCollecte(lire, ecrire, 'cache').obtenir(['fiche_a'], 3, 'jour', collecter, maintenant=T)
        self.assertEqual(collecter.await_count, 1)
        self.assertEqual(r['fiche_a']['collecte_iso'], T.isoformat(timespec='seconds'))

    async def test_scanner_cache_et_date_origine_dans_series(self):
        collecter = AsyncMock(return_value={'fiche_a': mesure()})
        with patch.object(etats, '_cache_collecte', CacheCollecte()), patch.object(etats, '_historique_releves', None), \
             patch.object(etats, '_scanner_sans_cache', collecter):
            a = await etats.scanner(['@fiche_a', 'fiche_a'])
            b = await etats.scanner(['fiche_a'])
            self.assertEqual(collecter.await_count, 1)
            self.assertEqual(a['fiche_a']['collecte_iso'], b['fiche_a']['collecte_iso'])
            sauvegarder = Mock(return_value=1)
            with patch.object(series, 'ajouter_releves', sauvegarder):
                etats._alimenter_series([{'handle': 'fiche_a'}], b, set(), 'nouvelle-date')
            self.assertEqual(sauvegarder.call_args.args[0][0]['releve']['t'], a['fiche_a']['collecte_iso'])

class HistoriqueTests(unittest.TestCase):
    def test_archive_durable_idempotente_sans_bio_ni_cle(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'historique.sqlite'
            m = dict(mesure(), collecte_iso=T.isoformat(), bio='donnee-a-exclure', token='secret-a-exclure')
            HistoriqueReleves(p).enregistrer({'fiche_a': m})
            HistoriqueReleves(p).enregistrer({'fiche_a': m, 'fiche_b': {'lu': False}})
            with sqlite3.connect(p) as c:
                rows = c.execute('SELECT mesure FROM releves').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertNotIn('donnee-a-exclure', rows[0][0])
            self.assertNotIn('secret-a-exclure', rows[0][0])
            self.assertEqual(json.loads(rows[0][0])['followers'], 100)

    def test_retention_90_jours_et_points_quotidiens(self):
        old = T - timedelta(days=90)
        reel = {'publie': old.isoformat(), 'vues': [[(old + timedelta(days=i)).isoformat(), i*10] for i in range(91)]}
        d = {'comptes': {'fiche_a': {'releves': [{'t': old.isoformat()}], 'reels': {'code_test': reel}}}, 'alias': {}}
        series._purger(d, maintenant=T)
        self.assertEqual(len(d['comptes']['fiche_a']['reels']['code_test']['vues']), 91)
        self.assertEqual(len(d['comptes']['fiche_a']['releves']), 1)
        series._purger(d, maintenant=T + timedelta(days=11))
        self.assertNotIn('fiche_a', d['comptes'])

class Reponse:
    def __init__(self, status, contenu=None): self.status, self.contenu = status, contenu
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def json(self): return self.contenu

class Session:
    def __init__(self, reponse): self.reponse, self.appels = reponse, 0
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def post(self, *args, **kwargs): self.appels += 1; return self.reponse

class BudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_refus_acces_arrete_les_lots_et_libere_reservation(self):
        s = Session(Reponse(403))
        with patch.object(etats.aiohttp, 'ClientSession', return_value=s), \
             patch.object(etats, 'garde_apify', AsyncMock(return_value='reservation')), \
             patch.object(etats, 'noter_depense') as noter, patch.object(etats, 'liberer_reservation') as liberer:
            self.assertIsNone(await etats._apify(['fiche_'+str(i) for i in range(250)]))
        self.assertEqual(s.appels, 1)
        noter.assert_not_called()
        liberer.assert_called_once_with('reservation')
        self.assertEqual(len(etats._derniers_echecs), 250)

    async def test_timeout_reels_ne_devient_pas_depense_zero(self):
        s = Session(Reponse(408))
        with patch.object(etats, 'APIFY_TOKEN', 'test-sans-reseau'), patch.object(etats, '_deps', {}), \
             patch.object(etats.aiohttp, 'ClientSession', return_value=s), \
             patch.object(etats, 'garde_apify', AsyncMock(return_value='reservation')), \
             patch.object(etats, 'noter_depense') as noter:
            await etats._completer_reels([{'username':'fiche_a'}], 'matin')
        self.assertGreater(noter.call_args.args[0], 0)
        self.assertEqual(noter.call_args.kwargs['reservation'], 'reservation')

    async def test_lot_en_echec_n_est_pas_relance_par_scanner(self):
        calls = []
        async def apify(cles, refuses, priorite):
            calls.append(cles)
            etats._derniers_echecs.clear()
            etats._derniers_echecs.add('fiche_b')
            return [{'username':'fiche_a', 'followersCount':1, 'postsCount':0, 'latestPosts':[]}]
        with patch.object(etats, 'APIFY_TOKEN', 'test-sans-reseau'), patch.object(etats, '_deps', {}), \
             patch.object(etats, 'garde_apify', AsyncMock(return_value=True)), patch.object(etats, '_apify', apify):
            r = await etats._scanner_sans_cache(['fiche_a','fiche_b'])
        self.assertEqual(len(calls), 1)
        self.assertFalse(r['fiche_b']['lu'])

if __name__ == '__main__': unittest.main()
