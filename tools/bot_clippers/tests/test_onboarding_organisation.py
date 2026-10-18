"""Organisation Discord fictive : reprises, permissions et absence de faux succès."""
from types import SimpleNamespace as N
import unittest
from unittest.mock import AsyncMock, patch

import discord
import onboarding_discord as accueil
import test_process_onboarding as orchestration
from test_process_onboarding import charger


class Organisation(unittest.IsolatedAsyncioTestCase):
    setUp = orchestration.OnboardingTests.setUp
    contexte = orchestration.OnboardingTests.contexte

    async def test_salon_identifie_deplace_sans_synchroniser_ni_recreer(self):
        for journalise in (False, True):
            with self.subTest(journalise=journalise):
                salon = N(id=99, topic='clipper-uid:42', category_id=10,
                          overwrites={'fictif': 'prive'})
                categorie = N(id=50)
                async def deplacer(**kw):
                    salon.category_id = kw['category'].id
                    return salon
                salon.edit = AsyncMock(side_effect=deplacer)
                guild = N(fetch_channels=AsyncMock(return_value=[salon]))
                creation = AsyncMock(side_effect=AssertionError('Aucune création'))
                if journalise:
                    self.store.put('salon:42', {'salon_id': '99'})
                fn = charger('assurer_salon_perso', {'_assurer_salon_perso': creation})
                for _ in range(2):
                    resultat, cree, erreur = await fn(guild, N(id=42), categorie, 'Fictive', 'test')
                    self.assertIs(salon, resultat)
                    self.assertFalse(cree)
                    self.assertEqual('', erreur)
                salon.edit.assert_awaited_once_with(category=categorie, sync_permissions=False, reason='test')
                self.assertEqual({'fictif': 'prive'}, salon.overwrites)
                creation.assert_not_awaited()

    async def test_deplacement_accepte_reponse_perdue_repris_sans_seconde_mutation(self):
        salon = N(id=99, topic='clipper-uid:42', category_id=10)
        async def deplacer(**kw):
            salon.category_id = 50
            raise TimeoutError('réponse perdue')
        salon.edit = AsyncMock(side_effect=deplacer)
        guild = N(fetch_channels=AsyncMock(return_value=[salon]))
        creation = AsyncMock()
        fn = charger('assurer_salon_perso', {'_assurer_salon_perso': creation})
        self.assertIn('non confirmé', (await fn(guild, N(id=42), N(id=50), 'Fictive', 'test'))[2])
        self.assertEqual('', (await fn(guild, N(id=42), N(id=50), 'Fictive', 'test'))[2])
        salon.edit.assert_awaited_once()
        creation.assert_not_awaited()

    async def test_deplacement_refuse_conserve_identite_et_rejoue_le_meme_salon(self):
        salon = N(id=99, topic='clipper-uid:42', category_id=10)
        salon.edit = AsyncMock(side_effect=discord.Forbidden(N(status=403, reason='fictif'), 'refus'))
        guild = N(fetch_channels=AsyncMock(return_value=[salon]))
        creation = AsyncMock()
        fn = charger('assurer_salon_perso', {'_assurer_salon_perso': creation})
        self.assertIn('non confirmé', (await fn(guild, N(id=42), N(id=50), 'Fictive', 'test'))[2])
        self.assertEqual('99', self.store.get('salon:42')['salon_id'])
        async def deplacer(**kw):
            salon.category_id = 50
            return salon
        salon.edit.side_effect = deplacer
        self.assertEqual('', (await fn(guild, N(id=42), N(id=50), 'Fictive', 'test'))[2])
        self.assertEqual(2, salon.edit.await_count)
        creation.assert_not_awaited()

    async def test_categorie_ou_information_absente_ambigue_bloque_avant_droits(self):
        for categorie in (None, N(id=50, text_channels=[]),
                          N(id=50, text_channels=[N(name='infos'), N(name='ℹ️-autre')])):
            ns, membre, salon, _ = self.contexte()
            ns['categorie_de_creatrice'] = lambda *a: categorie
            resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
            self.assertIn('informations', resultat)
            ns['assurer_salon_perso'].assert_not_awaited()
            salon.set_permissions.assert_not_awaited()
            ns['onboarding'].livrer.assert_not_awaited()

    async def test_rang_rookie_ne_remplace_pas_role_clippeur(self):
        ns, membre, salon, _ = self.contexte()
        membre.roles = [N(id=3, name='Rookie')]
        resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
        ns['poser_role_equipe'].assert_awaited_once()
        self.assertEqual({1, 2, 3}, {r.id for r in membre.roles})
        self.assertIn('Message du compte 1 vérifié', resultat)
        self.assertIn('remise des accès non attestée', resultat)
        self.assertNotIn('livré', resultat)
        self.assertEqual(90, salon.set_permissions.await_args.args[0].id)

    async def test_role_clippeur_absent_ambigu_ou_mauvais_role_configure_bloque(self):
        for panne in ('absent', 'ambigu', 'configuration'):
            ns, membre, salon, _ = self.contexte()
            if panne == 'absent': membre.guild.roles = [r for r in membre.guild.roles if r.id != 1]
            if panne == 'ambigu': membre.guild.roles.append(N(id=5, name='Clippeur'))
            if panne == 'configuration': ns['role_team'] = lambda *a:N(id=3, name='Team International')
            resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
            self.assertIn('Rôle Clippeur absent, ambigu ou configuration divergente', resultat)
            ns['onboarding'].livrer.assert_not_awaited()
            ns['poser_role_equipe'].assert_not_awaited()

    async def test_relecture_discord_requise_avant_reservation_puis_reprise(self):
        for panne in ('role', 'tl', 'membre', 'info', 'categorie', 'lecture'):
            with self.subTest(panne=panne):
                ns, membre, salon, _ = self.contexte()
                info = ns['categorie_de_creatrice'](None, None).text_channels[0]
                if panne == 'role': membre.add_roles.side_effect = None
                if panne in ('tl', 'membre'):
                    cible = 90 if panne == 'tl' else 42
                    salon.permissions_for = lambda m: N(view_channel=True, read_message_history=True,
                                                         send_messages=m.id != cible)
                if panne == 'info': info.permissions_for = lambda m: N(view_channel=False, read_message_history=False)
                if panne == 'categorie': salon.category_id = 10
                lecture = membre.guild.fetch_member.side_effect
                if panne == 'lecture': membre.guild.fetch_member.side_effect = TimeoutError()
                fn = charger('onboarder_membre', ns)
                self.assertIn('Organisation non confirmée', await fn(membre.guild, membre, 'Fictive', None, {}, []))
                ns['onboarding'].livrer.assert_not_awaited()
                ns['parcours'].demarrer_parcours.assert_not_awaited()
                ns['attribution']._sortir_d_attente.assert_not_called()
                membre.add_roles.side_effect = lambda r, **kw: membre.roles.append(r)
                membre.guild.fetch_member.side_effect = lecture
                droits = lambda m: N(view_channel=True, send_messages=True, read_message_history=True)
                salon.permissions_for = info.permissions_for = droits
                salon.category_id = 50
                self.assertIn('Message du compte 1 vérifié', await fn(membre.guild, membre, 'Fictive', None, {}, []))
                ns['onboarding'].livrer.assert_awaited_once()

    async def test_permission_tl_refusee_puis_reprise_sans_reservation_prematuree(self):
        ns, membre, salon, _ = self.contexte()
        salon.set_permissions.side_effect = discord.Forbidden(N(status=403, reason='fictif'), 'refus')
        fn = charger('onboarder_membre', ns)
        self.assertIn('Accès TL non confirmé', await fn(membre.guild, membre, 'Fictive', None, {}, []))
        ns['onboarding'].livrer.assert_not_awaited()
        salon.set_permissions.side_effect = None
        self.assertIn('Message du compte 1 vérifié', await fn(membre.guild, membre, 'Fictive', None, {}, []))
        ns['onboarding'].livrer.assert_awaited_once()

    async def test_parcours_ordinaire_preserve_autres_permissions_tl(self):
        ns, membre, salon, _ = self.contexte()
        originale = discord.PermissionOverwrite(view_channel=True, read_message_history=True,
            send_messages=False, attach_files=False, embed_links=True, add_reactions=True,
            manage_messages=False)
        avant = originale.pair()
        salon.overwrites_for = lambda m: originale
        resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
        self.assertIn('Message du compte 1 vérifié', resultat)
        cible = salon.set_permissions.await_args.args[0]
        kw = salon.set_permissions.await_args.kwargs
        self.assertEqual(90, cible.id)
        self.assertEqual({'overwrite', 'reason'}, set(kw))
        envoyee = kw['overwrite']
        self.assertTrue(envoyee.view_channel and envoyee.send_messages and envoyee.read_message_history)
        self.assertFalse(envoyee.attach_files)
        self.assertTrue(envoyee.embed_links)
        for permission, valeur in originale:
            if permission not in ('view_channel', 'send_messages', 'read_message_history'):
                self.assertEqual(valeur, getattr(envoyee, permission), permission)
        self.assertEqual(avant, originale.pair())

    async def test_parcours_ancien_clippeur_ou_rang_ne_remplace_pas_clippeur(self):
        for nom in ('Ancien Clippeur', 'Clippeur confirmé', 'Rookie', 'Elite'):
            with self.subTest(nom=nom):
                ns, membre, salon, _ = self.contexte()
                membre.guild.roles[0].name = nom
                resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
                self.assertIn('Rôle Clippeur absent, ambigu ou configuration divergente', resultat)
                ns['onboarding'].livrer.assert_not_awaited()
                ns['poser_role_equipe'].assert_not_awaited()

    async def test_parcours_ordinaire_ecriture_ou_historique_refuse_ne_livre_rien(self):
        for permission in ('send_messages', 'read_message_history'):
            with self.subTest(permission=permission):
                ns, membre, salon, _ = self.contexte()
                def droits(personne):
                    valeurs = dict(view_channel=True, send_messages=True, read_message_history=True)
                    if personne.id == membre.id:
                        valeurs[permission] = False
                    return N(**valeurs)
                salon.permissions_for = droits
                resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
                self.assertIn('Organisation non confirmée', resultat)
                ns['onboarding'].livrer.assert_not_awaited()
                ns['parcours'].demarrer_parcours.assert_not_awaited()
                ns['attribution']._sortir_d_attente.assert_not_called()
                self.assertEqual(90, salon.set_permissions.await_args.args[0].id)

    async def test_message_local_sans_preuve_distante_ne_clot_pas_attente(self):
        for panne in ('absent', 'lecture', 'humain'):
            ns, membre, salon, _ = self.contexte()
            if panne == 'absent':
                salon.fetch_message.side_effect = discord.NotFound(N(status=404, reason='fictif'), {'code':10008})
            if panne == 'lecture': salon.fetch_message.side_effect = TimeoutError()
            if panne == 'humain': salon.fetch_message.return_value.author = N(id=100)
            resultat = await charger('onboarder_membre', ns)(membre.guild, membre, 'Fictive', None, {}, [])
            self.assertIn('non vérifiés', resultat)
            self.assertNotIn('livré', resultat)
            ns['attribution']._sortir_d_attente.assert_not_called()
            ns['attribution'].resoudre_blocage.assert_not_called()


