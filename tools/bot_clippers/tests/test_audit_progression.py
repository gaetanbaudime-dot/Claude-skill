"""Rapports synthétiques uniquement : aucun accès Discord ni archive réelle."""
import json
import sys,unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit_complet as audit
from audit_complet import progression

class ProgressionTests(unittest.TestCase):
 def test_salons_complets_ne_masquent_pas_decouverte_restante(self):
  r=progression([{'statut':'complet'}]*50,[{'statut':'complet'}]*21+[{'statut':'a_lire'}]*113,10,100,10,10,False)
  self.assertEqual({'salons':0,'operations_decouverte':113},r['travail_restant'])
  self.assertEqual(['budget_pages_decouverte'],r['raisons_arret'])
  self.assertIn('incomplète',r['instruction'])
 def test_erreur_ou_permissions_absentes_ne_sont_pas_du_travail_termine(self):
  r=progression([{'statut':'illisible'}],[{'statut':'permissions_absentes'}],1,100,1,10,False)
  self.assertEqual({'salons':1,'operations_decouverte':1},r['travail_restant'])
  self.assertIn('decouverte_ou_reprises_restantes',r['raisons_arret'])
 def test_fin_et_budgets_distincts(self):
  r=progression([{'statut':'complet'}],[{'statut':'complet'}],100,100,10,10,False)
  self.assertEqual([],r['raisons_arret'])
  r=progression([{'statut':'a_reprendre'}],[],100,100,0,10,True)
  self.assertEqual(['borne_temps_ou_volume','budget_pages_messages'],r['raisons_arret'])
 def test_borne_atteinte_ne_promet_pas_une_couverture_complete_meme_sans_reliquat(self):
  r=progression([{'statut':'complet'}],[{'statut':'complet'}],1,100,1,10,True)
  self.assertEqual({'salons':0,'operations_decouverte':0},r['travail_restant'])
  self.assertEqual(['borne_temps_ou_volume'],r['raisons_arret'])
  self.assertIn('incomplète',r['instruction'])


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_collecteur_reste_partiel_apres_salons_complets_puis_reprend_sans_rescan(self):
        class Salon:
            id = 123
            def __init__(self): self.appels = 0
            def permissions_for(self, me): return N(view_channel=True, read_message_history=True)
            async def history(self, **kwargs):
                self.appels += 1
                for message in []:
                    yield message
        class Forum:
            def __init__(self, ident): self.id, self.appels = ident, 0
            def permissions_for(self, me): return N(view_channel=True, read_message_history=True)
            async def archived_threads(self, **kwargs):
                self.appels += 1
                for thread in []:
                    yield thread
        # PR53 utilise le même collecteur avec integral=True : les deux modes
        # doivent garder la découverte partielle visible sans changer les budgets.
        for integral in (False, True):
            with self.subTest(integral=integral), tempfile.TemporaryDirectory() as tmp:
                salon, forums = Salon(), [Forum(500), Forum(501)]
                guild = N(id=9, me=N(id=99), channels=[salon, *forums],
                          active_threads=AsyncMock(return_value=[]), get_channel_or_thread=lambda _: None)
                path = Path(tmp) / 'synthese.sqlite3'
                premier = await audit.collecter(guild, path, decouverte_max=1, integral=integral)
                self.assertTrue(all(s['statut'] == 'complet' for s in premier['salons']))
                self.assertFalse(premier['borne_atteinte'])
                self.assertFalse(premier['complet'])
                self.assertEqual({'salons':0,'operations_decouverte':1}, premier['travail_restant'])
                self.assertEqual(['budget_pages_decouverte'], premier['raisons_arret'])
                second = await audit.collecter(guild, path, decouverte_max=1, integral=integral)
                self.assertEqual(premier['avant'], second['avant'])
                self.assertTrue(second['complet'])
                self.assertEqual({'salons':0,'operations_decouverte':0}, second['travail_restant'])
                self.assertEqual([], second['raisons_arret'])
                self.assertEqual(1, salon.appels)
                self.assertEqual([1, 1], [f.appels for f in forums])

    async def test_message_prive_et_json_indiquent_la_decouverte_restante(self):
        rapport = dict(complet=False, **progression(
            [{'statut':'complet'}]*50, [{'statut':'complet'}]*21+[{'statut':'a_lire'}]*113,
            10, 100, 10, 10, False))
        message = N(guild=N(id=9), author=N(send=AsyncMock()))
        with patch.object(audit, 'collecter', AsyncMock(return_value=rapport)) as collecter:
            await audit.commande(message, Path('archive-fictive.sqlite3'))
            collecter.assert_awaited_once_with(message.guild, Path('archive-fictive.sqlite3'))
        dernier = message.author.send.await_args
        self.assertIn('0 salon(s) et 113 opération(s)', dernier.args[0])
        self.assertIn('pour poursuivre les lectures et la découverte', dernier.args[0])
        self.assertNotIn('photographie est terminée', dernier.args[0])
        self.assertEqual('couverture-audit.json', dernier.kwargs['file'].filename)
        self.assertEqual(rapport, json.loads(dernier.kwargs['file'].fp.getvalue()))

    async def test_rapport_termine_ne_demande_pas_de_collecte_supplementaire(self):
        rapport = dict(complet=True, **progression(
            [{'statut':'complet'}], [{'statut':'complet'}], 1, 100, 1, 10, False))
        message = N(guild=N(id=9), author=N(send=AsyncMock()))
        with patch.object(audit, 'collecter', AsyncMock(return_value=rapport)):
            await audit.commande(message, Path('archive-fictive.sqlite3'))
        self.assertIn('photographie est terminée', message.author.send.await_args.args[0])
        self.assertNotIn('Relance', message.author.send.await_args.args[0])
