"""File héritée : aucune transmission ni perte de données pendant les reprises."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import onboarding


def empreinte(valeur):
    return hashlib.sha256(json.dumps(valeur,sort_keys=True).encode()).hexdigest()


class RemiseSecurisee(unittest.IsolatedAsyncioTestCase):
    async def test_file_heritee_conservee_et_reprise_sans_envoi(self):
        etat={'clippers':{'42':{'a_dire':['compte-fictif','sans-acces-fictif'],
            'acces':[{'handle':'compte-fictif','mdp':secrets.token_hex(16),'mail':'fictif'}],
            'remplaces':[{'ancien':'ancien-fictif','nouveau':'compte-fictif'}]}},
            'livres':{'ancien-fictif':{'uid':'42'}}}
        initial=empreinte(etat)
        def ecrire(d):etat.clear();etat.update(deepcopy(d))
        sauvegarde=Mock(side_effect=ecrire)
        membre=SimpleNamespace(send=AsyncMock())
        salon=SimpleNamespace(send=AsyncMock())
        with patch.object(onboarding,'_lire_etat',side_effect=lambda:deepcopy(etat)), \
             patch.object(onboarding,'_ecrire_etat',sauvegarde), \
             patch.object(onboarding,'message_nouveau_compte',side_effect=AssertionError('Formatage interdit')), \
             patch.dict(onboarding._deps,{'salon_perso':lambda uid:salon}):
            for _ in range(3):
                envoyes,restes=await onboarding.dire_nouveaux_comptes(membre,'42')
                self.assertEqual([],envoyes)
                self.assertEqual(['compte-fictif','sans-acces-fictif'],restes)
            membre.send.assert_not_awaited();salon.send.assert_not_awaited()
            self.assertEqual(1,sauvegarde.call_count)
        marque=etat['clippers']['42'].pop('remise_securisee')
        self.assertEqual('humaine_requise',marque['etat'])
        self.assertEqual(initial,empreinte(etat))  # pas de données sensibles dans un diff d'assertion

    async def test_file_vide_necrit_rien_et_nenvoie_rien(self):
        membre=SimpleNamespace(send=AsyncMock())
        with patch.object(onboarding,'_lire_etat',return_value={'clippers':{}}), \
             patch.object(onboarding,'_ecrire_etat') as ecrire:
            self.assertEqual(([],[]),await onboarding.dire_nouveaux_comptes(membre,'42'))
            ecrire.assert_not_called();membre.send.assert_not_awaited()

    async def test_telephones_herites_reprises_conservent_acces_et_compteurs(self):
        etat={'clippers':{'42':{'telephones':{'Fictive':{
            'acces':[{'handle':'un-fictif','mdp':secrets.token_hex(16)},
                     {'handle':'deux-fictif','mail':secrets.token_hex(16),'prive':True}],
            'donnes':1,'dernier':'2020-01-01T00:00:00+00:00','lien_du':True}}}}}
        initial=empreinte(etat)
        def ecrire(d):etat.clear();etat.update(deepcopy(d))
        salon=SimpleNamespace(send=AsyncMock())
        membre=SimpleNamespace(mention='<@42>',send=AsyncMock())
        with patch.object(onboarding,'_lire_etat',side_effect=lambda:deepcopy(etat)), \
             patch.object(onboarding,'_ecrire_etat',side_effect=ecrire) as sauvegarde, \
             patch.object(onboarding,'message_telephone',side_effect=AssertionError('Formatage interdit')), \
             patch.object(onboarding,'lien_autre_creatrice',AsyncMock()) as lien, \
             patch.object(onboarding,'lien_drive_creatrice',AsyncMock()) as drive, \
             patch.dict(onboarding._deps,{'salon_perso':lambda uid:salon,'membre_par_id':lambda uid:membre}):
            self.assertEqual(0,await onboarding.donner_telephones())
            self.assertEqual(0,await onboarding.donner_telephones('42'))
            self.assertEqual(0,await onboarding.donner_telephones('autre'))
            salon.send.assert_not_awaited();membre.send.assert_not_awaited()
            lien.assert_not_awaited();drive.assert_not_awaited()
            self.assertEqual(1,sauvegarde.call_count)
        marque=etat['clippers']['42']['telephones']['Fictive'].pop('remise_securisee')
        self.assertEqual('humaine_requise',marque['etat'])
        self.assertEqual(initial,empreinte(etat))

    def test_tous_les_formateurs_herites_excluent_les_acces(self):
        from parcours import _identifiants
        valeurs=[secrets.token_hex(16) for _ in range(3)]
        acces={'handle':'compte-fictif','mdp':valeurs[0],'mail':valeurs[1],
               'phone':valeurs[2],'etat':'à créer'}
        textes=[onboarding._bloc_acces(acces),
                onboarding.message_nouveau_compte('<@42>',1,acces),
                onboarding.message_telephone('<@42>','Fictive',1,acces),
                onboarding.message_comptes([acces],'Fictif','Fictive'),
                _identifiants(1)]
        for texte in textes:
            self.assertFalse(any(v in texte for v in valeurs))
            self.assertTrue('responsable' in texte)
