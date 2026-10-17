"""Admission initiale prouvée, jamais remise à zéro d'un revenant."""
from datetime import datetime, timezone, timedelta
import recrutement_suivi


def preuve_nouveau(uid, pipe, onboarding, parcours, sortis, oublis, maintenant=None, registre=None):
    uid=str(uid)
    maintenant=maintenant or datetime.now(timezone.utc)
    if not all(isinstance(x,dict) for x in (pipe,onboarding,parcours,oublis,registre)) or not isinstance(sortis,list):
        return None
    if uid in recrutement_suivi.uids_en_conflit(pipe):
        return None
    arr=(pipe.get('arrivees') or {}).get(uid) or {}
    arrivee=recrutement_suivi.instant(arr.get('date'))
    if (arr.get('retour') or arr.get('via') != 'site' or not arrivee
            or not timedelta(0) <= maintenant-arrivee <= timedelta(days=7)):
        return None
    if any(str(s.get('uid'))==uid for s in sortis) or uid in oublis:
        return None
    ancien=(onboarding.get('clippers') or {}).get(uid) or {}
    if ancien or any(str(v.get('uid'))==uid for v in (onboarding.get('livres') or {}).values()):
        return None
    p=parcours.get(uid) or {}
    # Une bienvenue d'attente n'est pas une création ; toute étape de compte est ambiguë.
    if p.get('reels') or p.get('comptes') or any(k != 'bienvenue' for k in (p.get('messages') or {})) or p.get('dates'):
        return None
    ids=[cid for cid,us in recrutement_suivi.liaisons(pipe).items() if us=={uid}]
    if len(ids)!=1:
        return None
    cid=ids[0]
    f=(pipe.get('candidatures_web') or {}).get(cid) or {}
    q=f.get('premiere_reussite') or f.get('quiz') or {}
    candidature=recrutement_suivi.instant(f.get('date'))
    quiz=recrutement_suivi.instant(q.get('date'))
    # Preuves positives de cette admission, pas simple absence du registre.
    if q.get('reussi') is not True or not candidature or not quiz or not candidature <= quiz <= arrivee:
        return None
    fiche_registre=(registre or {}).get(uid) or {}
    date_registre=recrutement_suivi.instant(fiche_registre.get('date'))
    if fiche_registre and (not date_registre or date_registre < candidature):
        return None
    return {'type':'premiere_admission_site','uid':uid,'candidate_id':cid,
            'candidature':candidature.isoformat(),'quiz':quiz.isoformat(),'arrivee':arrivee.isoformat()}


def tl_pour(uid, creatrice, mapping, registre):
    """Affectation individuelle existante, sinon mandat unique de la créatrice."""
    if mapping.get(str(uid)):
        return str(mapping[str(uid)])
    def cle(v):
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD',str(v).strip().lower()) if not unicodedata.combining(c))
    candidats=[str(u) for u,f in registre.items() if cle(f.get('chef',''))==cle(creatrice) and creatrice]
    return candidats[0] if len(candidats)==1 else None


async def salon_vide_verifie(salon):
    """Lecture bornée : aucun ancien message n'est partagé sur une simple supposition.

    Sans lecture complète autorisée au bot, une réponse vide ne prouve rien.
    Tout message (même du bot), pièce jointe ou erreur garde le handoff humain.
    """
    try:
        permissions = salon.permissions_for(salon.guild.me)
        if not (permissions.view_channel and permissions.read_message_history):
            return False
        async for _message in salon.history(limit=1):
            return False
        return True
    except Exception:
        return False
