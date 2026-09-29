"""Site du tunnel candidat, servi par le bot lui-même (décision du 23/09/2026, « machine horizontale v2 »).

Remplace Google Forms + Apps Script + la liaison par téléphone :
  /candidature        le formulaire (questions dans questions_candidature.json, éditable sans code)
  /discord/connexion  le bouton « Rejoindre le Discord » : autorisation Discord officielle (OAuth2,
                      scopes identify + guilds.join) qui porte l'identifiant de candidature ; le bot
                      ajoute lui-même le candidat au serveur, déjà relié à ses réponses (100 %).
  /quiz               le quiz, servi ici (quiz.json), score renvoyé directement au bot.
  /formation          29/09 (Gaëtan, GO axe 1) : juste après le formulaire, la vidéo et le quiz sur place ; l'invitation
                      Discord ne s'affiche qu'au quiz réussi (QUIZ_AVANT_DISCORD=0 rend l'ancien ordre).
  /health             état du service (pour Railway et pour Claude).

Tout est derrière WEB_ACTIVER=1 (défaut : actif si DISCORD_CLIENT_ID et DISCORD_CLIENT_SECRET sont
posés). Le module ne connaît pas bot_discord : il reçoit ses dépendances dans `demarrer(client, deps)`.
"""

import asyncio
import hashlib
import hmac
import html
import json
import unicodedata
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
QUIZ_SEUIL = int(os.environ.get("QUIZ_SEUIL", "30") or 30)   # 24/09 : 27 → 30
QUIZ_ESSAIS_MAX = int(os.environ.get("QUIZ_ESSAIS_MAX", "2") or 2)
QUIZ_CYCLE_H = int(os.environ.get("QUIZ_CYCLE_H", "24") or 24)          # deux échecs → deux nouveaux essais 24 h plus tard
# 29/09 (Gaëtan, GO axe 1) : le pic de motivation, c'est la seconde où il envoie le formulaire. La formation et le quiz se
# passent là, sur le site ; Discord n'arrive qu'au quiz réussi, avec le test de montage qui l'y attend.
QUIZ_AVANT_DISCORD = os.environ.get("QUIZ_AVANT_DISCORD", "1").strip() != "0"
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


def lien_parrainage(uid) -> str:
    """29/09 (GO axe 8) : le lien du formulaire propre à un clipper ; la candidature envoyée par ce lien porte son parrain, et
    le parrainage s'enregistre tout seul à l'arrivée du filleul sur Discord (plus de `!parrain` à taper)."""
    base = lien_candidature()
    return f"{base}?p={jeton('p' + str(uid))}" if base else ""


