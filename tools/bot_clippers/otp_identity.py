"""Conservative Gmail alias recovery for explicitly rostered Discord clippers.

Never transfer account ownership. Candidates are accepted only when:
1) user is on active team roster with exact creator;
2) its name+creator pair is unique among current roster members;
3) sheet Manager/Gérant exactly matches that name and sheet creator matches;
4) no different UID already owns the Instagram handle in onboarding.
The returned email addresses must only be used for private/ephemeral 2FA delivery.
"""
import unicodedata


def assignment_diagnostics(data, uid, normalize_handle):
    """Explain local assignment refusals using counts only; never return access values.

    This mirrors the existing local authorization rules without changing them or
    filling missing assignments from another source. Reasons are exclusive per handle.
    """
    uid = str(uid)
    declared, rows, alias_owners, handle_owners = set(), {}, {}, {}
    deliveries = data.get("livres") or {}
    for owner, record in (data.get("clippers") or {}).items():
        if not isinstance(record, dict):
            continue
        owner = str(owner)
        valid = {normalize_handle(h) for h in record.get("comptes") or []
                 if isinstance(h, str) and h.strip()}
        blocks = [record.get("acces") or []]
        for phone in (record.get("telephones") or {}).values():
            if isinstance(phone, dict):
                delivered = (phone.get("acces") or [])[:max(0, int(phone.get("donnes") or 0))]
                blocks.append(delivered)
                valid.update(normalize_handle(a.get("handle") or "")
                             for a in delivered if isinstance(a, dict))
        if owner == uid:
            declared.update(valid - {""})
        for block in blocks:
            for item in block:
                if not isinstance(item, dict):
                    continue
                handle = normalize_handle(item.get("handle") or "")
                if not handle or handle not in valid:
                    continue
                alias = str(item.get("mail") or "").strip().lower()
                delivery = deliveries.get(handle) or deliveries.get(str(item.get("handle") or "").strip().lower()) or {}
                delivered_to = str(delivery.get("uid") or "")
                if owner == uid:
                    rows.setdefault(handle, []).append((alias, delivered_to))
                if "@" in alias:
                    alias_owners.setdefault(alias, set()).add((owner, handle))
                    handle_owners.setdefault(handle, set()).add((owner, alias))
    counts = dict(compte_autorise=0, acces_absent=0, adresse_absente=0,
                  livraison_autre_uid=0, alias_ambigu=0, compte_ambigu=0)
    for handle in declared:
        entries = rows.get(handle, [])
        emails = [(alias, owner) for alias, owner in entries if "@" in alias]
        owned = [(alias, owner) for alias, owner in emails if not owner or owner == uid]
        unambiguous_alias = [(alias, owner) for alias, owner in owned if len(alias_owners[alias]) == 1]
        if not entries:
            reason = "acces_absent"
        elif not emails:
            reason = "adresse_absente"
        elif not owned:
            reason = "livraison_autre_uid"
        elif not unambiguous_alias:
            reason = "alias_ambigu"
        elif len(handle_owners[handle]) != 1:
            reason = "compte_ambigu"
        else:
            reason = "compte_autorise"
        counts[reason] += 1
    return counts


def normalized(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").casefold())
                   if unicodedata.category(c) != "Mn").strip()


def unique_aliases(uid, creator, first_name, roster, sheet_rows, owners):
    uid = str(uid)
    creator_key = normalized(creator)
    name_key = normalized(first_name)
    if not uid or not creator_key or not name_key:
        return set(), "identity_missing"
    identities = [
        str(k) for k, info in (roster or {}).items()
        if normalized((info or {}).get("creatrice")) == creator_key
        and normalized((info or {}).get("prenom")) == name_key
        and (info or {}).get("active", True)
    ]
    if identities != [uid]:
        return set(), "ambiguous_or_not_in_roster"
    alias_handles, handle_aliases = {}, {}
    for row in sheet_rows or []:
        handle = normalized(str(row.get("handle") or "").lstrip("@"))
        alias = str(row.get("mail") or "").strip().lower()
        if handle and "@" in alias:
            alias_handles.setdefault(alias, set()).add(handle)
            handle_aliases.setdefault(handle, set()).add(alias)
    candidates, seen_handles, conflicts = set(), set(), 0
    for row in sheet_rows or []:
        if normalized(row.get("creatrice")) != creator_key:
            continue
        if normalized(row.get("gerant")) != name_key:
            continue
        handle = normalized(str(row.get("handle") or "").lstrip("@"))
        alias = str(row.get("mail") or "").strip().lower()
        if not handle or "@" not in alias:
            continue
        if len(alias_handles.get(alias, ())) != 1 or len(handle_aliases.get(handle, ())) != 1:
            conflicts += 1
            continue
        owner_uids = set(map(str, owners.get(handle, set())))
        if owner_uids and owner_uids != {uid}:
            conflicts += 1
            continue
        if handle in seen_handles:
            continue
        seen_handles.add(handle)
        candidates.add(alias)
    if conflicts:
        # Fail closed for any ownership conflict; never accidentally mix accounts.
        return set(), "ownership_conflict"
    if not candidates:
        return set(), "no_verified_address"
    if len(seen_handles) > 3:
        return set(), "too_many_accounts"
    return candidates, "matched"
