"""Identité et mesures du recrutement, sans transport ni décision automatique.

Les liaisons proviennent uniquement d'une invitation consommée ou d'OAuth.
Aucun rapprochement par prénom, téléphone, pseudo ou date approximative.
"""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit


def instant(valeur):
    try:
        d = datetime.fromisoformat(str(valeur).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def code_reel(valeur):
    """Une URL canonique et son shortcode désignent le même Reel, sans ses paramètres."""
    texte = str(valeur or '').strip()
    if '://' in texte:
        url = urlsplit(texte)
        if url.hostname not in ('instagram.com', 'www.instagram.com', 'm.instagram.com'):
            return None
        match = re.fullmatch(r'/reels?/([A-Za-z0-9_-]+)/?', url.path)
        return match[1] if match else None
    return texte if re.fullmatch(r'[A-Za-z0-9_-]+', texte) else None


def dossier_candidature(pipe, cid):
    """Le snapshot fait foi ; repli ancien seulement si son ID concorde."""
    fiche = (pipe.get('candidatures_web') or {}).get(cid) or {}
    if 'dossier' in fiche:
        return fiche['dossier']
    ancien = (pipe.get('candidatures') or {}).get(fiche.get('tel')) or {}
    if ancien.get('id') == cid:
        return ancien
    archives = (pipe.get('candidatures_contact_historique') or {}).get(fiche.get('tel')) or []
    trouves = [a for a in archives if a.get('id') == cid]
    return trouves[0] if trouves and all(a == trouves[0] for a in trouves) else {}


def liaisons(pipe):
    resultat = {}
    for cid, f in (pipe.get('candidatures_web') or {}).items():
        for uid in f.get('discord_uids') or []:
            resultat.setdefault(cid, set()).add(str(uid))
    for f in (pipe.get('invitations') or {}).values():
        if f.get('cand') and f.get('membre'):
            resultat.setdefault(f['cand'], set()).add(str(f['membre']))
    for uid, f in (pipe.get('web_attendus') or {}).items():
        if f.get('cand'):
            resultat.setdefault(f['cand'], set()).add(str(uid))
    return resultat


def uids_en_conflit(pipe):
    """UID retenus par une contradiction explicite, sans récursion inter-dossiers."""
    fiches = pipe.get('candidatures_web') or {}
    return {uid for cid, uids in liaisons(pipe).items()
            if len(uids) > 1 or (fiches.get(cid) or {}).get('conflit_identite')
            for uid in uids}


def candidature_en_conflit(pipe, cid):
    fiche = (pipe.get('candidatures_web') or {}).get(cid) or {}
    uids = liaisons(pipe).get(cid, set())
    return bool(fiche.get('conflit_identite')) or len(uids) > 1 or bool(uids & uids_en_conflit(pipe))


def lier_discord(pipe, cid, uid):
    """À appeler après preuve Discord. Conserve le conflit, ne réattribue rien."""
    fiche = (pipe.get('candidatures_web') or {}).get(cid)
    if fiche is None or not str(uid).isdigit():
        return False
    retenu = str(uid) in uids_en_conflit(pipe) or candidature_en_conflit(pipe, cid)
    uids = liaisons(pipe).get(cid, set()) | {str(uid)}
    fiche['discord_uids'] = sorted(uids)
    fiche['conflit_identite'] = retenu or len(uids) != 1
    return not fiche['conflit_identite']


def publications_attribuees(pipe, parcours):
    """Jointure en lecture sur UID ; les preuves v2 survivent aux alias du @.

    Renvoie aussi les publications sans candidature liée. Une nouvelle candidature
    d'un membre ne s'approprie jamais ses anciens Reels : on expose tous ses IDs.
    """
    liens = liaisons(pipe)
    ambigus = uids_en_conflit(pipe)
    out = []
    for uid, fiche in parcours.items():
        ids = sorted(cid for cid, uids in liens.items() if uids == {str(uid)})
        conflit = str(uid) in ambigus
        preuves = {}
        for suivi in (fiche.get('reels') or {}).values():
            for code, date in (suivi.get('reels_verifies_v2') or {}).items():
                code = code_reel(code)
                if not code:
                    continue
                if code in preuves and preuves[code] != date:
                    preuves[code] = None  # doublon contradictoire conservé, non compté
                else:
                    preuves[code] = date
        out.extend(dict(uid=str(uid), candidatures=[] if conflit else ids,
                        attribution='conflit' if conflit else ('liee' if ids else 'inconnue'),
                        code=code, date=date, verifie=date is not None)
                   for code, date in sorted(preuves.items()))
    return out


def mesurer(dossiers, publications, maintenant, couverture=False):
    """Dossiers uniques par UID. J7/J14 = 7 jours précédant l'anniversaire exact.

    Un Reel vérifié dans la fenêtre suffit pour « actif ». Cadence = Reels / 7,
    jamais nombre d'attributions/créations. Zéro exige une couverture complète.
    L'objectif <48 h est informatif ; aucune exclusion n'est produite.
    """
    if maintenant.tzinfo is None:
        raise ValueError('Instant avec fuseau requis')
    groupes = {}
    for d in dossiers:
        uid = str(d.get('uid') or '') or ('candidature:' + str(d['candidate_id']) if d.get('candidate_id') else '')
        if not uid:
            raise ValueError('UID ou candidate_id requis, aucune jointure par prénom')
        groupes.setdefault(uid, []).append(d)
    reels = {}
    conflits = {uid for uid, copies in groupes.items() if any(d.get('conflit_identite') for d in copies)}
    for p in publications:
        uid, code, date = str(p.get('uid') or ''), code_reel(p.get('code')), instant(p.get('date'))
        if not uid:
            continue
        if not code:
            conflits.add(uid)
            continue
        key = (uid, code)
        if p.get('attribution') != 'liee' or p.get('verifie') is not True or not date or date > maintenant:
            conflits.add(uid)
            continue
        if key in reels and reels[key] != date:
            conflits.add(uid)
        reels[key] = date
    lignes = []
    for uid, copies in groupes.items():
        dates = {instant(d.get('validation')) for d in copies if d.get('preuve_validation')}
        dates.discard(None)
        # Ne pas choisir arbitrairement une date parmi plusieurs retours/admissions.
        date = next(iter(dates)) if len(dates) == 1 and not any(d.get('conflit_identite') for d in copies) else None
        if date and date > maintenant:
            date = None
        responsables = {str(d.get('tl_uid')) for d in copies if d.get('tl_uid')}
        bloque = any(d.get('blocage_technique') for d in copies)
        connues = couverture is True and uid not in conflits
        publies = sorted(d for (u, _), d in reels.items() if u == uid and date and d >= date)
        premier = publies[0] if publies else None
        ligne = dict(uid=uid, validation=date.isoformat() if date else None,
                     qualite_date='connue' if date else 'inconnue_ou_conflit',
                     responsable=next(iter(responsables)) if len(responsables) == 1 else 'manager',
                     blocage_technique=bloque,
                     premier_reel=premier.isoformat() if premier else None,
                     delai_heures=(premier-date).total_seconds()/3600 if premier else None,
                     objectif_48h='non_mesure', actif_recent=None, cadence_7j=None,
                     premier_reel_complet=connues,
                     attribution_connue=any(d.get('attribution') for d in copies),
                     pret_le=next((d['pret_le'] for d in copies if instant(d.get('pret_le'))), None),
                     comptes_reserves=max(d.get('comptes_reserves',0) for d in copies),
                     comptes_crees_prouves=max(d.get('comptes_crees_prouves',0) for d in copies))
        if date and premier and connues:
            ligne['objectif_48h'] = 'atteint' if premier-date < timedelta(hours=48) else 'a_analyser'
        elif date and connues:
            ligne['objectif_48h'] = 'en_cours' if maintenant-date < timedelta(hours=48) else 'a_analyser'
        if bloque:
            ligne['objectif_48h'] = 'blocage_technique'
        if date and connues:
            recent = [d for d in publies if maintenant-timedelta(days=7) <= d <= maintenant]
            ligne.update(actif_recent=bool(recent), cadence_7j=len(recent)/7)
        for jour in (7, 14):
            fin = date + timedelta(days=jour) if date else None
            mature = bool(fin and fin <= maintenant)
            compte = sum(fin-timedelta(days=7) <= d < fin for d in publies) if mature and connues else None
            ligne[f'j{jour}'] = dict(mature=mature, mesure=compte is not None,
                                    actif=bool(compte) if compte is not None else None, reels=compte)
        lignes.append(ligne)
    cohortes = {}
    for jour in (7, 14):
        mesures = [d[f'j{jour}'] for d in lignes if d[f'j{jour}']['mesure']]
        cohortes[f'j{jour}'] = dict(denominateur=len(mesures), actifs=sum(d['actif'] for d in mesures),
            exclus_immatures=sum(d['validation'] is not None and not d[f'j{jour}']['mature'] for d in lignes),
            exclus_non_mesures=sum(d[f'j{jour}']['mature'] and not d[f'j{jour}']['mesure'] for d in lignes),
            dates_inconnues=sum(d['validation'] is None for d in lignes),
            blocages_techniques=sum(d[f'j{jour}']['mesure'] and d['blocage_technique'] for d in lignes))
    return dict(fuseau='UTC', dossiers=lignes, cohortes=cohortes,
                definitions=dict(j7='Activation : au moins un Reel dans [validation, validation+7j[',
                                 j14='Rétention : au moins un Reel dans [validation+7j, validation+14j['))


def premieres_reussites(pipe):
    """Un succès par candidate_id, note historique absente jamais reconstituée."""
    out = {}
    for cid, f in (pipe.get('candidatures_web') or {}).items():
        essais = list((f.get('quiz_historique') or {}).values()) + [f.get('premiere_reussite') or {}, f.get('quiz') or {}]
        dates = [instant(q.get('date')) for q in essais if q.get('reussi') is True and instant(q.get('date'))]
        if dates:
            out[cid] = min(dates).isoformat()
    return out


def decision_volume(mesures, seuils):
    """Seuils explicitement approuvés seulement ; jamais d'annonce ou dépense."""
    if not seuils.get('preuve_approbation'):
        return dict(statut='a_valider', raisons=['Seuils non approuvés'], automatique=False)
    raisons = []
    # Charge mesurée et capacité d'aide sur la même période, taux dans [0, 1].
    for cle in ('aide_disponible', 'aide_requise', 'activation_j7', 'retention_j14', 'effectif'):
        valeur = mesures.get(cle)
        if not isinstance(valeur, (float, int)) or isinstance(valeur, bool) or not 0 <= valeur < float('inf'):
            raisons.append(f'{cle} non mesuré')
    for cle in ('activation_j7', 'retention_j14'):
        seuil = seuils.get(cle)
        if not isinstance(seuil, (int, float)) or isinstance(seuil, bool) or not 0 <= seuil <= 1:
            raisons.append(f'Seuil {cle} absent ou invalide')
        elif mesures.get(cle) is not None and isinstance(mesures[cle], (int, float)):
            if not seuil <= mesures[cle] <= 1:
                raisons.append(f'{cle} insuffisant ou invalide')
    minimum = seuils.get('effectif_min')
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum <= 0:
        raisons.append('Effectif minimal non validé')
    elif isinstance(mesures.get('effectif'), (int, float)) and mesures['effectif'] < minimum:
        raisons.append('Cohorte trop petite')
    if all(isinstance(mesures.get(k), (int, float)) for k in ('aide_disponible','aide_requise')):
        if mesures['aide_requise'] > mesures['aide_disponible']:
            raisons.append('Capacité d’aide insuffisante')
    return dict(statut='maintenir' if raisons else 'revue_montee_possible', raisons=raisons, automatique=False)


def dossiers_depuis_sources(pipe, equipes, parcours, comptes):
    """Instantanés serveur existants, aucune lecture réseau, aucun export de secrets.

    comptes : registre à vie, liste {uid, status, created_at, evidence}. Attribution
    n'est pas création ; « prêt » exige une attestation datée explicite du dossier.
    Les TL sont lus dans les équipes existantes : aucune nouvelle règle de rotation.
    """
    liens = liaisons(pipe)
    ambigus = uids_en_conflit(pipe)
    out = []
    for cid, f in (pipe.get('candidatures_web') or {}).items():
        uids = liens.get(cid, set())
        conflit = candidature_en_conflit(pipe, cid) or bool(uids & ambigus)
        uid = next(iter(uids)) if len(uids) == 1 and not conflit else None
        etat = (pipe.get('etats') or {}).get(uid) or {}
        equipe = equipes.get(uid) or {}
        creatrice = equipe.get('creatrice')
        tls = [str(u) for u, e in equipes.items() if creatrice and e.get('chef') == creatrice]
        q = f.get('premiere_reussite') or f.get('quiz') or {}
        # Validation explicite de l'agence. Ne pas substituer date d'attribution ou quiz.
        validation = etat.get('validation')
        preuve = bool(validation and etat.get('valide_par'))
        fiche = parcours.get(uid) or {}
        propres = [c for c in comptes if str(c.get('uid')) == uid]
        out.append(dict(candidate_id=cid, uid=uid, source=f.get('source'), campagne=f.get('campagne'),
                        conflit_identite=conflit, validation=validation, preuve_validation=preuve,
                        quiz_reussi=q.get('reussi') is True, date_quiz=q.get('date'),
                        score_quiz=q.get('score'), essais_conserves=len(f.get('quiz_historique') or {}),
                        tl_uid=tls[0] if len(tls)==1 else None,
                        attribution=equipe.get('date'),
                        comptes_reserves=sum(c.get('status')=='reserved' for c in propres),
                        comptes_crees_prouves=sum(c.get('status')=='created' and bool(c.get('evidence')) for c in propres),
                        pret_le=fiche.get('pret_le') if fiche.get('preuve_pret') else None,
                        blocage_technique=fiche.get('blocage_technique') or bool(fiche.get('ligne_attendue'))))
    # Les Discord historiques sans candidature restent des dossiers distincts, non datés par déduction.
    connus = {d['uid'] for d in out if d['uid']} | ambigus
    for uid, e in equipes.items():
        if str(uid) not in connus and e.get('creatrice'):
            etat = (pipe.get('etats') or {}).get(str(uid)) or {}
            out.append(dict(uid=str(uid), validation=etat.get('validation'),
                            preuve_validation=bool(etat.get('valide_par')), candidature_inconnue=True))
    return out
