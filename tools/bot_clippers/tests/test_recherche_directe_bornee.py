"""Lecteur et mails fictifs : aucune connexion, aucun envoi, délais accélérés."""
import asyncio
import threading
import unittest
from unittest.mock import patch, AsyncMock
from test_codes_reliable import load_codes

class RechercheBorneeTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_ne_libere_pas_place_avant_arret_du_thread(self):
        c=load_codes();stop=threading.Event();lock=threading.Lock();counts={'active':0,'peak':0}
        def reader(*args):
            with lock:
                counts['active']+=1;counts['peak']=max(counts['peak'],counts['active'])
            stop.wait(1)
            with lock: counts['active']-=1
            return []
        real_wait=asyncio.wait_for
        async def court(aw,timeout): return await real_wait(aw,timeout=.02)
        tasks=[]
        with patch.object(c,'actif',return_value=True),patch.object(c,'_scan_recent_sync',reader),patch.object(c.asyncio,'wait_for',court):
            try:
                tasks=[asyncio.create_task(c._scanner_sur_demande({'fictif@example.invalid'},str(i))) for i in range(4)]
                await asyncio.sleep(.1)
                self.assertLessEqual(counts['peak'],2)
            finally:
                stop.set()
                await asyncio.gather(*tasks,return_exceptions=True)
                await asyncio.sleep(.05)
            self.assertEqual(2,c._SCAN_SEMAPHORE[1]._value)
            self.assertFalse(c._SCAN_EN_COURS)
            self.assertFalse(c._SCAN_TRAVAUX)

    async def test_meme_demande_ne_cree_pas_thread_survivant_en_double(self):
        c=load_codes();stop=threading.Event();starts=[]
        def reader(*args):
            starts.append(True);stop.wait(1);return []
        real_wait=asyncio.wait_for
        async def court(aw,timeout): return await real_wait(aw,timeout=.02)
        try:
            with patch.object(c,'actif',return_value=True),patch.object(c,'_scan_recent_sync',reader),patch.object(c.asyncio,'wait_for',court):
                await c._scanner_sur_demande({'fictif@example.invalid'},'fictif')
                c._SCAN_LAST.clear()
                await c._scanner_sur_demande({'fictif@example.invalid'},'fictif')
                self.assertEqual(1,len(starts))
        finally:
            stop.set();await asyncio.sleep(.05)

    async def test_resultat_tardif_apres_timeout_jamais_mis_en_cache(self):
        c=load_codes();stop=threading.Event();signals=[];state={'codes':[]}
        def reader(aliases,minutes,arret):
            signals.append(arret);stop.wait(1)
            return [{'mid':'fictif-tardif'}]
        real_wait=asyncio.wait_for
        async def court(aw,timeout):
            self.assertEqual(35,timeout)
            return await real_wait(aw,timeout=.02)
        with patch.object(c,'actif',return_value=True),patch.object(c,'_scan_recent_sync',reader),patch.object(c.asyncio,'wait_for',court),patch.object(c,'_etat',return_value=state),patch.object(c,'_sauver') as save,patch.object(c,'_reveiller',AsyncMock()) as wake:
            try:
                await c._scanner_sur_demande({'fictif@example.invalid'},'fictif')
                self.assertTrue(signals[0].is_set())
            finally:
                stop.set();await asyncio.sleep(.05)
            self.assertEqual([],state['codes']);save.assert_not_called();wake.assert_not_awaited()

    async def test_annulation_coroutine_garde_place_jusqua_fin_thread(self):
        c=load_codes();stop=threading.Event();started=threading.Event();signals=[]
        def reader(a,m,event):
            signals.append(event);started.set();stop.wait(1);return []
        with patch.object(c,'actif',return_value=True),patch.object(c,'_scan_recent_sync',reader):
            task=asyncio.create_task(c._scanner_sur_demande({'fictif@example.invalid'},'fictif'))
            try:
                while not started.is_set(): await asyncio.sleep(.005)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task
                self.assertTrue(signals[0].is_set())
                self.assertEqual(1,c._SCAN_SEMAPHORE[1]._value)
            finally:
                stop.set();await asyncio.sleep(.05)
            self.assertEqual(2,c._SCAN_SEMAPHORE[1]._value)

