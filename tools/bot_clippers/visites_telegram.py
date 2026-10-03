"""Les visiteurs du site de chaque créatrice dans son groupe Telegram (03/10, Gaëtan : « une automatisation qui enverrait le
nombre de visiteurs sur chloe-callista.fr et sarah-ivanova.fr dans un groupe Telegram, dans un salon « visites de la veille » où
les gens ne peuvent pas parler, pour motiver les créatrices à poster des Reels et voir leurs clics augmenter » ; puis « simplifie :
seulement les visiteurs du domaine, pas de comparaison avec le clipping, hier, 7 derniers jours, 30 derniers jours »).

Chaque matin à VISITES_TELEGRAM_HEURE (9 h Paris), pour chaque groupe Telegram relié à une créatrice (son prénom dans le titre :
« Chloé | G&M »), le bot poste trois chiffres dans le sujet « 📈 Visites de la veille » — créé par lui, **fermé** (personne n'y
écrit : il le rouvre le temps de poster, puis le referme) :

    📈 chloe-callista.fr
    Hier (02/10) : 412 visiteurs
    7 derniers jours : 2 411
    30 derniers jours : 9 870

Les visiteurs = tous les liens GAML du domaine de la créatrice, hors robots (`/analytics/countries`, un appel par lien et par
période). Jamais un nom de clipper, jamais un lien, aucune répartition.

Découverte des groupes : le bot Telegram doit être ajouté au groupe en admin (« Gérer les sujets ») ; il voit son ajout
(`my_chat_member`) ou une mention @bot (`getUpdates`), retient le chat et le relie à la créatrice. `!visites-telegram groupes`
liste ce qu'il connaît (et le nom du bot à ajouter), `!visites-telegram test [Créatrice]` poste tout de suite."""
import asyncio
import logging
import os
import re
from datetime import date, timedelta
from urllib.parse import urlparse

import paie_clics
import telegram

journal = logging.getLogger("bot.visites_telegram")
ACTIF = os.environ.get("VISITES_TELEGRAM", "1").strip() != "0"                     # 03/10 : coupe-circuit
HEURE_PARIS = int(os.environ.get("VISITES_TELEGRAM_HEURE", "9") or 9)
SUJET_NOM = os.environ.get("VISITES_TELEGRAM_SUJET", "📈 Visites de la veille").strip() or "📈 Visites de la veille"
INTERVALLE_DECOUVERTE = int(os.environ.get("VISITES_TELEGRAM_DECOUVERTE_SEC", "300") or 300)
CREATRICES_DEFAUT = ("Chloé", "Sarah", "Sophie", "Jade", "Maddie", "Clara", "Leatitia")
# 03/10 (Gaëtan : « ajoute Leatitia ») : des créatrices sans clippers n'ont pas d'onglet dans le classeur des logins → la liste
# vient du classeur + ces prénoms + VISITES_TELEGRAM_CREATRICES (« Prénom,Prénom »), sans doublon
EN_PLUS = tuple(x.strip() for x in os.environ.get("VISITES_TELEGRAM_CREATRICES", "").split(",") if x.strip())
PERIODES = (("hier", 1), ("j7", 7), ("j30", 30))
_deps: dict = {}


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER, heure_paris, normaliser, est_staff, creatrices() (prénoms), canal_admin."""
    _deps.update(deps)


def actif() -> bool:
    return ACTIF and bool(telegram.TELEGRAM_TOKEN) and paie_clics.actif()


def _cle(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _n(t))


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
    vus, out = set(), []
    for n in [*noms, *CREATRICES_DEFAUT, *EN_PLUS]:
        if n and _n(n) not in vus:
            vus.add(_n(n)); out.append(n)
    return out


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


def liens_par_creatrice(liens: list, creatrices=None) -> dict:
    """{créatrice: {"domaine": …, "liens": [liens]}} — la créatrice du groupe GAML du lien, sinon celle dont le prénom est dans
    le domaine. 03/10 : le groupe d'abord, car un domaine ne porte pas toujours le prénom (Maddie → maaaad.fr)."""
    out = {}
    for l in liens or []:
        dom = _domaine(l.get("url") or "")
        c = creatrice_de((l.get("group") or {}).get("name") or "", creatrices) or (creatrice_de(dom, creatrices) if dom else "")
        if c:
            out.setdefault(c, {"domaine": dom, "liens": []})["liens"].append(l)
    return out


async def visiteurs(liens: list, debut: date, fin: date) -> int:
    """Les visiteurs hors robots d'une période, tous liens confondus (un appel GAML par lien)."""
    total = 0
    base = {"range": "custom", "date_from": debut.isoformat(), "date_to": fin.isoformat(), "timezone": paie_clics.FUSEAU}
    for l in liens:
        if not l.get("id"):
            continue
        pays = await paie_clics._requete("GET", "/analytics/countries", params={**base, "link_id": l["id"]})
        pays = pays if isinstance(pays, list) else (pays or {}).get("member", [])
        total += sum(int(x.get("count", 0)) for x in pays)
    return total


async def chiffres(liens: list, hier: date) -> dict:
    """{hier, j7, j30} : la veille, les 7 et les 30 derniers jours (la veille incluse)."""
    out = {}
    for cle, jours in PERIODES:
        out[cle] = await visiteurs(liens, hier - timedelta(days=jours - 1), hier)
    return out


