"""Diagnostic de droits et chaîne mail→cache→réponse privée avec données synthétiques."""
import asyncio
import ast
from pathlib import Path
from datetime import datetime, timezone
from email.message import EmailMessage
import json
import types
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import otp_identity
from unittest.mock import Mock
from test_codes_reliable import load_codes


class Role:
    def __init__(self, uid, name): self.id, self.name = uid, name


class AuditTests(unittest.TestCase):
    def test_diagnostic_livraison_actuelle_prime_sur_ancienne_fiche(self):
        data = {'clippers': {uid: {'comptes': ['one'], 'acces': [
                    {'handle': 'one', 'mail': 'same@example.invalid'}]} for uid in ('100', '200')},
                'livres': {'one': {'uid': '200'}}}
        old = otp_identity.assignment_diagnostics(data, '100', lambda h: h)
        current = otp_identity.assignment_diagnostics(data, '200', lambda h: h)
        self.assertEqual(old['livraison_autre_uid'], 1)
        self.assertEqual(current['compte_autorise'], 1)
        self.assertEqual(current['alias_ambigu'], 0)

    def test_causes_exclusives_et_accord_avec_autorisation_reelle(self):
        data = {"clippers": {"100": {"comptes": ["ok", "absent", "sansmail", "autre", "partage", "double"],
            "acces": [{"handle": "ok", "mail": "ok@example.invalid", "password": "secret-test"},
                      {"handle": "sansmail"}, {"handle": "autre", "mail": "autre@example.invalid"},
                      {"handle": "partage", "mail": "shared@example.invalid"},
                      {"handle": "double", "mail": "first@example.invalid"},
                      {"handle": "double", "mail": "second@example.invalid"}]},
            "200": {"comptes": ["other"], "acces": [{"handle": "other", "mail": "shared@example.invalid"}]}},
            "livres": {"autre": {"uid": "200"}}}
        tree = ast.parse((Path(__file__).resolve().parents[1]/'bot_discord.py').read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_adresses_codes_fiche']
        ns = dict(lire_json=lambda *_: data, FICHIER_ONBOARDING='mock',
                  onboarding=types.SimpleNamespace(_cle_handle=lambda h: h))
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), 'audit-synthetic', 'exec'), ns)
        counts = otp_identity.assignment_diagnostics(data, '100', lambda h: h)
        self.assertEqual(counts, dict(compte_autorise=1, acces_absent=1, adresse_absente=1,
                         livraison_autre_uid=1, alias_ambigu=1, compte_ambigu=1))
        self.assertEqual(counts['compte_autorise'], len(ns['_adresses_codes_fiche']('100')))
        for secret in ('example.invalid', 'secret-test', 'sansmail', 'shared'):
            self.assertNotIn(secret, str(counts))

    def test_diagnostic_ignore_anciens_comptes_et_telephone_non_livre(self):
        data = {"clippers": {"100": {"comptes": [], "acces": [{"handle": "retire", "mail": "old@example.invalid"}],
            "telephones": {"phone": {"donnes": 1, "acces": [
                {"handle": "livre", "mail": "delivered@example.invalid"},
                {"handle": "futur", "mail": "future@example.invalid"}]}}}}}
        counts = otp_identity.assignment_diagnostics(data, '100', lambda h: h)
        self.assertEqual(counts['compte_autorise'], 1)
        self.assertEqual(sum(counts.values()), 1)

    def test_permissions_effectives_et_projection_sans_secrets(self):
        c=load_codes()
        everyone,clipper,manager=Role(1,"@everyone"),Role(2,"Clippeur"),Role(3,"Manager")
        members=[types.SimpleNamespace(id=100,bot=False),types.SimpleNamespace(id=200,bot=False),types.SimpleNamespace(id=300,bot=True)]
        guild=types.SimpleNamespace(members=members,roles=[everyone,clipper,manager],default_role=everyone,
                                   me=members[2],member_count=3,chunked=True)
        perms=lambda obj:types.SimpleNamespace(view_channel=obj.id in (2,3,100,300),
                                               send_messages=obj.id in (2,3,100,300),administrator=obj.id==3)
        salon=types.SimpleNamespace(id=400,guild=guild,permissions_for=perms,
             overwrites={everyone:types.SimpleNamespace(view_channel=False,send_messages=None)})
        c._deps['audit_liaisons']=lambda _: [dict(uid="100",comptes_declares=1,adresses_autorisees=1,
              salon_perso=True,voit_codes=True,dans_serveur=True,mail="private@example.invalid",code="111111",password="secret-test")]
        c.journal=Mock()
        r=c.audit_salon_codes(salon)
        self.assertEqual((r['cache_complet'],r['visibles'],r['humains_visibles']),(True,2,1))
        self.assertFalse(r['roles'][0]['voir'])
        for secret in ("private@example.invalid","111111","secret-test"): self.assertNotIn(secret,str(c.journal.info.call_args_list))
        liaison=json.loads(c.journal.info.call_args_list[1].args[1])
        self.assertEqual(liaison['adresses_autorisees'],1)

    def test_liaisons_projetees_sans_donnees_acces(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'bot_discord.py').read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='audit_liaisons_codes']
        data={'clippers':{'100':{'comptes':['one'],'acces':[{'handle':'one','mail':'private@example.invalid','password':'secret-test'}],
             'telephones':{'phone':{'donnes':1,'acces':[{'handle':'two','mail':'second@example.invalid'},{'handle':'future'}]}}}}}
        member=types.SimpleNamespace(id=100)
        salon=types.SimpleNamespace(permissions_for=lambda _:types.SimpleNamespace(view_channel=True))
        guild=types.SimpleNamespace(get_channel=lambda _:salon,get_member=lambda _:member)
        ns=dict(lire_json=lambda *_:data,FICHIER_ONBOARDING='mock',codes_2fa=types.SimpleNamespace(salon_codes_id=lambda:'400'),
                onboarding=types.SimpleNamespace(_cle_handle=lambda h:h),_adresses_codes_fiche=lambda _:{'private@example.invalid','second@example.invalid'},
                salon_perso_de=lambda _:salon, otp_identity=otp_identity)
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs,type_ignores=[])),'audit-synthetic','exec'),ns)
        rows=list(ns['audit_liaisons_codes'](guild))
        self.assertEqual(rows[0]['comptes_declares'],2)
        self.assertEqual(rows[0]['adresses_autorisees'],2)
        for secret in ('secret-test','example.invalid','future'):self.assertNotIn(secret,str(rows))

    def test_cache_incomplet_explicitement_signale(self):
        c=load_codes();r=Role(1,'@everyone');m=types.SimpleNamespace(id=100,bot=True)
        guild=types.SimpleNamespace(members=[m],roles=[r],default_role=r,me=m,member_count=50,chunked=False)
        salon=types.SimpleNamespace(id=400,guild=guild,overwrites={},permissions_for=lambda _:types.SimpleNamespace(view_channel=True,send_messages=True,administrator=False))
        c.journal=Mock()
        self.assertFalse(c.audit_salon_codes(salon)['cache_complet'])


