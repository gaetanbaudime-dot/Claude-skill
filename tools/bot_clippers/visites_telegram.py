"""Les visites de la veille dans le groupe Telegram de chaque créatrice (03/10, Gaëtan : « une automatisation qui enverrait le nombre
de visiteurs sur chloe-callista.fr et sarah-ivanova.fr dans un groupe Telegram, dans un salon « visites de la veille » où les gens ne
peuvent pas parler, pour motiver les créatrices à poster des Reels et voir leurs clics augmenter » — Loris fait le marketing vertical
de Chloé et Sarah en octobre).

Chaque matin à VISITES_TELEGRAM_HEURE (9 h Paris), pour chaque groupe Telegram relié à une créatrice (son prénom dans le titre :
« Chloé | G&M »), le bot poste dans le sujet « 📈 Visites de la veille » — créé par lui, **fermé** (personne n'y écrit : il le rouvre
le temps de poster, puis le referme) : les visites hors robots de la veille sur TOUS les liens GAML de son domaine, réparties
« toi / clippers / agence », la variation vs l'avant-veille, les francophones, la courbe des 7 jours, le record des 30 jours. Jamais
un nom de clipper ni un lien de tracking : la créatrice voit un chiffre qui monte, pas la machine.

Découverte des groupes : le bot Telegram doit être ajouté au groupe en admin (« Gérer les sujets ») ; il voit son ajout
(`my_chat_member`) ou une mention @bot (`getUpdates`), retient le chat et le relie à la créatrice. `!visites-telegram groupes`
liste ce qu'il connaît (et le nom du bot à ajouter), `!visites-telegram test [Créatrice]` poste tout de suite."""
import asyncio
import logging
import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import paie_clics
import telegram

journal = logging.getLogger("bot.visites_telegram")
HEURE_PARIS = int(os.environ.get("VISITES_TELEGRAM_HEURE", "9") or 9)
SUJET_NOM = os.environ.get("VISITES_TELEGRAM_SUJET", "📈 Visites de la veille").strip() or "📈 Visites de la veille"
INTERVALLE_DECOUVERTE = int(os.environ.get("VISITES_TELEGRAM_DECOUVERTE_SEC", "300") or 300)
JOURS_COURBE, JOURS_RECORD = 7, 30
CREATRICES_DEFAUT = ("Chloé", "Sarah", "Sophie", "Jade", "Maddie", "Clara")
MOTS_CLIPPERS = ("clipping", "clipper")
MOTS_AGENCE = ("rianah", "metricool", "loris", "facebook", "fb", "agence", "tiktok", "ytb", "youtube")
BARRES = "▁▂▃▄▅▆▇█"
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, heure_paris, normaliser, est_staff, creatrices() (prénoms), canal_admin."""
    _deps.update(deps)


def actif() -> bool:
    return bool(telegram.TELEGRAM_TOKEN) and paie_clics.actif()


def _n(t):
    return _deps["normaliser"](t or "") if _deps.get("normaliser") else (t or "").strip().lower()


def _lire() -> dict:
    d = _deps["lire_json"](_deps["FICHIER"], {}) if _deps.get("lire_json") else {}
    d.setdefault("groupes", {}); d.setdefault("historique", {}); d.setdefault("offset", 0)
    return d


def _ecrire(d: dict):
    if _deps.get("ecrire_json"):
        _deps["ecrire_json"](_deps["FICHIER"], d)


def _creatrices() -> list:
    try:
        noms = list(_deps["creatrices"]()) if _deps.get("creatrices") else []
    except Exception:                                                   # noqa: BLE001
        noms = []
    return [n for n in noms if n] or list(CREATRICES_DEFAUT)


def creatrice_de(texte: str, creatrices=None) -> str:
    """Le prénom de créatrice contenu dans un titre de groupe ou un domaine (« Chloé | G&M », chloe-callista.fr) ; '' sinon."""
    plat = re.sub(r"[^a-z0-9]", "", _n(texte))
    for c in (creatrices or _creatrices()):
        if re.sub(r"[^a-z0-9]", "", _n(c)) in plat:
            return c
    return ""


def _domaine(url: str) -> str:
    try:
        return (urlparse(url if "://" in (url or "") else f"https://{url}").netloc or "").lower().removeprefix("www.")
    except Exception:                                                   # noqa: BLE001
        return ""


def categorie(lien: dict) -> str:
    """« clippers » (note ou nom « Clipping Prénom »), « agence » (Rianah, Metricool, Loris, Facebook…), sinon « toi »."""
    texte = _n(f"{lien.get('name') or ''} {lien.get('note') or ''} {lien.get('slug') or ''}")
    if any(m in texte for m in MOTS_CLIPPERS):
        return "clippers"
    mots = set(re.split(r"[^a-z0-9]+", texte))
    if any(m in mots for m in MOTS_AGENCE):
        return "agence"
    return "toi"


def liens_par_creatrice(liens: list, creatrices=None) -> dict:
    """{créatrice: {"domaine": …, "liens": [liens]}} — le domaine du lien (url) contient le prénom de la créatrice."""
    out = {}
    for l in liens or []:
        if not l.get("enabled", True) and l.get("enabled") is not None:
            pass                                                        # un lien désactivé compte quand même : ses visites passées existent
        dom = _domaine(l.get("url") or "")
        c = creatrice_de(dom, creatrices) if dom else ""
        if not c:
            continue
        out.setdefault(c, {"domaine": dom, "liens": []})["liens"].append(l)
    return out


async def releve_jour(liens: list, jour: date) -> dict:
    """Les visites hors robots d'un jour pour une liste de liens : total, toi/clippers/agence, francophones (payables)."""
    out = {"total": 0, "toi": 0, "clippers": 0, "agence": 0, "fr": 0, "liens": 0}
    base = {"range": "custom", "date_from": jour.isoformat(), "date_to": jour.isoformat(), "timezone": paie_clics.FUSEAU}
    for l in liens:
        if not l.get("id"):
            continue
        pays = await paie_clics._requete("GET", "/analytics/countries", params={**base, "link_id": l["id"]})
        pays = pays if isinstance(pays, list) else (pays or {}).get("member", [])
        n = sum(int(x.get("count", 0)) for x in pays)
        fr = sum(int(x.get("count", 0)) for x in pays if str(x.get("country", "")) in paie_clics.PAYS_PAYES)
        out["total"] += n; out["fr"] += fr; out[categorie(l)] += n; out["liens"] += 1
    return out


