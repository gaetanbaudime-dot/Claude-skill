"""Provision TOP-talent brands with the agency's existing Metricool credentials.

Official API: https://app.metricool.com/api/swagger.json (Brands/Connections V2).
Single bot, durable journal and filesystem lock on /data. An uncertain creation is
never retried automatically. No credentials, app keys or connection URLs in logs.
"""
import asyncio
import fcntl
import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp
import google_api

LOG = logging.getLogger("metricool.onboarding")
TAB = "Metricool · demandes"
LOCK = asyncio.Lock()


def instant(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return t if t.tzinfo else None
    except (ValueError, TypeError):
        return None


def eligible(row, now):
    t = instant(row[11] if len(row) > 11 else "")
    try:
        f = float(str(row[6]).replace(" ", "").replace(",", "."))
        return f.is_integer() and f >= 500 and t is not None and timedelta(0) <= now-t <= timedelta(hours=48)
    except (ValueError, TypeError, IndexError):
        return False


def url_valide(url):
    u = urlparse(str(url))
    host = u.hostname or ""
    return u.scheme == "https" and (host in {"app.metricool.com", "mtr.cool"} or host.endswith(".mtr.cool")) and not u.username and not u.password and not u.port and u.path not in {"", "/"}


def expiration(data):
    e = data.get("expiresAt") or {}
    if not isinstance(e, dict):
        return instant(e)
    t = datetime.fromisoformat(e["dateTime"])
    return t.replace(tzinfo=ZoneInfo(e["timezone"])) if not t.tzinfo else t


class Api:
    def __init__(self, session):
        self.session = session
        self.uid = os.environ.get("METRICOOL_USER_ID", "").strip()
        self.token = os.environ.get("METRICOOL_API_KEY", "").strip()

    async def call(self, method, route, brand=None, **kwargs):
        if not self.uid.isdigit() or not self.token:
            raise RuntimeError("identifiants Metricool absents")
        params = {"userId": self.uid}
        if brand:
            params["blogId"] = str(brand)
        async with self.session.request(method, "https://app.metricool.com/api/"+route,
                params=params, headers={"X-Mc-Auth": self.token}, allow_redirects=False, **kwargs) as r:
            if r.status == 404:
                return None
            if r.status >= 300:
                raise RuntimeError(f"Metricool HTTP {r.status}")
            d = await r.json()
            return d.get("data", d) if isinstance(d, dict) else d

    async def brands(self):
        b = await self.call("GET", "v2/settings/brands")
        if not isinstance(b, list) or any(not isinstance(x, dict) or not x.get("id") or not x.get("ownerUserId") for x in b):
            raise RuntimeError("liste de marques non comprise")
        return b

    async def capacity(self):
        v = await self.call("GET", "admin/max-profiles")
        if isinstance(v, bool) or not str(v).isdigit():
            raise RuntimeError("plafond Metricool non compris")
        return min(25, int(v))


def save(path, state):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        os.chmod(tmp, 0o600)
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


async def provision(api, row, state, persist, now):
    """row was validated against current app identity and agency recovery evidence."""
    key = hashlib.sha256(f"{row[1]}:{row[2]}:{row[3]}".encode()).hexdigest()[:20]
    label = f"G&M TOP · @{row[3]} · {key}"
    brands = await api.brands()
    owned = [b for b in brands if str(b.get("ownerUserId")) == api.uid and not b.get("isShared")]
    cap = await api.capacity()
    if not 0 < cap <= 25 or len(owned) > cap:
        raise RuntimeError("capacité invalide")
    record = state.get(key) or {}
    candidates = [b for b in owned if str(b["id"]) == str(record.get("id")) or b.get("label") == label
                  or (b.get("networksData") or {}).get("instagramData") == row[3]]
    if len(candidates) > 1:
        raise RuntimeError("marque ambiguë")
    if candidates:
        brand = candidates[0]
    else:
        if record:
            raise RuntimeError("création incertaine : rapprochement administrateur requis")
        if len(owned) >= cap:
            raise RuntimeError("plafond de marques atteint")
        # Durable intent BEFORE a non-idempotent create. Never blindly retry it.
        state[key] = {"phase": "creating", "label": label}
        persist()
        form = aiohttp.FormData()
        form.add_field("brandLabel", label, content_type="text/plain")
        created = await api.call("POST", "v2/settings/brands", data=form)
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError("résultat création incertain")
        state[key] = {"phase": "created", "id": created["id"], "label": label}
        persist()
        brands = await api.brands()
        owned = [b for b in brands if str(b.get("ownerUserId")) == api.uid and not b.get("isShared")]
        brand = next((b for b in owned if b["id"] == created["id"]), None)
        if brand is None or len(owned) > cap:
            raise RuntimeError("propriété/capacité non confirmée après création")
    if (brand.get("networksData") or {}).get("instagramData") not in (None, "", row[3]):
        raise RuntimeError("autre Instagram déjà connecté")
    info = await api.call("GET", "v2/settings/brands/connections/anonymous-link", brand["id"])
    if info is None or not expiration(info) or expiration(info) <= now:
        info = await api.call("POST", "v2/settings/brands/connections/anonymous-link", brand["id"])
    expires = expiration(info)
    if not url_valide(info.get("link")) or not expires or expires <= now:
        u = urlparse(str(info.get("link")))
        raise RuntimeError(f"lien non valide : scheme={u.scheme}, host={u.hostname}, chemin_present={u.path not in {'', '/'}}, expiration={expires}")
    state[key] = {"phase": "ready", "id": brand["id"], "label": label}
    persist()
    # O contains the actual API expiry (not an assumed duration).
    connected = (brand.get("networksData") or {}).get("instagramData") == row[3]
    return ["connecté" if connected else "prêt", str(brand["id"]), "oui", "oui", str(len(owned)), now.isoformat(),
            info["link"], now.isoformat(), expires.isoformat()]


async def traiter(classeur, comptes_app):
    if LOCK.locked() or not os.environ.get("DONNEES_DIR"):
        return
    async with LOCK:
        root = Path(os.environ["DONNEES_DIR"])
        with (root / "metricool_onboarding.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            path = root / "metricool_onboarding.json"
            state = json.loads(path.read_text()) if path.exists() else {}
            try:
                rows = await google_api.sheets_lire(classeur, f"'{TAB}'!A2:O")
            except Exception:
                return  # No requests yet. Do not create the sheet from the bot.
            if not any(len(r) > 6 and r[6] in {"demandé", "préparation", "prêt"} for r in rows):
                return
            import onboarding
            import codes_2fa
            accounts = await onboarding.lire_comptes()
            aliases = codes_2fa._lire()
            now = datetime.now(timezone.utc)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                api = Api(session)
                for idx, raw in enumerate(rows, 2):
                    r = (raw + [""] * 15)[:15]
                    if r[6] not in {"demandé", "préparation", "prêt"}:
                        continue
                    current = [c for c in comptes_app if c[0] == r[1] and c[3] == r[2] and c[4] == r[3]]
                    if len(current) != 1 or not eligible(current[0], now):
                        continue
                    source = [c for c in accounts if c.get("handle") == r[3] and c.get("mdp") and c.get("mail")]
                    # Existing controlled mailbox + registered agency recovery route,
                    # or explicit admin approval in the PRIVATE sheet. No client flag.
                    proof = len(source) == 1 and source[0]["mail"].strip().lower() in aliases and codes_2fa.actif()
                    if r[9] != "oui" and not proof:
                        LOG.info("Metricool demande ligne %s : contrôle récupération agence requis", idx)
                        continue
                    try:
                        values = await provision(api, r, state, lambda: save(path, state), now)
                        await google_api.sheets_ecrire(classeur, f"'{TAB}'!G{idx}:O{idx}", [values], brut=True)
                        LOG.info("Metricool provisioning ligne %s : prêt, marque %s", idx, values[1])
                    except Exception as e:
                        LOG.warning("Metricool provisioning ligne %s : %s", idx, str(e)[:130])


async def boucle(client):
    """Requests need not wait for the next 15-minute Dashboard publication."""
    await client.wait_until_ready()
    await asyncio.sleep(100)
    while not client.is_closed():
        try:
            import pilotage
            classeur = await pilotage._classeur()
            if classeur:
                current = await google_api.sheets_lire(classeur, "'Comptes app'!A2:L")
                await traiter(classeur, current)
        except Exception as error:
            LOG.warning("Metricool onboarding : %s", type(error).__name__)
        await asyncio.sleep(60)
