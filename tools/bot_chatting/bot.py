"""
Assistant chatting — bot Discord du serveur chatting, propriété de Maxence.

STRICTEMENT SÉPARÉ du bot clippers : autre application Discord, autre service Railway,
autre volume, aucune donnée partagée avec le marketing. C'est une décision de Gaëtan
(31/07/2026) : deux mondes, zéro pont.

CE QUE FAIT CE BOT : il répond aux questions des chatteurs à partir d'UNE SEULE source de
vérité — sa base de connaissances — et il dit franchement quand il ne sait pas (la question
part alors dans les « lacunes », que Maxence vide en enrichissant la base).

COMMENT MAXENCE L'AMÉLIORE, sans toucher au code :
    !apprendre <texte>     ajoute un bloc de connaissance (ou joindre un fichier .md/.txt)
    !oublier <n°>          retire le bloc n° (visible via !connaissances)
    !connaissances         liste les blocs, numérotés
    !lacunes               questions restées sans réponse ; « !lacunes vider » pour purger
    !ici                   active/désactive le bot dans le salon courant
    !aide                  rappel de tout ça

Le bot répond : en message privé, quand on le mentionne, ou dans les salons activés
par « !ici ». Partout ailleurs, il se tait.

Variables d'environnement (service Railway dédié) :
    DISCORD_TOKEN       token du bot (application Discord séparée)
    ANTHROPIC_API_KEY   clé API Claude (une clé dédiée, pour suivre le coût à part)
    ADMIN_IDS           ids Discord des admins, séparés par des virgules (Maxence + Gaëtan)
    DONNEES_DIR         répertoire persistant (volume Railway monté sur /data)
    MODELE              défaut : claude-haiku-4-5-20251001
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import discord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chatting")

MODELE = os.environ.get("MODELE", "claude-haiku-4-5-20251001")
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x}
DONNEES = Path(os.environ.get("DONNEES_DIR", "./donnees"))
DONNEES.mkdir(parents=True, exist_ok=True)

F_CONNAISSANCES = DONNEES / "connaissances.json"   # [{date, texte}]
F_LACUNES = DONNEES / "lacunes.json"               # [{date, question, salon}]
F_SALONS = DONNEES / "salons.json"                 # [ids des salons activés par !ici]
GRAINE = Path(__file__).parent / "connaissances_depart.md"

claude = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY dans l'environnement

# Marqueur que le modèle émet quand la base ne couvre pas la question. C'est le mécanisme
# central du bot : chaque [LACUNE] devient une ligne à combler pour Maxence, et la base
# grandit exactement là où les chatteurs butent — pas là où on imagine qu'ils butent.
MARQUEUR_LACUNE = "[LACUNE]"

SYSTEME = """Tu es l'assistant du pôle chatting de l'agence. Tu réponds aux chatteurs en
français, tutoiement, direct et concret. Trois règles absolues :

1. Ta SEULE source de vérité est la base de connaissances ci-dessous. Tu ne complètes
   jamais avec des généralités inventées : si la base ne couvre pas la question, tu le dis
   en une phrase et tu termines ta réponse par le marqueur {m} sur une ligne seule.
2. Doctrine maison, à rappeler chaque fois que c'est pertinent : le golden ratio (part des
   messages qui sont des PPV) doit rester BAS — la conversation d'abord ; l'unlock rate
   (part des PPV achetés) doit être HAUT — des PPV rares et bien placés. Un chatteur qui
   spamme des PPV dégrade la LTV même quand son chiffre du jour a l'air bon.
3. Tu expliques les méthodes, les règles et les prix ; tu ne rédiges JAMAIS le texte des
   messages à envoyer aux fans. Le verbatim des scripts vit dans le CRM — tu renvoies
   vers le CRM et le team leader, tu ne le récites pas et tu ne l'improvises pas.

