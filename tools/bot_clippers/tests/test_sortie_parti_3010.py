"""30/10 (audit du parcours) : la sortie déposée d'un clipper parti attend que la paie au clic ait ses dépendances.

Au démarrage, roster.demarrage passait avant paie_clics.boucle : « Sortie déposée de Meiji (parti) : 'lire_json' » à chaque
redémarrage, liens GAML jamais libérés. Fonction extraite de l'AST de production, sans Discord."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def paie_prete(paie):
    arbre = ast.parse((ROOT / "bot_discord.py").read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_paie_prete")
    ns = {"paie_clics": paie, "asyncio": asyncio}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[f], type_ignores=[])), "bot", "exec"), ns)
    return ns["_paie_prete"]


class PaiePreteTests(unittest.IsolatedAsyncioTestCase):
    async def test_attend_les_dependances_de_la_paie(self):
        paie = SimpleNamespace(actif=lambda: True, _deps={})

        async def boucle_de_paie():
            await asyncio.sleep(1.2)
            paie._deps["lire_json"] = lambda f, d: d
        tache = asyncio.create_task(boucle_de_paie())
        self.assertTrue(await paie_prete(paie)(attente_s=5))
        await tache

    async def test_paie_jamais_prete_la_sortie_attend(self):
        paie = SimpleNamespace(actif=lambda: True, _deps={})
        self.assertFalse(await paie_prete(paie)(attente_s=0))

    async def test_sans_paie_au_clic_rien_a_attendre(self):
        paie = SimpleNamespace(actif=lambda: False, _deps={})
        self.assertTrue(await paie_prete(paie)(attente_s=0))

    def test_la_sortie_du_parti_verifie_avant_de_chercher(self):
        source = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        debut = source.index("async def sortir_parti(")
        corps = source[debut:source.index("\ndef ", debut)]
        self.assertLess(corps.index("await _paie_prete()"), corps.index("uid_parti("))


if __name__ == "__main__":
    unittest.main()
