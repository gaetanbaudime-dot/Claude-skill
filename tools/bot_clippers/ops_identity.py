"""Read-only identity projection for the marketing operations cockpit.

Join on immutable Discord UID, then GAML link UUID and normalized Instagram handle.
No passwords, access tokens, 2FA codes or app access keys are written to Sheets.
All account/manager mutations remain in their existing validated workflows.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta

COLUMNS = [
    "Discord UID", "Prénom", "Rôle", "Créatrice", "Team Leader", "TL Discord UID",
    "Manager", "Manager Discord UID", "App clipper disponible",
    "Instagram 1", "État IG 1", "Instagram 2", "État IG 2",
    "Instagram 3", "État IG 3", "Comptes attribués",
    "Lien(s) GAML", "GAML UUID", "Liens GAML attribués",
    "Visites payables 7 j clos", "Fraîcheur des visites",
    "Reels 7 j connus", "Contrôles à effectuer",
]


def _norm(value):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(value or "").casefold())
                   if unicodedata.category(ch) != "Mn").strip().lstrip("@")


def build_rows(app_keys: dict, teams: dict, accounts_for_uid, sheet_accounts: dict,
               link_state: dict, name_for_uid, measured_visits=None, today: date = None,
               reels_by_handle: dict = None) -> list:
    """Pure projection; caller injects the existing GAML accounting measurement."""
    team_role, names = {}, {}
    for group_name, group in (teams or {}).items():
        tl = str(group.get("tl") or "")
        mgr = str(group.get("manager") or "")
        for uid in group.get("vas") or []:
            team_role[str(uid)] = ("Clipper", group_name, tl, mgr)
        if tl:
            team_role[tl] = ("Team Leader", group_name, tl, mgr)
        if mgr and mgr not in team_role:
            team_role[mgr] = ("Manager", group_name, "", mgr)
        for uid, display in (group.get("noms") or {}).items():
            names[str(uid)] = display
    # Additional app-linked users with no team must still appear for reconciliation.
    uids = sorted(set(str(uid) for uid in (app_keys or {})) | set(team_role),
                  key=lambda u: _norm(names.get(u) or name_for_uid(u) or u))
    links_by_uid = {}
    for lid, data in ((link_state or {}).get("liens") or {}).items():
        uid = str((data or {}).get("uid") or "")
        if uid:
            links_by_uid.setdefault(uid, []).append((str(lid), data))
    rows = []
    for uid in uids:
        role, team_creator, tl, mgr = team_role.get(uid, ("Clipper", "", "", ""))
        name = str(names.get(uid) or name_for_uid(uid) or uid).split(" - ")[0].strip()
        handles = list(accounts_for_uid(uid) or [])
        stable_handles = [_norm(h) for h in handles if _norm(h)]
        creator_set = {str((sheet_accounts or {}).get(h, {}).get("creatrice") or "").strip()
                       for h in stable_handles}
        creator_set.discard("")
        creator = next(iter(sorted(creator_set)), team_creator)
        links = sorted(links_by_uid.get(uid) or [], key=lambda t: t[0])
        link_ids = [lid for lid, _ in links]
        urls = [str(info.get("url") or "").strip() for _, info in links if info.get("url")]
        alerts = []
        if not stable_handles and role != "Manager":
            alerts.append("Aucun compte IG relié")
        if len(stable_handles) != 3 and role == "Clipper":
            alerts.append(f"{len(stable_handles)}/3 comptes IG")
        if len(creator_set) > 1:
            alerts.append("Créatrices incohérentes")
        if role == "Clipper" and not tl:
            alerts.append("TL non assigné")
        if role == "Team Leader" and not mgr:
            alerts.append("Manager non assigné")
        if role != "Manager" and not link_ids:
            alerts.append("Lien GAML absent")
        if role != "Manager" and uid not in (app_keys or {}):
            alerts.append("App non associée")
        if any(info.get("libere") or info.get("supprime_gaml") or info.get("desactive")
               for _, info in links):
            alerts.append("Lien GAML à vérifier")
        visits, fresh = "", "Pas de lien"
        if link_ids and measured_visits is not None:
            try:
                x = measured_visits(link_ids)
                visits, fresh = (int(x), "Complet") if x is not None else ("", "Partiel / non relevé")
            except Exception:
                visits, fresh = "", "Source illisible"
        reels = []
        for h in stable_handles:
            v = (reels_by_handle or {}).get(h, {}).get("r7")
            if v is not None and str(v).strip() != "":
                try:
                    reels.append(int(v))
                except (ValueError, TypeError):
                    pass
        cells = []
        for h in stable_handles[:3]:
            cells += [h, str((sheet_accounts or {}).get(h, {}).get("etat") or "")]
        cells += [""] * (6 - len(cells))
        rows.append([
            uid, name, role, creator, str(name_for_uid(tl)).split(" - ")[0].strip() if tl else "",
            tl, str(name_for_uid(mgr)).split(" - ")[0].strip() if mgr else "", mgr,
            "OUI" if uid in (app_keys or {}) else "NON",
            *cells,
            len(stable_handles), " · ".join(urls), " · ".join(link_ids), len(link_ids),
            visits, fresh, sum(reels) if len(reels) == len(stable_handles) and reels else "",
            " · ".join(alerts) if alerts else "OK",
        ])
    return rows
