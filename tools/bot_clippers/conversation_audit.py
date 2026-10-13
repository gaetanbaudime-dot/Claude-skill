"""Private, read-only Discord conversation audit export.

Admin-invoked with !audit-discussions [days]. Only private DM delivery. No Sheets,
Railway logging of message bodies, member mutations or permanent storage.
The export is *sampled*: up to 400 recent messages per selected channel.
"""
from __future__ import annotations

import io
import json
import logging
import re
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone

import discord

LOG = logging.getLogger("audit_discussions")
MAX_DAYS = 180
MAX_CHANNELS = 150
MAX_MESSAGES_PER_CHANNEL = 400
MAX_ARCHIVE_BYTES = 7_000_000

PRIVATE_CATEGORY_MARKERS = ("chloe", "sarah", "sophie", "jade", "maddie", "clara", "clippers")
IGNORED_ROOM_MARKERS = ("base", "info", "equipe", "team", "annonce")
SENSITIVE_LINE = re.compile(
    r"\b(?:mdp|mot[\s-]*de[\s-]*passe|password|passwd|passphrase|"
    r"secret|api[\s_-]*key|token|private[\s_-]*key|code[\s_-]*2fa|"
    r"code[\s_-]*otp|backup[\s_-]*code|wallet|seed[\s_-]*phrase|"
    r"authenticat(?:ion|or)[\s_-]*code)\b",
    re.IGNORECASE,
)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I)
URL = re.compile(r"https?://[^\s<>]+|(?<!@)\b(?:[\w-]+\.)+(?:fr|com|net|io|app|ae|org)/[^\s<>]*", re.I)
LONG_SECRET = re.compile(r"\b[A-Za-z0-9_-]{28,}\b")
OTP_DIGITS = re.compile(r"(?<!\d)\d{4,8}(?!\d)")
PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\d[\s.-]?){10,14}(?!\d)")


def _norm(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(value).casefold())
                   if unicodedata.category(c) != "Mn")


def sanitize_message(content: str) -> str:
    """Redact probable credentials and identifiers; never assert perfect sanitization."""
    safe = []
    for line in str(content or "").splitlines()[:20]:
        if SENSITIVE_LINE.search(line):
            safe.append("[LIGNE SENSIBLE MASQUÉE]")
            continue
        line = URL.sub("[URL MASQUÉE]", line)
        line = EMAIL.sub("[EMAIL MASQUÉ]")
        line = PHONE.sub("[TÉLÉPHONE MASQUÉ]", line)
        line = LONG_SECRET.sub("[CHAÎNE MASQUÉE]", line)
        line = OTP_DIGITS.sub("[CODE MASQUÉ]", line)
        safe.append(line[:450])
    return "\n".join(safe)[:1200]


def _personal_room(channel: discord.TextChannel) -> bool:
    if channel.permissions_for(channel.guild.default_role).view_channel:
        return False
    cat = _norm(getattr(getattr(channel, "category", None), "name", ""))
    room = _norm(channel.name)
    if not any(m in cat for m in PRIVATE_CATEGORY_MARKERS):
        return False
    if any(m in room for m in IGNORED_ROOM_MARKERS):
        return False
    return any(isinstance(x, (discord.Member, discord.User))
               and getattr(ow, "view_channel", None) is True
               for x, ow in channel.overwrites.items())


def _select_channels(guild: discord.Guild, active_pairs: list) -> list:
    channels = {}
    for channel in guild.text_channels:
        if "assistant-ia" in _norm(channel.name).replace("_", "-"):
            channels[channel.id] = channel
        elif _personal_room(channel):
            channels[channel.id] = channel
    for channel, _member in active_pairs or []:
        if isinstance(channel, discord.TextChannel):
            channels[channel.id] = channel
    return sorted(channels.values(), key=lambda c: (_norm(getattr(c.category, "name", "")), _norm(c.name)))[:MAX_CHANNELS]


async def export_to_admin_dm(message, active_pairs: list, days: int = 90) -> dict:
    """Read selected guild history and DM its sanitized sample ONLY to invoker."""
    if message.guild is None:
        raise ValueError("Cette commande doit être lancée depuis le serveur.")
    if not (1 <= days <= MAX_DAYS):
        raise ValueError(f"Nombre de jours autorisé : 1 à {MAX_DAYS}.")

    # Test DM delivery before touching the history, to avoid producing an undeliverable export.
    try:
        await message.author.send("🔒 Audit en lecture seule démarré. Je prépare l'archive privée des discussions.")
    except discord.Forbidden as exc:
        raise ValueError("Ouvre tes MP Discord avec le bot avant de demander l'export.") from exc

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rooms = _select_channels(message.guild, active_pairs)
    if not rooms:
        raise ValueError("Aucun salon lisible par le bot parmi ceux demandés.")

    report = {
        "version": "gm-conversations-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "max_messages_per_room": MAX_MESSAGES_PER_CHANNEL,
        "coverage": "assistant-ia + salons personnels visibles par le bot",
        "disclaimer": "Export échantillonné, masquage automatique non infaillible; vérifier avant tout autre partage.",
        "rooms": [], "errors": [],
    }
    total = 0
    for channel in rooms:
        try:
            msgs = []
            async for m in channel.history(limit=MAX_MESSAGES_PER_CHANNEL, after=cutoff, oldest_first=False):
                msgs.append({
                    "date_utc": m.created_at.isoformat(),
                    "author_uid": str(m.author.id),
                    "author": str(getattr(m.author, "display_name", m.author.name))[:100],
                    "bot": bool(m.author.bot),
                    "text_redacted": sanitize_message(m.content),
                    "attachments_count": len(m.attachments),
                    "question": "?" in (m.content or ""),
                })
            msgs.reverse()  # Chronological within the newest messages, not oldest.
            total += len(msgs)
            report["rooms"].append({
                "channel_id": str(channel.id),
                "category": getattr(channel.category, "name", "") or "",
                "channel": channel.name,
                "messages": msgs,
                "count": len(msgs),
                "limit_reached": len(msgs) == MAX_MESSAGES_PER_CHANNEL,
            })
        except (discord.Forbidden, discord.HTTPException) as exc:
            report["errors"].append({
                "channel": channel.name,
                "type": type(exc).__name__,
            })
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as bundle:
        data = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
        bundle.writestr("audit_discussions_redige.json", data.encode("utf-8"))
        bundle.writestr("LISEZ-MOI.txt", (
            "Export des discussions pour audit interne G&M. Contient des conversations "
            "personnelles et des identifiants Discord; ne pas diffuser.\n"
            "Le masquage automatique peut manquer des secrets: inspectez avant toute transmission.\n"
            "Les salons non accessibles au bot, les MP et les fils archivés ne sont pas inclus.\n"
        ).encode("utf-8"))
    bio.seek(0)
    if bio.getbuffer().nbytes > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive trop volumineuse pour un envoi privé; réduis la période.")
    await message.author.send(
        f"🔒 Export privé : {len(report['rooms'])} salons, {total} messages récents, "
        f"{len(report['errors'])} salons illisibles, fenêtre {days} jours.\n"
        "Avant de partager l'archive, vérifie qu'aucun identifiant sensible n'y figure.",
        file=discord.File(fp=bio, filename="audit_discussions_gm.zip"),
    )
    LOG.info("Export privé Discord fourni à l'admin : %d salons, %d messages, %d erreurs",
             len(report["rooms"]), total, len(report["errors"]))
    return {"rooms": len(report["rooms"]), "messages": total, "errors": len(report["errors"])}
