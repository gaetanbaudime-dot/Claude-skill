"""Commande bornée : données et Discord fictifs, journal et SQLite temporaires."""
import asyncio
from copy import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import discord
import organisation_ciblee as org
from process_store import Store
from test_process_onboarding import charger


class Objet(N):
    __hash__ = object.__hash__
    __eq__ = object.__eq__


class OrganisationCiblee(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fichiers = {
            'equipes': {'42': {'creatrice':'Fictive', 'salon_id':'99'}, '90': {'chef':'Fictive'}},
            'pipeline': {'etats': {'42': {'etat':'valide', 'score_quiz':'10 / 10'}}},
            'parcours': {'42': {'creatrice':'Fictive', 'salon_id':'99', 'messages': {'1':'123'}}},
            'onboarding': {'clippers': {'42': {'creatrice':'Fictive', 'acces':[{'mdp':'SECRET_FICTIF'}]}}},
            'sortis': [],
        }
        self.ecrire()
        self.store = Store(self.root/'process_clippeur.sqlite3')
        self.store.reconcile('42', [], 'preuve-fictive')
        self.store.reserve('42', ['compte_fictif'])
        self.origine = {p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        def role(ident, nom, position):
            return Objet(id=ident, name=nom, managed=False, position=position, permissions=discord.Permissions.none())
        self.defaut, self.clippeur, self.creatrice, self.role_bot = (
            role(0, '@everyone', 0), role(2, 'Clippeur', 2), role(3, 'Fictive', 3), role(4, 'Bot', 10))
        self.roles = [self.defaut, self.clippeur, self.creatrice, self.role_bot]
        self.membre = Objet(id=42, bot=False, roles=[self.defaut], guild_permissions=N(administrator=False))
        self.tl = Objet(id=90, bot=False, roles=[self.defaut])
        self.autre = Objet(id=43, bot=False, roles=[self.clippeur])
        self.bot = Objet(id=91, bot=True, roles=[self.role_bot], guild_permissions=N(manage_roles=True))
        self.categorie = Objet(id=50, name='Fictive', type=discord.ChannelType.category,
                              permissions_for=lambda m:N(manage_channels=True))
        self.salon = Objet(id=99, name='fictif', topic='clipper-uid:42 · Salon personnel', category_id=10,
                          type=discord.ChannelType.text, send=AsyncMock())
        self.salon.overwrites = {
            self.defaut: discord.PermissionOverwrite(view_channel=False),
            self.tl: discord.PermissionOverwrite(attach_files=False, embed_links=True),
            self.autre: discord.PermissionOverwrite(view_channel=False, add_reactions=False),
        }
        self.salon.overwrites_for = lambda m:copy(self.salon.overwrites.get(m, discord.PermissionOverwrite()))
        def permissions(m):
            if m.id == 91:
                return N(view_channel=True, send_messages=True, read_message_history=True,
                         manage_channels=True, manage_roles=True)
            explicites = self.salon.overwrites_for(m)
            roles = {r.id for r in getattr(m, 'roles', [])}
            visible = explicites.view_channel if explicites.view_channel is not None else ({2, 3} <= roles)
            return N(view_channel=visible, send_messages=explicites.send_messages is not False,
                     read_message_history=explicites.read_message_history is not False)
        self.salon.permissions_for = permissions
        async def historique(**kw):
            if False: yield None
        self.salon.history = historique
        async def ajouter(r, **kw): self.membre.roles.append(r)
        async def deplacer(**kw): self.salon.category_id = kw['category'].id; return self.salon
        async def ouvrir(cible, **kw): self.salon.overwrites[cible] = copy(kw['overwrite'])
        self.ajouter, self.deplacer, self.ouvrir = ajouter, deplacer, ouvrir
        self.membre.add_roles = AsyncMock(side_effect=ajouter)
        self.salon.edit = AsyncMock(side_effect=deplacer)
        self.salon.set_permissions = AsyncMock(side_effect=ouvrir)
        self.guild = Objet(id=77, owner_id=1, me=self.bot, default_role=self.defaut,
            fetch_channels=AsyncMock(side_effect=lambda:[self.categorie, self.salon]),
            fetch_roles=AsyncMock(side_effect=lambda:list(self.roles)),
            fetch_member=AsyncMock(side_effect=lambda uid:{42:self.membre, 90:self.tl}[uid]))
        self.salon.guild = self.guild
        self.categorie.guild = self.guild
        self.message = N(id=100, guild=self.guild, author=N(id=1, send=AsyncMock()), reply=AsyncMock())
        self.mapping = Mock(return_value={'42':'90'})

    def ecrire(self):
        for nom, valeur in self.fichiers.items():
            (self.root/(nom+'.json')).write_text(json.dumps(valeur))

    async def appeler(self, mode='appliquer'):
        await org.commande(self.message, ('!organisation 42 ' + mode).strip(), self.root, {'1'}, self.mapping)
        return self.message.author.send.await_args.args[0]

    def aucun_effet(self):
        self.membre.add_roles.assert_not_awaited()
        self.salon.edit.assert_not_awaited()
        self.salon.set_permissions.assert_not_awaited()
        self.salon.send.assert_not_awaited()

    def sources_inchangees(self):
        for nom, contenu in self.origine.items():
            self.assertEqual(contenu, (self.root/nom).read_bytes(), nom)
        self.assertEqual({'reserved':1}, self.store.counts('42'))
        self.salon.send.assert_not_awaited()
        self.message.reply.assert_not_awaited()

    def journal(self):
        return [json.loads(l) for l in (self.root/'organisation-42.jsonl').read_text().splitlines()]

    async def test_diagnostic_par_defaut_sans_ecriture_ni_envoi_au_clippeur(self):
        texte = await self.appeler('')
        self.assertIn('Diagnostic organisation', texte)
        for mention in ('<@&2>', '<@&3>', '<#50>', '<@90>'):
            self.assertIn(mention, texte)
        self.assertNotIn('SECRET_FICTIF', texte)
        self.aucun_effet()
        self.sources_inchangees()
        self.assertEqual(set(self.origine), {p.name for p in self.root.iterdir()})

    async def test_application_bornee_preserve_permissions_journal_et_rejeu(self):
        avant_autre = self.salon.overwrites_for(self.autre).pair()
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.assertEqual({0, 2, 3}, {r.id for r in self.membre.roles})
        self.assertEqual(50, self.salon.category_id)
        kwargs = self.salon.edit.await_args.kwargs
        self.assertFalse(kwargs['sync_permissions'])
        droits = self.salon.overwrites_for(self.tl)
        self.assertTrue(droits.view_channel and droits.send_messages and droits.read_message_history)
        self.assertFalse(droits.attach_files)
        self.assertTrue(droits.embed_links)
        self.assertEqual(avant_autre, self.salon.overwrites_for(self.autre).pair())
        self.assertFalse(self.salon.permissions_for(self.autre).view_channel)
        self.assertEqual('termine', self.journal()[-1]['etat'])
        self.assertEqual({'message':'100', 'par':'1', 'serveur':'77'}, self.journal()[-1]['source'])
        self.assertEqual(4, sum(e['etat']=='intention' for e in self.journal()))
        self.assertEqual(4, sum(e['etat']=='confirme' for e in self.journal()))
        self.assertEqual(0o600, (self.root/'organisation-42.jsonl').stat().st_mode & 0o777)
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.assertEqual(2, self.membre.add_roles.await_count)
        self.salon.edit.assert_awaited_once()
        self.salon.set_permissions.assert_awaited_once()
        self.sources_inchangees()
        self.assertNotIn('SECRET_FICTIF', (self.root/'organisation-42.jsonl').read_text())

    async def test_historique_prive_ou_illisible_bloque_avant_tout_effet(self):
        async def prive(**kw): yield N(content='SECRET_FICTIF')
        self.salon.history = prive
        self.assertIn('Historique privé présent ou illisible', await self.appeler())
        self.aucun_effet()
        self.assertFalse((self.root/'organisation-42.jsonl').exists())
        self.salon.history = Mock(side_effect=discord.Forbidden(N(status=403, reason='fictif'), 'SECRET_FICTIF'))
        self.assertIn('Historique privé présent ou illisible', await self.appeler())
        self.aucun_effet()

    async def verifier_refus_clippeur(self, permission, deja_organise):
        restriction = discord.PermissionOverwrite(view_channel=True, send_messages=True,
            read_message_history=True, attach_files=False, add_reactions=False)
        setattr(restriction, permission, False)
        self.salon.overwrites[self.membre] = restriction
        avant = restriction.pair()
        autres_avant = self.salon.overwrites_for(self.autre).pair()
        if deja_organise:
            self.membre.roles.extend([self.clippeur, self.creatrice])
            self.salon.category_id = self.categorie.id
            self.salon.overwrites[self.tl].update(view_channel=True, send_messages=True, read_message_history=True)
        texte = await self.appeler()
        self.assertIn('Lecture, écriture ou historique refusé', texte)
        self.assertNotIn('Organisation vérifiée', texte)
        journal = self.root/'organisation-42.jsonl'
        if deja_organise:
            self.aucun_effet()
            self.assertFalse(journal.exists())
        else:
            self.assertTrue(journal.exists())
            self.assertNotIn('termine', {e['etat'] for e in self.journal()})
            self.assertEqual('non_confirme', self.journal()[-1]['etat'])
        self.assertEqual(avant, self.salon.overwrites_for(self.membre).pair())
        self.assertEqual(autres_avant, self.salon.overwrites_for(self.autre).pair())
        self.assertTrue(all(a.args[0].id == self.tl.id for a in self.salon.set_permissions.await_args_list))
        self.sources_inchangees()

    async def test_ecriture_refusee_apres_reparation_ne_marque_pas_succes(self):
        await self.verifier_refus_clippeur('send_messages', deja_organise=False)

    async def test_lecture_refusee_apres_reparation_ne_marque_pas_succes(self):
        await self.verifier_refus_clippeur('view_channel', deja_organise=False)

    async def test_historique_refuse_apres_reparation_ne_marque_pas_succes(self):
        await self.verifier_refus_clippeur('read_message_history', deja_organise=False)

    async def test_ecriture_refusee_organisation_deja_en_place_ne_marque_pas_succes(self):
        await self.verifier_refus_clippeur('send_messages', deja_organise=True)

    async def test_historique_refuse_organisation_deja_en_place_ne_marque_pas_succes(self):
        await self.verifier_refus_clippeur('read_message_history', deja_organise=True)

    async def test_historique_deja_visible_tl_pas_de_nouvelle_exposition(self):
        self.salon.overwrites[self.tl].update(view_channel=True, read_message_history=True, send_messages=False)
        self.salon.history = Mock(side_effect=AssertionError('Lecture inutile'))
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.salon.history.assert_not_called()
        self.sources_inchangees()

    async def test_timeout_apres_deplacement_accepte_relecture_evite_second_patch(self):
        async def timeout(**kw):
            await self.deplacer(**kw)
            raise TimeoutError('SECRET_FICTIF')
        self.salon.edit.side_effect = timeout
        self.assertIn('non confirmé', await self.appeler())
        self.salon.set_permissions.assert_not_awaited()
        self.assertEqual('non_confirme', self.journal()[-1]['etat'])
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.salon.edit.assert_awaited_once()
        self.assertEqual(2, self.membre.add_roles.await_count)
        self.sources_inchangees()

    async def test_timeout_apres_acces_tl_accepte_relecture_evite_second_put(self):
        async def timeout(cible, **kw):
            await self.ouvrir(cible, **kw)
            raise TimeoutError()
        self.salon.set_permissions.side_effect = timeout
        self.assertIn('non confirmé', await self.appeler())
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.salon.set_permissions.assert_awaited_once()
        self.sources_inchangees()

    async def test_role_creatrice_refuse_apres_clippeur_reprise_partielle(self):
        async def ajouter(r, **kw):
            if r.id == 3: raise discord.Forbidden(N(status=403, reason='fictif'), 'SECRET_FICTIF')
            await self.ajouter(r, **kw)
        self.membre.add_roles.side_effect = ajouter
        self.assertIn('non confirmé', await self.appeler())
        self.assertEqual({0, 2}, {r.id for r in self.membre.roles})
        self.salon.edit.assert_not_awaited()
        self.membre.add_roles.side_effect = self.ajouter
        self.assertIn('Organisation vérifiée', await self.appeler())
        self.assertEqual([2, 3, 3], [a.args[0].id for a in self.membre.add_roles.await_args_list])
        self.sources_inchangees()

    async def test_journal_indisponible_aucune_mutation_discord(self):
        with patch.object(org, 'journaliser', side_effect=OSError('SECRET_FICTIF')):
            self.assertIn('non confirmé', await self.appeler())
        self.aucun_effet()
        self.assertNotIn('SECRET_FICTIF', str(self.message.author.send.call_args_list))

    async def test_non_proprietaire_ou_non_admin_sans_lecture(self):
        with patch.object(org, 'sources') as lire:
            self.message.author.id = 2
            await org.commande(self.message, '!organisation 42 appliquer', self.root, {'2'}, self.mapping)
            self.message.author.id = 1
            await org.commande(self.message, '!organisation 42 appliquer', self.root, set(), self.mapping)
        lire.assert_not_called()
        self.guild.fetch_channels.assert_not_awaited()
        self.message.author.send.assert_not_awaited()

    async def test_affectation_contradictoire_et_sortie_bloquent(self):
        for nom in ('parcours', 'onboarding', 'pipeline', 'sortis'):
            original = json.dumps(self.fichiers)
            if nom == 'parcours': self.fichiers[nom]['42']['creatrice'] = 'Autre'
            if nom == 'onboarding': self.fichiers[nom]['clippers']['42']['creatrice'] = 'Autre'
            if nom == 'pipeline': self.fichiers[nom]['etats']['42']['creatrice_attendue'] = 'Autre'
            if nom == 'sortis': self.fichiers[nom] = [{'uid':'42'}]
            self.ecrire()
            self.assertIn('retenue', await self.appeler())
            self.aucun_effet()
            self.fichiers = json.loads(original)
        self.ecrire()

    async def test_source_absente_ou_identite_salon_ambigue_aucune_creation(self):
        (self.root/'parcours.json').unlink()
        self.assertIn('retenue', await self.appeler())
        self.ecrire()
        self.salon.topic = 'clipper-uid:42 · clipper-uid:43'
        self.assertIn('unique non confirmé', await self.appeler())
        self.aucun_effet()

    async def test_role_puissant_ou_hierarchie_insuffisante_retient(self):
        self.creatrice.permissions.administrator = True
        self.assertIn('permissions administratives', await self.appeler())
        self.creatrice.permissions.administrator = False
        self.role_bot.position = 1
        self.assertIn('Hiérarchie', await self.appeler())
        self.aucun_effet()

    async def test_ancien_clippeur_ou_rang_seul_retenu_sans_mutation(self):
        for nom in ('Ancien Clippeur', 'Clippeur confirmé', 'Rookie', 'Elite'):
            with self.subTest(nom=nom):
                self.clippeur.name = nom
                self.assertIn('rôles attendus absents ou ambigus', await self.appeler())
                self.aucun_effet()
        self.assertFalse((self.root/'organisation-42.jsonl').exists())
        self.sources_inchangees()

    async def test_changement_affectation_durant_lecture_retenu(self):
        async def lire():
            self.fichiers['equipes']['42']['creatrice'] = 'Autre'
            self.ecrire()
            return list(self.roles)
        self.guild.fetch_roles.side_effect = lire
        self.assertIn('retenue', await self.appeler())
        self.aucun_effet()

    async def test_permissions_modifiees_pendant_deplacement_interrompent_suite(self):
        async def deplacer(**kw):
            await self.deplacer(**kw)
            self.salon.overwrites[self.autre].add_reactions = True
            return self.salon
        self.salon.edit.side_effect = deplacer
        self.assertIn('permissions non confirmés', await self.appeler())
        self.salon.set_permissions.assert_not_awaited()
        self.assertEqual('non_confirme', self.journal()[-1]['etat'])

    async def test_deux_commandes_meme_uid_serialisees_sans_double_mutation(self):
        entre, libere = asyncio.Event(), asyncio.Event()
        async def deplacer(**kw):
            entre.set()
            await libere.wait()
            return await self.deplacer(**kw)
        self.salon.edit.side_effect = deplacer
        premier = asyncio.create_task(self.appeler())
        await asyncio.wait_for(entre.wait(), 2)
        second = asyncio.create_task(self.appeler())
        await asyncio.sleep(0)
        libere.set()
        await asyncio.gather(premier, second)
        self.salon.edit.assert_awaited_once()
        self.salon.set_permissions.assert_awaited_once()
        self.assertEqual(2, self.membre.add_roles.await_count)
        self.sources_inchangees()

    async def test_dispatch_vers_commande_bornee_sans_parcours(self):
        ns = {'ADMIN_IDS':{'1'}, 'DONNEES':self.root, 'equipes_tl':N(tl_par_va=self.mapping)}
        fn = charger('commande_admin', ns)
        self.assertTrue(await fn(self.message, '!organisation 42'))
        self.assertIn('Diagnostic organisation', self.message.author.send.await_args.args[0])
        self.aucun_effet()

    def test_module_ne_depend_pas_du_parcours_des_comptes(self):
        import ast
        arbre = ast.parse(Path(org.__file__).read_text())
        imports = {n.module for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom)}
        imports |= {alias.name for n in ast.walk(arbre) if isinstance(n, ast.Import) for alias in n.names}
        self.assertFalse(imports & {'onboarding', 'parcours', 'process_adapters', 'process_livraison', 'remise_compte1'})

    def test_permissions_discord_reelles_utilisent_roles_relus_sans_changer_cache(self):
        class Serveur:
            id, owner_id = 77, 1
            @property
            def default_role(self): return self._roles[77]
            def get_role(self, rid): return self._roles.get(rid)
        guild = Serveur()
        def role(rid, permissions):
            return discord.Role(guild=guild, state=N(), data={
                'id':str(rid), 'name':'fictif', 'permissions':str(permissions.value)})
        defaut = role(77, discord.Permissions.none())
        ancien = role(9, discord.Permissions(view_channel=True, read_message_history=True))
        actuel = role(9, discord.Permissions.none())
        guild._roles = {77:defaut, 9:ancien}
        canal = discord.TextChannel(guild=guild, state=N(), data={
            'id':'99', 'name':'fictif', 'type':0, 'position':0, 'permission_overwrites':[]})
        tl = N(id=90, _roles=discord.utils.SnowflakeList([9]), is_timed_out=lambda:False)
        self.assertTrue(canal.permissions_for(tl).view_channel)
        vue = org.canal_avec_roles_frais(canal, [defaut, actuel])
        self.assertFalse(vue.permissions_for(tl).view_channel)
        self.assertTrue(canal.permissions_for(tl).view_channel)


if __name__ == '__main__':
    unittest.main()
