"""19/10 (Gaëtan) : `!code` tapé dans le salon commun #code-instagram donne le dernier code admissible
(connexion/création/vérification) des FRAIS_MIN dernières minutes, toutes adresses confondues — sans vérifier que
celui qui tape en est le propriétaire. Ce fichier vérifie que :
  1. ce comportement existe bien dans le salon commun ;
  2. il reste borné à connexion/création/vérification (jamais un code gardé/sécurité) et à la fenêtre FRAIS_MIN ;
  3. il n'affecte AUCUN autre chemin : `!code` dans un autre salon garde la vérification de propriétaire intacte.
Aucun appel Gmail/Discord réel.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import unittest

from test_codes_reliable import load_codes

SALON_COMMUN = "999000"
AUTRE_SALON = "111222"


class FauxAuteur:
    def __init__(self, uid):
        self.id = uid
        self.roles = []


class FauxCanal:
    def __init__(self, cid):
        self.id = cid


class FauxMessage:
    def __init__(self, texte, canal_id, auteur_id="42"):
        self.content = texte
        self.channel = FauxCanal(canal_id)
        self.guild = object()
        self.author = FauxAuteur(auteur_id)
        self.replies = []

    async def reply(self, texte, **kwargs):
        envoye = {"content": texte}
        self.replies.append(envoye)
        async def edit(content):
            envoye["content"] = content
        return type("Msg", (), {"edit": staticmethod(edit)})()


class SalonPartageTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 19, 13, 12, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now
        self.state = {"uid": {}, "codes": [], "faits": {}, "sante": {}, "n": 0}
        self.c._etat = lambda: self.state
        self.c._sauver = lambda: None
        self.c.actif = lambda: True
        self.c.salon_codes_id = lambda: SALON_COMMUN
        self.c.ATTENTE_SEC = 0  # le guet ne doit pas bloquer le test : une seule itération
        self.c.discord.HTTPException = type("HTTPException", (Exception,), {})
        self.c.discord.Forbidden = type("Forbidden", (self.c.discord.HTTPException,), {})

    def entree(self, code, alias, usage="connexion", decision="donner", age=0):
        self.state["codes"].append(dict(code=code, alias=alias, type=usage, decision=decision, mid=code,
                                        date=(self.now - timedelta(minutes=age)).isoformat()))

    # ---- _dernier_code_partage : la fonction pure ----

    def test_ignore_le_proprietaire(self):
        self.entree("111111", "alice@example.invalid")
        montre = self.c._dernier_code_partage()
        self.assertIsNotNone(montre)
        self.assertEqual(montre["code"], "111111")

    def test_prend_le_plus_recent_toutes_adresses(self):
        self.entree("111111", "alice@example.invalid", age=5)
        self.entree("222222", "bob@example.invalid", age=1)
        montre = self.c._dernier_code_partage()
        self.assertEqual(montre["code"], "222222")

    def test_exclut_hors_fenetre_frais_min(self):
        self.entree("111111", "alice@example.invalid", age=self.c.FRAIS_MIN + 1)
        self.assertIsNone(self.c._dernier_code_partage())

    def test_exclut_les_codes_gardes(self):
        self.entree("111111", "alice@example.invalid", decision="garder")
        self.assertIsNone(self.c._dernier_code_partage())

    def test_exclut_les_types_hors_login_signup(self):
        self.entree("111111", "alice@example.invalid", usage="appel")
        self.assertIsNone(self.c._dernier_code_partage())

    def test_verification_compte_comme_signup(self):
        self.entree("111111", "alice@example.invalid", usage="verification")
        montre = self.c._dernier_code_partage()
        self.assertEqual(montre["code"], "111111")

    def test_adresse_filtre_sans_elargir(self):
        self.entree("111111", "alice@example.invalid", age=1)
        self.entree("222222", "bob@example.invalid", age=0)
        montre = self.c._dernier_code_partage(adresse="alice@example.invalid")
        self.assertEqual(montre["code"], "111111")

    # ---- bout en bout via commande() : le routage par salon ----

    def test_salon_commun_donne_le_code_sans_adresse_rattachee(self):
        self.entree("787718", "pie.polygone_3j@icloud.com")
        message = FauxMessage("!code", SALON_COMMUN, auteur_id="999")
        # Aucune fonction adresses_de_membre fournie : si le chemin passait encore par
        # _commande_salon_commun, il répondrait "aucune adresse" et ne donnerait rien.
        traite = asyncio.run(self.c.commande(message, admin_ids=set(), adresses_de_membre=lambda uid: set()))
        self.assertTrue(traite)
        texte = "\n".join(r["content"] for r in message.replies)
        self.assertIn("787718", texte)

    def test_salon_commun_route_vers_commande_salon_partage(self):
        appels = []
        self.c._commande_salon_partage = self._espion(appels, True)
        self.c._commande_salon_commun = self._espion(appels, True, nom="commun")
        message = FauxMessage("!code", SALON_COMMUN, auteur_id="1")
        asyncio.run(self.c.commande(message, admin_ids=set(), adresses_de_membre=lambda uid: set()))
        self.assertEqual(appels, ["partage"])

    def test_autre_salon_garde_la_verification_de_proprietaire(self):
        appels = []
        self.c._commande_salon_partage = self._espion(appels, True, nom="partage")
        self.c._commande_salon_commun = self._espion(appels, True, nom="commun")
        message = FauxMessage("!code", AUTRE_SALON, auteur_id="1")
        asyncio.run(self.c.commande(message, admin_ids=set(), adresses_de_membre=lambda uid: set()))
        self.assertEqual(appels, ["commun"])

    def test_autre_salon_toujours_bloque_sans_adresse(self):
        self.entree("787718", "pie.polygone_3j@icloud.com")
        message = FauxMessage("!code", AUTRE_SALON, auteur_id="999")
        asyncio.run(self.c.commande(message, admin_ids=set(), adresses_de_membre=lambda uid: set()))
        texte = "\n".join(r["content"] for r in message.replies)
        self.assertNotIn("787718", texte)

    @staticmethod
    def _espion(appels, retour, nom="partage"):
        async def f(*a, **k):
            appels.append(nom)
            return retour
        return f


if __name__ == "__main__":
    unittest.main()
