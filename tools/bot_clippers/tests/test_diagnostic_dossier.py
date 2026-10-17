"""Diagnostic sans données réelles, sans réseau et sans initialisation implicite."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diagnostic_dossier as d


class Diagnostic(unittest.IsolatedAsyncioTestCase):
    async def test_refus_avant_lecture_et_sans_message(self):
        for author, owner, admins, guild in [(2, 1, {'2'}, True), (1, 1, set(), True), (1, 1, {'1'}, False)]:
            msg = SimpleNamespace(author=SimpleNamespace(id=author, send=AsyncMock()),
                                  guild=SimpleNamespace(owner_id=owner) if guild else None)
            with patch.object(d, 'rapport') as lecture:
                self.assertTrue(await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', '/absent', admins))
                lecture.assert_not_called()
                msg.author.send.assert_not_awaited()

    def test_absence_ne_cree_rien_et_ne_vaut_pas_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            rapport = d.rapport(tmp, '3', 'Sarah', '4')
            self.assertIsNone(rapport['processus']['comptes_observes'])
            self.assertIsNone(rapport['reservation_onboarding_nombre'])
            self.assertEqual([], list(Path(tmp).iterdir()))

    def test_projection_sans_secrets_et_sans_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            poison = 'SECRET-FICTIF-NE-PAS-EXPORTER'
            (root / 'onboarding.json').write_text(json.dumps({'clippers': {'3': {
                'creatrice': poison, 'comptes': [poison], 'mail': poison, 'mdp': poison, 'tel': poison, 'token': poison}}}))
            (root / 'parcours.json').write_text(json.dumps({'3': {'messages': {'1': '123', '2': poison}, 'notes': poison}}))
            dbpath = root / 'process_clippeur.sqlite3'
            with sqlite3.connect(dbpath) as db:
                db.executescript('CREATE TABLE histories(uid TEXT,evidence TEXT); CREATE TABLE accounts(id TEXT,uid TEXT,status TEXT,evidence TEXT); CREATE TABLE jobs(key TEXT,data TEXT);')
                db.execute('INSERT INTO accounts VALUES(?,?,?,?)', ('fictif', '3', 'unknown', poison))
                db.execute('INSERT INTO jobs VALUES(?,?)', ('message-compte1:3', json.dumps({'message_id':'456', 'salon':'789', 'token':poison, 'etat':'incertain'})))
            avant = {p.name:p.read_bytes() for p in root.iterdir()}
            rapport = d.rapport(root, '3', 'Sarah', '4')
            self.assertNotIn(poison, json.dumps(rapport))
            self.assertEqual({'unknown':1}, rapport['processus']['comptes_observes'])
            self.assertIsNone(rapport['processus']['total_crees_a_vie'])
            self.assertEqual('456', rapport['processus']['message_compte1_id'])
            self.assertFalse(rapport['onboarding']['choix_conforme'])
            self.assertEqual(avant, {p.name:p.read_bytes() for p in root.iterdir()})

    async def test_proprietaire_recoit_seulement_fichier_prive(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg = SimpleNamespace(author=SimpleNamespace(id=1, send=AsyncMock()), guild=SimpleNamespace(owner_id=1))
            await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', tmp, {'1'})
            msg.author.send.assert_awaited_once()
            self.assertEqual({'file'}, set(msg.author.send.call_args.kwargs))
            data = json.loads(msg.author.send.call_args.kwargs['file'].fp.getvalue())
            self.assertEqual('absente_ou_illisible', data['parcours']['lecture'])

    def test_affectations_exporte_les_roles_sans_sante_inventee_ni_acces(self):
        poison = 'secret-fictif'
        result = d.affectations({'comptes': ['growth.prv', 'real.backstage'], 'acces': [
            {'handle': 'growth.prv', 'role_confirme': 'croissance', 'mdp': poison},
            {'handle': 'real.backstage', 'role_confirme': 'prive', 'prive': True, 'mail': poison}]},
            {'ordre': 'prive3', 'ordre_confirme': {'valeur': 'prive2', 'reference': poison}})
        self.assertEqual(['growth.prv', 'real.backstage'], result['comptes'])
        self.assertEqual('croissance', result['acces_roles'][0]['role_confirme'])
        self.assertEqual('prive2', result['ordre_confirme'])
        self.assertNotIn(poison, json.dumps(result))
        self.assertNotIn('GOOD', json.dumps(result))

    def test_corruption_et_symlink_restent_inconnus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'cible').write_text('invalide')
            (root / 'process_clippeur.sqlite3').symlink_to(root / 'cible')
            self.assertIsNone(d.registre(root / 'process_clippeur.sqlite3', '3')['comptes_observes'])
            self.assertIsNone(d.lire(root / 'cible'))

    def test_historique_avec_compte_inconnu_ne_prouve_pas_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'process_clippeur.sqlite3'
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE histories(uid TEXT,evidence TEXT); CREATE TABLE accounts(uid TEXT,status TEXT); CREATE TABLE jobs(key TEXT,data TEXT); INSERT INTO histories VALUES('3','preuve-fictive'); INSERT INTO accounts VALUES('3','unknown');")
            self.assertIsNone(d.registre(path, '3')['total_crees_a_vie'])

    async def test_diagnostic_lecteurs_frais_joint_seulement_au_fichier_prive(self):
        import remise_compte1
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'parcours.json').write_text(json.dumps({'3':{'salon_id':'99'}}))
            guild=SimpleNamespace(id=7, owner_id=1, fetch_channel=AsyncMock())
            guild.fetch_channel.return_value=SimpleNamespace(guild=guild)
            msg=SimpleNamespace(author=SimpleNamespace(id=1, send=AsyncMock()), guild=guild)
            with patch.object(remise_compte1, 'diagnostic_lecteurs', return_value={'lecteurs':[{'uid':'5','autorise':False}]}) as inspecter:
                await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', root, {'1'})
            guild.fetch_channel.assert_awaited_once_with(99)
            inspecter.assert_called_once()
            fichier=msg.author.send.call_args.kwargs['file']
            contenu=json.loads(fichier.fp.getvalue())
            self.assertEqual('reussie', contenu['lecteurs_discord']['lecture'])
            self.assertEqual('5', contenu['lecteurs_discord']['lecteurs'][0]['uid'])

    async def test_creatrice_divergente_utilise_mandat_reel_et_non_attendu(self):
        import remise_compte1
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'parcours.json').write_text(json.dumps({'3': {'salon_id': '99', 'creatrice': 'Chloé'}}))
            membres = [SimpleNamespace(id=i, roles=[], bot=False) for i in (1, 3, 4, 5, 9)]
            guild = SimpleNamespace(id=7, owner_id=1, me=membres[-1], members=membres,
                                    default_role=SimpleNamespace(id=0), chunked=True, fetch_channel=AsyncMock())
            salon = SimpleNamespace(guild=guild, permissions_for=lambda m: SimpleNamespace(view_channel=m.id in (1, 3, 5, 9)))
            guild.fetch_channel.return_value = salon
            msg = SimpleNamespace(author=SimpleNamespace(id=1, send=AsyncMock()), guild=guild)
            with patch.object(remise_compte1.equipes_tl, 'tl_par_va', return_value={}), patch.object(
                    remise_compte1.equipes_tl, '_fiches', return_value={'4': {'chef': 'Sarah'}, '5': {'chef': 'Chloé'}}):
                await d.commande(msg, '!diagnostic-dossier 3 Sarah 4', root, {'1'})
                reel = remise_compte1.diagnostic_lecteurs(guild, salon, '3', 'Chloé', {'1'}, lambda m: False)
                errone = remise_compte1.diagnostic_lecteurs(guild, salon, '3', 'Sarah', {'1'}, lambda m: False)
            data = json.loads(msg.author.send.call_args.kwargs['file'].fp.getvalue())
            diag = data['lecteurs_discord']
            self.assertEqual('Sarah', data['attendu']['creatrice'])
            self.assertEqual('Sarah', diag['creatrice_attendue'])
            self.assertEqual('parcours', diag['source_creatrice'])
            self.assertTrue(diag['creatrice_divergente'])
            self.assertEqual('5', diag['tl_effectif'])
            self.assertEqual(reel['lecteurs'], diag['lecteurs'])
            self.assertTrue(diag['remise_autorisee'])
            self.assertFalse(errone['remise_autorisee'])