def courbe(valeurs: list) -> str:
    haut = max([v for v in valeurs if v is not None] or [0])
    out = ""
    for v in valeurs:
        if v is None:
            out += "·"
        elif haut <= 0:
            out += BARRES[0]
        else:
            out += BARRES[min(len(BARRES) - 1, int(round(v / haut * (len(BARRES) - 1))))]
    return out


def _pct(nouveau: int, ancien: int) -> str:
    if ancien <= 0:
        return "" if nouveau <= 0 else "▲ nouveau"
    delta = (nouveau - ancien) / ancien * 100
    fleche = "▲" if delta > 0.5 else ("▼" if delta < -0.5 else "＝")
    return f"{fleche} {delta:+.0f} % vs la veille"


JOURS_FR = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")


def texte(creatrice: str, domaine: str, historique: dict, jour: date) -> str:
    """Le message du matin pour une créatrice : hier, la répartition, les francophones, 7 jours, le record du mois."""
    h = historique.get(creatrice) or {}
    hier = h.get(jour.isoformat()) or {}
    avant = h.get((jour - timedelta(days=1)).isoformat()) or {}
    total = int(hier.get("total", 0))
    lignes = [f"📈 {creatrice} · visites d'hier ({JOURS_FR[jour.weekday()]} {jour.strftime('%d/%m')})"]
    variation = _pct(total, int(avant.get("total", 0))) if avant else ""
    lignes.append(f"👀 {total} sur {domaine}" + (f" · {variation}" if variation else ""))
    parts = [(f"toi {int(hier.get('toi', 0))}" if hier.get("toi") else ""),
             (f"agence {int(hier.get('agence', 0))}" if hier.get("agence") else ""),
             (f"clippers {int(hier.get('clippers', 0))}" if hier.get("clippers") else "")]
    parts = [x for x in parts if x]
    if len(parts) > 1:
        lignes.append("   " + " · ".join(parts))
    if hier.get("fr"):
        lignes.append(f"🇫🇷 {int(hier['fr'])} francophones")
    jours = [(jour - timedelta(days=i)) for i in range(JOURS_COURBE - 1, -1, -1)]
    valeurs = [int(h[j.isoformat()]["total"]) if h.get(j.isoformat()) else None for j in jours]
    total7 = sum(v for v in valeurs if v)
    sem = [h.get((jour - timedelta(days=i)).isoformat()) for i in range(JOURS_COURBE, 2 * JOURS_COURBE)]
    sem_avant = sum(int(x["total"]) for x in sem if x) if all(sem) else 0
    tendance = ""
    if sem_avant > 0:
        d7 = (total7 - sem_avant) / sem_avant * 100
        tendance = f" · semaine {'▲' if d7 > 0.5 else ('▼' if d7 < -0.5 else '＝')} {d7:+.0f} %"
    lignes.append(f"📅 7 jours : {courbe(valeurs)} · {total7}{tendance}")
    passe = [(j, int(v["total"])) for j, v in h.items() if (jour - date.fromisoformat(j)).days < JOURS_RECORD]
    if passe:
        j_rec, rec = max(passe, key=lambda jv: jv[1])
        if rec > 0:
            lignes.append(f"🏆 record 30 jours : {rec}" + (" (hier !)" if j_rec == jour.isoformat() else f" ({date.fromisoformat(j_rec).strftime('%d/%m')})"))
    return "\n".join(lignes)