class LectureDirecteTests(unittest.TestCase):
    def setUp(self):
        self.c=load_codes()

    def test_filtre_date_evite_corps_anciens_sans_sauter_mail_recent(self):
        from datetime import datetime,timezone,timedelta
        from email.utils import format_datetime
        now=datetime(2026,10,15,15,0,tzinfo=timezone.utc)
        entetes={1:('From: Instagram <security@mail.instagram.com>\r\nDate: '+format_datetime(now-timedelta(hours=2))+'\r\nMessage-ID: <ancien>\r\n\r\n').encode(),
                 2:('From: Instagram <security@mail.instagram.com>\r\nDate: '+format_datetime(now)+'\r\nMessage-ID: <recent>\r\n\r\n').encode()}
        bodies=[]
        class Boite:
            def uid(_,cmd,ids,champs):
                if 'HEADER.FIELDS' in champs: return 'OK',[(f'1 (UID {u})'.encode(),h) for u,h in entetes.items()]
                bodies.append(ids);return 'OK',[(f'1 (UID {ids})'.encode(),entetes[int(ids)]+b'Contenu fictif')]
        r=self.c.Lecteur();r.boite=Boite()
        r.filtre_recherche=lambda h:self.c._entete_recente(h,now-timedelta(minutes=10),now)
        rows=r._lire('INBOX',[1,2],False)
        self.assertEqual(['2'],bodies);self.assertEqual([2],[x['uid'] for x in rows])

    def test_lecteur_principal_garde_comportement_sans_filtre_direct(self):
        r=self.c.Lecteur()
        self.assertIsNone(getattr(r,'filtre_recherche',None))
        self.assertIsNone(getattr(r,'controle_recherche',None))

    def test_arret_avant_fetch_ne_fait_aucune_requete(self):
        r=self.c.Lecteur()
        from unittest.mock import Mock
        r.boite=Mock()
        def stop(): raise self.c.RechercheInterrompue()
        r.controle_recherche=stop
        with self.assertRaises(self.c.RechercheInterrompue):r._lire('INBOX',[1],False)
        r.boite.uid.assert_not_called()

    def test_date_invalide_ou_absente_reste_a_classer(self):
        import email
        from datetime import datetime,timezone,timedelta
        now=datetime.now(timezone.utc)
        for h in ['', 'Date: inconnue', 'Date: Thu, 15 Oct 2026 12:00:00']:
            self.assertTrue(self.c._entete_recente(email.message_from_string(h),now-timedelta(minutes=10),now))

    def test_connexion_auth_echouee_reste_fermable(self):
        from unittest.mock import Mock
        boite=Mock();boite.login.side_effect=self.c.imaplib.IMAP4.error('échec fictif')
        r=self.c.Lecteur()
        with patch.object(self.c.imaplib,'IMAP4_SSL',return_value=boite):
            with self.assertRaises(self.c.imaplib.IMAP4.error):r._connecter()
        r.fermer();boite.logout.assert_called_once()

    def test_annulation_entre_entetes_et_corps_ne_lit_pas_le_corps(self):
        from unittest.mock import Mock
        arret=threading.Event();r=self.c.Lecteur()
        def uid(*args):
            arret.set()
            return 'OK',[(b'1 (UID 1)',b'From: Instagram <security@mail.instagram.com>\r\nMessage-ID: <fictif>\r\n\r\n')]
        r.boite=Mock();r.boite.uid.side_effect=uid
        def check():
            if arret.is_set():raise self.c.RechercheInterrompue()
        r.controle_recherche=check
        with self.assertRaises(self.c.RechercheInterrompue):r._lire('INBOX',[1],False)
        self.assertEqual(1,r.boite.uid.call_count)

    def test_scan_preannule_ne_connecte_pas_et_ferme(self):
        from unittest.mock import Mock
        r=Mock();event=threading.Event();event.set()
        with patch.object(self.c,'Lecteur',return_value=r):
            with self.assertRaises(self.c.RechercheInterrompue):self.c._scan_recent_sync({'fictif@example.invalid'},10,event)
        r._connecter.assert_not_called();r.fermer.assert_called_once()
