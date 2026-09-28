"""Alerte Telegram de l'agence (29/09 : sortie du module inputs_clippers, retiré à l'élagage).

Le bot pousse dans la poche de Gaëtan ce qui ne doit pas attendre l'ouverture de Discord : une acceptation des
conditions, une sortie d'équipe, et la copie du digest du matin si TELEGRAM_QUOTIDIEN=1. Silencieux tant que
TELEGRAM_TOKEN et TELEGRAM_CHAT_ID ne sont pas posés dans Railway."""

import asyncio
import logging
import os
import re

import aiohttp

journal = logging.getLogger("bot_clippers")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_QUOTIDIEN = os.environ.get("TELEGRAM_QUOTIDIEN", "0").strip() == "1"     # copie du digest du matin


def _sans_markdown(texte: str) -> str:
    """Telegram en Markdown refusait tout message contenant un « _ » ou un « * » orphelin (pseudo
    Instagram avec underscore, par exemple) : le rapport n'arrivait pas. On envoie du texte brut."""
    texte = texte.replace("**", "").replace("*", "")
    return "\n".join(re.sub(r"^_(.+)_$", r"\1", ligne) for ligne in texte.split("\n"))


async def envoyer_telegram(texte: str):
    """Pousse un message sur le canal Telegram de l'agence (texte brut). Silencieux si non configuré."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    charge = {"chat_id": TELEGRAM_CHAT_ID, "text": _sans_markdown(texte)[:4000]}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=charge) as reponse:
                if reponse.status >= 400:
                    journal.warning("Telegram HTTP %s", reponse.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as erreur:
        journal.warning("Telegram injoignable : %s", erreur)
