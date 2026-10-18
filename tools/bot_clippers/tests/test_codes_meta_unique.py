"""OTP e-mail des trois services, bouton unique et isolement des comptes. Mocks uniquement."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import types
import unittest
from unittest.mock import Mock
from test_codes_reliable import load_codes


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()

    def test_connexion_des_trois_marques_et_meta_pour_instagram(self):
        for sender, service, body in [
            ("security@mail.instagram.com", "instagram", "Use this code to log in to your Instagram account: 111111"),
            ("security@facebookmail.com", "facebook", "Use this code to log in to your Facebook account: 111111"),
            ("security@facebook.com", "facebook", "Votre code de connexion Facebook est 111111. Utilisez ce code pour vous connecter."),
            ("security@account.meta.com", "meta", "Use this code to log in to your Meta account: 111111"),
            ("security@metamail.com", "meta", "Use this code to log in to your Meta account: 111111"),
            ("security@global.metamail.com", "meta", "Votre code de connexion Meta est 111111. Utilisez ce code pour vous connecter."),
            ("security@meta.com", "instagram", "Use this code to log in to your Instagram account: 111111"),
        ]:
            with self.subTest(sender=sender):
                r=self.c.classer(sender, "Your login code", body)
                self.assertEqual((r["decision"], r["type"], r["service"]), ("donner", "connexion", service))

    def test_otp_email_de_double_authentification_livrable_sans_graine(self):
        for sender in ("security@mail.instagram.com", "security@facebookmail.com", "security@meta.com"):
            r=self.c.classer(sender, "Your login code", "Use this two-factor authentication code to log in to your account: 111111.")
            self.assertEqual(r["decision"], "donner")
            self.assertEqual(r["type"], "connexion")

    def test_connexion_espace_comptes_sans_reconfiguration(self):
        r=self.c.classer("security@accountscenter.meta.com", "Your login code",
                         "Use this code to log in to your Meta account in Accounts Center: 111111")
        self.assertEqual((r["decision"],r["service"]), ("donner","meta"))
        for action in ("link your account", "set up two-factor authentication", "configure two-factor authentication",
                       "activer la double authentification", "associer votre compte"):
            r=self.c.classer("security@meta.com", "Your login code",
                             "Use this code to log in and " + action + ": 111111")
            self.assertNotEqual(r["decision"], "donner")

    def test_pied_meta_facebook_ne_change_pas_le_service(self):
        r=self.c.classer("security@meta.com", "Your login code",
                         "Use this code to log in to your Meta account: 111111. This email was sent to you by Facebook.")
        self.assertEqual((r["decision"],r["service"]), ("donner","meta"))

    def test_creation_et_verification_fb_meta(self):
        for sender in ("security@facebookmail.com", "security@meta.com"):
            for body, typ in [("Use this code to create an account: 111111", "creation"),
                              ("Please verify your email address with this code: 111111", "verification")]:
                with self.subTest(sender=sender, typ=typ):
                    r=self.c.classer(sender, "Your confirmation code", body)
                    self.assertEqual((r["decision"],r["type"]), ("donner",typ))

    def test_pas_de_recuperation_mutation_graine_ou_corps_transmis(self):
        for sender in ("security@facebookmail.com", "security@meta.com", "security@mail.instagram.com"):
            for texte in ("Use 111111 to reset your password before you log in.",
                          "Your backup code is 111111. Use it to log in.",
                          "Use 111111 to disable two-factor authentication and log in.",
                          "Your authenticator secret key is 111111. Use it to log in.",
                          "Use 111111 to change your email address and log in.",
                          "Use 111111 to recover your account and log in.",
                          "Use 111111 to appeal the suspension before you log in."):
                with self.subTest(sender=sender, texte=texte):
                    self.assertNotEqual(self.c.classer(sender,"Your login code",texte)["decision"],"donner")

    def test_mutation_dans_autre_partie_mime_bloquee(self):
        for sender in ("security@facebookmail.com", "security@meta.com"):
            r=self.c.classer(sender,"Your login code","Use this code to log in to your account: 111111",
                             ["Use this code to change your email address: 111111"])
            self.assertNotEqual(r["decision"],"donner")

    def test_expediteurs_imites_refuses(self):
        for sender in ("Meta <security@gmail.com>", "security@meta.com.fake.invalid", "security@notfacebookmail.com",
                       "security@facebookmail.com.attacker.invalid", "security@metamail.com.evil.invalid"):
            r=self.c.classer(sender,"Your login code","Use this code to log in to your account: 111111")
            self.assertEqual(r["decision"],"rien")
            self.assertIsNone(r["code"])

    def test_relais_icloud_des_trois_services(self):
        for sender, service in [("security_at_mail_instagram_com_a1_b2@icloud.com", "instagram"),
                                ("security_at_facebookmail_com_a1_b2@icloud.com", "facebook"),
                                ("security_at_account_meta_com_a1_b2@icloud.com", "meta"),
                                ("security_at_global_metamail_com_a1_b2@icloud.com", "meta")]:
            r=self.c.classer(sender,"Your login code","Use this code to log in to your account: 111111")
            self.assertEqual((r["decision"],r["service"]), ("donner",service))


class PointUniqueTests(unittest.TestCase):
    def setUp(self):
        self.c=load_codes()
        self.now=datetime(2026,10,14,10,tzinfo=timezone.utc)
        self.c._maintenant=lambda:self.now
        self.state={"codes":[],"n":0}
        self.c._etat=lambda:self.state
        self.c._sauver=lambda:None

    def entree(self, code, service="instagram", usage="connexion", alias="one@example.invalid", age=0):
        self.state["codes"].append(dict(mid=code, code=code, service=service, type=usage, alias=alias,
            decision="donner", date=(self.now-timedelta(minutes=age)).isoformat(), n=len(self.state["codes"])))

    def servir(self, aliases=None, relire=None):
        messages=[]
        async def dire(t): messages.append(t)
        r=asyncio.run(self.c._servir(aliases or {"one@example.invalid"},dire,"u|100",usage="auto",duree=0,relire=relire))
        return r,"\n".join(messages)

    def test_un_clic_trois_services_labelises_sans_code_autre_clipper(self):
        self.entree("111111")
        self.entree("222222",service="facebook")
        self.entree("333333",service="meta")
        self.entree("444444",alias="other@example.invalid")
        r,texte=self.servir()
        self.assertEqual(r,"code")
        for marque in ("Instagram","Facebook","Meta","111111","222222","333333"): self.assertIn(marque,texte)
        self.assertNotIn("444444",texte)

    def test_creation_n_est_pas_etiquetee_connexion(self):
        self.entree("111111",usage="creation")
        r,texte=self.servir()
        self.assertEqual(r,"code")
        self.assertIn("création de compte",texte)
        self.assertNotIn("connexion",texte)

    def test_seul_dernier_code_par_service_compte_usage(self):
        self.entree("111111",age=1)
        self.entree("222222")
        self.entree("333333",usage="creation")
        texte=self.servir()[1]
        self.assertNotIn("111111",texte)
        self.assertIn("222222",texte)
        self.assertIn("333333",texte)

    def test_code_expire_meme_apres_lecture_precedente(self):
        self.entree("111111")
        self.assertIn("111111",self.servir()[1])
        self.now+=timedelta(minutes=21)                                 # 18/10 : la fenêtre passe à 20 minutes
        self.assertNotIn("111111",self.servir()[1])

    def test_frais_deja_lu_accessible_sans_nouveau_menu(self):
        self.entree("111111")
        self.assertIn("111111",self.servir()[1])
        self.assertIn("111111",self.servir()[1])

    def test_retrait_de_droits_toujours_prioritaire(self):
        self.entree("111111")
        r,texte=self.servir(relire=lambda:set())
        self.assertEqual(r,"sortie")
        self.assertNotIn("111111",texte)

    def test_codes_anciens_futurs_et_non_email_non_presentes(self):
        self.entree("111111",age=21)                                    # 18/10 : au-delà des 20 minutes
        self.entree("222222",age=-10)
        self.entree("333333",usage="2fa")
        self.entree("444444",service="unknown")
        texte=self.servir()[1]
        for code in ("111111","222222","333333","444444"): self.assertNotIn(code,texte)

    def test_plusieurs_comptes_autorises_sans_menu(self):
        self.entree("111111")
        self.entree("222222",alias="two@example.invalid")
        self.entree("333333",alias="other@example.invalid")
        texte=self.servir({"one@example.invalid","two@example.invalid"})[1]
        self.assertIn("111111",texte)
        self.assertIn("222222",texte)
        self.assertNotIn("333333",texte)

    def test_arrivee_actualise_la_reponse_privee_automatiquement(self):
        messages=[]
        temps=[0]
        self.c.time=types.SimpleNamespace(monotonic=lambda:temps[0])
        async def dire(t): messages.append(t)
        async def attendre(_):
            self.entree("222222",service="facebook")
            temps[0]=2
        self.c._attendre_nouveau=attendre
        r=asyncio.run(self.c._servir({"one@example.invalid"},dire,"u|100",usage="auto",duree=1))
        self.assertEqual(r,"code")
        self.assertNotIn("222222",messages[0])
        self.assertIn("222222",messages[-1])
        self.assertIn("Facebook",messages[-1])

    def test_retrait_droits_efface_la_reponse_auto(self):
        self.entree("111111")
        droits={"one@example.invalid"}
        messages=[]
        async def dire(t): messages.append(t)
        async def attendre(_): droits.clear()
        self.c._attendre_nouveau=attendre
        r=asyncio.run(self.c._servir(set(droits),dire,"u|100",usage="auto",duree=1,relire=lambda:droits))
        self.assertEqual(r,"sortie")
        self.assertIn("111111",messages[0])
        self.assertNotIn("111111",messages[-1])

    def test_recherche_directe_inclut_tous_services(self):
        msg=EmailMessage()
        msg["From"]="security@metamail.com"
        msg["To"]="one@example.invalid"
        msg["Date"]="Wed, 14 Oct 2026 10:00:00 +0000"
        msg["Subject"]="Your login code"
        msg.set_content("Use this code to log in to your Meta account: 111111")
        boite=types.SimpleNamespace(uid=Mock(return_value=("OK",[b"1"])))
        lecteur=types.SimpleNamespace(_connecter=Mock(), dossiers=lambda:["INBOX"], _selectionner=Mock(),
           boite=boite,_lire=lambda *_:[{"msg":msg}], fermer=Mock())
        self.c.Lecteur=lambda:lecteur
        r=self.c._scan_recent_sync({"one@example.invalid"})
        requetes=str(boite.uid.call_args_list)
        for marque in ("instagram","facebook","meta.com","metamail","fb.com"): self.assertIn(marque,requetes)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]["service"],"meta")
        lecteur.fermer.assert_called_once()
        boite.uid.assert_called_once()
