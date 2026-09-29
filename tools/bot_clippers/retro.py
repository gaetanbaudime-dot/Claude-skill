"""Rétrospective nocturne (27/09, Gaëtan : « fais en sorte que le bot s'améliore tout seul avec chacune des interactions
personnelles… il faut qu'il arrive à s'auto-corriger comme on le fait ensemble »).

Chaque soir, le bot relit les salons persos actifs des dernières 24 h, se note, et en tire :
- des LEÇONS : une question ou une confusion vue dans un salon + la bonne réponse selon la doctrine → ajoutées à la FAQ
  apprise (le même fichier que `!apprendre`, donc `!faq` les montre et `!faq retirer N` les annule) ;
- des CONSIGNES : deux règles de style au plus par jour, injectées dans le prompt de l'assistant (12 au maximum, les plus
  anciennes tombent) ;
- un DIGEST au salon admin : salons lus, note moyenne, leçons ajoutées, défauts vus, ce que le bot a changé.

Garde-fous : jamais de nom, numéro, e-mail, mot de passe ou identifiant dans une leçon ; jamais de leçon qui contredit la
doctrine (rappelée dans le prompt, et la base curée prime toujours dans le prompt de l'assistant) ; 3 leçons par salon et
20 par jour au plus ; une leçon déjà connue (même début de question) n'est pas réajoutée. `!retro` lance la même chose à
la main. L'objectif de fond, écrit dans le prompt : transformer chaque clipper en trois comptes Instagram qui postent le
plus souvent possible des Reels de qualité exceptionnelle, avec le moins de messages possible."""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

import discord

journal = __import__("logging").getLogger("bot_clippers")
_deps = {}
OBJECTIF = ("Transformer chaque clipper en trois comptes Instagram qui postent le plus souvent possible des Reels de qualité "
            "exceptionnelle, avec le moins de messages possible, sans jamais contredire la doctrine.")
DOCTRINE = ("Doctrine (elle prime sur tout) : le clipper met SON numéro de téléphone (un numéro = ses 3 comptes) ; le selfie "
            "vidéo, il le fait lui-même ; un compte par jour, 24 h de warm-up après chaque compte, premier Reel après ; le lien "
            "vit dans la bio du compte privé et dans la story à la une, jamais dans un Reel ; paie 0,05 $ par visite "
            "francophone réelle, tous les 15 jours ; codes par `!code`, code de récupération par `!recup` ; trois cas seulement "
            "vont à un humain (ban, numéro refusé, paiement) via WhatsApp ; le bot ne donne jamais la cause d'un blocage, "
            "seulement la marche à suivre ; jamais de pseudo inventé ; jamais « ton manager te donne une solution demain » ; "
            "un « ok » ne mérite aucune réponse ; une réponse fait trois lignes au plus, une action à la fois.")
MAX_LECONS_SALON, MAX_LECONS_JOUR, MAX_CONSIGNES = 3, 20, 12


def configurer(deps: dict):
    """deps : lire_json, ecrire_json, FICHIER (retro.json), FICHIER_FAQ_APPRISE (Path), FICHIER_CONSIGNES (Path), salons_persos
    (async -> [(salon, membre)]), canal_admin, heure_paris, claude, MODELE, est_staff, normaliser."""
    _deps.update(deps)


# ------------------------------------------------------------------ ce que l'assistant lit
def consignes() -> list:
    f = _deps.get("FICHIER_CONSIGNES")
    try:
        return list(_deps["lire_json"](f, [])) if f is not None else []
    except Exception:                                                       # noqa: BLE001
        return []


def consignes_actives() -> list:
    """29/09 : seules les consignes posées par le staff (`!retro consigne …`) entrent dans le prompt. Celles que la rétrospective
    a apprises toute seule (chaînes ou dicts sans `source`) sont ignorées : le 28/09 elle avait appris « attendre la réponse du
    humain avant de continuer le parcours » et « jamais vidéo + quiz dans le même message », deux contresens du process."""
    return [x for x in consignes() if isinstance(x, dict) and x.get("source") == "staff" and x.get("texte")]


