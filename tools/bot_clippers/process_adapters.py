"""Adaptateurs du processus : aucun effet à l'import. Services réels appelés seulement par le bot."""
from pathlib import Path
from process_store import Store, Bloque
import process_liens


def store():
    import onboarding
    return Store(Path(onboarding._deps['FICHIER_ONBOARDING']).parent / 'process_clippeur.sqlite3')


class LiensAPI:
    def __init__(self, uid, tous):
        self.uid, self.tous = str(uid), tous

    async def capacite(self, creatrice):
        import onboarding as o
        import paie_clics as p
        import reserve_mym as m
        if p.liens_de(p._lire(), self.uid):
            raise Bloque('Lien préexistant sans journal : rapprochement requis avant toute création')
        liens = await p.liens_gaml()
        if not getattr(liens, "complete", False):
            raise Bloque("Inventaire GAML incomplet : aucune allocation")
        utilises = {str(info.get(champ) or '').strip() for info in p._lire().get('liens', {}).values()
                    for champ in ('tracking', 'mym')} - {''}
        for lien in liens:
            detail = await p.lien_detail(lien['id'])
            utilises.update(str(c.get('value') or '').strip() for c in detail.get('contents') or [])
        modeles = [l for l in liens if o._norm(str(l.get('name') or '').split()[0] if l.get('name') else '') == o._norm(creatrice.split()[0])]
        if modeles:
            self._verifier_modele(await p.lien_detail(modeles[0]['id']))
        reserve = await m.lignes()
        mym = next((r for r in reserve if o._norm(r['creatrice']) == o._norm(creatrice)
                    and not r['pose'] and r['url'] not in utilises and not store().resource_owner('mym', r['url'])), None)
        of = next((str(c.get('lien_infloww') or '').strip() for c in self.tous if o._pour_creatrice(c, creatrice)
                   and str(c.get('lien_infloww') or '').startswith('https://')
                   and c['lien_infloww'].strip() not in utilises
                   and not store().resource_owner('of', c['lien_infloww'].strip())), '')
        return {'modele': modeles[0]['id'] if modeles else '', 'mym': mym['url'] if mym else '',
                'mym_ligne': mym['ligne'] if mym else None, 'of': of}

    @staticmethod
    def _verifier_modele(detail):
        import paie_clics as p
        try:
            p.cartes_tracking(detail)
        except ValueError as erreur:
            raise Bloque(str(erreur)) from erreur

    async def preparer_clone(self, modele):
        import paie_clics as p
        self._verifier_modele(await p.lien_detail(modele))

    async def cloner(self, modele):
        import paie_clics as p
        # Pas de suppression compensatoire ; le résultat est enregistré avant tout PATCH.
        return await p._requete('POST', f'/links/{modele}/clone')

    async def configurer(self, lid, uid):
        import paie_clics as p
        self._verifier_modele(await p.lien_detail(lid))
        await p._requete('PATCH', f'/links/{lid}', corps={'note': f'Clipping UID:{uid}', 'enabled': True})

    async def poser(self, lid, kind, destination):
        import paie_clics as p
        resultat = await (p.poser_mym(lid, destination) if kind == 'mym' else p.poser_tracking(lid, destination))
        if not (resultat == 'déjà' or resultat.startswith('ok')):
            raise Bloque('Destination non posée, reprise nécessaire')

    async def verifier(self, job):
        import paie_clics as p
        detail = await p.lien_detail(job['lid'])
        cartes = detail.get('contents') or []
        cibles = {job['mym'], job['of']}
        destinations = [str(c.get('value') or '').strip() for c in cartes
                        if str(c.get('value') or '').strip() in cibles or not p.annexe_sure(c)]
        job['lien'] = detail.get('url') or job.get('lien', '')
        if not (job['lien'] and detail.get('enabled') is True and job['mym'] != job['of'] and len(destinations) == 2
                and set(destinations) == {job['mym'], job['of']}):
            return False
        liens = await p.liens_gaml()
        if not getattr(liens, 'complete', False):
            raise Bloque('Inventaire incomplet : unicité du tracking non prouvée')
        cibles = {job['mym'], job['of']}
        for lien in liens:
            if str(lien['id']) == str(job['lid']):
                continue
            autre = await p.lien_detail(lien['id'])
            if cibles & {str(c.get('value') or '').strip() for c in autre.get('contents') or []}:
                raise Bloque('Tracking dupliqué : livraison bloquée, mappings historiques conservés')
        for lid, info in p._lire().get('liens', {}).items():
            if str(lid) != str(job['lid']) and cibles & {info.get('mym'), info.get('tracking')}:
                raise Bloque('Tracking historique dupliqué : livraison bloquée')
        return True

    async def marquer_capacite(self, job):
        import reserve_mym as m
        lignes = await m.lignes()
        r = next((r for r in lignes if r['ligne'] == job['mym_ligne'] and r['url'] == job['mym']), None)
        if not r or r['pose'] not in ('', job['lien']):
            raise Bloque('Réserve MYM modifiée pendant la préparation')
        await m._marquer(r['ligne'], job['lien'])


