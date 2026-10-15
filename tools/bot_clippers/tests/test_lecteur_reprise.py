"""Interruptions après FETCH : aucune boîte réelle, aucun code réel."""
import asyncio
from collections import OrderedDict
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from test_codes_reliable import load_codes

class RepriseTests(unittest.IsolatedAsyncioTestCase):
    async def test_curseur_et_dedup_non_valides_sur_traitement_echoue(self):
        c=load_codes();c.actif=lambda:True;c._lire=lambda:{};c._deps={}
        state={'uid':{'INBOX':{'dernier':1}},'codes':[],'sante':{},'faits':{}}
        c._etat=lambda:state;c._sauver=Mock();c._sante_ok=AsyncMock()
        seen=[];saved=[]
        reader=SimpleNamespace(etat={},vus=OrderedDict(),idle=False)
        def cycle(attendre):
            seen.append((reader.etat['INBOX']['dernier'],list(reader.vus)))
            reader.etat={'INBOX':{'dernier':2}};reader.vus['mail-fictif']=True
            return {'mails':[]}
        reader.cycle=cycle;c.LECTEUR=reader
        calls=0
        async def traiter(*args):
            nonlocal calls
            calls+=1
            if calls==1:raise RuntimeError('panne fictive')
        c._traiter_lus=traiter
        c.asyncio=SimpleNamespace(to_thread=asyncio.to_thread,sleep=AsyncMock())
        client=SimpleNamespace(wait_until_ready=AsyncMock(),is_closed=lambda:len(seen)>=2)
        c._sauver=lambda:saved.append(state['uid']['INBOX']['dernier'])
        await c.boucle_codes(client,AsyncMock(),set())
        self.assertEqual([(1,[]),(1,[])],seen)
        self.assertEqual([2],saved)
        c._sante_ok.assert_awaited_once()

    async def test_un_mail_rate_ne_cache_pas_lechec_ni_ne_bloque_les_suivants(self):
        c=load_codes();c._etat=lambda:{'codes':[]};c.salon_codes_id=lambda:''
        c._signaux=AsyncMock();c._sauver=Mock();c._reveiller=AsyncMock()
        traites=[]
        async def traiter(client,lu,*args):
            traites.append(lu['id'])
            if lu['id']=='mauvais':raise ValueError('fixture')
        c._traiter_un=traiter
        with self.assertRaises(RuntimeError):
            await c._traiter_lus(None,{'mails':[{'id':'mauvais'},{'id':'bon'}]})
        self.assertEqual(['mauvais','bon'],traites)

    async def test_timeout_suivi_de_reprise_reinitialise_sante(self):
        c=load_codes();c._SANTE={'ok_t':None,'echecs':0,'erreur':''};c._une_fois=lambda *a,**k:False
        c._etat=lambda:{'panne_signalee':False};c._sauver=Mock();c._admin=AsyncMock()
        await c._sante_erreur(TimeoutError())
        self.assertEqual(1,c._SANTE['echecs'])
        await c._sante_ok()
        self.assertEqual(0,c._SANTE['echecs']);self.assertIsNotNone(c._SANTE['ok_t'])
        c._admin.assert_not_awaited()
