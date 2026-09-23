"""Site du tunnel candidat, servi par le bot lui-même (décision du 23/09/2026, « machine horizontale v2 »).

Remplace Google Forms + Apps Script + la liaison par téléphone :
  /candidature        le formulaire (questions dans questions_candidature.json, éditable sans code)
  /discord/connexion  le bouton « Rejoindre le Discord » : autorisation Discord officielle (OAuth2,
                      scopes identify + guilds.join) qui porte l'identifiant de candidature ; le bot
                      ajoute lui-même le candidat au serveur, déjà relié à ses réponses (100 %).
  /quiz               le quiz, servi ici (quiz.json), score renvoyé directement au bot.
  /health             état du service (pour Railway et pour Claude).

Tout est derrière WEB_ACTIVER=1 (défaut : actif si DISCORD_CLIENT_ID et DISCORD_CLIENT_SECRET sont
posés). Le module ne connaît pas bot_discord : il reçoit ses dépendances dans `demarrer(client, deps)`.
"""

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from aiohttp import web

journal = logging.getLogger("web")
DOSSIER = Path(__file__).parent

WEB_ACTIVER = os.environ.get("WEB_ACTIVER", "").strip()
PORT = int(os.environ.get("PORT", "8080") or 8080)
WEB_URL_PUBLIQUE = os.environ.get("WEB_URL_PUBLIQUE", "").strip().rstrip("/")
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "").strip()
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
WEB_SECRET = os.environ.get("WEB_SECRET", "").strip() or DISCORD_CLIENT_SECRET
QUIZ_SEUIL = int(os.environ.get("QUIZ_SEUIL", "27") or 27)
QUIZ_ESSAIS_MAX = int(os.environ.get("QUIZ_ESSAIS_MAX", "2") or 2)
GUILD_ID = os.environ.get("GUILD_ID", "").strip()
FICHIER_QUESTIONS = DOSSIER / "questions_candidature.json"
FICHIER_QUIZ = DOSSIER / "quiz.json"
API_DISCORD = "https://discord.com/api/v10"

_deps = {}                 # injecté par demarrer()
_client = None
_debut = time.time()
_tentatives_ip = {}        # anti-rafale : ip -> [timestamps]


def actif() -> bool:
    if WEB_ACTIVER == "0":
        return False
    return WEB_ACTIVER == "1" or bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET)


# ------------------------------------------------------------------ signatures
def _signer(valeur: str) -> str:
    return hmac.new((WEB_SECRET or "sans-secret").encode(), valeur.encode(), hashlib.sha256).hexdigest()[:24]


def jeton(valeur: str) -> str:
    """Jeton signé « valeur.signature » : porte l'identifiant sans qu'il soit falsifiable."""
    return f"{valeur}.{_signer(valeur)}"


def verifier_jeton(jeton_recu: str):
    if not jeton_recu or "." not in jeton_recu:
        return None
    valeur, sig = jeton_recu.rsplit(".", 1)
    return valeur if hmac.compare_digest(sig, _signer(valeur)) else None


def lien_quiz(uid) -> str:
    """Le lien de quiz personnel servi ici — vide si le site ou le quiz ne sont pas prêts."""
    if not (actif() and WEB_URL_PUBLIQUE and FICHIER_QUIZ.exists()):
        return ""
    return f"{WEB_URL_PUBLIQUE}/quiz?t={jeton(str(uid))}"


def lien_candidature() -> str:
    return f"{WEB_URL_PUBLIQUE}/candidature" if (actif() and WEB_URL_PUBLIQUE) else ""


