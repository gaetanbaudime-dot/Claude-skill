"""30/10 (Gaëtan : « j'aimerais savoir d'où viennent les candidatures, j'ai du mal à double down sur ce qui marche ») : le
formulaire du site demande « Où as-tu vu notre annonce ? » (question `annonce`, texte libre). Ce module range cette réponse
dans un canal court, pour compter les candidatures par source au digest du matin.

Ordre de décision (source_candidature) : le lien de l'annonce d'abord (`?src=tg-<groupe>`, c'est un fait), puis ce que le
candidat a écrit, sinon « web » (source inconnue, comme avant). Les réponses vides ou qu'on ne sait pas classer ne sont
jamais devinées : vide → '', texte non reconnu → « autre »."""
import re
import unicodedata

# (canal, motifs) dans l'ordre : le premier qui correspond gagne. Motifs = expressions régulières sur le texte en minuscules
# sans accents. Disboard avant Discord (un listing, pas un serveur d'annonces) ; parrainage en dernier (« un ami sur Telegram »
# reste Telegram : c'est le canal qui a porté l'annonce).
CANAUX = (
    ("disboard", (r"disboard",)),
    ("telegram", (r"telegram", r"telegramme", r"\btg\b", r"t\.me", r"\btele\b")),
    ("discord", (r"discord", r"\bdisc\b")),
    ("indeed", (r"indeed",)),
    ("ofmjob", (r"ofm ?jobs?",)),
    ("tiktok", (r"tik ?tok", r"\btt\b")),
    ("instagram", (r"instagram", r"\binsta\b", r"\big\b")),
    ("youtube", (r"youtube", r"\byt\b")),
    ("facebook", (r"facebook", r"\bfb\b", r"\bmeta\b")),
    ("whatsapp", (r"whatsapp", r"whats app", r"\bwa\b")),
    ("linkedin", (r"linkedin",)),
    ("google", (r"google", r"recherche internet", r"sur internet")),
    ("pub", (r"\bpubs?\b", r"publicite")),
    ("parrainage", (r"parrain", r"\bamie?s?\b", r"\bpotes?\b", r"cousine?", r"frere", r"soeur", r"collegue",
                    r"bouche a oreille", r"connaissance", r"recommand")),
)


def _propre(texte) -> str:
    t = unicodedata.normalize("NFD", str(texte or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", t).strip()


def canal(texte) -> str:
    """Le canal d'une réponse libre à « Où as-tu vu notre annonce ? » : telegram, discord, disboard, indeed, instagram…
    '' si la réponse est vide, « autre » si elle ne correspond à rien de connu."""
    t = _propre(texte)
    if not t or t in ("-", ".", "?", "non", "rien", "aucun", "aucune"):
        return ""
    for nom, motifs in CANAUX:
        if any(re.search(m, t) for m in motifs):
            return nom
    return "autre"


def source_candidature(src_lien, reponse_annonce) -> str:
    """La source d'une candidature pour le digest : le lien (`tg-<groupe>`) s'il en porte une, sinon le canal déclaré,
    sinon « web » (inconnue). « web » et « formulaire » venus du lien ne sont pas une vraie source : on regarde la réponse."""
    lien = str(src_lien or "").split(" · ")[0].strip().lower()[:30]
    if lien and lien not in ("web", "formulaire") and not lien.startswith("form-"):
        return lien
    return canal(reponse_annonce) or "web"
