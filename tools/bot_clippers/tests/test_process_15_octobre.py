"""Tests synthétiques hors réseau du processus confirmé le 15 octobre."""
import ast
import __future__
import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import process_clippeur as regles


def fonctions(fichier, noms, ns):
    arbre = ast.parse((ROOT / fichier).read_text())
    noeuds = [n for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in noms]
    exec(compile(ast.Module(body=noeuds, type_ignores=[]), fichier, 'exec', flags=__future__.annotations.compiler_flag), ns)
    return ns


class ProcessTests(unittest.TestCase):
    def test_quota_rejeu_depart_et_retour(self):
        d = {'clippers': {'42': {'comptes': ['a', 'b', 'c']}}}
        avant = deepcopy(regles.reserver_identites(d, '42', ['a', 'b', 'c']))
        d['clippers'].clear()
        self.assertEqual(avant, regles.reserver_identites(d, '42', ['a']))
        with self.assertRaises(RuntimeError):
            regles.reserver_identites(d, '42', ['d'])
        with self.assertRaises(RuntimeError):
            regles.reserver_identites(d, '43', ['a'])

    def test_renommage_garde_identite_et_quota(self):
        d = {'clippers': {'42': {'comptes': ['a', 'b', 'c']}}}
        avant = regles.registre(d, '42')[0]['id']
        d['clippers']['42']['renommes'] = [{'ancien': 'a', 'nouveau': 'z'}]
        regles.registre(d, '42')
        self.assertEqual(avant, regles.reserver_identites(d, '42', ['z'])[0]['id'])
        self.assertEqual(3, len(d['comptes_a_vie']['42']))

    def test_absence_et_retour_ne_prouvent_pas_sante_ou_propriete(self):
        ns = fonctions('etats_comptes.py', ['decider'], {'_norm': str.lower, 'WARMUP_ACTIF': False})
        for etat in ('GOOD', 'PRIVE', 'BAN', 'À créer', 'Faire appel'):
            for existe in (True, False):
                self.assertEqual('', ns['decider'](etat, {'existe': existe}, [{'existe': False}] * 100, True))

    def test_paliers_comptes_distincts_et_reels_uniques(self):
        ns = fonctions('parcours.py', ['sources_reels', 'reels_detail', 'reels_pour'], {
            'process_clippeur': regles, 'datetime': datetime, 'timezone': timezone,
            '_date_creation': lambda f, n: datetime(2026, 10, 1, tzinfo=timezone.utc),
            'ordre': lambda f: f.get('ordre', 'prive3'),
            '_comptes_ordonnes': lambda uid, fiche_p: ['a', 'b', 'c']})
        f = {'reels': {'a': {'vus': 99, 'reels_verifies_v2': dict.fromkeys('1234', '2026-10-02T12:00:00Z')},
                       'b': {'vus': 99, 'reels_verifies_v2': dict.fromkeys('123', '2026-10-02T12:00:00Z')}}}
        self.assertEqual(4, ns['reels_pour']('42', f, 2))
        self.assertEqual(3, ns['reels_pour']('42', f, 3))
        f['reels']['b']['reels_verifies_v2']['4'] = '2026-10-02T12:00:00Z'
        f['reels']['a'] = {'vus': 0}
        self.assertEqual(4, ns['reels_pour']('42', f, 3))
        f['ordre'] = 'prive2'
        self.assertEqual(0, ns['reels_pour']('42', f, 3))

    def test_ancien_delai_ne_retarde_pas_le_palier(self):
        ns = fonctions('parcours.py', ['_a_traiter'], {})
        self.assertTrue(ns['_a_traiter']({}, {'type': 'etape', 'n': 3, 'quand': '2099-01-01'}, None))

    def test_remplacement_sans_aucun_effet(self):
        ns = fonctions('remplacements.py', ['remplacer'], {})
        self.assertIn('interdit', asyncio.run(ns['remplacer']('Fictif', 'Fictive')))

    def test_publications_rejouees_anciennes_futures_et_sans_date(self):
        debut = datetime(2026, 10, 1, tzinfo=timezone.utc)
        maintenant = datetime(2026, 10, 15, tzinfo=timezone.utc)
        preuves = [{'code': 'r1', 'publie': '2026-10-02T12:00:00+00:00'},
                   {'code': 'ancien', 'publie': '2026-09-01T12:00:00+00:00'},
                   {'code': 'futur', 'publie': '2099-01-01T12:00:00+00:00'},
                   {'code': 'inconnu', 'publie': None}]
        une = regles.cumuler_publications({}, preuves, debut, maintenant)
        deux = regles.cumuler_publications({'publications_verifiees': une}, preuves, debut, maintenant)
        self.assertEqual({'r1'}, set(deux))
        self.assertEqual(une, deux)

    def test_mail_suspension_doit_etre_date_et_qualifie(self):
        import email.utils
        from email.header import make_header, decode_header
        import re
        from types import SimpleNamespace
        ns = fonctions('bans_mail.py', ['extraire'], {
            'codes_2fa': SimpleNamespace(expediteur_meta=lambda _: True, relais_accepte=lambda _: True),
            'make_header': make_header, 'decode_header': decode_header,
            '_texte': lambda m: m.get('corps', ''), 'email': email,
            'datetime': datetime, 'timezone': timezone, 'SUJETS_BAN': ('suspended',),
            'MOTS_CORPS': (), 'MOTIF_SUJET_COMPTE': re.compile(r'NEVER(.)'),
            'MOTIF_CORPS_COMPTE': re.compile(r'NEVER(.)'), 'MOTIF_ADRESSE': re.compile(r'NEVER(.)')})
        mail = {'Subject': 'Your account is suspended', 'Date': 'Thu, 15 Oct 2026 10:00:00 +0000'}
        for corps, attendu in [('You can appeal this decision', 'appel'),
                               ('Your account is permanently disabled', 'ban_definitif'),
                               ('Account suspended', 'a_verifier')]:
            mail['corps'] = corps
            self.assertEqual(attendu, ns['extraire'](mail)['type'])
        mail.pop('Date')
        self.assertIsNone(ns['extraire'](mail))

    def test_reservation_partielle_concurrente_conserve_intention(self):
        d = {'clippers': {}}
        async def scenario():
            verrou = asyncio.Lock()
            async def reserver(uid, handles, panne=False):
                async with verrou:
                    regles.reserver_identites(d, uid, handles)
                    await asyncio.sleep(0)
                    if panne:
                        raise RuntimeError('Sheets indisponible')
            resultats = await asyncio.gather(reserver('42', ['a', 'b', 'c'], True),
                                             reserver('43', ['a']), return_exceptions=True)
            self.assertTrue(all(isinstance(r, RuntimeError) for r in resultats))
            await reserver('42', ['a', 'b', 'c'])
            with self.assertRaises(RuntimeError):
                await reserver('42', ['d'])
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
