"""Axes validés le 16/10 : projection pure pour le bot et l'app, sans effets externes.

Les entrées sont des instantanés serveur, jamais des assertions envoyées par l'app.
Ce module ne réserve, n'admet, ne partage et n'envoie rien. Les transactions et
les preuves du processus existant restent la seule autorité d'exécution.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from process_clippeur import cumuler_reels_verifies, pseudo_disponible

AXES = (1, 3, 5, 6, 7, 8, 10)


def instant(valeur):
    try:
        d = datetime.fromisoformat(str(valeur).replace('Z', '+00:00'))
        return d if d.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def preuve_valide(p, maintenant):
    date = instant((p or {}).get('date'))
    return bool(p and p.get('verifie') is True and p.get('reference') and p.get('source')
                and date and date <= maintenant)


def fiches_uniques(fiches):
    """Même UID au retour/renommage ; jamais de rapprochement par prénom/pseudo.

    Les candidatures encore sans UID restent distinctes. Une candidature reliée à
    plusieurs UID est conservée comme conflit et ne peut pas être admise automatiquement.
    """
    groupes, liens = {}, {}
    for f in fiches:
        uid, cid = str(f.get('uid') or ''), str(f.get('candidature_id') or '')
        if not uid and not cid:
            raise ValueError('Identifiant de candidature ou Discord UID requis')
        if cid and uid:
            liens.setdefault(cid, set()).add(uid)
    for f in fiches:
        uid, cid = str(f.get('uid') or ''), str(f.get('candidature_id') or '')
        possibles = liens.get(cid, set())
        if not uid and len(possibles) == 1:
            uid = next(iter(possibles))
        cle = 'discord:' + uid if uid else 'candidature:' + cid
        g = groupes.setdefault(cle, dict(cle=cle, uid=uid or None, candidatures=[], pseudos=[], conflit=False))
        if cid and cid not in g['candidatures']:
            g['candidatures'].append(cid)
        pseudo = str(f.get('pseudo') or '')
        if pseudo and pseudo not in g['pseudos']:
            g['pseudos'].append(pseudo)
        g['conflit'] |= len(possibles) > 1
    return sorted(groupes.values(), key=lambda g: g['cle'])


def projection(dossier, maintenant=None):
    """Une prochaine action et ses preuves ; toutes les exceptions ont un responsable.

    Schéma normalisé décrit dans docs/recrutement-axes-valides.md. Le résultat est
    un avis de lecture : admission_prete ne remplace jamais les claims SQLite.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    uid = str(dossier.get('uid') or '')
    tl = str(dossier.get('tl_uid') or '')
    responsables = {'clippeur': uid or 'candidat', 'tl': tl or 'manager', 'manager': 'manager'}
    blocages = []
    def bloquer(code, preuve, role='manager'):
        blocages.append(dict(code=code, responsable=responsables[role], preuve_manquante=preuve))
    def action(code, texte, preuve, role='clippeur'):
        return dict(code=code, texte=texte, responsable=responsables[role], preuve_attendue=preuve)
    def resultat(prochaine, prete=False, test=None):
        return dict(version=1, uid=uid or None, axes=list(AXES), admission_prete=prete,
                    prochaine_action=prochaine, blocages=blocages, test_operationnel=test)
    if not preuve_valide(dossier.get('quiz_reussi'), maintenant):
        return resultat(action('quiz', 'Revois la formation puis réussis le quiz.', 'Résultat réussi du quiz daté'))
    if not uid and not dossier.get('conflit_identite'):
        return resultat(action('discord', 'Rejoins Discord depuis ton lien personnel.',
                               'Liaison authentifiée entre candidature et Discord UID'))
    if dossier.get('conflit_identite') or not uid:
        bloquer('identite', 'Liaison unique candidature → Discord UID')
    vie = dossier.get('historique_vie') or {}
    comptes = vie.get('comptes') or []
    ids = [c.get('id') for c in comptes]
    if not vie.get('reference') or vie.get('complet') is not True or not all(ids) or len(ids) != len(set(ids)):
        bloquer('historique', 'Historique complet rapproché, avec identifiants stables')
    if len(comptes) > 3:
        bloquer('limite_vie', 'Rapprochement du dépassement ; aucun quatrième compte autorisé')
    if any(c.get('statut') not in ('created', 'reserved') for c in comptes):
        bloquer('creation_incertaine', 'Preuve datée de création ou de non-création', 'tl')
    if dossier.get('sorti'):
        bloquer('depart', 'Décision du manager avant toute reprise ; historique conservé')
    if dossier.get('ordre_ancien'):
        bloquer('ordre_ancien', 'Rapprochement de l’ancien ordre des comptes', 'tl')
    capacite = dossier.get('capacite') or {}
    if not dossier.get('admis'):
        for champ in ('creatrice', 'tl', 'tracking'):
            item = capacite.get(champ) or {}
            if not item.get('valeur') or not preuve_valide(item.get('preuve'), maintenant) or item.get('uid') != uid:
                bloquer('capacite_' + champ, f'{champ} vérifié et réservé pour ce Discord UID')
        ident = capacite.get('handle') or {}
        if not ident.get('valeur') or ident.get('uid') != uid or not pseudo_disponible(ident.get('preuve') or {}, maintenant):
            bloquer('capacite_handle', 'Disponibilité réelle du @ attestée depuis moins de 24 h')
        tr = capacite.get('tracking') or {}
        if not all(tr.get(k) for k in ('gaml_id', 'mym', 'of')) or tr.get('mym') == tr.get('of'):
            bloquer('tracking_unique', 'GAML propre et destinations MYM/OF uniques vérifiées')
    if blocages:
        premier = blocages[0]
        return resultat(dict(code='resoudre_blocage', texte='Faire vérifier le point bloquant indiqué.',
                             responsable=premier['responsable'], preuve_attendue=premier['preuve_manquante']))
    if not dossier.get('admis'):
        return resultat(action('admission', 'Finaliser l’admission avec la capacité préparée.',
                               'Relecture des réservations, rôle, salon personnel et accès Drive existants', 'manager'), prete=True)
    par_rang = {c.get('rang'): c for c in comptes}
    if len(par_rang) != len(comptes) or any(r not in (1, 2, 3) for r in par_rang):
        bloquer('rangs', 'Rangs uniques croissance 1, croissance 2, privé', 'tl')
        return resultat(action('verification', 'Faire vérifier l’ordre des comptes.', blocages[-1]['preuve_manquante'], 'tl'))
    test = None
    for rang in (1, 2, 3):
        c = par_rang.get(rang)
        if not c:
            if len(comptes) >= 3:
                bloquer('limite_vie', 'Réutiliser uniquement les identités propres déjà créées ; aucun remplacement')
                return resultat(action('verification', 'Faire vérifier le registre à vie.', blocages[-1]['preuve_manquante'], 'manager'), test=test)
            return resultat(action('preparer_compte', f'Préparer le compte {rang} dans le processus existant.',
                                   'Réservation transactionnelle dans la limite de trois identités à vie', 'manager'), test=test)
        if c.get('statut') == 'created' and c.get('etat') not in ('Good', 'Ban', 'Faire appel'):
            bloquer('sante_inconnue', 'État de santé confirmé, distinct du type privé', 'tl')
            return resultat(action('verification', 'Faire vérifier l’état du compte.', blocages[-1]['preuve_manquante'], 'tl'), test=test)
        if c.get('etat') in ('Ban', 'Faire appel'):
            bloquer('sante_compte', 'Preuve mail datée et issue de l’appel ; aucun compte de remplacement', 'tl')
            return resultat(action('verification', 'Faire vérifier la situation du compte.', blocages[-1]['preuve_manquante'], 'tl'), test=test)
        creation = instant(c.get('cree_le'))
        if c.get('statut') == 'created' and (not creation or creation > maintenant or not c.get('preuve_creation')):
            bloquer('preuve_creation', 'Date et preuve de la création existante ; ne pas recréer le compte', 'tl')
            return resultat(action('verification', 'Faire vérifier la création déjà enregistrée.', blocages[-1]['preuve_manquante'], 'tl'), test=test)
        if c.get('statut') != 'created':
            return resultat(action('creer_compte', f'Créer le compte {rang} réservé à ton nom.',
                                   'Création confirmée et datée sur son identifiant stable'), test=test)
        if rang == 3:
            return resultat(action('routine', 'Poursuis les publications sur tes comptes de croissance.',
                                   'Reels publiés, datés et vérifiés'), test=test)
        reels = cumuler_reels_verifies({}, c.get('publications') or [], instant(c['cree_le']), maintenant)
        complet = len(reels) >= 4
        if rang == 1:
            test = dict(statut='valide' if complet else 'en_cours', publies_verifies=len(reels), objectif=4,
                        preuve=sorted(reels), validation='automatique_sur_preuves')
        if not complet:
            return resultat(action('publier_reels', f'Publie les {4-len(reels)} Reels restants sur le compte {rang}.',
                                   'Quatre Reels distincts, publiés après création, typés et datés'), test=test)
    raise AssertionError('Parcours non couvert')


