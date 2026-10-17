"""Messages fictifs : affectation et livraison distinctes."""
from pathlib import Path
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class Messages(unittest.IsolatedAsyncioTestCase):
    async def test_pas_de_faux_lien_historique(self):
        import onboarding as o
        import process_adapters as p
        with patch.object(p,'store') as store, patch.object(o,'_lire_etat',return_value={'clippers':{}}):
            store.return_value.get.return_value={}
            resultat=await p.attribuer(SimpleNamespace(id=3),'Fictive',creer=False)
        self.assertNotIn('historique',str(resultat))
        self.assertIn('avant le compte privé',str(resultat))

    async def test_reservation_recente_sans_message_pas_livree(self):
        import onboarding as o
        with patch.object(o.process_adapters,'store'),patch.object(o,'_lire_etat',return_value={'clippers':{'3':{'comptes':['fictif.un'],'date':datetime.now(timezone.utc).isoformat()}}}):
            resultat=await o.livrer(SimpleNamespace(id=3,display_name='Fictif'),'Fictive')
        self.assertNotIn('déjà livré',resultat)
        self.assertIn('lignes déjà affectées',resultat)
