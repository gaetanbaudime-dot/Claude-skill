"""Google Drive et Sheets par compte de service (machine horizontale v2, 23/09/2026).

Le bot parle aux API officielles avec le compte de service posé dans GOOGLE_SERVICE_ACCOUNT_JSON
(le JSON complet, tel que téléchargé depuis Google Cloud). Aucun risque pour les comptes de Gaëtan :
le compte de service ne voit que ce qu'on lui partage (le classeur des logins, le dossier des créatrices).

  Drive  : lister, créer un dossier, copier un fichier ou une arborescence entière côté serveur
           (photos et Reels d'une créatrice → dossier personnel du clipper), partager en lecture par e-mail.
  Sheets : lire une plage, écrire une plage, ajouter des lignes.

Sans variable, `actif()` est faux et tout renvoie une erreur claire. Le jeton d'accès (JWT RS256 signé
avec la clé privée, échangé contre un jeton d'une heure) est mis en cache.
"""

import asyncio
import json
import logging
import os
import time
import urllib.parse

import aiohttp

journal = logging.getLogger("google")

SCOPES = ("https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets")
DRIVE = "https://www.googleapis.com/drive/v3"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
DOSSIER_MIME = "application/vnd.google-apps.folder"

_compte = None
_jeton = {"valeur": "", "expire": 0.0}
_session = None
_verrou = asyncio.Lock()


def _charger():
    global _compte
    if _compte is None:
        brut = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        _compte = json.loads(brut) if brut else {}
    return _compte


def actif() -> bool:
    c = _charger()
    return bool(c.get("client_email") and c.get("private_key"))


def email_compte() -> str:
    return _charger().get("client_email", "")


# ------------------------------------------------------------------ jeton
async def _session_http():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120), trust_env=True)
    return _session