# ------------------------------------------------------------------ HTML
STYLE = """
<style>
:root{--n:#1F3A5F;--g:#F2F4F7;--t:#111}*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--g);color:var(--t)}
.w{max-width:640px;margin:0 auto;padding:16px}
.c{background:#fff;border-radius:14px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
h1{font-size:22px;margin:0 0 10px;color:var(--n)}p{line-height:1.45;margin:10px 0}hr{border:0;border-top:1px solid #e3e6eb;margin:16px 0}
label{display:block;font-weight:600;margin:18px 0 6px;font-size:15px}
input,select,textarea{width:100%;font:inherit;padding:12px;border:1px solid #cfd4dc;border-radius:10px;background:#fff}
textarea{min-height:96px}small{color:#555;display:block;margin-top:4px}
.b{display:block;width:100%;margin-top:22px;padding:15px;border:0;border-radius:12px;background:var(--n);color:#fff;font-size:17px;font-weight:700;text-align:center;text-decoration:none;cursor:pointer}
.e{background:#fdecec;border:1px solid #f5b5b5;color:#8a1f1f;padding:12px;border-radius:10px;margin:12px 0}
.ok{background:#e9f7ef;border:1px solid #b7e1c5;color:#1e5a34;padding:12px;border-radius:10px;margin:12px 0}
.hp{position:absolute;left:-9999px}.q{margin:22px 0}.o{display:block;padding:10px 12px;border:1px solid #cfd4dc;border-radius:10px;margin:6px 0;font-weight:400}
.o input{width:auto;margin-right:8px}
</style>"""


def _page(titre: str, corps: str) -> web.Response:
    doc = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width,initial-scale=1'><title>{html.escape(titre)}</title>{STYLE}</head>"
           f"<body><div class='w'><div class='c'>{corps}</div><p style='text-align:center;color:#777;"
           f"font-size:12px'>LTP · candidature clipper</p></div></body></html>")
    return web.Response(text=doc, content_type="text/html", charset="utf-8")


def _questions() -> dict:
    try:
        return json.loads(FICHIER_QUESTIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"titre": "Candidature", "intro": "", "questions": []}


def _champ(q: dict, valeur: str = "") -> str:
    i, t = html.escape(q["id"]), q.get("type", "text")
    req = " required" if q.get("requis") else ""
    v = html.escape(valeur or "")
    if t == "textarea":
        h = f"<textarea name='{i}'{req}>{v}</textarea>"
    elif t == "select":
        opts = "".join(f"<option value='{html.escape(o)}'{' selected' if o == valeur else ''}>{html.escape(o)}</option>"
                       for o in q.get("options", []))
        h = f"<select name='{i}'{req}><option value=''>— choisis —</option>{opts}</select>"
    elif t == "number":
        h = (f"<input type='number' name='{i}' value='{v}' min='{q.get('min', 0)}' max='{q.get('max', 120)}'"
             f" inputmode='numeric'{req}>")
    elif t == "tel":
        h = f"<input type='tel' name='{i}' value='{v}' inputmode='tel' autocomplete='tel'{req}>"
    else:
        h = f"<input type='text' name='{i}' value='{v}'{req}>"
    aide = f"<small>{html.escape(q['aide'])}</small>" if q.get("aide") else ""
    return f"<label>{html.escape(q['label'])}{' *' if q.get('requis') else ''}</label>{h}{aide}"


def _intro_html(intro) -> str:
    """La présentation de l'annonce : une chaîne ou une liste de paragraphes (questions_candidature.json).
    `**gras**` devient du gras, une ligne `---` devient un séparateur. Tout le reste est échappé."""
    paragraphes = intro if isinstance(intro, list) else [intro]
    out = []
    for p in paragraphes:
        p = str(p or "").strip()
        if not p:
            continue
        if p == "---":
            out.append("<hr>")
            continue
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(p))
        out.append(f"<p>{t}</p>")
    return "".join(out)


def _formulaire(valeurs=None, erreur: str = "") -> web.Response:
    cfg = _questions(); valeurs = valeurs or {}
    champs = "".join(_champ(q, valeurs.get(q["id"], "")) for q in cfg["questions"])
    err = f"<div class='e'>{html.escape(erreur)}</div>" if erreur else ""
    corps = (f"<h1>{html.escape(cfg.get('titre', 'Candidature'))}</h1>{_intro_html(cfg.get('intro', ''))}{err}"
             f"<form method='post' action='/candidature' autocomplete='on'>"
             f"<input class='hp' type='text' name='site_web' tabindex='-1' autocomplete='off'>{champs}"
             f"<button class='b' type='submit'>Envoyer ma candidature</button></form>")
    return _page(cfg.get("titre", "Candidature"), corps)


# ------------------------------------------------------------------ candidature
def _ip(request) -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?")


def _rafale(ip: str, max_par_heure: int = 6) -> bool:
    maintenant = time.time()
    liste = [t for t in _tentatives_ip.get(ip, []) if maintenant - t < 3600]
    _tentatives_ip[ip] = liste
    if len(liste) >= max_par_heure:
        return True
    liste.append(maintenant)
    return False


