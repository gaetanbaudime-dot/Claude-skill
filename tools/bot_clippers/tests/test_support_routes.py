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