async def jeton() -> str:
    """Jeton d'accès valable une heure (rafraîchi 5 minutes avant expiration)."""
    if not actif():
        raise RuntimeError("Google inactif : GOOGLE_SERVICE_ACCOUNT_JSON absent")
    async with _verrou:
        if _jeton["valeur"] and _jeton["expire"] - time.time() > 300:
            return _jeton["valeur"]
        import jwt                                              # PyJWT + cryptography (requirements.txt)
        c = _charger(); maintenant = int(time.time())
        assertion = jwt.encode({"iss": c["client_email"], "scope": " ".join(SCOPES), "aud": c["token_uri"],
                                "iat": maintenant, "exp": maintenant + 3600}, c["private_key"], algorithm="RS256")
        s = await _session_http()
        async with s.post(c["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                                 "assertion": assertion}) as r:
            corps = await r.json(content_type=None)
            if r.status != 200 or not corps.get("access_token"):
                raise RuntimeError(f"Google jeton {r.status} : {str(corps)[:200]}")
        _jeton["valeur"] = corps["access_token"]
        _jeton["expire"] = maintenant + int(corps.get("expires_in", 3600))
        return _jeton["valeur"]


async def _appel(methode: str, url: str, params=None, corps=None, brut=None, content_type=None):
    """Appel authentifié, une reprise sur 429/5xx, erreurs Google renvoyées lisibles."""
    s = await _session_http()
    for essai in range(3):
        entetes = {"Authorization": f"Bearer {await jeton()}"}
        if content_type:
            entetes["Content-Type"] = content_type
        async with s.request(methode, url, params=params, json=corps if brut is None else None,
                             data=brut, headers=entetes) as r:
            if r.status in (429, 500, 502, 503) and essai < 2:
                await asyncio.sleep(2 * (essai + 1))
                continue
            texte = await r.text()
            if r.status >= 400:
                try:
                    msg = json.loads(texte).get("error", {}).get("message", texte)
                except ValueError:
                    msg = texte
                raise RuntimeError(f"Google {r.status} : {str(msg)[:200]}")
            return json.loads(texte) if texte else {}
    raise RuntimeError("Google : trop de tentatives")


# ------------------------------------------------------------------ Drive
_PARAMS_DRIVES = {"supportsAllDrives": "true"}


async def drive_infos(fichier_id: str) -> dict:
    return await _appel("GET", f"{DRIVE}/files/{fichier_id}",
                        params={**_PARAMS_DRIVES, "fields": "id,name,mimeType,parents,webViewLink,driveId"})


async def drive_lister(dossier_id: str) -> list:
    """Fichiers et sous-dossiers directs (nom, id, mimeType, taille), corbeille exclue."""
    out, page = [], ""
    while True:
        params = {**_PARAMS_DRIVES, "includeItemsFromAllDrives": "true", "pageSize": "1000",
                  "q": f"'{dossier_id}' in parents and trashed = false",
                  "fields": "nextPageToken,files(id,name,mimeType,size,shortcutDetails)"}
        if page:
            params["pageToken"] = page
        r = await _appel("GET", f"{DRIVE}/files", params=params)
        out += r.get("files", [])
        page = r.get("nextPageToken", "")
        if not page:
            return out


async def drive_trouver_dossier(nom: str, parent_id: str) -> str:
    for f in await drive_lister(parent_id):
        if f.get("mimeType") == DOSSIER_MIME and f.get("name", "").strip().lower() == nom.strip().lower():
            return f["id"]
    return ""


async def drive_creer_dossier(nom: str, parent_id: str) -> str:
    r = await _appel("POST", f"{DRIVE}/files", params={**_PARAMS_DRIVES, "fields": "id"},
                     corps={"name": nom, "mimeType": DOSSIER_MIME, "parents": [parent_id]})
    return r["id"]


async def drive_copier_fichier(fichier_id: str, parent_id: str, nom: str = "") -> str:
    corps = {"parents": [parent_id]}
    if nom:
        corps["name"] = nom
    r = await _appel("POST", f"{DRIVE}/files/{fichier_id}/copy", params={**_PARAMS_DRIVES, "fields": "id"}, corps=corps)
    return r["id"]


async def drive_copier_arborescence(source_id: str, parent_id: str, nom: str, filtre=None) -> dict:
    """Copie côté serveur un dossier entier (sous-dossiers compris) sous `parent_id/nom`.
    `filtre(fichier) -> bool` pour ne copier qu'une partie (ex. : que les photos). Idempotent sur le nom :
    un dossier déjà présent est réutilisé et les fichiers déjà copiés (même nom) sont sautés.
    Renvoie {"id", "fichiers", "dossiers", "sautes"}."""
    cible = await drive_trouver_dossier(nom, parent_id) or await drive_creer_dossier(nom, parent_id)
    bilan = {"id": cible, "fichiers": 0, "dossiers": 0, "sautes": 0}
    existants = {f["name"] for f in await drive_lister(cible)}
    for f in await drive_lister(source_id):
        if f.get("mimeType") == DOSSIER_MIME:
            sous = await drive_copier_arborescence(f["id"], cible, f["name"], filtre)
            bilan["dossiers"] += 1 + sous["dossiers"]; bilan["fichiers"] += sous["fichiers"]; bilan["sautes"] += sous["sautes"]
            continue
        if filtre is not None and not filtre(f):
            continue
        if f["name"] in existants:
            bilan["sautes"] += 1
            continue
        src = f.get("shortcutDetails", {}).get("targetId") or f["id"]
        await drive_copier_fichier(src, cible, f["name"])
        bilan["fichiers"] += 1
    return bilan


async def drive_raccourci(nom: str, cible_id: str, parent_id: str) -> str:
    """Raccourci vers un fichier ou dossier (aucun espace consommé : c'est ce que le compte de service peut créer).
    Réutilise un raccourci homonyme déjà présent."""
    for f in await drive_lister(parent_id):
        if f.get("name") == nom and f.get("shortcutDetails", {}).get("targetId") == cible_id:
            return f["id"]
    r = await _appel("POST", f"{DRIVE}/files", params={**_PARAMS_DRIVES, "fields": "id"},
                     corps={"name": nom, "mimeType": "application/vnd.google-apps.shortcut", "parents": [parent_id],
                            "shortcutDetails": {"targetId": cible_id}})
    return r["id"]


async def drive_partager(fichier_id: str, email: str, role: str = "reader", prevenir: bool = False) -> str:
    """Partage à une adresse (reader / writer). Renvoie l'identifiant de permission."""
    r = await _appel("POST", f"{DRIVE}/files/{fichier_id}/permissions",
                     params={**_PARAMS_DRIVES, "sendNotificationEmail": "true" if prevenir else "false", "fields": "id"},
                     corps={"type": "user", "role": role, "emailAddress": email})
    return r.get("id", "")


async def drive_partages(fichier_id: str) -> list:
    r = await _appel("GET", f"{DRIVE}/files/{fichier_id}/permissions",
                     params={**_PARAMS_DRIVES, "fields": "permissions(id,emailAddress,role,type)"})
    return r.get("permissions", [])


async def drive_supprimer(fichier_id: str):
    await _appel("DELETE", f"{DRIVE}/files/{fichier_id}", params=_PARAMS_DRIVES)


async def drive_televerser_texte(nom: str, parent_id: str, contenu: str, mime: str = "text/plain") -> str:
    """Petit fichier texte (tests, fiches) : envoi multipart en une requête."""
    frontiere = "==frontiere_bot_ltp=="
    meta = json.dumps({"name": nom, "parents": [parent_id]})
    corps = (f"--{frontiere}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
             f"--{frontiere}\r\nContent-Type: {mime}\r\n\r\n{contenu}\r\n--{frontiere}--").encode("utf-8")
    r = await _appel("POST", "https://www.googleapis.com/upload/drive/v3/files",
                     params={**_PARAMS_DRIVES, "uploadType": "multipart", "fields": "id"},
                     brut=corps, content_type=f"multipart/related; boundary={frontiere}")
    return r["id"]


async def drive_partager_public(fichier_id: str) -> bool:
    """Lecture « toute personne ayant le lien » (26/09 : OpusClip lit la vidéo par son lien Drive). False si refusé."""
    try:
        await _appel("POST", f"{DRIVE}/files/{fichier_id}/permissions", params=_PARAMS_DRIVES,
                     corps={"type": "anyone", "role": "reader"})
        return True
    except RuntimeError as erreur:
        journal.info("Partage public de %s refusé : %s", fichier_id[:8], erreur)
        return False


async def drive_telecharger(fichier_id: str, max_octets: int = 120_000_000) -> bytes:
    """Contenu binaire d'un fichier Drive (26/09 : les TOP 20 Reels pour les variantes par clipper)."""
    s_ = await _session_http()
    entetes = {"Authorization": f"Bearer {await jeton()}"}
    async with s_.get(f"{DRIVE}/files/{fichier_id}", params={"alt": "media", **_PARAMS_DRIVES}, headers=entetes) as r:
        if r.status >= 400:
            raise RuntimeError(f"Google {r.status} : téléchargement de {fichier_id[:8]} refusé")
        donnees = await r.read()
    if len(donnees) > max_octets:
        raise RuntimeError(f"fichier trop lourd ({len(donnees) // 1_000_000} Mo)")
    return donnees


def drive_lien(fichier_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{fichier_id}"


# ------------------------------------------------------------------ Sheets
def _plage(p: str) -> str:
    return urllib.parse.quote(p, safe="!:$")


async def sheets_lire(classeur_id: str, plage: str) -> list:
    """Valeurs d'une plage (ex. « Instagram!A1:K »), lignes de chaînes, cellules vides = ''."""
    r = await _appel("GET", f"{SHEETS}/{classeur_id}/values/{_plage(plage)}",
                     params={"valueRenderOption": "UNFORMATTED_VALUE", "dateTimeRenderOption": "FORMATTED_STRING"})
    return [[("" if c is None else str(c)) for c in ligne] for ligne in r.get("values", [])]


async def sheets_ecrire(classeur_id: str, plage: str, valeurs: list) -> int:
    r = await _appel("PUT", f"{SHEETS}/{classeur_id}/values/{_plage(plage)}",
                     params={"valueInputOption": "USER_ENTERED"}, corps={"values": valeurs})
    return int(r.get("updatedCells", 0))


async def sheets_ajouter(classeur_id: str, plage: str, lignes: list) -> int:
    r = await _appel("POST", f"{SHEETS}/{classeur_id}/values/{_plage(plage)}:append",
                     params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
                     corps={"values": lignes})
    return int(r.get("updates", {}).get("updatedRows", 0))


async def sheets_onglets(classeur_id: str) -> list:
    r = await _appel("GET", f"{SHEETS}/{classeur_id}", params={"fields": "sheets(properties(title,sheetId,gridProperties))"})
    return [s["properties"]["title"] for s in r.get("sheets", [])]


async def sheets_creer_onglet(classeur_id: str, titre: str) -> bool:
    """Crée un onglet s'il n'existe pas. Renvoie True s'il a été créé, False s'il existait déjà."""
    if titre in await sheets_onglets(classeur_id):
        return False
    try:
        await _appel("POST", f"{SHEETS}/{classeur_id}:batchUpdate",
                     corps={"requests": [{"addSheet": {"properties": {"title": titre}}}]})
        return True
    except RuntimeError as erreur:
        if "already exists" in str(erreur).lower():
            return False
        raise


def colonne(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    lettres = ""
    index += 1
    while index:
        index, reste = divmod(index - 1, 26)
        lettres = chr(65 + reste) + lettres
    return lettres