class PipelineTests(unittest.TestCase):
    def test_creation_connexion_et_renvoi_pour_les_trois_services(self):
        for service,sender in (("instagram","security@mail.instagram.com"),("facebook","security@facebookmail.com"),("meta","security@meta.com")):
            for usage,phrase in (("creation","create an account"),("connexion","log in to your account")):
                with self.subTest(service=service,usage=usage):
                    self.pipeline(service,sender,usage,phrase)

    def pipeline(self,service,sender,usage,phrase):
        c=load_codes();now=datetime(2026,10,14,10,tzinfo=timezone.utc)
        c._maintenant=lambda:now
        state={"codes":[],"faits":{},"sante":{},"n":0};c._etat=lambda:state;c._sauver=lambda:None
        c._proprietaire=lambda _:dict(canal_id="400");c.salon_codes_id=lambda:"400"
        c.journal=Mock()
        t=[0];c.time=types.SimpleNamespace(monotonic=lambda:t[0])
        messages=[]
        def mail(code,alias="one@example.invalid"):
            m=EmailMessage();m['From']=sender;m['To']=alias;m['Date']='Wed, 14 Oct 2026 10:00:00 +0000'
            m['Message-ID']=f'<synthetic-{code}@example.invalid>';m['Subject']='Your requested code'
            m.set_content(f'Use this code to {phrase}: {code}')
            return dict(msg=m,dossier='INBOX')
        async def dire(texte):messages.append(texte)
        async def renvoi(_):
            await c._traiter_lus(None,dict(mails=[mail("222222"),mail("333333","other@example.invalid")]))
            t[0]=2
        c._attendre_nouveau=renvoi
        async def test():
            await c._traiter_lus(None,dict(mails=[mail("111111")]))
            return await c._servir({"one@example.invalid"},dire,"u|100",usage="auto",duree=1,relire=lambda:{"one@example.invalid"})
        self.assertEqual(asyncio.run(test()),"code")
        self.assertIn("111111",messages[0]);self.assertIn("222222",messages[-1])
        self.assertNotIn("111111",messages[-1]);self.assertNotIn("333333",' '.join(messages))
        self.assertIn(c.SERVICES_EMAIL[service],messages[-1]);self.assertIn(c.QUOI[usage],messages[-1])
        traces=[call.args[1] for call in c.journal.info.call_args_list if call.args[0].startswith('OTP_REPONSE')]
        self.assertTrue(traces)
        for secret in ("111111","222222","333333","example.invalid"):self.assertNotIn(secret,str(traces))
