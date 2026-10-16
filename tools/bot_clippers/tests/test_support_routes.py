import ast
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock
ROOT=Path(__file__).resolve().parents[1]

def extraire(nom,ns):
    tree=ast.parse((ROOT/'bot_discord.py').read_text())
    fn=next(x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==nom)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'route-fictive','exec'),ns)
    return ns[nom]

class RoutesTests(unittest.IsolatedAsyncioTestCase):
    async def test_support_interdit_hors_admin_ne_lit_ni_envoie_rien(self):
        f=extraire('commande_admin',{'COMMANDES_RETIREES':{},'ADMIN_IDS':{'42'}})
        m=N(author=N(id=99,send=AsyncMock()),reply=AsyncMock())
        self.assertTrue(await f(m,'!support 123'))
        m.author.send.assert_not_awaited();m.reply.assert_not_awaited()
    def test_faute_propose_commande_sans_arguments_sensibles(self):
        f=extraire('suggestion_commande',{})
        s=f('!mesclcis VALEUR-FICTIVE-A-NE-PAS-REPRENDRE')
        self.assertIn('!mesclics',s);self.assertNotIn('VALEUR',s)

class EscaladeIATests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmation_depend_du_resultat_reel(self):
        for transmis in (False,True):
            signal=AsyncMock(return_value=transmis)
            f=extraire('reponse_escalade_verifiee',{'signaler_escalade':signal})
            texte=await f(N(),'question fictive')
            signal.assert_awaited_once()
            self.assertEqual(transmis,'est signalée' in texte)
            self.assertEqual(not transmis,'n’est pas confirmée' in texte)
    async def test_escalade_ia_utilise_ticket_et_ne_copie_pas_question(self):
        signal=AsyncMock(return_value={'statut':'a_envoyer'})
        f=extraire('signaler_escalade',{'signaler_support':signal,'normaliser':str.lower})
        self.assertFalse(await f(N(),'EXEMPLE-SECRET-FICTIF'))
        self.assertNotIn('EXEMPLE',signal.call_args.args[1])
    async def test_route_suivi_enregistre_piece_meme_sans_motif(self):
        import re
        suivi=N(ajouter_suivi=__import__('unittest.mock',fromlist=['Mock']).Mock())
        notifier=AsyncMock()
        f=extraire('alerter_admin_salon',{'support_suivi':suivi,'FICHIER_SUPPORT':'fictif','MOTIFS_ALERTE':[('suspendu',re.compile('suspendu'))],'signaler_support':notifier})
        m=N(author=N(id=42),guild=N(id=1),channel=N(id=2),id=4,attachments=[N()])
        self.assertFalse(await f(m,'Voici la capture demandée'))
        suivi.ajouter_suivi.assert_called_once_with('fictif','42',1,2,4,1)
        notifier.assert_not_awaited()
    def test_variantes_de_confirmation_ia_passent_par_le_controle(self):
        import re,unicodedata
        def norm(t):return ''.join(c for c in unicodedata.normalize('NFD',t.lower()) if unicodedata.category(c)!='Mn')
        f=extraire('est_escalade',{'normaliser':norm,'MESSAGE_ESCALADE':'message canonique fictif','re':re})
        for texte in ['J’ai transmis le problème à ton équipe.','Ton équipe est prévenue.','Je signale ce blocage au manager.', 'J’ai informé l’équipe de ton problème', 'J’ai alerté le manager', 'Le manager a été informé.', 'Ton équipe a été alertée.', 'J’ai envoyé un message\nau responsable.']:
            self.assertTrue(f(texte))
        self.assertFalse(f('Publie les Reels après vérification.'))