async def attribuer(membre, creatrice, tous=None, creer=True):
    import onboarding as o
    import paie_clics as p
    uid = str(membre.id)
    registre = store()
    key = 'liens:' + uid + ':' + creatrice.casefold()
    if registre.get("sortie:" + uid):
        raise Bloque("Départ enregistré : nouvelle allocation de liens bloquée")
    job = registre.get(key)
    if not creer and job.get('phase') != 'pret':
        # Lecture historique uniquement : aucune adoption, activation ou nouvelle attribution.
        fiche = (o._lire_etat().get('clippers') or {}).get(uid) or {}
        return {'lien': fiche.get('lien', ''), 'lid': '',
                'lignes': ['Lien existant conservé, non vérifié pour une nouvelle livraison.' if fiche.get('lien')
                           else 'Liens non préparés ; requis avant le compte privé et l’application.']}

    if creer:
        registre.reserve(uid, [])  # historique complet obligatoire, jamais zéro présumé
        job = await process_liens.preparer(registre, uid, creatrice, LiensAPI(uid, tous if tous is not None else await o.lire_comptes()))
    if job.get('phase') != 'pret' or job.get('archive'):
        raise Bloque('Liens non prêts')
    if not await LiensAPI(uid, []).verifier(job):
        raise Bloque('Liens non vérifiés : livraison bloquée')
    d = p._lire()
    existant = d.setdefault('liens', {}).get(job['lid']) or {}
    if existant.get('uid') and str(existant['uid']) != uid:
        raise Bloque('Lien déjà attribué à une autre identité')
    d['liens'][job['lid']] = {**existant, 'uid': uid, 'creatrice': creatrice, 'url': job['lien'],
                            'tracking': job['of'], 'mym': job['mym'], 'note': f'Clipping UID:{uid}',
                            'par': 'processus-15-octobre'}
    p._ecrire(d)
    etat = o._lire_etat()
    etat['clippers'].setdefault(uid, {}).update(lien=job['lien'], liens_prets=True, creatrice=creatrice)
    o._ecrire_etat(etat)
    return {'lien': job['lien'], 'lid': job['lid'], 'lignes': ['GAML, MYM et OF vérifiés']}