# ------------------------------------------------------------------ Telegram : groupes et sujets
async def decouvrir(d: dict) -> list:
    """Lit les mises à jour Telegram (ajout du bot à un groupe, mention @bot) et relie les groupes aux créatrices. Renvoie les
    chat_id nouvellement reliés."""
    nouveaux = []
    try:
        maj = await telegram.appeler("getUpdates", {"offset": int(d.get("offset") or 0), "timeout": 0,
                                                    "allowed_updates": ["message", "my_chat_member"]})
    except RuntimeError as erreur:
        journal.warning("Visites Telegram : getUpdates : %s", erreur)
        return []
    creatrices = _creatrices()
    for u in maj or []:
        d["offset"] = max(int(d.get("offset") or 0), int(u.get("update_id", 0)) + 1)
        chat = (u.get("my_chat_member") or u.get("message") or {}).get("chat") or {}
        if chat.get("type") not in ("group", "supergroup") or not chat.get("id"):
            continue
        if u.get("my_chat_member") and (u["my_chat_member"].get("new_chat_member") or {}).get("status") in ("left", "kicked"):
            d["groupes"].pop(str(chat["id"]), None)
            continue
        cle = str(chat["id"])
        info = d["groupes"].setdefault(cle, {})
        info["titre"] = chat.get("title") or ""
        info["forum"] = bool(chat.get("is_forum"))
        if not info.get("creatrice"):
            info["creatrice"] = creatrice_de(info["titre"], creatrices)
        if info.get("creatrice") and cle not in nouveaux and not info.get("sujet_id"):
            nouveaux.append(cle)
    return nouveaux


async def assurer_sujet(chat_id: str, info: dict) -> int | None:
    """Le sujet « Visites de la veille » du groupe : créé s'il manque (droit « gérer les sujets »), fermé après création."""
    if info.get("sujet_id"):
        return int(info["sujet_id"])
    if not info.get("forum"):
        return None                                                     # groupe sans sujets : on poste dans le fil principal
    try:
        sujet = await telegram.appeler("createForumTopic", {"chat_id": int(chat_id), "name": SUJET_NOM, "icon_color": 0x6FB9F0})
        info["sujet_id"] = int(sujet["message_thread_id"])
        try:
            await telegram.appeler("closeForumTopic", {"chat_id": int(chat_id), "message_thread_id": info["sujet_id"]})
            info["ferme"] = True
        except RuntimeError as erreur:
            journal.warning("Visites Telegram : sujet non fermé dans %s : %s", info.get("titre"), erreur)
        return info["sujet_id"]
    except RuntimeError as erreur:
        journal.warning("Visites Telegram : sujet non créé dans %s (%s) — le bot est-il admin « gérer les sujets » ?", info.get("titre"), erreur)
        info["erreur"] = str(erreur)[:120]
        return None


