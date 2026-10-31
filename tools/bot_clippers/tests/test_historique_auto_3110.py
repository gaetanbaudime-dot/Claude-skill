"""31/10 (Gaëtan : « Gère le problème entre le compte un et les comptes deux et trois… ils n'ont pas le lien ») : au passage de 8 h,
un compte 3, un lien et une création restaient retenus en boucle par « Historique à vie non rapproché ». La décision du 24/10
(reprise d'après ce que le bot connaît) vaut maintenant pour eux, une fois toutes les 6 h. Cas fictifs, sans réseau."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboarding
import parcours


class RepriseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.d = {"42": {"prenom": "Fictive", "etape": 3}}

        def ecrire(d):
            self.d = deepcopy(d)
        self.reprendre = MagicMock(return_value=True)
        for patcher in (patch.object(parcours, "_lire", side_effect=lambda: deepcopy(self.d)),
                        patch.object(parcours, "_ecrire", side_effect=ecrire),
                        patch.object(parcours, "_reprendre_historique", self.reprendre),
                        patch.object(onboarding, "lire_comptes", AsyncMock(return_value=[{"handle": "un.fictif", "etat": "GOOD"}]))):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_seulement_pour_le_registre_et_une_fois_toutes_les_6_h(self):
        self.assertFalse(await parcours.reprise_si_historique("42", "Fictive", RuntimeError("Plus de ligne libre"), "le compte 3"))
        self.reprendre.assert_not_called()
        ok = await parcours.reprise_si_historique("42", "Fictive",
                                                  RuntimeError("Historique à vie non rapproché : allocation bloquée"), "le compte 3")
        self.assertTrue(ok)
        self.assertEqual("regle-gaetan-31/10-comptes-2-3-lien", self.reprendre.call_args.kwargs["source"])
        self.assertIn("un.fictif", self.reprendre.call_args.args[2])
        # pas en boucle : la suivante attend 6 h
        self.assertFalse(await parcours.reprise_si_historique("42", "Fictive",
                                                              RuntimeError("Historique à vie non rapproché"), "le lien"))
        self.assertEqual(1, self.reprendre.call_count)
        self.d["42"]["reprise_auto"] = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
        self.assertTrue(await parcours.reprise_si_historique("42", "Fictive",
                                                             RuntimeError("Création sans réservation valide"), "le lien"))


class ClasseurEtatTests(unittest.IsolatedAsyncioTestCase):
    async def _jouer(self, registre, reprise=False):
        marquer = AsyncMock()
        with patch.dict(parcours._deps, {"marquer_etat": marquer}), \
                patch.object(parcours, "_comptes_ordonnes", return_value=["un.fictif", "deux.fictif", "trois.fictif"]), \
                patch.object(parcours, "_lire", return_value={"42": {"prenom": "Fictive"}}), \
                patch.object(onboarding.process_adapters, "store", return_value=registre), \
                patch.object(parcours, "reprise_si_historique", AsyncMock(return_value=reprise)):
            await parcours._classeur_etat("42", 2)
        return marquer

    async def test_le_log_suit_meme_quand_le_registre_refuse(self):
        registre = N(created=MagicMock(side_effect=RuntimeError("Création sans réservation valide")), owner_for_handle=lambda h: None)
        marquer = await self._jouer(registre)
        marquer.assert_awaited_once_with("deux.fictif", "GOOD")

    async def test_reprise_puis_creation_notee(self):
        appels = []

        def created(uid, h, preuve):
            appels.append(h)
            if len(appels) == 1:
                raise RuntimeError("Historique à vie non rapproché : allocation bloquée")
        registre = N(created=created, owner_for_handle=lambda h: "42")
        marquer = await self._jouer(registre, reprise=True)
        self.assertEqual(["deux.fictif", "deux.fictif"], appels)
        marquer.assert_awaited_once()

    async def test_jamais_le_log_d_un_compte_d_un_autre_clipper(self):
        registre = N(created=MagicMock(side_effect=RuntimeError("Création sans réservation valide")), owner_for_handle=lambda h: "77")
        marquer = await self._jouer(registre)
        marquer.assert_not_awaited()


class BrancheTests(unittest.TestCase):
    def test_compte_et_lien_retentent_apres_reprise(self):
        source = Path(parcours.__file__).read_text(encoding="utf-8")
        self.assertIn('f"le compte {n}"):\n                    continue', source)
        self.assertIn('erreur_l, "le lien"):\n                    raise\n                await _deps["attribuer_lien"](membre)', source)


if __name__ == "__main__":
    unittest.main()