class DepartAPI:
    def __init__(self, membre, raison, expulser=True, expulsion_trace=None, roles_retirer=()):
        self.membre, self.raison, self.expulser = membre, raison, expulser
        self.expulsion_trace = expulsion_trace or (lambda ok: None)
        self.roles_retirer = tuple(roles_retirer)

    async def liens(self, uid):
        import paie_clics as p
        import onboarding as o
        if not p.actif():
            raise Bloque('GAML indisponible : archivage préalable impossible')
        liens = await p.liens_gaml()
        if not getattr(liens, 'complete', False):
            raise Bloque('Inventaire GAML incomplet')
        locaux = {lid for lid, info in p._lire().get('liens', {}).items() if str(info.get('uid') or '') == uid}
        locaux.update(l['id'] for l in liens if str(l.get('note') or '') in (f'Clipping UID:{uid}', f'X Clipping UID:{uid}'))
        if not locaux <= {l['id'] for l in liens}:
            raise Bloque('Lien local absent de GAML : rapprochement requis')
        fiche = o._lire_etat()['clippers'].get(uid) or {}
        if not fiche.get("comptes") and not locaux:
            raise Bloque("Historique de départ vide : rapprochement requis")
        store().put('depart-comptes:' + uid, {'handles': list(fiche.get('comptes') or [])})
        return sorted(locaux)

    async def archiver_x(self, lid):
        import paie_clics as p
        detail = await p.lien_detail(lid)
        changes = {k: str(detail.get(k) or '') if str(detail.get(k) or '').startswith('X ') else 'X ' + str(detail.get(k) or '')
                   for k in ('name', 'note')}
        if any(detail.get(k) != v for k, v in changes.items()):
            await p._requete('PATCH', f'/links/{lid}', corps=changes)
        relu = await p.lien_detail(lid)
        if any(relu.get(k) != v for k, v in changes.items()):
            raise Bloque('Archivage X non confirmé')
        d = p._lire()
        fiche = d.setdefault('liens', {}).setdefault(lid, {})
        if not fiche.get('archive'):
            p.garder_dus(fiche, str(fiche.get('uid') or ''), d)
            fiche['archive_date'] = p._aujourdhui().isoformat()
        fiche.update(archive=True, hors_clipping=True, note=changes['note'], metricool_a_preparer=True)
        p._ecrire(d)  # uid et historique de rémunération conservés

    async def preparer_metricool(self, uid, liens):
        import onboarding as o
        import google_api
        handles = set(store().get('depart-comptes:' + uid).get('handles') or [])
        comptes = await o.lire_comptes()
        retenus = [c for c in comptes if c['handle'] in handles]
        if {c['handle'] for c in retenus} != handles:
            raise Bloque('Comptes de départ incomplets dans le classeur')
        for c in retenus:
            # Préparation seulement : aucun lancement, transfert de compte ou mot de passe.
            await google_api.sheets_ecrire(o.CLASSEUR_LOGINS_ID, o.cellule(c, 'utilisation'), [['à mettre Metricool']])
        relus = await o.lire_comptes()
        if any(not any(c['handle'] == h and o._norm(c['utilisation']) == 'a mettre metricool' for c in relus) for h in handles):
            raise Bloque('Préparation Metricool non confirmée')
        store().put('metricool:' + uid, {'handles': sorted(handles), 'liens': liens, 'statut': 'a_traiter'})

    async def exclure(self, uid):
        import discord
        import onboarding as o
        membre = self.membre
        for salon in membre.guild.channels:
            if membre in salon.overwrites:
                await salon.set_permissions(membre, overwrite=None, reason=self.raison)
        if self.expulser:
            self.expulsion_trace(True)
            try:
                await membre.kick(reason=self.raison[:500])
            except discord.NotFound:
                pass  # expulsion déjà réussie avant un arrêt
            except Exception:
                self.expulsion_trace(False)
                raise
        else:
            roles = [r for r in self.roles_retirer if r in membre.roles and not r.is_default() and not r.managed]
            if roles:
                await membre.remove_roles(*roles, reason=self.raison)
        import codes_2fa
        fiche = o._lire_etat()['clippers'].get(uid) or {}
        if codes_2fa.actif():
            codes_2fa.detacher([a['mail'] for a in fiche.get('acces') or [] if a.get('mail')])
        etat = o._lire_etat()
        etat['clippers'].setdefault(uid, {}).update(sorti=True, liens_prets=False)
        o._ecrire_etat(etat)