async def poster(chat_id: str, info: dict, message: str) -> bool:
    """Poste dans le sujet (rouvert le temps du message, puis refermé), sinon dans le fil principal."""
    sujet = await assurer_sujet(chat_id, info)
    if sujet and info.get("ferme"):
        try:
            await telegram.appeler("reopenForumTopic", {"chat_id": int(chat_id), "message_thread_id": sujet})
        except RuntimeError as erreur:
            journal.warning("Visites Telegram : réouverture du sujet dans %s : %s", info.get("titre"), erreur)
    try:
        await telegram.envoyer(int(chat_id), message, sujet)
        ok = True
    except RuntimeError as erreur:
        journal.warning("Visites Telegram : message non posté dans %s : %s", info.get("titre"), erreur)
        info["erreur"] = str(erreur)[:120]
        ok = False
    if sujet:
        try:
            await telegram.appeler("closeForumTopic", {"chat_id": int(chat_id), "message_thread_id": sujet})
            info["ferme"] = True
        except RuntimeError as erreur:
            info["ferme"] = False
            journal.warning("Visites Telegram : sujet non refermé dans %s : %s", info.get("titre"), erreur)
    return ok


# ------------------------------------------------------------------ cycle
async def executer(jour: date | None = None, seulement: str = "", d: dict | None = None) -> dict:
    """Un passage : les relevés manquants (hier et jusqu'à 7 jours en arrière), un message par groupe relié. Renvoie un bilan."""
    bilan = {"postes": 0, "releves": 0, "groupes": 0, "erreurs": []}
    if not actif():
        return bilan
    d = d if d is not None else _lire()
    hier = jour or (_deps["heure_paris"]().date() - timedelta(days=1) if _deps.get("heure_paris") else date.today() - timedelta(days=1))
    cibles = {cle: info for cle, info in d["groupes"].items() if info.get("creatrice")
              and (not seulement or _n(info["creatrice"]) == _n(seulement))}
    if not cibles:
        return bilan
    liens = await paie_clics.liens_gaml()
    liens = liens if isinstance(liens, list) else (liens or {}).get("member", [])
    par_creatrice = liens_par_creatrice(liens, _creatrices())
    for cle, info in cibles.items():
        c = info["creatrice"]
        bloc = par_creatrice.get(c)
        if not bloc:
            bilan["erreurs"].append(f"{c} : aucun lien GAML sur un domaine à son prénom")
            continue
        h = d["historique"].setdefault(c, {})
        for i in range(JOURS_COURBE - 1, -1, -1):                      # les jours manquants, du plus ancien au plus récent
            j = hier - timedelta(days=i)
            if j.isoformat() in h and (i > 0 or h[j.isoformat()].get("liens")):
                continue
            try:
                h[j.isoformat()] = await releve_jour(bloc["liens"], j)
                bilan["releves"] += 1
            except RuntimeError as erreur:
                bilan["erreurs"].append(f"{c} {j.isoformat()} : {erreur}")
                break
        for j in [k for k in h if (hier - date.fromisoformat(k)).days > 2 * JOURS_RECORD]:
            h.pop(j, None)
        _ecrire(d)
        if hier.isoformat() not in h:
            continue
        if await poster(cle, info, texte(c, bloc["domaine"], d["historique"], hier)):
            bilan["postes"] += 1
            info["dernier"] = hier.isoformat()
        bilan["groupes"] += 1
        _ecrire(d)
    return bilan


