"""Modèles synthétiques uniquement : aucun mail, alias ou code opérationnel."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from test_codes_reliable import load_codes


class Confirmation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 17, 10, 20, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now
        self.c.IMAP_USER = 'boite@example.invalid'
        self.c.SECURITES = True
        self.state = {'codes': [], 'n': 0, 'faits': {}, 'sante': {}}
        self.c._etat = lambda: self.state
        self.c._sauver = lambda: None
        self.c._proprietaire = lambda _: {'canal_id':'200'}
        self.c._admin = AsyncMock()
        self.c._deps = {'compte_alias_uid': lambda uid, alias: 'compte.fictif' if uid == '100' and alias == 'alias@example.invalid' else ''}

    def mail(self, html=False, mid='message-a', preuve=True, corps=None):
        m = EmailMessage()
        m['From'] = 'Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>'
        m['To'] = 'Masquer mon adresse <boite@example.invalid>'
        m['Subject'] = 'Confirmer l’adresse e-mail'
        m['Date'] = format_datetime(self.now)
        m['Message-ID'] = '<' + mid + '@example.invalid>'
        if preuve:
            m['Authentication-Results'] = 'mx.google.com; dkim=pass header.d=mail.instagram.com'
        body = corps or 'Bonjour compte.fictif,\nConfirmez votre adresse e-mail avec ce code :\n111111\nCe message a été envoyé à alias@example.invalid.\nRéférence postale 75001.'
        if html:
            m.set_content('<html><body>' + ''.join('<p>'+l+'</p>' for l in body.splitlines()) + '</body></html>', subtype='html')
        else:
            m.set_content(body)
        return m

    async def ingester(self, m, connus=None):
        bilan = dict(donnes=0, gardes=0, orphelins=0, alertes=0)
        await self.c._traiter_un(None, {'msg':m, 'dossier':'INBOX'}, self.state, connus if connus is not None else set(), '', bilan)

    async def servir(self, uid='100', usage='verification'):
        sortie = []
        async def dire(t): sortie.append(t)
        resultat = await self.c._servir({'alias@example.invalid'}, dire, 'u|'+uid, duree=0, usage=usage,
                                        relire=lambda: {'alias@example.invalid'})
        return resultat, '\n'.join(sortie)

    def test_fr_html_et_texte_alias_corps_type_distinct(self):
        for html in (False, True):
            r = self.c.classer_mail(self.mail(html=html))
            self.assertEqual(('donner','verification','alias@example.invalid','compte.fictif'),
                             (r['decision'],r['type'],r['alias'],r['compte']))
            self.assertTrue(r['confirmation_adresse'])
            self.assertEqual('111111',r['code'])

    def test_provenance_alias_et_numero_parasite_refuses(self):
        cas = [self.mail(preuve=False), self.mail(corps='Bonjour compte.fictif,\nConfirmez votre adresse e-mail.\nRéférence 75001.\nalias@example.invalid')]
        faux = self.mail(); faux.replace_header('From', 'Instagram <faux@example.invalid>'); cas.append(faux)
        conflit = self.mail(); conflit.replace_header('To','autre@example.invalid'); cas.append(conflit)
        deux = self.mail(corps='Bonjour compte.fictif,\nConfirmez votre adresse e-mail avec ce code :\n111111\n222222\nalias@example.invalid'); cas.append(deux)
        for msg in cas:
            self.assertNotEqual('donner',self.c.classer_mail(msg)['decision'])

    async def test_compte_uid_exact_et_pas_connexion(self):
        await self.ingester(self.mail())
        self.assertNotIn('111111', (await self.servir(uid='101'))[1])
        self.assertNotIn('111111', (await self.servir(usage='connexion'))[1])
        self.c._deps['compte_alias_uid'] = lambda *_: 'autre.fictif'
        self.assertIn('compte exact', (await self.servir())[1])
        self.c._deps['compte_alias_uid'] = lambda *_: 'compte.fictif'
        self.assertIn('111111', (await self.servir())[1])

    async def test_renvoi_meme_valeur_message_id_distinct(self):
        connus = set()
        a, b = self.mail(mid='a'), self.mail(mid='b')
        await self.ingester(a, connus)
        self.assertIn('111111', (await self.servir())[1])
        await self.ingester(a, connus)
        await self.ingester(b, connus)
        self.assertEqual(2,len(self.state['codes']))
        self.assertIn('111111', (await self.servir())[1])
        self.assertEqual('<b@example.invalid>',self.state['codes'][-1]['mid'])

    async def test_ancien_refuse_et_securite_autre_partie(self):
        m = self.mail(); m.replace_header('Date',format_datetime(self.now-timedelta(minutes=12)))
        await self.ingester(m)
        rendu = (await self.servir())[1]
        self.assertNotIn('111111',rendu)
        self.assertIn('trop ancien',rendu)
        for texte in ('Use this code to reset your password.', 'TOTP secret key', 'Ajoutez une nouvelle adresse e-mail.'):
            m = self.mail(); m.add_alternative('<p>'+texte+'</p>',subtype='html')
            self.assertNotEqual('donner',self.c.classer_mail(m)['decision'])

    async def test_code_sans_argument_declenche_parcours_prive(self):
        self.c.actif = lambda: True
        self.c._adresses_membre = lambda _: {'alias@example.invalid','second@example.invalid'}
        self.c._demander_scan = lambda *_: None
        self.c.vue_mon_code = lambda: 'bouton-fictif'
        self.c._servir = AsyncMock(return_value='rien')
        m = SimpleNamespace(author=SimpleNamespace(id=100,send=AsyncMock()),reply=AsyncMock())
        await self.c._commande_salon_commun(m,False,False)
        self.c._servir.assert_awaited_once()
        self.assertEqual('auto',self.c._servir.call_args.kwargs['usage'])
        self.assertEqual({'alias@example.invalid','second@example.invalid'},self.c._servir.call_args.args[0])

    async def test_refus_provenance_explicite_sans_code(self):
        m = self.mail(preuve=False)
        m.replace_header('To', 'alias@example.invalid')
        await self.ingester(m)
        rendu = (await self.servir())[1]
        self.assertNotIn('111111', rendu)
        self.assertIn('provenance', rendu)