def consignes_texte() -> str:
    """Le bloc injecté dans le prompt de l'assistant (vide s'il n'y a rien)."""
    c = consignes_actives()
    if not c:
        return ""
    return ("\n\n## Consignes du staff (posées à la main — secondaires : la doctrine et la base curée priment)\n"
            + "\n".join(f"- {x['texte']}" for x in c[-MAX_CONSIGNES:]))


def ajouter_consigne(texte: str, par: str = "") -> list:
    """`!retro consigne …` : une consigne du staff, datée, la seule sorte que l'assistant lit."""
    actuelles = consignes()
    actuelles.append({"texte": texte.strip()[:200], "date": datetime.now(timezone.utc).strftime("%d/%m"), "source": "staff", "par": par})
    _deps["ecrire_json"](_deps["FICHIER_CONSIGNES"], actuelles[-MAX_CONSIGNES * 2:])
    return consignes_actives()


def oublier_consigne(numero: int) -> list:
    """`!retro oublier n` : retire la n-ième consigne active (1 = la première de la liste)."""
    actives = consignes_actives()
    if not 1 <= numero <= len(actives):
        return actives
    cible = actives[numero - 1]
    reste = [x for x in consignes() if x is not cible and x != cible]
    _deps["ecrire_json"](_deps["FICHIER_CONSIGNES"], reste)
    return consignes_actives()


# ------------------------------------------------------------------ transcription d'un salon
async def transcrire(salon, membre, depuis) -> list:
    """Les messages des dernières 24 h, une ligne chacun, rôle en tête : CLIPPER, BOT, HUMAIN (staff)."""
    lignes = []
    try:
        async for m in salon.history(limit=80, after=depuis, oldest_first=True):
            texte = (m.content or "").strip()
            if not texte and not m.attachments:
                continue
            if m.author.bot:
                role = "BOT"
            elif m.author.id == membre.id:
                role = "CLIPPER"
            else:
                role = "HUMAIN"
            if m.attachments and not texte:
                texte = "[pièce jointe]"
            texte = re.sub(r"\s+", " ", texte)[:400]
            lignes.append(f"[{m.created_at.strftime('%H:%M')}] {role} : {texte}")
    except (discord.Forbidden, discord.HTTPException) as erreur:
        journal.info("Rétro : salon %s illisible (%s)", getattr(salon, "name", "?"), erreur)
    return lignes