def _nb(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def texte(domaine: str, hier: date, c: dict) -> str:
    """Trois chiffres, rien d'autre."""
    return (f"📈 {domaine}\n"
            f"Hier ({hier.strftime('%d/%m')}) : {_nb(c.get('hier', 0))} visiteurs\n"
            f"7 derniers jours : {_nb(c.get('j7', 0))}\n"
            f"30 derniers jours : {_nb(c.get('j30', 0))}")


# ------------------------------------------------------------------ Telegram : groupes et sujets
async def decouvrir(d: dict) -> list:
    """Lit les mises à jour Telegram (ajout du bot à un groupe, mention @bot) et relie les groupes aux créatrices. Renvoie les
    chat_id nouvellement reliés (sans sujet encore)."""
    avant = set(d["groupes"])
    try:
        maj = await telegram.appeler("getUpdates", {"offset": int(d.get("offset") or 0), "timeout": 0,
                                                    "allowed_updates": ["message", "my_chat_member"]})
    except RuntimeError as erreur:
        journal.warning("Visites Telegram : getUpdates : %s", erreur)
        return []
    creatrices = _creatrices()
    for u in maj or []:
        d["offset"] = max(int(d.get("offset") or 0), int(u.get("update_id", 0)) + 1)
        msg = u.get("message") or {}
        chat = (u.get("my_chat_member") or msg).get("chat") or {}
        if chat.get("type") not in ("group", "supergroup") or not chat.get("id"):
            continue
        if u.get("my_chat_member") and (u["my_chat_member"].get("new_chat_member") or {}).get("status") in ("left", "kicked"):
            d["groupes"].pop(str(chat["id"]), None)
            continue
        cle = str(chat["id"])
        info = d["groupes"].setdefault(cle, {})
        info["titre"] = chat.get("title") or ""
        info["forum"] = info.get("forum") or bool(chat.get("is_forum")) or bool(msg.get("is_topic_message"))
        if not info.get("creatrice"):
            info["creatrice"] = creatrice_de(info["titre"], creatrices)
        # 03/10 : le sujet créé à la main par Gaëtan — reconnu à son nom dès qu'un message y est posté (ou à sa création)
        cree = msg.get("forum_topic_created") or ((msg.get("reply_to_message") or {}).get("forum_topic_created"))
        if msg.get("message_thread_id") and cree and _cle(cree.get("name", "")) == _cle(SUJET_NOM):
            if str(info.get("sujet_id")) != str(msg["message_thread_id"]):
                info["sujet_id"] = int(msg["message_thread_id"]); info["ferme"] = False; info.pop("erreur", None)
                journal.info("Visites Telegram : sujet « %s » retrouvé dans %s", cree.get("name"), info["titre"])
    # 03/10 : un groupe déjà connu mais pas encore relié (créatrice ajoutée depuis, ex. Leatitia) est réexaminé à chaque passage
    for info in d["groupes"].values():
        if not info.get("creatrice") and info.get("titre"):
            info["creatrice"] = creatrice_de(info["titre"], creatrices)
    return [cle for cle in d["groupes"] if cle not in avant and d["groupes"][cle].get("creatrice")]


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
    if sujet is None and info.get("forum"):                            # 03/10 (Gaëtan : « tu envoies dans le mauvais salon ») : jamais dans General
        info["erreur"] = "sujet introuvable : écris un mot dans « Visites de la veille », ou donne au bot le droit « Gérer les sujets »"
        journal.warning("Visites Telegram : pas de sujet dans %s, rien posté", info.get("titre"))
        return False
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
    """Un passage : les trois chiffres de chaque créatrice reliée, un message par groupe. Renvoie un bilan."""
    bilan = {"postes": 0, "groupes": 0, "erreurs": []}
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
        if not h.get(hier.isoformat()):
            try:
                h[hier.isoformat()] = await chiffres(bloc["liens"], hier)
            except RuntimeError as erreur:
                bilan["erreurs"].append(f"{c} : {erreur}")
                continue
            for j in [k for k in h if (hier - date.fromisoformat(k)).days > 60]:
                h.pop(j, None)
            _ecrire(d)
        if await poster(cle, info, texte(bloc["domaine"], hier, h[hier.isoformat()])):
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
                if not info.get("dernier"):
                    bilan = await executer(seulement=info["creatrice"], d=d)
                    journal.info("Visites Telegram : premier message pour %s : %s", info.get("creatrice"), bilan)
            if maintenant.hour >= HEURE_PARIS:
                d = _lire()
                if any(i.get("creatrice") and i.get("dernier") != hier for i in d["groupes"].values()):
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
        await message.reply(f"📈 {bilan['postes']} message(s) posté(s) dans {bilan['groupes']} groupe(s)"
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
    lignes = [f"📈 Visiteurs du site sur Telegram · {HEURE_PARIS} h Paris · sujet « {SUJET_NOM} »"]
    for cle, info in d["groupes"].items():
        etat = ("sujet prêt" if info.get("sujet_id") else ("sujets non activés dans le groupe" if not info.get("forum") else "sujet à trouver"))
        lignes.append(f"• {info.get('titre') or cle} → {info.get('creatrice') or 'créatrice non reconnue dans le titre'} · {etat}"
                      + (f" · dernier : {info['dernier']}" if info.get("dernier") else "") + (f" · ⚠️ {info['erreur']}" if info.get("erreur") else ""))
    if not d["groupes"]:
        lignes.append("Aucun groupe connu.")
    lignes.append(f"Pour relier un groupe : ajoute {nom_bot} au groupe Telegram de la créatrice en admin, puis écris un mot **dans le sujet « {SUJET_NOM} »** "
                  f"(le bot le retrouve à son nom). Sans sujet existant, il le crée s'il a le droit « Gérer les sujets ». Le prénom de la créatrice doit être dans le titre du groupe. "
                  "Jamais de message dans General.")
    await message.reply("\n".join(lignes)[:1900])
    return True