class LiensSheetsAPI:
    """Aucune recherche par prénom, aucun appel de création ou de partage."""
    def __init__(self, uid, registre):
        self.uid, self.registre = str(uid), registre

    async def verifier(self, job):
        import paie_clics as p
        # L'unicité globale a été prouvée à l'allocation et ses claims sont relus.
        # Ici un seul GET, sans refaire l'inventaire GAML pour chaque clippeur.
        detail = await p.lien_detail(job['lid'])
        cibles = {job['mym'], job['of']}
        destinations = [str(c.get('value') or '').strip() for c in detail.get('contents') or []
                        if str(c.get('value') or '').strip() in cibles or not p.annexe_sure(c)]
        return bool(detail.get('enabled') is True and detail.get('url') == job['lien']
                    and len(destinations) == 2 and set(destinations) == cibles)

    async def lignes(self):
        import onboarding as o
        import google_api
        rows = await o.lire_comptes()
        # Lecture indépendante stricte : le lecteur historique tolère une panne.
        merges = await google_api.sheets_fusions(o.CLASSEUR_LOGINS_ID)
        if not isinstance(merges, dict):
            raise Bloque('fusions_non_verifiees')
        for r in rows:
            if r['onglet'] not in merges:
                raise Bloque('fusions_non_verifiees')
            cols = o._colonnes_lues_par_onglet.get(r['onglet']) or {}
            for champ in ('lien_gaml', 'lien_mym', 'lien_infloww', 'gerant', 'handle', 'creatrice'):
                col = cols.get(champ)
                if col is not None and any(r0 <= r['ligne']-1 < r1 and c0 <= col < c1
                    for r0,r1,c0,c1 in merges.get(r['onglet'], [])):
                    r.setdefault('fusions', {})[champ] = 'intersection'
        return rows

    def appartient(self, r, uid, creatrice):
        import onboarding as o
        h = r.get('handle') or ''
        fiche = (o._lire_etat().get('clippers') or {}).get(str(uid)) or {}
        # Une ancienne livraison ne prouve pas l'attribution Sheets actuelle.
        # Liaison attestée explicitement, jamais déduite d'un prénom ou d'un préfixe.
        binding = self.registre.get('attribution-sheet:' + str(r.get('onglet')) + ':' + o._cle_handle(h)) or {}
        courant = (binding.get('preuve') and str(binding.get('uid')) == str(uid)
                   and binding.get('gerant') == r.get('gerant')
                   and binding.get('creatrice') == creatrice)
        canonique = o._norm(r.get('creatrice')) == o._norm(creatrice)
        alias = self.registre.get('alias-creatrice:' + o._norm(r.get('creatrice'))) or {}
        canonique = canonique or bool(alias.get('preuve') and alias.get('canonique') == creatrice)
        return bool(courant and canonique and h and r.get('gerant') and o._norm(r.get('gerant')) not in o.GERANTS_LIBRES
                    and not fiche.get('sorti') and h in fiche.get('comptes', [])
                    and o._proprietaires().get(o._cle_handle(h)) == {str(uid)}
                    and self.registre.owner_for_handle(h) == str(uid)
                    and canonique)

    def colonne(self, champ, onglet):
        import onboarding as o
        return o.a_colonne(champ, onglet)

    async def ecrire(self, r, changements):
        import onboarding as o
        import google_api
        await google_api.sheets_ecrire_plusieurs(o.CLASSEUR_LOGINS_ID,
            [(o.cellule(r, k), [[v]]) for k,v in changements.items()])