async def boucle(client):
    """Toutes les INTERVALLE_DECOUVERTE secondes : les nouveaux groupes (premier message tout de suite) ; chaque jour à HEURE_PARIS,
    le message du matin dans chaque groupe relié."""
    if not actif():
        journal.info("Visites Telegram désactivées (TELEGRAM_TOKEN ou GAML_API_KEY absent)")
        return
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            d = _lire()
            nouveaux = await decouvrir(d)
            _ecrire(d)
            maintenant = _deps["heure_paris"]()
            hier = (maintenant.date() - timedelta(days=1)).isoformat()
            for cle in nouveaux:
                info = d["groupes"][cle]
                journal.info("Visites Telegram : groupe « %s » relié à %s", info.get("titre"), info.get("creatrice"))
                bilan = await executer(seulement=info["creatrice"], d=d)
                journal.info("Visites Telegram : premier message pour %s : %s", info.get("creatrice"), bilan)
            if maintenant.hour >= HEURE_PARIS:
                d = _lire()
                en_retard = [c for c, i in d["groupes"].items() if i.get("creatrice") and i.get("dernier") != hier]
                if en_retard:
                    bilan = await executer(d=d)
                    journal.info("Visites Telegram : %s", bilan)
        except Exception as erreur:                                      # noqa: BLE001
            journal.exception("Visites Telegram : %s", erreur)
        await asyncio.sleep(INTERVALLE_DECOUVERTE)


async def commande(message, texte_cmd: str) -> bool:
    """`!visites-telegram` : état · `groupes` : les groupes connus et le bot à ajouter · `test [Créatrice]` : poste tout de suite ·
    `lier Créatrice chat_id` : relie un groupe à la main · `oublier chat_id`."""
    mots = texte_cmd.split()
    if not mots or mots[0].lower() not in ("!visites-telegram", "!visites-tg"):
        return False
    if _deps.get("est_staff") and not _deps["est_staff"](message.author):
        await message.reply("Réservé aux managers et aux admins.")
        return True
    if not actif():
        await message.reply("Visites Telegram inactives : `TELEGRAM_TOKEN` et `GAML_API_KEY` dans Railway.")
        return True
    action = mots[1].lower() if len(mots) > 1 else "groupes"
    d = _lire()
    if action == "test":
        bilan = await executer(seulement=" ".join(mots[2:]) if len(mots) > 2 else "", d=d)
        await message.reply(f"📈 {bilan['postes']} message(s) posté(s) dans {bilan['groupes']} groupe(s), {bilan['releves']} relevé(s) GAML"
                            + (" · " + " ; ".join(bilan["erreurs"])[:900] if bilan["erreurs"] else "")
                            + ("" if bilan["groupes"] else " · aucun groupe relié : `!visites-telegram groupes`"))
        return True
    if action == "lier" and len(mots) >= 4:
        d["groupes"][mots[3]] = {"titre": mots[3], "creatrice": mots[2], "forum": True}
        _ecrire(d)
        await message.reply(f"✅ Groupe {mots[3]} relié à {mots[2]}. `!visites-telegram test {mots[2]}` pour poster.")
        return True
    if action == "oublier" and len(mots) >= 3:
        d["groupes"].pop(mots[2], None); _ecrire(d)
        await message.reply("🗑️ Oublié.")
        return True
    await decouvrir(d); _ecrire(d)
    try:
        moi = await telegram.appeler("getMe", {})
        nom_bot = f"@{moi.get('username')}" if isinstance(moi, dict) and moi.get("username") else "le bot"
    except RuntimeError:
        nom_bot = "le bot"
    lignes = [f"📈 Visites de la veille sur Telegram · {HEURE_PARIS} h Paris · sujet « {SUJET_NOM} »"]
    for cle, info in d["groupes"].items():
        etat = ("sujet prêt" if info.get("sujet_id") else ("sujets non activés dans le groupe" if not info.get("forum") else "sujet à créer"))
        lignes.append(f"• {info.get('titre') or cle} → {info.get('creatrice') or 'créatrice non reconnue dans le titre'} · {etat}"
                      + (f" · dernier : {info['dernier']}" if info.get("dernier") else "") + (f" · ⚠️ {info['erreur']}" if info.get("erreur") else ""))
    if not d["groupes"]:
        lignes.append("Aucun groupe connu.")
    lignes.append(f"Pour relier un groupe : ajoute {nom_bot} au groupe Telegram de la créatrice **en admin avec « Gérer les sujets »**, "
                  f"puis écris {nom_bot} dans le groupe. Le prénom de la créatrice doit être dans le titre du groupe. Le premier message part dans les 5 minutes.")
    await message.reply("\n".join(lignes)[:1900])
    return True