def _parrain_depuis(param: str) -> str:
    valeur = verifier_jeton((param or "").strip())
    return valeur[1:] if valeur and valeur.startswith("p") and valeur[1:].isdigit() else ""


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
.ck{display:flex;align-items:flex-start;gap:12px;margin:10px 0 4px;font-weight:600;font-size:16px;cursor:pointer}
.ck input{width:22px;height:22px;flex:none;margin:1px 0 0;accent-color:var(--n)}
.regles{margin:10px 0 0;padding-left:22px;color:#333}.regles li{margin:10px 0;line-height:1.5}
.aide2{color:#555;margin:14px 0 0;line-height:1.5}.aide2 a{color:var(--n);font-weight:600}
html{-webkit-text-size-adjust:100%}a,button,label{touch-action:manipulation;-webkit-tap-highlight-color:transparent}
.b{transition:transform .08s ease,opacity .15s ease}.b:active{transform:scale(.98);opacity:.9}.b[disabled]{opacity:.65;cursor:wait}
h2{font-size:18px;color:var(--n);margin:22px 0 8px}
.box{background:#eef3fa;border:1px solid #cddbef;border-radius:12px;padding:14px 16px;margin:16px 0;line-height:1.6}
.etapes{margin:8px 0 0;padding-left:22px}.etapes li{margin:8px 0;line-height:1.5}
.petit{color:#666;font-size:14px;line-height:1.5;margin:16px 0 0}.petit a{color:var(--n);font-weight:600}
.sec{display:flex;align-items:center;gap:10px;font-size:17px;color:var(--n);margin:30px 0 4px;padding-top:18px;border-top:1px solid #e3e6eb}
.sec span{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:var(--n);color:#fff;font-size:15px;flex:none}
.aide{color:#555;font-size:14px;font-weight:400;margin:-2px 0 8px;line-height:1.45}
input,select,textarea{font-size:16px}
</style>"""


# 30/09 (Gaëtan : « améliore la rapidité de chargement et la fluidité ») : un seul envoi par formulaire (le bouton passe à
# « ⏳ Un instant… » et se bloque — les candidatures en double venaient des doubles appuis), rétabli si on revient en arrière.
SCRIPT = ("<script>document.addEventListener('submit',function(e){var f=e.target;if(f.dataset.envoi){e.preventDefault();return}"
          "f.dataset.envoi='1';var b=f.querySelector('button[type=submit]');if(b){b.dataset.t=b.textContent;"
          "b.textContent='⏳ Un instant…';b.disabled=true}});window.addEventListener('pageshow',function(){"
          "document.querySelectorAll('form').forEach(function(f){delete f.dataset.envoi;var b=f.querySelector("
          "'button[type=submit]');if(b&&b.dataset.t){b.textContent=b.dataset.t;b.disabled=false}})});</script>")
# La connexion à Loom se prépare dès la première page : la vidéo de la page formation démarre plus vite.
PRECONNEXION = ("<link rel='preconnect' href='https://www.loom.com' crossorigin>"
                "<link rel='dns-prefetch' href='https://cdn.loom.com'>")


def _page(titre: str, corps: str, tete: str = "") -> web.Response:
    doc = (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width,initial-scale=1'><title>{html.escape(titre)}</title>{PRECONNEXION}{tete}{STYLE}</head>"
           f"<body><div class='w'><div class='c'>{corps}</div><p style='text-align:center;color:#777;"
           f"font-size:12px'>LTP · candidature clipper</p></div>{SCRIPT}</body></html>")
    r = web.Response(text=doc, content_type="text/html", charset="utf-8")
    r.enable_compression()                                              # gzip : la page pèse trois fois moins sur le réseau
    return r


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
    elif t == "checkbox":
        # 27/09 : « J'ACCEPTE devient une case cochée » — les 5 règles se lisent ici, la case est obligatoire
        h = (f"<label class='ck'><input type='checkbox' name='{i}' value='oui'{' checked' if valeur else ''}{req}> "
             f"{html.escape(q.get('case', 'Oui'))}</label>")
    elif t == "number":
        h = (f"<input type='number' name='{i}' value='{v}' min='{q.get('min', 0)}' max='{q.get('max', 120)}'"
             f" inputmode='numeric'{req}>")
    elif t == "tel":
        h = f"<input type='tel' name='{i}' value='{v}' inputmode='tel' autocomplete='tel'{req}>"
    else:
        h = f"<input type='text' name='{i}' value='{v}'{req}>"
    # 29/09 soir (Gaëtan : « plus lisible et compréhensible ») : l'aide se lit sous le libellé, avant la case à remplir
    aide = f"<div class='aide'>{html.escape(q['aide'])}</div>" if q.get("aide") else ""
    if t == "checkbox":
        # 29/09 : une règle par ligne, puis la case
        # 30/09 (Gaëtan) : une règle par ligne, ses phrases à la suite (pas de retour à la ligne dans une règle)
        regles = ("<ol class='regles'>" + "".join(f"<li>{html.escape(r)}</li>" for r in _regles(q["aide"])) + "</ol>") if q.get("aide") else ""
        return regles + h
    return f"<label>{html.escape(q['label'])}</label>{aide}{h}"


def _regles(texte: str) -> list:
    """« 1. … 2. … 5. … » en une ligne → une liste de règles sans leur numéro (l'ordre vient de la liste HTML)."""
    morceaux = [m.strip() for m in re.split(r"(?:^|\s)\d{1,2}\.\s+", texte) if m.strip()]
    return morceaux if len(morceaux) > 1 else [texte.strip()]


def _intro_html(intro) -> str:
    """La présentation de l'annonce : une chaîne ou une liste de paragraphes (questions_candidature.json).
    `**gras**` devient du gras, une ligne `---` devient un séparateur. Tout le reste est échappé."""
    paragraphes = intro if isinstance(intro, list) else [intro]
    out = []

    def fmt(t: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(t)).replace("\n", "<br>")

    for p in paragraphes:
        if isinstance(p, list):                                        # 29/09 soir : une liste = les étapes numérotées
            out.append("<ol class='etapes'>" + "".join(f"<li>{fmt(str(e))}</li>" for e in p if str(e).strip()) + "</ol>")
            continue
        p = str(p or "").strip()
        if not p:
            continue
        if p == "---":
            out.append("<hr>")
        elif p.startswith("## "):
            out.append(f"<h2>{fmt(p[3:])}</h2>")
        elif p.startswith("!! "):
            out.append(f"<div class='box'>{fmt(p[3:])}</div>")
        elif p.startswith("-# "):
            out.append(f"<p class='petit'>{fmt(p[3:])}</p>")
        else:
            out.append(f"<p>{fmt(p)}</p>")
    return "".join(out)


def _formulaire(valeurs=None, erreur: str = "", parrain: str = "") -> web.Response:
    cfg = _questions(); valeurs = valeurs or {}
    champs, section, n = "", None, 0
    for q in cfg["questions"]:
        if q.get("section") and q["section"] != section:              # 29/09 soir : les questions groupées en étapes
            section, n = q["section"], n + 1
            champs += f"<div class='sec'><span>{n}</span>{html.escape(section)}</div>"
        champs += _champ(q, valeurs.get(q["id"], ""))
    err = f"<div class='e'>{html.escape(erreur)}</div>" if erreur else ""
    corps = (f"<h1>{html.escape(cfg.get('titre', 'Candidature'))}</h1>{_intro_html(cfg.get('intro', ''))}{err}"
             f"<form method='post' action='/candidature' autocomplete='on'>"
             f"<input type='hidden' name='f' value='{html.escape(jeton('f' + str(int(time.time()))))}'>"
             + (f"<input type='hidden' name='p' value='{html.escape(parrain)}'>" if parrain else "") + f"{champs}"
             f"<button class='b' type='submit'>Passer à la formation + quizz</button></form>")   # 30/09 (Gaëtan)
    video = re.search(r"loom\.com/(?:share|embed)/([0-9a-f]{16,})", _deps.get("LIEN_VIDEO_FORMATION", "") or "")
    tete = (f"<link rel='prefetch' href='https://www.loom.com/embed/{video.group(1)}'>" if video else "")
    return _page(cfg.get("titre", "Candidature"), corps, tete)


# ------------------------------------------------------------------ candidature
def _ip(request) -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?")


def _jeton_formulaire_ok(valeur: str, maintenant: float = None) -> bool:
    """Le jeton « f<horodatage> » posé à l'affichage : signature valide, envoi entre 3 secondes et 24 heures après."""
    v = verifier_jeton(valeur or "")
    if not v or not v.startswith("f") or not v[1:].isdigit():
        return False
    ecart = (maintenant or time.time()) - int(v[1:])
    return 3 <= ecart <= 86400


def _rafale(ip: str, max_par_heure: int = 6) -> bool:
    maintenant = time.time()
    liste = [t for t in _tentatives_ip.get(ip, []) if maintenant - t < 3600]
    _tentatives_ip[ip] = liste
    if len(liste) >= max_par_heure:
        return True
    liste.append(maintenant)
    return False


async def get_candidature(request):
    p = request.query.get("p", "")
    return _formulaire(parrain=p if _parrain_depuis(p) else "")


async def post_candidature(request):
    data = await request.post()
    # 29/09 soir : le pot de miel (champ caché « site_web ») était rempli par la saisie automatique des navigateurs, et un vrai
    # candidat recevait « Merci, candidature reçue » sans que rien ne soit enregistré (Gaëtan l'a vu en testant). Remplacé
    # par un jeton signé posé à l'affichage du formulaire : absent, faux, ou renvoyé en moins de 3 secondes → on réaffiche
    # le formulaire avec un message, jamais un faux « merci ».
    if not _jeton_formulaire_ok(data.get("f", "")):
        journal.warning("Candidature web refusée : jeton de formulaire %s", "absent" if not data.get("f") else "invalide ou trop rapide")
        reprise = {k: str(v) for k, v in data.items() if k not in ("f", "p")}
        return _formulaire(reprise, "Petit souci technique : vérifie tes réponses et appuie de nouveau sur « Envoyer ».",
                           data.get("p", ""))
    if _rafale(_ip(request)):
        return _formulaire(dict(data), "Trop de tentatives depuis ta connexion. Réessaie dans une heure.", data.get("p", ""))
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
        return _formulaire(reponses, "Il manque : " + " · ".join(m[:60] for m in manquants[:4]), data.get("p", ""))
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
                                     "par exemple +261 34 12 345 67 ou +229 01 23 45 67.", data.get("p", ""))
    cand_id = secrets.token_urlsafe(9)
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    ancienne = pipe.setdefault("candidatures", {}).get(tel) or {}
    pipe["candidatures"][tel] = {**ancienne, "prenom": (reponses.get("prenom") or "").strip().title(),
                                 "pays": reponses.get("pays", ""), "pseudo": reponses.get("telegram", ""),
                                 "date": maintenant, "id": cand_id, "source": "web",
                                 "reponses": reponses}
    parrain = _parrain_depuis(data.get("p", ""))
    if parrain:
        pipe["candidatures"][tel]["parrain"] = parrain
    pipe.setdefault("candidatures_web", {})[cand_id] = {"tel": tel, "date": maintenant}
    ecrire(fichier, pipe)
    journal.info("Candidature web %s (%s, …%s)%s", cand_id, reponses.get("pays", "?"), tel[-4:], " parrainée" if parrain else "")
    # 29/09 : la sauvegarde dans le classeur passe AVANT l'invitation — depuis l'invitation personnelle du matin, le chemin qui
    # redirige vers l'invitation sortait de la fonction sans écrire la ligne « Candidatures bot ». En tâche de fond : la page
    # suivante ne l'attend pas.
    if _deps.get("journaliser_candidature"):
        asyncio.create_task(_journaliser(reponses))
    fiche_inv = {"tel": tel, "prenom": pipe["candidatures"][tel]["prenom"], "pays": reponses.get("pays", "")}
    if _deps.get("invitation_site") and QUIZ_AVANT_DISCORD and _quiz().get("questions"):
        # 30/09 (« améliore la rapidité ») : l'invitation se crée pendant qu'il regarde la formation, la page arrive sans
        # attendre les deux appels à Discord ; /discord/invitation l'attend ou la crée si besoin.
        _lancer_invitation(cand_id, fiche_inv)
        raise web.HTTPSeeOther(location=f"/formation?t={jeton(cand_id)}")
    # 29/09 : une invitation personnelle plutôt que l'autorisation Discord (4 candidats sur 5 s'y perdaient).
    invitation = ""
    if _deps.get("invitation_site"):
        try:
            invitation = await _deps["invitation_site"](cand_id, {"tel": tel, "prenom": pipe["candidatures"][tel]["prenom"],
                                                                  "pays": reponses.get("pays", "")})
        except Exception as erreur:                                 # noqa: BLE001 — l'OAuth reste en secours
            journal.warning("Invitation du site : %s", erreur)
    if invitation:
        pipe = lire(fichier, {"liaisons": {}, "etats": {}})
        pipe.setdefault("candidatures_web", {}).setdefault(cand_id, {"tel": tel, "date": maintenant})["invitation"] = invitation
        ecrire(fichier, pipe)
        if QUIZ_AVANT_DISCORD and _quiz().get("questions"):
            raise web.HTTPSeeOther(location=f"/formation?t={jeton(cand_id)}")
        raise web.HTTPSeeOther(location=f"/discord/invitation?t={jeton(cand_id)}")
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and WEB_URL_PUBLIQUE):
        # Connexion Discord pas encore configurée : on garde le lien d'invitation classique.
        lien = _deps.get("LIEN_DISCORD", "")
        return _page("Merci", "<h1>Candidature reçue ✅</h1><p>Rejoins maintenant le Discord et envoie ton "
                              "numéro WhatsApp au bot en message privé : il te relie et t'envoie la formation.</p>"
                              + (f"<a class='b' href='{html.escape(lien)}'>Rejoindre le Discord</a>" if lien else ""))
    raise web.HTTPSeeOther(location=f"/discord/connexion?t={jeton(cand_id)}")


_invitations_en_cours: dict = {}                                            # cand_id → tâche de création de l'invitation


async def _creer_invitation(cand_id: str, fiche: dict) -> str:
    try:
        url = await _deps["invitation_site"](cand_id, fiche)
    except Exception as erreur:                                         # noqa: BLE001 — l'OAuth reste en secours
        journal.warning("Invitation du site : %s", erreur)
        return ""
    if url:
        lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
        pipe = lire(fichier, {"liaisons": {}, "etats": {}})
        pipe.setdefault("candidatures_web", {}).setdefault(cand_id, {"tel": fiche.get("tel", "")})["invitation"] = url
        ecrire(fichier, pipe)
    return url


def _lancer_invitation(cand_id: str, fiche: dict):
    t = _invitations_en_cours.get(cand_id)
    if t is None or (t.done() and not t.result()):
        _invitations_en_cours[cand_id] = asyncio.create_task(_creer_invitation(cand_id, fiche))


async def _invitation_prete(cand_id: str, attente: float = 10.0) -> str:
    """L'URL de l'invitation : déjà enregistrée, en cours de création (on l'attend), ou créée maintenant (après un redémarrage)."""
    pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
    fiche_web = (pipe.get("candidatures_web", {}).get(cand_id) or {})
    if fiche_web.get("invitation"):
        return fiche_web["invitation"]
    if not _deps.get("invitation_site") or not fiche_web.get("tel"):
        return ""
    cand = (pipe.get("candidatures", {}).get(fiche_web["tel"]) or {})
    _lancer_invitation(cand_id, {"tel": fiche_web["tel"], "prenom": cand.get("prenom", ""), "pays": cand.get("pays", "")})
    try:
        return await asyncio.wait_for(asyncio.shield(_invitations_en_cours[cand_id]), attente) or ""
    except asyncio.TimeoutError:
        return ""
    finally:
        t = _invitations_en_cours.get(cand_id)
        if t is not None and t.done():
            _invitations_en_cours.pop(cand_id, None)


async def _journaliser(reponses: dict):
    try:
        await _deps["journaliser_candidature"](reponses, "web")
    except Exception as erreur:                                     # noqa: BLE001
        journal.warning("Sauvegarde candidature : %s", erreur)


# ------------------------------------------------------------------ Discord OAuth2
def _url_autorisation(state: str) -> str:
    from urllib.parse import urlencode
    return "https://discord.com/oauth2/authorize?" + urlencode({
        "client_id": DISCORD_CLIENT_ID, "response_type": "code",
        "redirect_uri": f"{WEB_URL_PUBLIQUE}/discord/callback",
        "scope": "identify guilds.join", "state": state, "prompt": "consent"})


def _cand_depuis(param: str) -> str:
    """L'identifiant de candidature porté par `t`/`state`. Signature valide → direct. Sinon (29/09 : un navigateur Samsung a
    livré un jeton avec la signature altérée), l'identifiant seul suffit s'il existe côté serveur : il fait 72 bits d'aléa,
    il n'est pas devinable, et la candidature est déjà enregistrée. Journalisé pour suivre ces cas."""
    param = (param or "").strip()
    cand_id = verifier_jeton(param)
    if cand_id:
        return cand_id
    brut = param.split(".", 1)[0].strip()
    if brut and _deps.get("lire_json"):
        try:
            pipe = _deps["lire_json"](_deps["FICHIER_PIPELINE"], {})
            if brut in (pipe.get("candidatures_web") or {}):
                journal.warning("Site : jeton altéré (%s), candidature %s retrouvée par son identifiant", param[:60], brut)
                return brut
        except Exception as erreur:                                     # noqa: BLE001
            journal.warning("Site : lecture du pipeline impossible (%s)", erreur)
    journal.warning("Site : jeton invalide (%s)", param[:60])
    return ""


def _secours() -> str:
    """Le filet sous les pages Discord : WhatsApp de Gaëtan si configuré."""
    lien = _deps.get("WHATSAPP", "")
    return (f"<p class='aide2'>Ça bloque ? <a href='{html.escape(lien)}'>Écris à Gaëtan sur WhatsApp</a>, "
            "il te fait entrer à la main.</p>") if lien else ""


async def get_invitation(request):
    """29/09 : la page après le formulaire — un bouton vers l'invitation personnelle (l'appli Discord s'ouvre, « Accepter »)."""
    cand_id = _cand_depuis(request.query.get("t", ""))
    if not cand_id:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Ce lien est abîmé. Recommence depuis le formulaire, ça prend "
                                      "deux minutes.</p><a class='b' href='/candidature'>Refaire le formulaire</a>" + _secours())
    url = await _invitation_prete(cand_id)                              # 30/09 : créée en arrière-plan depuis le formulaire
    if not url:
        raise web.HTTPSeeOther(location=f"/discord/connexion?t={jeton(cand_id)}")
    journal.info("Site : page « Rejoindre le Discord » (invitation) pour la candidature %s", cand_id)
    corps = ("<h1>Candidature reçue ✅</h1>"
             "<p><b>Dernière étape : rejoins le Discord.</b> Appuie sur le bouton, l'appli Discord s'ouvre, tu appuies sur "
             "<b>Accepter l'invitation</b>, et ton salon perso t'attend avec la formation et ton quizz.</p>"
             "<ol class='regles'><li>Pas encore de compte Discord ? Crée-le quand Discord te le demande (e-mail + mot de passe), "
             "l'invitation s'ouvre juste après.</li>"
             "<li>Cette invitation est pour toi seul, valable 7 jours.</li>"
             "<li>Une fois sur le serveur, ouvre le salon à ton prénom : tout se passe là.</li></ol>"
             f"<a class='b' href='{html.escape(url)}'>Rejoindre le Discord</a>" + _secours())
    return _page("Rejoindre le Discord", corps)


async def get_connexion(request):
    cand_id = _cand_depuis(request.query.get("t", ""))
    if not cand_id:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Ce lien est abîmé. Recommence depuis le formulaire, "
                                      "ça prend deux minutes.</p>" + (f"<a class='b' href='/candidature'>Refaire le formulaire</a>")
                                      + _secours())
    journal.info("Site : page « Rejoindre le Discord » pour la candidature %s", cand_id)
    corps = ("<h1>Candidature reçue ✅</h1>"
             "<p><b>Dernière étape : rejoins le Discord.</b> Appuie sur le bouton, Discord te demande d'autoriser "
             "<b>LTP</b> à t'ajouter au serveur, tu appuies sur <b>Autoriser</b>, et le bot t'écrit tout de suite "
             "avec la formation.</p>"
             "<ol class='regles'><li>Discord te demande de te connecter ? Connecte-toi, puis il t'affiche l'autorisation.</li>"
             "<li>Pas encore de compte Discord ? Crée-le sur l'écran de Discord (e-mail + mot de passe), puis reviens ici "
             "et appuie à nouveau sur le bouton.</li>"
             "<li>Tu as l'appli Discord sur ton téléphone ? Elle peut s'ouvrir toute seule, c'est normal : appuie sur "
             "Autoriser.</li></ol>"
             f"<a class='b' href='{html.escape(_url_autorisation(jeton(cand_id)))}'>Rejoindre le Discord</a>"
             + _secours())
    return _page("Rejoindre le Discord", corps)


async def get_callback(request):
    cand_id = _cand_depuis(request.query.get("state", ""))
    code = request.query.get("code", "")
    if request.query.get("error"):                                      # 29/09 : Discord dit pourquoi (access_denied…), on le garde
        journal.warning("OAuth refusé par Discord pour %s : %s — %s", cand_id or "?", request.query.get("error"),
                        request.query.get("error_description", "")[:120])
    if not cand_id or not code:
        return _page("Refusé", ("<h1>Autorisation refusée</h1><p>Sans autorisation, le bot ne peut pas t'ajouter au serveur. "
                                "Réessaie et appuie sur <b>Autoriser</b> sur l'écran de Discord.</p>"
                                f"<a class='b' href='/discord/connexion?t={html.escape(jeton(cand_id))}'>Réessayer</a>" + _secours()) if cand_id
                               else "<h1>Lien invalide</h1><p>Recommence depuis le formulaire.</p><a class='b' href='/candidature'>Refaire le formulaire</a>" + _secours())
    journal.info("OAuth : retour Discord pour la candidature %s", cand_id)
    # 29/09 : le 27/09, quatre retours en double (même code, à 400 ms d'écart : l'appli Discord et le navigateur ouvrent tous
    # les deux le lien) ont donné « Invalid code » et une page d'erreur à un candidat pourtant ajouté. Le premier retour gagne,
    # les suivants revoient sa page pendant 10 minutes.
    deja = _retours.get(cand_id)
    if deja and time.time() - deja[0] < 600:
        return _page_bravo(deja[1])
    _retours[cand_id] = (time.time(), "")
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
        return _page("Presque", "<h1>Presque ✅</h1><p>Ta candidature est enregistrée mais Discord n'a pas voulu t'ajouter "
                               "au serveur automatiquement. Réessaie une fois ; si ça bloque encore, on te fait entrer à la main.</p>"
                               f"<a class='b' href='/discord/connexion?t={html.escape(jeton(cand_id))}'>Réessayer</a>" + _secours())
    journal.info("OAuth : candidature %s reliée au Discord %s (join %s)", cand_id, uid, statut)
    _retours[cand_id] = (time.time(), guild_id)
    return _page_bravo(guild_id)


_retours: dict = {}                                                         # cand_id → (instant, guild_id) des retours réussis


def _page_bravo(guild_id: str):
    lien_app = f"https://discord.com/channels/{guild_id}" if guild_id else "https://discord.com/app"
    return _page("C'est bon", "<h1>C'est bon 🎉</h1><div class='ok'>Tu es sur le serveur et ta candidature est reliée "
                             "à ton compte Discord.</div><p><b>Ouvre Discord</b> : ton salon perso t'attend, avec la "
                             "formation et ton lien de quizz. Le bot t'y parle.</p>"
                             f"<a class='b' href='{lien_app}'>Ouvrir Discord</a>")


# ------------------------------------------------------------------ formation + quiz avant Discord (29/09, GO axe 1)
def _fiche_cand(cand_id: str) -> dict:
    return ((_deps["lire_json"](_deps["FICHIER_PIPELINE"], {}).get("candidatures_web") or {}).get(cand_id)) or {}


def _url_discord(cand_id: str) -> str:
    """L'invitation personnelle si elle existe, sinon la connexion Discord (OAuth) en secours."""
    ok = _fiche_cand(cand_id).get("invitation") or _deps.get("invitation_site")   # 30/09 : l'invitation peut être en cours
    return ("/discord/invitation?t=" if ok else "/discord/connexion?t=") + jeton(cand_id)


def essais_cand(q: dict, maintenant: float = None) -> int:
    """Essais consommés dans le cycle en cours pour un quiz passé avant Discord : deux échecs → deux nouveaux essais
    QUIZ_CYCLE_H heures après le dernier."""
    essais = int((q or {}).get("essais", 0) or 0)
    if essais >= QUIZ_ESSAIS_MAX:
        try:
            age_h = ((maintenant or time.time()) - datetime.fromisoformat(q.get("date", "")).timestamp()) / 3600
        except (TypeError, ValueError):
            age_h = 0
        if age_h >= QUIZ_CYCLE_H:
            return 0
    return essais


def _attente_cand(q: dict) -> str:
    try:
        age_h = (time.time() - datetime.fromisoformat(q.get("date", "")).timestamp()) / 3600
    except (TypeError, ValueError):
        age_h = 0
    heures = max(1, int(QUIZ_CYCLE_H - age_h) + 1)
    return (f"<p>Tu as utilisé tes {QUIZ_ESSAIS_MAX} essais. <b>Tu peux recommencer dans {heures} h</b>, avec "
            f"{QUIZ_ESSAIS_MAX} nouveaux essais et ce même lien. D'ici là, revois la vidéo en entier et note les 5 mots-clés "
            "dans l'ordre.</p>")


def _video(url: str) -> str:
    """30/09 : le lecteur Loom dans la page (un bouton de moins), et un lien si le son ou l'image ne marche pas."""
    m = re.search(r"loom\.com/(?:share|embed)/([0-9a-f]{16,})", url or "")
    if not m:
        return f"<a class='b' href='{html.escape(url)}' target='_blank' rel='noopener'>1. Voir la formation</a>" if url else ""
    return (f"<div style='position:relative;padding-bottom:62%;height:0;margin:12px 0 6px;border-radius:12px;overflow:hidden'>"
            f"<iframe src='https://www.loom.com/embed/{m.group(1)}' frameborder='0' allow='autoplay; fullscreen' allowfullscreen "
            f"style='position:absolute;top:0;left:0;width:100%;height:100%'></iframe></div>"
            f"<p class='petit' style='margin-top:4px'>Pas de son ou pas d'image ? <a href='{html.escape(url)}' target='_blank' "
            f"rel='noopener'>Ouvre la vidéo sur Loom</a>.</p>")


async def get_formation(request):
    cand_id = _cand_depuis(request.query.get("t", ""))
    if not cand_id:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Ce lien est abîmé. Refais le formulaire, ça prend "
                                      "deux minutes.</p><a class='b' href='/candidature'>Refaire le formulaire</a>" + _secours())
    if (_fiche_cand(cand_id).get("quiz") or {}).get("reussi"):
        raise web.HTTPSeeOther(location=_url_discord(cand_id))
    journal.info("Site : page formation pour la candidature %s", cand_id)
    # 30/09 (Gaëtan : « ajoute un 1 et 2 aux étapes », « des phrases niveau collège », « chaque bouton pertinent »)
    corps = ("<h1>Candidature reçue ✅</h1>"
             # 30/09 (Gaëtan) : plus de paragraphe d'étapes, les titres 1️⃣ et 2️⃣ suffisent
             "<h2>1️⃣ Regarder la formation</h2>"
             + _video(_deps.get("LIEN_VIDEO_FORMATION", ""))
             + "<p><b>Note les 5 mots-clés cachés, dans l'ordre.</b> Le quizz te les demande.</p>"
             f"<a class='b' style='background:#2e7d4f' href='/quiz?c={html.escape(jeton(cand_id))}'>2️⃣ Passer le quizz</a>"
             # 30/09 (Gaëtan : « mets juste : pas le temps maintenant ? rejoins le Discord et passe le quiz plus tard »)
             f"<p class='aide2'>Pas le temps maintenant ? <a href='{html.escape(_url_discord(cand_id))}'>Rejoins le Discord</a> "
             "et passe le quizz plus tard.</p>")
    return _page("La formation", corps)


def _formulaire_quiz(quiz: dict, champ: str, valeur: str, essai: int) -> web.Response:
    qs = ""
    for n, q in enumerate(quiz["questions"], 1):
        if q.get("reponses"):                                           # 28/09 : les mots-clés se tapent, ils ne se cochent pas
            k = sum(1 for x in quiz["questions"][:n] if x.get("reponses"))   # 30/09 : « 1er mot-clé », « 2e mot-clé »…
            opts = (f"<input type='text' name='q{n}' required autocomplete='off' maxlength='40' "
                    f"placeholder='{'1er' if k == 1 else f'{k}e'} mot-clé'>")
        else:
            opts = "".join(f"<label class='o'><input type='radio' name='q{n}' value='{i}' required>{html.escape(c)}</label>"
                           for i, c in enumerate(q["choix"]))
        qs += f"<div class='q'><b>{n}. {html.escape(q['q'])}</b>{opts}</div>"
    seuil, total = quiz_seuil_total()
    corps = (f"<h1>{html.escape(quiz.get('titre', 'Quiz'))}</h1><p>{total} questions. Il faut {seuil} bonnes réponses. "
             f"Essai {essai} sur {QUIZ_ESSAIS_MAX}.</p>"
             f"<form method='post' action='/quiz'><input type='hidden' name='{champ}' value='{html.escape(valeur)}'>"
             f"{qs}<button class='b' type='submit'>Valider mes réponses</button></form>")
    return _page("Quizz", corps)


async def get_quiz_cand(request, cand_id: str):
    quiz = _quiz()
    if not quiz.get("questions"):
        raise web.HTTPSeeOther(location=_url_discord(cand_id))
    q = _fiche_cand(cand_id).get("quiz") or {}
    if q.get("reussi"):
        raise web.HTTPSeeOther(location=_url_discord(cand_id))
    essais = essais_cand(q)
    if essais >= QUIZ_ESSAIS_MAX:
        return _page("Quizz", "<h1>Quizz</h1>" + _attente_cand(q) + f"<a class='b' href='/formation?t={html.escape(jeton(cand_id))}'>"
                                                                 "1️⃣ Revoir la formation</a>")
    return _formulaire_quiz(quiz, "c", jeton(cand_id), essais + 1)


async def post_quiz_cand(data, cand_id: str):
    quiz = _quiz()
    lire, ecrire, fichier = _deps["lire_json"], _deps["ecrire_json"], _deps["FICHIER_PIPELINE"]
    pipe = lire(fichier, {"liaisons": {}, "etats": {}})
    fiche = (pipe.get("candidatures_web") or {}).get(cand_id)
    if not fiche or not quiz.get("questions"):
        return _page("Introuvable", "<h1>Candidature introuvable</h1><p>Recommence depuis le formulaire.</p>"
                                    "<a class='b' href='/candidature'>Refaire le formulaire</a>")
    ancien = fiche.get("quiz") or {}
    if ancien.get("reussi"):
        raise web.HTTPSeeOther(location=_url_discord(cand_id))
    essais = essais_cand(ancien)
    if essais >= QUIZ_ESSAIS_MAX:
        return _page("Quizz", "<h1>Quizz</h1>" + _attente_cand(ancien))
    score, total, details = noter(quiz, data)
    seuil, _ = quiz_seuil_total()
    reussite = score >= seuil
    fiche["quiz"] = {"score": f"{score} / {total}", "reussi": reussite, "essais": essais + 1, "details": details,
                     "date": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    ecrire(fichier, pipe)
    prenom = (pipe.get("candidatures", {}).get(fiche.get("tel", "")) or {}).get("prenom", "")
    journal.info("Site : quiz avant Discord %s pour la candidature %s (essai %s)", f"{score}/{total}", cand_id, essais + 1)
    if _deps.get("quiz_candidat"):                                      # la ligne « Quiz bot » du classeur, en tâche de fond
        asyncio.create_task(_deps["quiz_candidat"](prenom, f"{score} / {total}", essais + 1, reussite, details))
    if reussite:
        return _page("Quizz validé", f"<h1>Bravo, {score}/{total} ✅</h1>"
                                    "<p><b>Dernière étape : rejoins le Discord.</b> Ton salon perso t'y attend, avec ton test "
                                    "de montage.</p>"
                                    "<ol class='regles'><li>Pas de compte Discord ? Crée-le quand Discord le demande (e-mail + mot "
                                    "de passe).</li><li>Sur le serveur, ouvre le salon à ton prénom : tout se passe là.</li></ol>"
                                    f"<a class='b' href='{html.escape(_url_discord(cand_id))}'>3️⃣ Rejoindre le Discord</a>" + _secours())
    reste = QUIZ_ESSAIS_MAX - (essais + 1)
    suite = (f"<p>Il te reste {reste} essai. Revois la vidéo et note les 5 mots-clés, dans l'ordre.</p>"
             f"<a class='b' href='/formation?t={html.escape(jeton(cand_id))}'>1️⃣ Revoir la formation</a>"
             f"<a class='b' style='background:#2e7d4f' href='/quiz?c={html.escape(jeton(cand_id))}'>2️⃣ Repasser le quizz</a>") if reste > 0 \
        else _attente_cand(fiche["quiz"])
    return _page("Quizz", f"<h1>{score}/{total}</h1><p>Il faut {seuil}.</p>" + suite + _secours())


# ------------------------------------------------------------------ quiz
def _quiz() -> dict:
    try:
        return json.loads(FICHIER_QUIZ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def quiz_seuil_total() -> tuple:
    """(seuil, total) du quiz du site s'il est prêt, sinon ceux du Google Form (30 sur 34)."""
    quiz = _quiz()
    if quiz.get("questions"):
        return int(quiz.get("seuil") or QUIZ_SEUIL), len(quiz["questions"])
    return QUIZ_SEUIL, 34


def _norm_reponse(t: str) -> str:
    """Réponse libre comparable : sans accents, minuscules, lettres seulement, sans « s » final (« Régularité. » = « regularite »)."""
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn" and (c.isalnum() or c == " ")).strip()
    t = re.sub(r"^(la |le |les |l )", "", t).strip()
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def noter(quiz: dict, data) -> tuple:
    """(score, total, détails) d'un formulaire rempli : question à choix → l'index coché est le bon ; question libre
    (« reponses ») → la réponse normalisée est dans la liste. Détails : réponses libres données, pour le classeur."""
    score, details = 0, []
    for n, q in enumerate(quiz.get("questions", []), 1):
        brut = str(data.get(f"q{n}", "") or "")
        if q.get("reponses"):
            ok = _norm_reponse(brut) in {_norm_reponse(r) for r in q["reponses"]}
            details.append(brut.strip()[:40])
        else:
            ok = brut == str(q.get("bonne", -1))
        score += 1 if ok else 0
    return score, len(quiz.get("questions", [])), details


async def get_quiz(request):
    if request.query.get("c"):                                          # 29/09 : quiz passé avant Discord
        cand_id = _cand_depuis(request.query.get("c", ""))
        if cand_id:
            return await get_quiz_cand(request, cand_id)
    uid = verifier_jeton(request.query.get("t", ""))
    if not uid:
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Demande ton lien personnel au bot : tape "
                                      "<code>!quiz</code> sur le serveur.</p>")
    quiz = _quiz()
    if not quiz.get("questions"):
        return _page("Quizz", "<h1>Le quizz arrive</h1><p>Il est en préparation, le bot te préviendra.</p>")
    essais = _deps["essais_quiz"](uid)
    if essais >= QUIZ_ESSAIS_MAX:
        return _page("Quizz", "<h1>Quizz</h1>" + _texte_attente(uid))
    return _formulaire_quiz(quiz, "t", jeton(uid), essais + 1)


def _texte_attente(uid) -> str:
    """29/09 : deux essais ratés → deux nouveaux essais plus tard (le bot dit combien d'heures), même lien."""
    heures = 0
    try:
        heures = int(_deps["prochain_essai_quiz"](uid)) if _deps.get("prochain_essai_quiz") else 0
    except Exception:                                                   # noqa: BLE001
        heures = 0
    if heures > 0:
        return (f"<p>Tu as utilisé tes {QUIZ_ESSAIS_MAX} essais. <b>Tu peux recommencer dans {heures} h</b>, avec "
                f"{QUIZ_ESSAIS_MAX} nouveaux essais et ce même lien. D'ici là, revois la vidéo en entier et note les 5 mots-clés "
                "dans l'ordre.</p>")
    return "<p>Tu as utilisé tes essais pour l'instant. Écris au bot dans ton salon : il te dit quand tu peux recommencer.</p>"


async def post_quiz(request):
    data = await request.post()
    if data.get("c"):                                                   # 29/09 : quiz passé avant Discord
        cand_id = _cand_depuis(data.get("c", ""))
        if cand_id:
            return await post_quiz_cand(data, cand_id)
        return _page("Lien invalide", "<h1>Lien invalide</h1><p>Recommence depuis le formulaire.</p>"
                                      "<a class='b' href='/candidature'>Refaire le formulaire</a>")
    uid = verifier_jeton(data.get("t", ""))
    quiz = _quiz()
    if not uid or not quiz.get("questions"):
        return _page("Lien invalide", "<h1>Lien invalide</h1>")
    if _deps["essais_quiz"](uid) >= QUIZ_ESSAIS_MAX:
        return _page("Quizz", "<h1>Quizz</h1>" + _texte_attente(uid))
    score, total, details = noter(quiz, data)
    seuil, _ = quiz_seuil_total()
    reussite = score >= seuil
    await _deps["traiter_quiz_web"](uid, f"{score} / {total}", reussite, details)
    if reussite:
        return _page("Quizz validé", f"<h1>Bravo, {score}/{total} ✅</h1><p>Le bot t'envoie ton test de montage "
                                    "dans ton salon Discord, tout de suite.</p>")
    return _page("Quizz", f"<h1>{score}/{total}</h1><p>Il faut {seuil}. Revois la formation ; "
                         "le bot t'a écrit dans ton salon pour la suite.</p>")


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
                    web.get("/discord/invitation", get_invitation), web.get("/formation", get_formation),
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
