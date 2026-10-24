"""Remise fictive du premier pseudo sans attestation ni création Instagram."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parcours as p
import process_adapters
from process_store import Store


class PremierPseudo(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'fictif.sqlite3')
        self.store.reconcile('42', [], 'historique-fictif')
        self.etat = {'42': {'creatrice': 'Fictive', 'dates': {}, 'messages': {}}}
        self.membre = N(id=42, mention='<@42>')
        self.salon = N(id=99, guild=None, send=AsyncMock(return_value=N(id=123)))
        def ecrire(d): self.etat = deepcopy(d)
        patches = [patch.object(process_adapters, 'store', return_value=self.store),
            patch.multiple(p, _lire=lambda:deepcopy(self.etat), _ecrire=ecrire, _deps={},
                _ligne_du_compte=AsyncMock(return_value=True),
                _comptes_ordonnes=lambda *a, **kw:['pseudo_fictif', 'autre_fictif'],
                _contexte=AsyncMock(return_value={'compte1':'incorrect_fictif', 'mdp1':'SECRET_FICTIF'}),
                _vue=lambda *a:None, _retirer_pret=AsyncMock()),
            patch.dict(p.onboarding._deps, {'FICHIER_ONBOARDING':Path(self.tmp.name)/'onboarding.json', 'lire_json':lambda *a:{}})]
        for patcher in patches: patcher.start(); self.addCleanup(patcher.stop)

    async def test_pseudo_propose_sans_preuve_sans_creation_et_sans_doublon(self):
        self.assertTrue(await p.envoyer_etape(self.salon, self.membre, 1))
        self.assertTrue(await p.envoyer_etape(self.salon, self.membre, 1))
        self.salon.send.assert_awaited_once()
        texte = self.salon.send.call_args.args[0]
        self.assertIn('@pseudo_fictif', texte)
        self.assertIn('Étape 1 · Ton compte 1', texte)
        self.assertIn('remis ici par le propriétaire', texte)
        self.assertNotIn('Pseudo proposé', texte)
        self.assertNotIn('Crée un seul', texte)
        self.assertTrue(texte.startswith('<@42>\n\n'))
        self.assertNotIn('SECRET_FICTIF', texte)
        self.assertNotIn('incorrect_fictif', texte)
        self.assertNotIn('1_fait', self.etat['42']['dates'])
        with self.store.transaction() as db:
            self.assertEqual([('reserved', None)], db.execute('SELECT status,evidence FROM accounts').fetchall())

    async def test_compte_ancien_ambigu_ou_autre_proprietaire_refuse(self):
        for status, uid in [('created', '42'), ('unknown', '42'), ('reserved', '43')]:
            with self.subTest(status=status, uid=uid):
                self.store.reconcile(uid, [{'aliases':['pseudo_fictif'], 'status':status}], 'fictif')
                self.assertFalse(await p.envoyer_etape(self.salon, self.membre, 1))
                self.salon.send.assert_not_awaited()
                with self.store.transaction() as db:
                    db.execute('DELETE FROM aliases'); db.execute('DELETE FROM accounts')

    async def test_quatrieme_identite_refusee(self):
        self.store.reserve('42', ['fictif_a', 'fictif_b', 'fictif_c'])
        self.assertFalse(await p.envoyer_etape(self.salon, self.membre, 1))
        self.salon.send.assert_not_awaited()

    async def test_compte2_garde_palier_reels_sans_preuve_de_disponibilite(self):
        # 24/10 (Gaëtan, « GO ») : la preuve que l'@ est libre n'est plus exigée ; le palier de Reels de l'ancien parcours reste
        # sous PARCOURS_SIMPLE_TOUS=0 (24/10 : par défaut, le compte 2 part sans Reels, 48 h après le compte 1).
        with patch.object(p, 'SIMPLE_POUR_TOUS', False):
            self.assertFalse(await p.envoyer_etape(self.salon, self.membre, 2))
            self.salon.send.assert_not_awaited()
            with patch.object(p, 'reels_pour', return_value=4):
                self.assertTrue(await p.envoyer_etape(self.salon, self.membre, 2))
        self.salon.send.assert_awaited()
        self.assertNotIn('SECRET_FICTIF', self.salon.send.call_args.args[0])