def _anonymiser(texte: str) -> str:
    texte = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[e-mail]", texte)
    texte = re.sub(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", "[numéro]", texte)
    return texte


# ------------------------------------------------------------------ l'analyse
def prompt_analyse(nom_salon: str, transcription: list, deja: list) -> str:
    return (f"Tu es le coach du bot Discord d'une agence de clippers Instagram. Objectif : {OBJECTIF}\n{DOCTRINE}\n\n"
            f"Voici la conversation des dernières 24 h dans le salon perso d'un clipper (#{nom_salon}). Le BOT, c'est toi.\n"
            "Note-toi honnêtement de 0 à 10 sur : le clipper a-t-il avancé vers ses 3 comptes qui postent ? as-tu été court, "
            "juste, sans inventer, sans contredire un HUMAIN ? Si un HUMAIN (staff) t'a corrigé, sa consigne devient une leçon.\n"
            "Rends UNIQUEMENT un JSON : {\"note\": 0-10, \"defauts\": [\"…\"], \"lecons\": [{\"q\": \"question ou situation, "
            "formulée de façon générale\", \"r\": \"la bonne réponse en 2 phrases, niveau collège\"}], \"consignes\": [\"règle de "
            "style courte, générale\"]}. Au plus 3 leçons et 2 consignes ; [] si rien à apprendre (c'est fréquent : ne force pas). "
            "Interdit dans les leçons : prénoms, numéros, e-mails, mots de passe, identifiants de comptes, et tout ce qui contredit "
            "la doctrine. Pas de leçon déjà connue.\n"
            + ("Leçons déjà connues (débuts de question) : " + " · ".join(deja[:40]) + "\n" if deja else "")
            + "\nConversation :\n" + "\n".join(transcription))


def analyser_sync(prompt: str) -> dict:
    try:
        reponse = _deps["claude"].messages.create(model=_deps["MODELE"], max_tokens=1200, messages=[{"role": "user", "content": prompt}])
        texte = "".join(b.text for b in reponse.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", texte, re.S)
        return json.loads(m.group(0)) if m else {}
    except Exception as erreur:                                             # noqa: BLE001
        journal.warning("Rétro : analyse impossible (%s)", erreur)
        return {}


# ------------------------------------------------------------------ application
def _debuts_connus() -> list:
    f = _deps.get("FICHIER_FAQ_APPRISE")
    if f is None or not f.exists():
        return []
    n = _deps["normaliser"]
    return [n(q)[:40] for q in re.findall(r"\*\*Q : (.+?)\*\*", f.read_text(encoding="utf-8"))]


def _meme(a: str, b: str) -> bool:
    """Deux débuts de question normalisés qui disent la même chose : identiques sur 30 caractères, ou l'un commence par l'autre."""
    a, b = (a or "").strip(" ?"), (b or "").strip(" ?")
    if not a or not b:
        return False
    return a[:30] == b[:30] or (len(min(a, b, key=len)) >= 18 and (a.startswith(b) or b.startswith(a)))


def _propre(texte: str) -> bool:
    """Une leçon acceptable : pas d'e-mail, de numéro, de mot de passe, d'identifiant de compte."""
    t = (texte or "").lower()
    if re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", t) or re.search(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)", t):
        return False
    return not any(k in t for k in ("mot de passe", "mdp", "password", "@", "identifiant :"))


def appliquer(resultats: list) -> dict:
    """Ajoute les leçons neuves à la FAQ apprise et les consignes au fichier des consignes. Renvoie le bilan."""
    n = _deps["normaliser"]
    connus = set(_debuts_connus())
    ajoutees, refusees, nouvelles_consignes = [], 0, []
    f = _deps.get("FICHIER_FAQ_APPRISE")
    jour = datetime.now(timezone.utc).strftime("%d/%m")
    for res in resultats:
        for lecon in (res.get("lecons") or [])[:MAX_LECONS_SALON]:
            q, r = str(lecon.get("q", "")).strip(), str(lecon.get("r", "")).strip()
            if not q or not r or not _propre(q + " " + r) or len(ajoutees) >= MAX_LECONS_JOUR:
                refusees += 1 if q or r else 0
                continue
            cle = n(q)[:40]
            if any(_meme(cle, c) for c in connus):                        # même question déjà apprise (début identique)
                continue
            connus.add(cle)
            ajoutees.append((q, r))
            if f is not None:
                with f.open("a", encoding="utf-8") as flux:
                    flux.write(f"\n**Q : {q}**\nR : {r} (appris tout seul le {jour})\n")
        for c in (res.get("consignes") or [])[:2]:
            c = str(c).strip()
            if c and _propre(c) and len(c) <= 200:
                nouvelles_consignes.append(c)
    # 29/09 : les consignes proposées ne sont plus écrites nulle part — elles apparaissent dans le digest, le staff garde
    # celles qu'il veut avec `!retro consigne …`. Les leçons (questions/réponses) restent apprises toutes seules.
    return {"lecons": ajoutees, "refusees": refusees, "consignes": nouvelles_consignes}


# ------------------------------------------------------------------ exécution
async def executer(client) -> str:
    """La rétrospective : renvoie le digest (posté au salon admin par l'appelant ou par la boucle)."""
    depuis = datetime.now(timezone.utc) - timedelta(hours=24)
    salons = await _deps["salons_persos"]()
    resultats, notes, defauts, lus = [], [], [], 0
    deja = _debuts_connus()
    for salon, membre in salons[:40]:
        transcription = await transcrire(salon, membre, depuis)
        if sum(1 for l in transcription if "] CLIPPER :" in l) < 1:
            continue
        lus += 1
        res = await asyncio.to_thread(analyser_sync, prompt_analyse(getattr(salon, "name", "?"), [_anonymiser(l) for l in transcription], deja))
        if not res:
            continue
        resultats.append(res)
        if isinstance(res.get("note"), (int, float)):
            notes.append(float(res["note"]))
        defauts += [str(d)[:120] for d in (res.get("defauts") or [])[:2]]
    bilan = appliquer(resultats)
    etat = _deps["lire_json"](_deps["FICHIER"], {"historique": []})
    etat["dernier"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    etat.setdefault("historique", []).append({"date": etat["dernier"], "salons": lus, "note": round(sum(notes) / len(notes), 1) if notes else None,
                                              "lecons": len(bilan["lecons"]), "consignes": len(bilan["consignes"])})
    etat["historique"] = etat["historique"][-90:]
    _deps["ecrire_json"](_deps["FICHIER"], etat)
    if not lus:
        return "🧠 Rétrospective : aucun salon perso actif ces 24 h."
    digest = (f"🧠 **Rétrospective du soir** : {lus} salon(s) lu(s) · note moyenne {round(sum(notes) / len(notes), 1) if notes else '—'}/10 · "
              f"{len(bilan['lecons'])} leçon(s) apprise(s) · {len(bilan['consignes'])} consigne(s)")
    if bilan["lecons"]:
        digest += "\n" + "\n".join(f"· **{q[:90]}** → {r[:160]}" for q, r in bilan["lecons"][:8])
    if bilan["consignes"]:
        digest += ("\n✏️ Propositions de consignes (NON appliquées — `!retro consigne …` pour en garder une) : "
                   + " · ".join(c[:120] for c in bilan["consignes"][:4]))
    if defauts:
        digest += "\n⚠️ Vu : " + " · ".join(dict.fromkeys(defauts))[:600]
    digest += "\n-# `!faq` pour relire, `!faq retirer N` pour annuler une leçon, `!retro` pour relancer."
    journal.info("Rétrospective : %d salons, %d leçons, %d consignes", lus, len(bilan["lecons"]), len(bilan["consignes"]))
    return digest


async def commande(message, texte: str) -> bool:
    if not texte.lower().startswith(("!retro", "!rétro")):
        return False
    if not _deps["est_staff"](message.author):
        await message.reply("Réservé aux admins et aux managers.")
        return True
    mots = texte.split(maxsplit=2)
    sous = mots[1].lower() if len(mots) > 1 else ""
    if sous in ("consigne", "consignes", "oublier"):                      # 29/09 : les consignes de l'assistant, à la main
        if sous == "consigne" and len(mots) > 2 and mots[2].strip():
            actives = ajouter_consigne(mots[2], getattr(message.author, "display_name", ""))
            await message.reply("✅ Consigne posée. " + _liste_consignes(actives))
        elif sous == "oublier" and len(mots) > 2 and mots[2].strip().isdigit():
            actives = oublier_consigne(int(mots[2].strip()))
            await message.reply("🗑️ " + _liste_consignes(actives))
        else:
            await message.reply(_liste_consignes(consignes_actives()) + "\n`!retro consigne Le texte.` pour en poser une, `!retro oublier n` pour en retirer une.")
        return True
    await message.reply("🧠 Je relis les salons persos des dernières 24 h… (une à deux minutes)")
    try:
        await message.channel.send((await executer(_deps.get("client")))[:1990])
    except Exception as erreur:                                             # noqa: BLE001
        journal.exception("Rétro : %s", erreur)
        await message.channel.send(f"❌ Rétrospective impossible : {type(erreur).__name__}")
    return True


def _liste_consignes(actives: list) -> str:
    if not actives:
        return "Aucune consigne du staff : l'assistant suit la doctrine et la base seules."
    return "Consignes du staff lues par l'assistant :\n" + "\n".join(f"{i}. {x['texte']} ({x.get('date', '')})" for i, x in enumerate(actives, 1))


async def boucle(client):
    """Chaque soir entre 20 h et 22 h (Paris), une fois par jour."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            maintenant = _deps["heure_paris"]()
            jour = maintenant.strftime("%Y-%m-%d")
            etat = _deps["lire_json"](_deps["FICHIER"], {})
            if 20 <= maintenant.hour < 22 and etat.get("jour") != jour:
                canal = await _deps["canal_admin"]()
                digest = await executer(client)
                etat = _deps["lire_json"](_deps["FICHIER"], {})
                etat["jour"] = jour
                _deps["ecrire_json"](_deps["FICHIER"], etat)
                if canal is not None:
                    try:
                        await canal.send(digest[:1990])
                    except (discord.Forbidden, discord.HTTPException):
                        pass
        except Exception as erreur:                                         # noqa: BLE001
            journal.warning("Boucle rétro : %s", erreur)
        await asyncio.sleep(1200)