def evenement_premier_lot(uid, compte, maintenant):
    """Date de la quatrième publication vérifiée sur croissance 1, pas date du scan."""
    if compte.get('rang') != 1 or not compte.get('preuve_creation'):
        return None
    reels = cumuler_reels_verifies({}, compte.get('publications') or [], instant(compte.get('cree_le')), maintenant)
    if len(reels) < 4:
        return None
    codes = sorted(reels, key=lambda c: (instant(reels[c]), c))[:4]
    return dict(type='premier_lot', identite=str(uid), date=reels[codes[-1]],
                reference='reels:' + ','.join(codes), verifie=True)


def metriques_hebdomadaires(evenements, debut, couverture, finance=None, fenetre_j30=None):
    """Semaine UTC [début, début+7j[, dédoublonnage par identité et première occurrence.

    Couverture explicite par métrique ; absence de source ≠ zéro. Actif J30 exige
    une définition de fenêtre approuvée (None par défaut), voir le contrat.
    """
    if debut.tzinfo is None:
        raise ValueError('Début de semaine avec fuseau requis')
    fin = debut + timedelta(days=7)
    noms = ('candidatures', 'quiz_reussis', 'premier_lot_publie', 'actifs_j30', 'marge')
    sortie = {n: dict(valeur=None, statut='non_mesure', raison='Source incomplète') for n in noms}
    premiers, invalides = {}, set()
    affecte = {'candidature':'candidatures', 'quiz_reussi':'quiz_reussis', 'premier_lot':'premier_lot_publie',
               'admission':'actifs_j30', 'reel':'actifs_j30'}
    for e in evenements:
        date = instant(e.get('date'))
        if not date or not e.get('identite') or not e.get('reference') or e.get('verifie') is not True:
            if e.get('type') in affecte:
                invalides.add(affecte[e['type']])
            continue
        key = (e.get('type'), e['identite'])
        premiers[key] = min(date, premiers.get(key, date))
    for nom, typ in [('candidatures','candidature'),('quiz_reussis','quiz_reussi'),('premier_lot_publie','premier_lot')]:
        if couverture.get(nom) is True and nom not in invalides:
            sortie[nom] = dict(valeur=sum(debut <= date < fin for (t, _), date in premiers.items() if t == typ), statut='mesure')
    if fenetre_j30 is None:
        sortie['actifs_j30']['raison'] = 'Définition de l’activité à J30 à valider'
    elif not isinstance(fenetre_j30, int) or isinstance(fenetre_j30, bool) or not 1 <= fenetre_j30 <= 30:
        raise ValueError('Fenêtre J30 : entier de 1 à 30 jours')
    elif couverture.get('actifs_j30') is True and 'actifs_j30' not in invalides:
        cohorte = {uid: d+timedelta(days=30) for (t, uid), d in premiers.items()
                   if t == 'admission' and debut <= d+timedelta(days=30) < fin}
        actifs = set()
        for e in evenements:
            j30, d = cohorte.get(e.get('identite')), instant(e.get('date'))
            if (j30 and d and e.get('type') == 'reel' and e.get('reference') and e.get('verifie') is True
                    and j30-timedelta(days=fenetre_j30-1) <= d < j30+timedelta(days=1)):
                actifs.add(e['identite'])
        sortie['actifs_j30'] = dict(valeur=len(actifs), statut='mesure', cohorte=len(cohorte), fenetre_jours=fenetre_j30)
    f = finance or {}
    if couverture.get('marge') is True and f.get('reference') and f.get('devise') and f.get('debut') == debut.isoformat() and f.get('fin') == fin.isoformat():
        try:
            montants = [Decimal(str(f[k])) for k in ('revenu_attribuable', 'remuneration', 'outils')]
            if all(x.is_finite() for x in montants) and all(x >= 0 for x in montants[1:]):
                sortie['marge'] = dict(valeur=str(montants[0]-montants[1]-montants[2]), statut='mesure', devise=f['devise'])
        except (KeyError, InvalidOperation, ValueError):
            pass
    return sortie


