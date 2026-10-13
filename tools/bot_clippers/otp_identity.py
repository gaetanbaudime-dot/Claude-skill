"""Conservative Gmail alias recovery for explicitly rostered Discord clippers.

Never transfer account ownership. Candidates are accepted only when:
1) user is on active team roster with exact creator;
2) its name+creator pair is unique among current roster members;
3) sheet Manager/Gérant exactly matches that name and sheet creator matches;
4) no different UID already owns the Instagram handle in onboarding.
The returned email addresses must only be used for private/ephemeral 2FA delivery.
"""
import unicodedata


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
