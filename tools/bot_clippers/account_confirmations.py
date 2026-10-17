"""Prépare des candidats JSON hors ligne ; ne remplace jamais le volume du bot.

Les accès doivent déjà exister sous le pseudo demandé. Un changement d'identité
non prouvé bloque la préparation ; aucun mot de passe n'est déplacé entre comptes.
"""
from copy import deepcopy
from datetime import datetime
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import process_clippeur


def prepare(onboarding, parcours, liens, confirmations):
    out, routes = deepcopy(onboarding), deepcopy(parcours)
    summary = []
    for confirmation in confirmations:
        uid = str(confirmation["uid"])
        proof = {k: confirmation[k] for k in ("par", "date", "reference")}
        if not all(proof.values()) or datetime.fromisoformat(proof["date"]).tzinfo is None:
            raise ValueError("Confirmation datée et attribuée requise")
        fiche = out.get("clippers", {}).get(uid)
        if not isinstance(fiche, dict):
            raise ValueError(f"{uid}: fiche canonique absente")
        if str(fiche.get("creatrice") or "").casefold() != str(confirmation["creatrice"]).casefold():
            raise ValueError(f"{uid}: créatrice canonique à rapprocher")
        wanted = confirmation["comptes"]
        handles = [process_clippeur.cle(c["handle"]) for c in wanted]
        if (not 1 <= len(handles) <= 3 or len(set(handles)) != len(handles)
                or any(not re.fullmatch(r"(?!\.)(?!.*\.$)[a-z0-9._]{1,30}", h) for h in handles)):
            raise ValueError(f"{uid}: liste active invalide")
        roles = [c["role"] for c in wanted]
        if any(r not in ("croissance", "prive") for r in roles) or roles.count("prive") != 1:
            raise ValueError(f"{uid}: rôles explicites requis")
        private = roles.index("prive") + 1
        if private not in (2, 3):
            raise ValueError(f"{uid}: position privée non prise en charge")
        owners = (set(out.get("clippers", {})) | set(out.get("comptes_a_vie", {}))
                  | {str(v.get("uid")) for v in out.get("livres", {}).values() if isinstance(v, dict) and v.get("uid")})
        for other in owners:
            identities = process_clippeur.registre(deepcopy(out), other)
            if other != uid and set(handles) & {a for c in identities for a in c["aliases"]}:
                raise ValueError(f"{uid}: identité détenue par un autre clipper")
        # Never manufacture IDs or declare an incomplete history complete.
        identities = out.get("comptes_a_vie", {}).get(uid) or []
        if any(not c.get("id") for c in identities):
            raise ValueError(f"{uid}: identifiant historique manquant")
        known = {process_clippeur.cle(a) for c in identities for a in c["aliases"]}
        if not (set(handles) | set(map(process_clippeur.cle, fiche.get("comptes") or []))) <= known:
            raise ValueError(f"{uid}: historique des identités à rapprocher")
        accesses = list(fiche.get("acces") or []) + list(fiche.get("acces_archives") or [])
        selected = []
        for h, role in zip(handles, roles):
            matches = [a for a in accesses if isinstance(a, dict) and process_clippeur.cle(a.get("handle")) == h]
            if len(matches) != 1:
                raise ValueError(f"{uid}: accès existant unique à rapprocher pour @{h}")
            selected.append({**matches[0], "handle": h, "prive": role == "prive", "role_confirme": role})
        before = list(fiche.get("comptes") or [])
        fiche["acces_archives"] = [a for a in accesses if process_clippeur.cle(a.get("handle")) not in handles]
        fiche["acces"] = selected
        fiche["comptes"] = handles
        fiche["affectation_confirmee"] = {**proof, "comptes": deepcopy(wanted)}
        routes.setdefault(uid, {})["ordre_confirme"] = {**proof, "valeur": f"prive{private}"}
        if confirmation.get("lien"):
            url = confirmation["lien"]
            matches = [(lid, info) for lid, info in liens.get("liens", {}).items()
                       if info.get("url") == url and str(info.get("uid")) == uid]
            if len(matches) != 1:
                raise ValueError(f"{uid}: lien existant et propriétaire exacts à rapprocher")
            lid, info = matches[0]
            if any(info.get(k) for k in ("archive", "desactive", "libere", "supprime_gaml")):
                raise ValueError(f"{uid}: lien confirmé indisponible")
            fiche["lien"] = url
            fiche["lien_confirme"] = {**proof, "url": url, "id": lid}
        summary.append({"uid": uid, "avant": before, "apres": handles,
                        "roles": roles, "lien_confirme": confirmation.get("lien"),
                        "identites_historique": len(out["comptes_a_vie"][uid])})
    return out, routes, summary


def check_database(path, confirmations):
    """Read-only ownership check; never instantiate Store or change its IDs."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Registre SQLite existant requis")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        for c in confirmations:
            for account in c["comptes"]:
                rows = db.execute("SELECT a.uid FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?",
                                  (process_clippeur.cle(account["handle"]),)).fetchall()
                if rows != [(str(c["uid"]),)]:
                    raise ValueError("Alias SQLite absent ou propriétaire divergent : rapprochement requis")
            if c.get("lien"):
                row = db.execute("SELECT data FROM jobs WHERE key=?", (f"liens:{c['uid']}:{c['creatrice'].casefold()}",)).fetchone()
                job = json.loads(row[0]) if row else {}
                if job and job.get("lien") != c["lien"]:
                    raise ValueError("Job GAML divergent : rapprochement requis")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path, help="Copie hors ligne des JSON du volume")
    parser.add_argument("--confirmations", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="Nouveau dossier privé, jamais le volume")
    args = parser.parse_args()
    if args.output_dir.resolve() == args.data_dir.resolve() or args.output_dir.exists():
        parser.error("Le dossier de sortie doit être nouveau et distinct des données")
    paths = [args.data_dir / name for name in ("onboarding.json", "parcours.json", "clics.json")]
    if any(p.is_symlink() for p in paths):
        parser.error("Liens symboliques refusés pour les données")
    raw = [p.read_bytes() for p in paths]
    confirmations = json.loads(args.confirmations.read_text())
    check_database(args.data_dir / "process_clippeur.sqlite3", confirmations)
    onb, routes, summary = prepare(*(json.loads(r) for r in raw), confirmations)
    if raw != [p.read_bytes() for p in paths]:
        parser.error("Les sources ont changé pendant la préparation : aucun candidat écrit")
    args.output_dir.mkdir(parents=True, mode=0o700)
    backup = args.output_dir / "backup"
    backup.mkdir(mode=0o700)
    for source, content in zip(paths, raw):
        target = backup / source.name
        target.touch(mode=0o600)
        target.write_bytes(content)
    dbpath = args.data_dir / "process_clippeur.sqlite3"
    target = backup / dbpath.name
    target.touch(mode=0o600)
    with sqlite3.connect(dbpath.resolve().as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    for name, data in (("onboarding.candidate.json", onb), ("parcours.candidate.json", routes)):
        path = args.output_dir / name
        path.touch(mode=0o600)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    report = {"sources_sha256": {p.name: hashlib.sha256(r).hexdigest() for p, r in zip(paths, raw)},
              "comptes": summary, "application": "NON APPLIQUÉ ; comparaison du volume et rapprochement SQLite requis"}
    (args.output_dir / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