async def get_candidature(request):
    return _formulaire()


async def post_candidature(request):
    data = await request.post()
    if data.get("site_web"):                                   # pot de miel : un robot a rempli le champ caché
        return _page("Merci", "<h1>Merci</h1><p>Candidature reçue.</p>")
    if _rafale(_ip(request)):
        return _formulaire(dict(data), "Trop de tentatives depuis ta connexion. Réessaie dans une heure.")
    cfg = _questions()
    reponses, manquants = {}, []
    for q in cfg["questions"]:
        val = (data.get(q["id"]) or "").strip()
        if q.get("type") == "select" and val and val not in q.get("options", []):
            val = ""
        if q.get("requis") and not val:
            manquants.append(q["label"])
        reponses[q["id"]] = val[:2000]
    if manquants:
        return _formulaire(reponses, "Il manque : " + " · ".join(m[:60] for m in manquants[:4]))
    # Mineurs : non négociable. On ne stocke rien.
    try:
        age = int(re.sub(r"\D", "", reponses.get("age", ""))[:3] or 0)
    except ValueError:
        age = 0
    if reponses.get("majeur") == "Non" or (0 < age < 18):
        return _page("Candidature", "<h1>Désolé</h1><p>Il faut avoir 18 ans pour travailler avec nous. "
                                    "Reviens nous voir plus tard.</p>")
    tel = _deps["tel_selon_pays"](reponses.get("whatsapp", ""), reponses.get("pays", ""))
    if not tel:
        return _formulaire(reponses, "Le numéro WhatsApp n'est pas lisible : écris-le avec l'indicatif, "
                                     "par exemple +261 34 12 345 67 ou +229 01 23 45 67.")
    cand_id = secrets.token_urlsafe(9)
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    ancienne = pipe.setdefault("candidatures", {}).get(tel) or {}
    pipe["candidatures"][tel] = {**ancienne, "prenom": (reponses.get("prenom") or "").strip().title(),
                                 "pays": reponses.get("pays", ""), "pseudo": reponses.get("telegram", ""),
                                 "date": maintenant, "id": cand_id, "source": "web",
                                 "reponses": reponses}
    pipe.setdefault("candidatures_web", {})[cand_id] = {"tel": tel, "date": maintenant}
    ecrire(fichier, pipe)
    journal.info("Candidature web %s (%s, …%s)", cand_id, reponses.get("pays", "?"), tel[-4:])
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and WEB_URL_PUBLIQUE):
        # Connexion Discord pas encore configurée : on garde le lien d'invitation classique.
        lien = _deps.get("LIEN_DISCORD", "")
        return _page("Merci", "<h1>Candidature reçue ✅</h1><p>Rejoins maintenant le Discord et envoie ton "
                              "numéro WhatsApp au bot en message privé : il te relie et t'envoie la formation.</p>"
                              + (f"<a class='b' href='{html.escape(lien)}'>Rejoindre le Discord</a>" if lien else ""))
    raise web.HTTPSeeOther(location=f"/discord/connexion?t={jeton(cand_id)}")


# ------------------------------------------------------------------ Discord OAuth2
def _url_autorisation(state: str) -> str:
    from urllib.parse import urlencode
    return "https://discord.com/oauth2/authorize?" + urlencode({
        "client_id": DISCORD_CLIENT_ID, "response_type": "code",
        "redirect_uri": f"{WEB_URL_PUBLIQUE}/discord/callback",
        "scope": "identify guilds.join", "state": state, "prompt": "consent"})


async def get_connexion(request):
    cand_id = verifier_jeton(request.query.get("t", ""))
    if not cand_id:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Recommence depuis le formulaire.</p>")
    corps = ("<h1>Candidature reçue ✅</h1><p>Dernière étape : rejoins le Discord. Discord te demande "
             "d'autoriser <b>LTP</b> à t'ajouter au serveur, tu confirmes, et le bot t'écrit tout de suite "
             "avec la formation.</p><p>Pas encore de compte Discord ? Crée-le sur l'écran suivant, puis "
             "reviens sur ce bouton.</p>"
             f"<a class='b' href='{html.escape(_url_autorisation(jeton(cand_id)))}'>Rejoindre le Discord</a>")
    return _page("Rejoindre le Discord", corps)


