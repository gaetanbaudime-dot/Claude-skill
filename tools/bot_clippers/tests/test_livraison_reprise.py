"""Reprises du vrai parcours avec POST Discord simulés et journal SQLite réel."""
import asyncio
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import discord
import parcours as p
import process_adapters
from process_store import Store
import onboarding_preuves


class Reprises(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'test.sqlite3');self.store.reconcile('42',[],'fictif')
        self.etat={}
        self.membre=N(id=42,mention='<@42>',display_name='Fictif')
        self.salon=N(id=99,guild=N(me=N(id=90)),send=AsyncMock(return_value=N(id=123)),
                     permissions_for=lambda m:N(view_channel=True,read_message_history=True))
        async def historique(**kw):
            if False:yield None
        self.salon.history=historique
        def ecrire(d):self.etat.clear();self.etat.update(deepcopy(d))
        patches=[patch.object(process_adapters,'store',return_value=self.store),
                 patch.object(p.process_clippeur,'pseudo_disponible',return_value=True),
                 patch.dict(p.onboarding._deps,{'FICHIER_ONBOARDING':Path(self.tmp.name)/'onboarding.json','lire_json':lambda *a:{}}),
                 patch.multiple(p,_lire=lambda:deepcopy(self.etat),_ecrire=ecrire,
                    _deps={'membre_par_id':lambda uid:self.membre},_reprendre_trace=lambda *a:None,
                    _ligne_du_compte=AsyncMock(return_value=True),_comptes_ordonnes=lambda *a,**kw:['compte-fictif'],
                    _contexte=AsyncMock(return_value={'prenom':'Fictif','creatrice':'Fictive'}),
                    _rendre=lambda texte,ctx:texte,_vue=lambda *a:None,_retirer_pret=AsyncMock())]
        for pa in patches:pa.start();self.addCleanup(pa.stop)

    async def test_refus_discord_puis_reprise_du_vrai_parcours(self):
        self.salon.send.side_effect=[discord.Forbidden(N(status=403,reason='fictif'),'refus'),N(id=123)]
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        self.assertNotIn('1',self.etat['42'].get('messages',{}))
        self.assertTrue(self.etat['42']['programme'])
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        self.assertEqual('123',self.etat['42']['messages']['1'])
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        self.assertEqual(2,self.salon.send.await_count)

    async def test_timeout_apres_acceptation_retrouve_message_sans_second_post(self):
        self.message=None
        async def send(texte,**kw):
            self.message=N(id=123,content=texte,author=N(id=90))
            raise TimeoutError()
        async def historique(**kw):yield self.message
        self.salon.send.side_effect=send;self.salon.history=historique
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        self.assertEqual('123',self.etat['42']['messages']['1'])
        self.salon.send.assert_awaited_once()

    async def test_erreur_ambigue_sans_message_visible_reste_bloquee(self):
        self.salon.send.side_effect=discord.HTTPException(N(status=503,reason='fictif'),'fictif')
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        self.assertNotIn('1',self.etat['42'].get('messages',{}))
        self.assertTrue(self.etat['42']['programme'])
        self.salon.send.assert_awaited_once()

    async def test_salon_non_vide_ou_lecture_interdite_non_partage(self):
        async def histoire(**kw):yield N(content='message privé fictif')
        self.salon.history=histoire
        self.assertFalse(await onboarding_preuves.salon_vide_verifie(self.salon))
        self.salon.permissions_for=lambda m:N(view_channel=True,read_message_history=False)
        self.assertFalse(await onboarding_preuves.salon_vide_verifie(self.salon))

    async def test_evenements_concurrents_et_programme_residuel_sans_doublon(self):
        entre,sortie=asyncio.Event(),asyncio.Event()
        async def send(*args,**kw):
            entre.set();await sortie.wait();return N(id=123)
        self.salon.send.side_effect=send
        premier=asyncio.create_task(p.demarrer_parcours(self.salon,self.membre,'Fictive'))
        await entre.wait()
        await p.demarrer_parcours(self.salon,self.membre,'Fictive')
        sortie.set();await premier
        await p.envoyer_etape(self.salon,self.membre,1)
        self.assertEqual('123',self.etat['42']['messages']['1'])
        self.salon.send.assert_awaited_once()