class Informations(unittest.IsolatedAsyncioTestCase):
    setUp = orchestration.OnboardingTests.setUp

    def test_role_clippeur_exige_nom_normalise_exact_et_unique(self):
        for nom in ('Ancien Clippeur', 'Clippeur confirmé', 'SuperClippeur', 'Clippeurs', 'АClippeur', 'Rookie', 'Elite'):
            with self.subTest(nom=nom):
                self.assertIsNone(accueil.role_clippeur(N(roles=[N(id=1, name=nom)])))
        for nom in ('Clippeur', ' CLIPPEUR ', '🎬 · Clippeur'):
            role = N(id=1, name=nom)
            ancien = N(id=2, name='Ancien Clippeur')
            self.assertIs(role, accueil.role_clippeur(N(roles=[ancien, role])))
        self.assertIsNone(accueil.role_clippeur(N(roles=[N(id=1, name='Clippeur', managed=True)])))
        self.assertIsNone(accueil.role_clippeur(N(roles=[N(id=1, name='Clippeur'), N(id=2, name='Clippeur')])))

    def test_selection_dans_la_seule_categorie_sans_repli_arbitraire(self):
        perso, info = N(id=1, name='fictif'), N(id=80, name='ℹ️-informations')
        categorie = N(text_channels=[perso, info])
        self.assertIs(info, accueil.salon_information(categorie))
        categorie.text_channels = [perso]
        self.assertIsNone(accueil.salon_information(categorie))
        categorie.text_channels += [info, N(id=81, name='infos')]
        self.assertIsNone(accueil.salon_information(categorie))
        self.assertIsNone(accueil.salon_information(None))

    async def test_complement_apres_timeout_sans_reenvoyer_compte_ni_secrets(self):
        original = N(id=123, author=N(id=91), content='Ancien accueil SECRET_FICTIF', edit=AsyncMock())
        messages = {123: original}
        salon = N(id=99, guild=N(me=N(id=91)),
                  fetch_message=AsyncMock(side_effect=lambda mid:messages[mid]),
                  permissions_for=lambda m:N(view_channel=True, read_message_history=True))
        async def envoyer(texte, **kw):
            messages[124] = N(id=124, content=texte, author=N(id=91))
            raise TimeoutError()
        async def histoire(**kw):
            yield messages[124]
        salon.send = AsyncMock(side_effect=envoyer)
        salon.history = histoire
        with self.assertRaises(TimeoutError):
            await accueil.confirmer_accueil(self.store, salon, '42', '123', 'Fictive', N(id=80))
        for _ in range(2):
            await accueil.confirmer_accueil(self.store, salon, '42', '123', 'Fictive', N(id=80))
        salon.send.assert_awaited_once()
        original.edit.assert_not_awaited()
        self.assertEqual('Ancien accueil SECRET_FICTIF', original.content)
        self.assertNotIn('SECRET_FICTIF', salon.send.await_args.args[0])
        self.assertIn('<#80>', salon.send.await_args.args[0])
        self.assertEqual({}, self.store.get('message-compte1:42'))
        self.assertEqual('124', self.store.get('message-infos:42')['message_id'])

    async def test_complement_incertain_absent_ne_declenche_pas_second_post(self):
        original = N(id=123, author=N(id=91), content='Ancien accueil')
        salon = N(id=99, guild=N(me=N(id=91)), fetch_message=AsyncMock(return_value=original),
                  send=AsyncMock(side_effect=TimeoutError()),
                  permissions_for=lambda m:N(view_channel=True, read_message_history=True))
        async def histoire(**kw):
            if False: yield None
        salon.history = histoire
        with self.assertRaises(TimeoutError):
            await accueil.confirmer_accueil(self.store, salon, '42', '123', 'Fictive', N(id=80))
        with self.assertRaisesRegex(RuntimeError, 'incertaine'):
            await accueil.confirmer_accueil(self.store, salon, '42', '123', 'Fictive', N(id=80))
        salon.send.assert_awaited_once()