Réponses courtes (moins de 250 mots), structurées, actionnables. Jamais de données
personnelles de clients, jamais de vrais noms de créatrices — noms de scène uniquement.
""".format(m=MARQUEUR_LACUNE)


# ─────────────────────────────────────────────────────────── stockage

def _lire(fichier: Path, defaut):
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def _ecrire(fichier: Path, donnees) -> None:
    fichier.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")


def _aujourd_hui() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def charger_connaissances() -> list:
    blocs = _lire(F_CONNAISSANCES, None)
    if blocs is not None:
        return blocs
    # Premier démarrage : la graine du dépôt devient la base initiale, un bloc par
    # section « ## ». Ensuite le volume fait foi — le dépôt n'est plus jamais relu,
    # sinon un redéploiement écraserait les ajouts de Maxence.
    blocs = []
    if GRAINE.exists():
        for section in GRAINE.read_text(encoding="utf-8").split("\n## "):
            section = section.strip().lstrip("# ").strip()
            if section:
                blocs.append({"date": _aujourd_hui(), "texte": "## " + section if not section.startswith("#") else section})
    _ecrire(F_CONNAISSANCES, blocs)
    return blocs


def texte_connaissances(blocs: list) -> str:
    return "\n\n".join(f"[bloc {i + 1} — {b['date']}]\n{b['texte']}" for i, b in enumerate(blocs))


# ─────────────────────────────────────────────────────────── Claude

historiques: dict[int, list] = {}   # salon → derniers échanges (mémoire courte, en RAM)


async def repondre(question: str, salon_id: int) -> str:
    blocs = charger_connaissances()
    systeme = SYSTEME + "\n\n# Base de connaissances\n\n" + (texte_connaissances(blocs) or "(vide — tout est lacune)")
    histo = historiques.setdefault(salon_id, [])
    messages = histo[-8:] + [{"role": "user", "content": question}]
    try:
        reponse = await asyncio.to_thread(
            lambda: claude.messages.create(model=MODELE, max_tokens=700, system=systeme, messages=messages)
        )
        texte = "".join(b.text for b in reponse.content if b.type == "text").strip()
    except anthropic.RateLimitError:
        return "Trop de questions d'un coup — réessaie dans une minute."
    except anthropic.APIError as erreur:
        log.error("API Claude : %s", erreur)
        return "Souci technique de mon côté, réessaie dans un instant."
    histo.extend([{"role": "user", "content": question}, {"role": "assistant", "content": texte}])
    del histo[:-8]

    if MARQUEUR_LACUNE in texte:
        texte = texte.replace(MARQUEUR_LACUNE, "").strip()
        lacunes = _lire(F_LACUNES, [])
        lacunes.append({"date": _aujourd_hui(), "question": question[:300], "salon": salon_id})
        _ecrire(F_LACUNES, lacunes[-200:])
    return texte or "Je n'ai rien trouvé dans ma base pour ça — c'est noté dans les lacunes."


# ─────────────────────────────────────────────────────────── Discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

derniere_question: dict[int, float] = {}   # anti-rafale : 1 question / 3 s / personne


async def envoyer(salon, texte: str) -> None:
    # Discord plafonne à 2 000 caractères : découpe aux sauts de ligne, jamais au milieu.
    while texte:
        morceau = texte[:1900]
        if len(texte) > 1900 and "\n" in morceau:
            morceau = morceau.rsplit("\n", 1)[0]
        await salon.send(morceau)
        texte = texte[len(morceau):].lstrip("\n")


def est_admin(m: discord.Message) -> bool:
    return m.author.id in ADMIN_IDS


async def gerer_commande(m: discord.Message) -> bool:
    contenu = m.content.strip()
    if not contenu.startswith("!"):
        return False
    commande, _, reste = contenu[1:].partition(" ")
    commande = commande.lower()
    reste = reste.strip()

    if commande == "aide":
        await envoyer(m.channel,
            "**Assistant chatting** — je réponds en MP, sur mention, ou dans les salons activés.\n"
            "Admin : `!apprendre <texte>` (ou fichier .md/.txt joint) · `!oublier <n°>` · "
            "`!connaissances` · `!lacunes` (+ `vider`) · `!ici` (active/désactive ce salon)")
        return True

    if not est_admin(m):
        return False   # les commandes de gestion sont réservées à Maxence et Gaëtan

    if commande == "apprendre":
        ajouts = []
        for pj in m.attachments:
            if pj.filename.lower().endswith((".md", ".txt")) and pj.size < 400_000:
                ajouts.append((await pj.read()).decode("utf-8", errors="replace"))
        if reste:
            ajouts.append(reste)
        if not ajouts:
            await envoyer(m.channel, "Donne le texte après la commande, ou joins un fichier .md/.txt.")
            return True
        blocs = charger_connaissances()
        for texte in ajouts:
            blocs.append({"date": _aujourd_hui(), "texte": texte.strip()})
        _ecrire(F_CONNAISSANCES, blocs)
        await envoyer(m.channel, f"Appris ✅ — la base compte {len(blocs)} bloc(s).")
        return True

    if commande == "oublier":
        blocs = charger_connaissances()
        try:
            n = int(reste)
            assert 1 <= n <= len(blocs)
        except (ValueError, AssertionError):
            await envoyer(m.channel, f"`!oublier <n°>` — un numéro entre 1 et {len(blocs)} (voir !connaissances).")
            return True
        retire = blocs.pop(n - 1)
        _ecrire(F_CONNAISSANCES, blocs)
        await envoyer(m.channel, f"Oublié le bloc {n} ({retire['texte'][:60]}…). Reste {len(blocs)} bloc(s).")
        return True

    if commande == "connaissances":
        blocs = charger_connaissances()
        if not blocs:
            await envoyer(m.channel, "Base vide — tout est à apprendre (`!apprendre`).")
            return True
        lignes = [f"**{i + 1}.** ({b['date']}) {b['texte'][:120].replace(chr(10), ' ')}…" for i, b in enumerate(blocs)]
        await envoyer(m.channel, "\n".join(lignes))
        return True

    if commande == "lacunes":
        lacunes = _lire(F_LACUNES, [])
        if reste.lower() == "vider":
            _ecrire(F_LACUNES, [])
            await envoyer(m.channel, f"{len(lacunes)} lacune(s) purgée(s).")
            return True
        if not lacunes:
            await envoyer(m.channel, "Aucune lacune — la base couvre tout ce qu'on lui a demandé 💪")
            return True
        lignes = [f"• ({l['date']}) {l['question']}" for l in lacunes[-25:]]
        await envoyer(m.channel, f"**{len(lacunes)} question(s) sans réponse** (25 dernières) :\n" + "\n".join(lignes)
                     + "\n\nRéponds-y avec `!apprendre`, puis `!lacunes vider`.")
        return True

    if commande == "ici":
        salons = _lire(F_SALONS, [])
        if m.channel.id in salons:
            salons.remove(m.channel.id)
            await envoyer(m.channel, "Je ne réponds plus automatiquement ici (mention/MP toujours possibles).")
        else:
            salons.append(m.channel.id)
            await envoyer(m.channel, "Je réponds désormais à tous les messages de ce salon.")
        _ecrire(F_SALONS, salons)
        return True

    return False


@client.event
async def on_ready():
    blocs = charger_connaissances()
    log.info("Connecté : %s · %d bloc(s) de connaissances · modèle %s", client.user, len(blocs), MODELE)


@client.event
async def on_message(m: discord.Message):
    if m.author.bot:
        return
    if await gerer_commande(m):
        return

    en_mp = m.guild is None
    mentionne = client.user in m.mentions
    salon_actif = m.channel.id in _lire(F_SALONS, [])
    if not (en_mp or mentionne or salon_actif):
        return

    maintenant = time.monotonic()
    if maintenant - derniere_question.get(m.author.id, 0.0) < 3:
        return
    derniere_question[m.author.id] = maintenant

    question = m.content.replace(f"<@{client.user.id}>", "").strip()
    if not question:
        return
    async with m.channel.typing():
        texte = await repondre(question, m.channel.id)
    await envoyer(m.channel, texte)


if __name__ == "__main__":
    client.run(os.environ["DISCORD_TOKEN"])