async def synchroniser_liens_sheets():
    """Reprise périodique des jobs prêts uniquement ; les anciens mappings restent intacts."""
    import onboarding as o
    import process_sheets
    registre = store()
    bilan = {'ecrits': 0, 'proteges': set(), 'conflits': []}
    etat = o._lire_etat()
    for uid, fiche in (etat.get('clippers') or {}).items():
        creatrice = str(fiche.get('creatrice') or '')
        key = 'liens:' + str(uid) + ':' + creatrice.casefold()
        job = registre.get(key)
        if not job:
            continue
        bilan['proteges'].update(o._cle_handle(h) for h in fiche.get('comptes') or [])
        try:
            resultat = await process_sheets.synchroniser(registre, uid, creatrice, LiensSheetsAPI(uid, registre))
            bilan['ecrits'] += resultat['ecrits']
            bilan['conflits'].extend(resultat['conflits'])
        except Exception as erreur:
            # Ne jamais recopier une URL ou une réponse distante dans les journaux.
            bilan['conflits'].append({'raison': str(erreur) if isinstance(erreur, Bloque) and str(erreur) in
                ('liens_non_prets','destination_absente','reservation_divergente','verification_gaml_echouee',
                 'aucune_ligne_attribuee_verifiee','allocation_modifiee') else 'synchronisation_indisponible'})
    if bilan['conflits']:
        o.journal.warning('Restitution liens Sheets : %d conflit(s), codes=%s', len(bilan['conflits']),
                          ','.join(sorted({c['raison'] for c in bilan['conflits']})))
    return bilan


async def reserver_attribution(comptes, gerant, uid, creatrice):
    """Intention neuve durable puis relecture : aucune attestation rétroactive."""
    import onboarding as o
    import google_api
    from datetime import datetime, timezone
    registre=store();api=LiensSheetsAPI(uid,registre);n=0
    with registre.lock('allocations-liens'):
        for cible in comptes:
            h=o._cle_handle(cible.get('handle'))
            onglet=cible.get('onglet')
            key='attribution-sheet:'+str(onglet)+':'+h
            intention_key='intention-'+key
            async def relire():
                rows=[r for r in await api.lignes() if o._cle_handle(r.get('handle'))==h]
                if len(rows)!=1 or rows[0].get('onglet')!=onglet or rows[0].get('doublons_ecartes'):
                    raise Bloque('attribution_identite_ambigue')
                r=rows[0]
                if o._norm(r.get('creatrice'))!=o._norm(creatrice):
                    raise Bloque('attribution_creatrice_divergente')
                if any(k in (r.get('fusions') or {}) for k in ('gerant','handle','creatrice')):
                    raise Bloque('attribution_cellule_fusionnee')
                if not o.a_colonne('gerant',onglet):raise Bloque('attribution_colonne_absente')
                if (o._proprietaires().get(h) or set())-{uid}:
                    raise Bloque('attribution_proprietaire_divergent')
                return r
            r=await relire()
            intention=registre.get(intention_key)
            attendu={'uid':uid,'gerant':gerant,'creatrice':creatrice,'handle':h,'onglet':onglet}
            if not intention:
                if (registre.owner_for_handle(h) is not None or o._proprietaires().get(h)
                        or o._norm(r.get('gerant')) not in o.GERANTS_LIBRES
                        or o._norm(r.get('etat')) not in o.A_CREER):
                    raise Bloque('attribution_historique_non_attestable')
                intention=dict(attendu,ligne_initiale=r['ligne'],date=datetime.now(timezone.utc).isoformat())
                registre.put(intention_key,intention)
            if any(intention.get(k)!=v for k,v in attendu.items()):
                raise Bloque('attribution_intention_divergente')
            if o._norm(r.get('gerant')) not in o.GERANTS_LIBRES and r.get('gerant')!=gerant:
                raise Bloque('attribution_courante_divergente')
            registre.reserve(uid,[h])
            if r.get('gerant')!=gerant:
                n+=await google_api.sheets_ecrire(o.CLASSEUR_LOGINS_ID,o.cellule(r,'gerant'),[[gerant]])
            confirmation=await relire()
            if confirmation.get('gerant')!=gerant or registre.owner_for_handle(h)!=uid:
                raise Bloque('attribution_ecriture_non_confirmee')
            registre.put(key,dict(attendu,ligne_constatee=confirmation['ligne'],
                preuve='nouvelle-attribution-relue',date=datetime.now(timezone.utc).isoformat()))
    return n