def dossier_depuis_sources(uid, entrees, pipeline, comptes_ordonnes, etats_par_handle, capacite=None, ordre_comptes=None):
    """Adapter les instantanés existants sans accès réseau/disque et sans secrets.

    entrees : controle.lire_entrees(); comptes_ordonnes : résultat du lecteur
    canonique parcours._comptes_ordonnes, jamais un tri par pseudo dans l'app.
    capacite : preuves serveur du préparateur, absentes tant que non enregistrées.
    """
    uid = str(uid)
    vie = entrees.get('historique_vie') or {}
    p = (entrees.get('parcours') or {}).get(uid) or {}
    registre = entrees.get('registre') or {}
    membre = registre.get(uid) or {}
    etat = (pipeline.get('etats') or {}).get(uid) or {}
    createur = membre.get('creatrice') or p.get('creatrice')
    tls = [str(k) for k, v in registre.items() if createur and v.get('chef') == createur]
    ordonnes = [str(h).lower().lstrip('@') for h in comptes_ordonnes]
    comptes = []
    for c in vie.get('comptes') or []:
        if str(c.get('uid')) != uid or c.get('status') == 'cancelled':
            continue  # cancelled = non-création explicitement prouvée dans le registre
        alias = {str(h).lower().lstrip('@') for h in c.get('aliases') or []}
        rangs = [i+1 for i, h in enumerate(ordonnes) if h in alias]
        rang = rangs[0] if len(rangs) == 1 else None
        creation = (p.get('profils') or {}).get(str(rang)) or (p.get('dates') or {}).get(f'{rang}_fait')
        publications = []
        for h in alias:
            suivi = (p.get('reels') or {}).get(h) or {}
            publications.extend(dict(code=code, publie=date, type_verifie='reel')
                                for code, date in (suivi.get('reels_verifies_v2') or {}).items())
        etats = {etats_par_handle[h] for h in alias if h in etats_par_handle}
        comptes.append(dict(id=c.get('id'),rang=rang,statut=c.get('status'),
                            etat=next(iter(etats)) if len(etats) == 1 else None,
                            cree_le=creation,preuve_creation=c.get('evidence'),publications=publications))
    quiz = {}
    if etat.get('valide_par') == 'quiz' and etat.get('validation') and etat.get('score_quiz'):
        quiz = dict(verifie=True,source='pipeline',reference=f'etats/{uid}/validation',date=etat['validation'])
    liens = {}
    for invitation in (pipeline.get('invitations') or {}).values():
        if invitation.get('cand') and invitation.get('membre'):
            liens.setdefault(str(invitation['cand']),set()).add(str(invitation['membre']))
    for membre_uid, attendu in (pipeline.get('web_attendus') or {}).items():
        if attendu.get('cand'):
            liens.setdefault(str(attendu['cand']),set()).add(str(membre_uid))
    conflit = any(uid in uids and len(uids) > 1 for uids in liens.values())
    for cid, uids in liens.items():
        q = ((pipeline.get('candidatures_web') or {}).get(cid) or {}).get('quiz') or {}
        if uids == {uid} and q.get('reussi') is True and q.get('date'):
            candidat = dict(verifie=True,source='quiz_site',reference=f'candidatures_web/{cid}/quiz',date=q['date'])
            if not quiz or (instant(candidat['date']) and instant(quiz['date']) and instant(candidat['date']) < instant(quiz['date'])):
                quiz = candidat
    revu = vie.get('disponible') is True and uid in (vie.get('revus') or [])
    sortis = entrees.get('sortis') or {}
    est_sorti = uid in sortis if isinstance(sortis,dict) else any(str(s.get('uid')) == uid for s in sortis)
    return dict(uid=uid,tl_uid=tls[0] if len(tls) == 1 else '',conflit_identite=conflit,
                admis=uid in registre,sorti=etat.get('etat') == 'sorti' or est_sorti,
                ordre_ancien=(ordre_comptes or p.get('ordre')) != 'prive3',quiz_reussi=quiz,
                historique_vie=dict(complet=revu,reference=f'process:histories/{uid}' if revu else None,comptes=comptes),
                capacite=capacite or {})
