"""Le palier exige quatre Reels prouvés, pas quatre publications ambiguës."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import etats_comptes as e
import parcours as p
import process_clippeur as r
NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)
CREATION=NOW-timedelta(days=2)

class PreuvesReelsTests(unittest.TestCase):
    def mesure(self,posts):
        return e._lire_items([{'username':'fictif','followersCount':1,'postsCount':len(posts),'private':False,'latestPosts':posts}],['fictif'],NOW)['fictif']
    def test_posts_sans_type_ne_sont_pas_preuves_de_reels(self):
        posts=[{'shortCode':f'fictif{i}','timestamp':(NOW-timedelta(hours=1)).isoformat()} for i in range(4)]
        preuves=self.mesure(posts).get('publications_verifiees',[])
        # Toute preuve employée pour ouvrir un palier doit avoir un type établi.
        self.assertFalse(any(x.get('type_verifie')=='reel' for x in preuves))
        self.assertEqual({},r.cumuler_reels_verifies({},preuves,CREATION,NOW))
    def test_quatre_reels_avec_type_ou_url_et_dates(self):
        posts=[{'shortCode':f'fictif{i}','timestamp':(NOW-timedelta(hours=1)).isoformat(),'productType':'clips','type':'Video'} for i in range(3)]
        posts.append({'shortCode':'fictif3','timestamp':(NOW-timedelta(hours=1)).isoformat(),'type':'Video','url':'https://www.instagram.com/reel/fictif3/'})
        preuves=self.mesure(posts+posts[:1]).get('publications_verifiees',[])
        confirms=r.cumuler_reels_verifies({},preuves,CREATION,NOW)
        self.assertEqual(4,len(confirms))
        self.assertEqual(confirms,r.cumuler_reels_verifies({'reels_verifies_v2':confirms},preuves,CREATION,NOW))
    def test_anciens_totaux_et_dates_invalides_nouvrent_pas(self):
        legacy={'publications_verifiees':dict.fromkeys('1234','2026-10-15T10:00:00Z'),
                'reels_verifies_v2':{'futur':'2099-01-01T00:00:00Z','ancien':'2020-01-01T00:00:00Z','invalide':'date'}}
        self.assertEqual({},r.cumuler_reels_verifies(legacy,[],CREATION,NOW))
        self.assertEqual(4,len(legacy['publications_verifiees']))
    def test_paliers_exactement_quatre_sur_le_compte_precedent(self):
        proofs={str(i):'2026-10-15T10:00:00Z' for i in range(4)}
        fiche={'ordre':'prive3','profils':{'1':CREATION.isoformat(),'2':CREATION.isoformat()},
               'reels':{'a':{'reels_verifies_v2':proofs},'b':{'reels_verifies_v2':dict(list(proofs.items())[:3])}}}
        with patch.object(p,'_comptes_ordonnes',return_value=['a','b','c']):
            self.assertEqual(4,p.reels_pour('42',fiche,2));self.assertEqual(3,p.reels_pour('42',fiche,3))
            fiche['reels']['a']={};fiche['reels']['b']['reels_verifies_v2']=proofs
            self.assertEqual(4,p.reels_pour('42',fiche,3))

    def test_type_contradictoire_et_video_generique_restent_ambigus(self):
        for post in ({"type":"Video"}, {"productType":"igtv"}, {"type":"Image","url":"https://www.instagram.com/reel/fictif/"}, {"productType":"feed","url":"https://www.instagram.com/reel/fictif/"}):
            self.assertFalse(e._reel_prouve(post))
        preuve=self.mesure([{"type":"Reel","shortCode":"fictif","timestamp":(NOW-timedelta(hours=1)).isoformat()}])['publications_verifiees']
        self.assertEqual(1,len(r.cumuler_reels_verifies({},preuve,CREATION,NOW)))