async def get_callback(request):
    cand_id = verifier_jeton(request.query.get("state", ""))
    code = request.query.get("code", "")
    if not cand_id or not code:
        return _page("Refusé", "<h1>Autorisation refusée</h1><p>Sans autorisation, le bot ne peut pas t'ajouter. "
                               f"<a href='/discord/connexion?t={html.escape(jeton(cand_id))}'>Réessayer</a>" if cand_id
                               else "<h1>Lien invalide</h1><p>Recommence depuis le formulaire.</p>")
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    fiche_web = pipe.get("candidatures_web", {}).get(cand_id)
    if not fiche_web:
        return _page("Introuvable", "<h1>Candidature introuvable</h1><p>Recommence depuis le formulaire.</p>")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.post(f"{API_DISCORD}/oauth2/token", data={
                "client_id": DISCORD_CLIENT_ID, "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": f"{WEB_URL_PUBLIQUE}/discord/callback"}) as r:
            if r.status != 200:
                journal.warning("OAuth token %s : %s", r.status, (await r.text())[:200])
                return _page("Erreur", "<h1>Discord n'a pas répondu</h1><p>Réessaie dans une minute : "
                                       f"<a href='/discord/connexion?t={html.escape(jeton(cand_id))}'>rejoindre le Discord</a>.</p>")
            jeton_acces = (await r.json()).get("access_token", "")
        async with session.get(f"{API_DISCORD}/users/@me", headers={"Authorization": f"Bearer {jeton_acces}"}) as r:
            if r.status != 200:
                return _page("Erreur", "<h1>Identité Discord illisible</h1><p>Réessaie dans une minute.</p>")
            moi = await r.json()
        uid = str(moi.get("id", ""))
        guild_id = GUILD_ID or (str(_client.guilds[0].id) if _client and _client.guilds else "")
        # Pré-enregistrement : on_member_join saura que cet arrivant est attendu et à qui il correspond.
        pipe = lire(fichier, {"liaisons": {}, "etats": {}})
        pipe.setdefault("web_attendus", {})[uid] = {"cand": cand_id, "tel": fiche_web["tel"],
                                                    "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        ecrire(fichier, pipe)
        prenom = (pipe.get("candidatures", {}).get(fiche_web["tel"]) or {}).get("prenom", "")
        async with session.put(f"{API_DISCORD}/guilds/{guild_id}/members/{uid}",
                               headers={"Authorization": f"Bot {_deps['DISCORD_TOKEN']}"},
                               json={"access_token": jeton_acces, **({"nick": prenom[:32]} if prenom else {})}) as r:
            statut = r.status
            if statut not in (201, 204):
                journal.warning("guilds.join %s : %s", statut, (await r.text())[:200])
    if statut == 204:
        # Déjà membre du serveur (arrivé avant par invitation) : on relie tout de suite.
        membre = _deps["membre_par_id"](uid)
        if membre is not None:
            asyncio.create_task(_deps["traiter_liaison"](membre, fiche_web["tel"]))
            pipe = lire(fichier, {"liaisons": {}, "etats": {}}); pipe.get("web_attendus", {}).pop(uid, None); ecrire(fichier, pipe)
    elif statut != 201:
        return _page("Presque", "<h1>Presque ✅</h1><p>Ta candidature est enregistrée mais je n'ai pas pu t'ajouter "
                               "au serveur automatiquement. Rejoins-le avec le lien de l'annonce et envoie ton "
                               "numéro WhatsApp au bot en message privé.</p>")
    journal.info("OAuth : candidature %s reliée au Discord %s (join %s)", cand_id, uid, statut)
    lien_app = f"https://discord.com/channels/{guild_id}" if guild_id else "https://discord.com/app"
    return _page("C'est bon", "<h1>C'est bon 🎉</h1><div class='ok'>Tu es sur le serveur et ta candidature est reliée "
                             "à ton compte Discord.</div><p><b>Ouvre Discord</b> : le bot t'a envoyé un message privé "
                             "avec la formation et ton lien de quiz. Si tu ne vois rien, active les messages privés "
                             "dans les paramètres de confidentialité du serveur.</p>"
                             f"<a class='b' href='{lien_app}'>Ouvrir Discord</a>")


# ------------------------------------------------------------------ quiz
def _quiz() -> dict:
    try:
        return json.loads(FICHIER_QUIZ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


async def get_quiz(request):
    uid = verifier_jeton(request.query.get("t", ""))
    if not uid:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Demande ton lien personnel au bot : tape "
                                      "<code>!quiz</code> sur le serveur.</p>")
    quiz = _quiz()
    if not quiz.get("questions"):
        return _page("Quiz", "<h1>Le quiz arrive</h1><p>Il est en préparation, le bot te préviendra.</p>")
    essais = _deps["essais_quiz"](uid)
    if essais >= QUIZ_ESSAIS_MAX:
        return _page("Quiz", "<h1>Quiz</h1><p>Tu as utilisé tes essais. Écris au bot si tu veux retenter "
                             "dans quelques semaines.</p>")
    qs = ""
    for n, q in enumerate(quiz["questions"], 1):
        opts = "".join(f"<label class='o'><input type='radio' name='q{n}' value='{i}' required>{html.escape(c)}</label>"
                       for i, c in enumerate(q["choix"]))
        qs += f"<div class='q'><b>{n}. {html.escape(q['q'])}</b>{opts}</div>"
    corps = (f"<h1>{html.escape(quiz.get('titre', 'Quiz'))}</h1><p>{len(quiz['questions'])} questions · seuil "
             f"{QUIZ_SEUIL}/{len(quiz['questions'])} · essai {essais + 1}/{QUIZ_ESSAIS_MAX}</p>"
             f"<form method='post' action='/quiz'><input type='hidden' name='t' value='{html.escape(jeton(uid))}'>"
             f"{qs}<button class='b' type='submit'>Valider mes réponses</button></form>")
    return _page("Quiz", corps)


async def post_quiz(request):
    data = await request.post()
    uid = verifier_jeton(data.get("t", ""))
    quiz = _quiz()
    if not uid or not quiz.get("questions"):
        return _page("Lien invalide", "<h1>Lien invalide</h1>")
    if _deps["essais_quiz"](uid) >= QUIZ_ESSAIS_MAX:
        return _page("Quiz", "<h1>Quiz</h1><p>Tu as utilisé tes essais.</p>")
    score = sum(1 for n, q in enumerate(quiz["questions"], 1)
                if str(data.get(f"q{n}", "")) == str(q.get("bonne", -1)))
    total = len(quiz["questions"])
    reussite = score >= QUIZ_SEUIL
    await _deps["traiter_quiz_web"](uid, f"{score} / {total}", reussite)
    if reussite:
        return _page("Quiz validé", f"<h1>Bravo, {score}/{total} ✅</h1><p>Le bot t'envoie ton test de montage "
                                    "en message privé sur Discord, tout de suite.</p>")
    return _page("Quiz", f"<h1>{score}/{total}</h1><p>Il faut {QUIZ_SEUIL}. Revois la formation ; "
                         "le bot t'a écrit pour la suite.</p>")


# ------------------------------------------------------------------ santé
async def get_health(request):
    return web.json_response({"ok": True, "uptime_s": int(time.time() - _debut),
                              "bot_connecte": bool(_client and _client.is_ready()),
                              "candidature": bool(lien_candidature()), "quiz": FICHIER_QUIZ.exists(),
                              "oauth": bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and WEB_URL_PUBLIQUE)})


async def get_racine(request):
    raise web.HTTPFound(location="/candidature")


def creer_app() -> web.Application:
    app = web.Application(client_max_size=256 * 1024)
    app.add_routes([web.get("/", get_racine), web.get("/health", get_health),
                    web.get("/candidature", get_candidature), web.post("/candidature", post_candidature),
                    web.get("/discord/connexion", get_connexion), web.get("/discord/callback", get_callback),
                    web.get("/quiz", get_quiz), web.post("/quiz", post_quiz)])
    return app


async def demarrer(client, deps: dict):
    """Lance le serveur HTTP sur PORT (Railway) dans le même processus que le bot."""
    global _client, _deps
    _client, _deps = client, deps
    if not actif():
        journal.info("Site candidature inactif (WEB_ACTIVER / DISCORD_CLIENT_ID absents)")
        return
    runner = web.AppRunner(creer_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    journal.info("Site candidature démarré sur le port %s (%s)", PORT, WEB_URL_PUBLIQUE or "URL publique non posée")
