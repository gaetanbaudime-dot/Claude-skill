"""Transport proposé, aucune création d'onglet ni modification de partage."""
import re
from datetime import date
from audit_diagnostic import CATEGORIES

COUVERTURE = 'Audit-processus — couverture'
SIGNAUX = 'Audit-processus — signaux'
ENTETE_COUVERTURE = ['Lot', 'Avant', 'Après', 'Collecte complète', 'Salons identifiés', 'Salons complets',
                     'Opérations découverte', 'Découvertes complètes', 'Messages', 'Lot prêt']
ENTETE_SIGNAUX = ['Lot', 'Jour', 'Catégories', 'Référence Discord', 'Bot']
CATEGORIES_PERMISES = {c for c,_ in CATEGORIES} | {'autre'}
REFERENCE = re.compile(r'https://discord\.com/channels/[0-9]+/[0-9]+/[0-9]+\Z')


class TransportSheets:
    def __init__(self, classeur_existant, config, api=None):
        if (not classeur_existant or config.get('classeur_approuve') != classeur_existant
                or not config.get('destinataires_verifies')):
            raise ValueError('Destination audit non approuvée')
        if api is None:
            import google_api as api
        self.api,self.classeur=api,classeur_existant
        self.verifie=False

    async def verifier_schema(self):
        # Le worker crée les deux onglets et en-têtes après accord sur cette destination.
        for nom,entete,fin in ((COUVERTURE,ENTETE_COUVERTURE,'J'),(SIGNAUX,ENTETE_SIGNAUX,'E')):
            valeurs=await self.api.sheets_lire(self.classeur,f"'{nom}'!A1:{fin}1")
            if valeurs != [entete]:
                raise ValueError('Schéma audit absent ou différent')
        self.verifie=True

    @staticmethod
    def lignes(lot,diagnostic):
        if not str(lot).isdigit():raise ValueError('Lot invalide')
        rows=[]
        for cas in diagnostic.get('cas') or []:
            jour=date.fromisoformat(cas['jour']).isoformat()
            categories=cas.get('categories') or []
            if not categories or any(c not in CATEGORIES_PERMISES for c in categories):
                raise ValueError('Catégorie non autorisée')
            source=str(cas.get('source') or '')
            if not REFERENCE.fullmatch(source):raise ValueError('Référence invalide')
            rows.append([str(lot),jour,','.join(sorted(set(categories))),source,'oui' if cas.get('bot') is True else 'non'])
        return rows

    async def ecrire(self,plage,rows):
        if not self.verifie:await self.verifier_schema()
        # Les lignes sont reconstruites sur liste blanche ; RAW empêche toute formule.
        await self.api.sheets_ecrire_brut(self.classeur,plage,rows)
        retour=await self.api.sheets_lire(self.classeur,plage)
        if retour != rows:
            raise ValueError('Publication audit non confirmée')

    async def signaux(self,ligne,rows):
        if not rows:return
        if ligne<2 or ligne+len(rows)>100002:raise ValueError('Capacité audit atteinte')
        await self.ecrire(f"'{SIGNAUX}'!A{ligne}:E{ligne+len(rows)-1}",rows)

    async def couverture(self,ligne,lot,rapport,pret):
        if ligne<2:raise ValueError('Ligne manifeste invalide')
        salons,decouverte=rapport['salons'],rapport['decouverte']
        row=[str(lot),str(rapport['avant']),str(rapport.get('apres') or 0),
             'oui' if rapport['complet'] else 'non',str(len(salons)),str(sum(s['statut']=='complet' for s in salons)),
             str(len(decouverte)),str(sum(s['statut']=='complet' for s in decouverte)),
             str(sum(s.get('messages',0) for s in salons)),'oui' if pret else 'non']
        if not all(x.isdigit() for x in (row[0],row[1],row[2])):raise ValueError('Bornes invalides')
        await self.ecrire(f"'{COUVERTURE}'!A{ligne}:J{ligne}",[row])


def creer_transport():
    import onboarding
    import audit_autonome
    return TransportSheets(onboarding.CLASSEUR_LOGINS_ID,audit_autonome.configuration())
