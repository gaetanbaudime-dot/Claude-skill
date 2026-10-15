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
        reserve = await m.lignes()
        mym = next((r for r in reserve if o._norm(r['creatrice']) == o._norm(creatrice)
                    and not r['pose'] and r['url'] not in utilises and not store().resource_owner('mym', r['url'])), None)
        of = next((str(c.get('lien_infloww') or '').strip() for c in self.tous if o._pour_creatrice(c, creatrice)
                   and str(c.get('lien_infloww') or '').startswith('https://')
                   and c['lien_infloww'].strip() not in utilises
                   and not store().resource_owner('of', c['lien_infloww'].strip())), '')
        return {'modele': modeles[0]['id'] if modeles else '', 'mym': mym['url'] if mym else '',
                'mym_ligne': mym['ligne'] if mym else None, 'of': of}

    async def cloner(self, modele):
        import paie_clics as p
        # Pas de suppression compensatoire ; le résultat est enregistré avant tout PATCH.
        return await p._requete('POST', f'/links/{modele}/clone')

    async def configurer(self, lid, uid):
        import paie_clics as p
        await p._requete('PATCH', f'/links/{lid}', corps={'note': f'Clipping UID:{uid}', 'enabled': True})

    async def poser(self, lid, kind, destination):
        import paie_clics as p
        resultat = await (p.poser_mym(lid, destination) if kind == 'mym' else p.poser_tracking(lid, destination))
        if not (resultat == 'déjà' or resultat.startswith('ok')):
            raise Bloque('Destination non posée, reprise nécessaire')

    async def verifier(self, job):
        import paie_clics as p
        detail = await p.lien_detail(job['lid'])
        destinations = {str(c.get('value') or '').strip() for c in detail.get('contents') or []}
        job['lien'] = detail.get('url') or job.get('lien', '')
        if not (job['lien'] and detail.get('enabled') is True and {job['mym'], job['of']} <= destinations):
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
                'lignes': ['⚠️ Lien historique conservé ; nouvelle livraison bloquée jusqu’au rapprochement']}

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
