"""Compatibilité des historiques fictifs sans connecteur réel."""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock, AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboarding
import parcours
import process_adapters
from process_compat import sauvegarder
from process_store import Store, Bloque

class CompatTests(unittest.TestCase):
    def test_snapshot_une_fois_sans_modification_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'historique.json').write_text('{"uid":"42"}')
            cible=sauvegarder(p)
            (p/'historique.json').write_text('{"uid":"43"}')
            self.assertEqual(cible, sauvegarder(p))
            self.assertEqual('{"uid":"42"}', (cible/'historique.json').read_text())
            self.assertEqual('{"uid":"43"}', (p/'historique.json').read_text())
            self.assertEqual(0o700, cible.stat().st_mode & 0o777)

    def test_alias_historique_suivi_sans_autoriser_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(Path(tmp)/'process.sqlite3')
            s.observe_alias('42','ancien','fiche-fictive')
            s.rename('42','ancien','nouveau')
            self.assertEqual({'unknown':1},s.counts('42'))
            self.assertEqual('42',s.owner_for_handle('nouveau'))
            with self.assertRaises(Bloque): s.reserve('42',['deuxieme'])
            with self.assertRaises(Bloque): s.observe_alias('43','ancien','autre-fiche')

    def test_app_deja_livree_ne_requiert_pas_migration(self):
        with patch.object(parcours,'_onb',return_value={'lien':'https://example.invalid/ancien'}), patch.object(parcours,'_lire',return_value={'42':{'app':'date-historique'}}), patch.object(parcours,'_ecrire') as write:
            self.assertEqual('deja',asyncio.run(parcours.livrer_app('42')))
            write.assert_not_called()
        with patch.object(parcours,'_onb',return_value={'lien':'https://example.invalid/ancien'}), patch.object(parcours,'_lire',return_value={'42':{}}):
            self.assertEqual('sans_lien',asyncio.run(parcours.livrer_app('42')))

    def test_onboarding_non_rapproche_ne_modifie_pas_historique(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(process_adapters,'store',return_value=Store(Path(tmp)/'process.sqlite3')), patch.object(onboarding,'_ecrire_etat') as write, patch.object(onboarding,'lire_comptes',AsyncMock()) as read:
            result=asyncio.run(onboarding.livrer(SimpleNamespace(id=42,display_name='Fictif'),'Fictive'))
            self.assertIn('reporting existants conservés',result)
            write.assert_not_called();read.assert_not_called()

    def test_lecture_lien_historique_sans_journal_ne_lefface_pas(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(process_adapters,'store',return_value=Store(Path(tmp)/'process.sqlite3')), patch.object(onboarding,'_lire_etat',return_value={'clippers':{'42':{'lien':'https://example.invalid/ancien'}}}), patch.object(onboarding,'_ecrire_etat') as write:
            result=asyncio.run(process_adapters.attribuer(SimpleNamespace(id=42),'Fictive',creer=False))
            self.assertEqual('https://example.invalid/ancien',result['lien'])
            write.assert_not_called()
