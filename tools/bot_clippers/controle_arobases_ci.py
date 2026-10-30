"""Contrôle des @ à donner, lancé par GitHub Actions (30/10/2026).

Gaëtan (30/10) : « il faut vraiment s'assurer que tous les arobas qu'on envoie et qui sont dans le sheet soient bien disponibles à
chaque fois sur Instagram pour les nouveaux clippers ». La clé RapidAPI de Railway répond 403 sur FlashAPI ; celle du dépôt marche.
Ce script examine (arobase_libre.examen : ID, puis profil s'il existe) les lignes « à créer » attribuées à un clipper et les
prochaines du stock de chaque créatrice (arobase_libre.cibles_ci), et écrit l'onglet « IG · Contrôle des @ » du tableur App
clippers · usage. Le bot le lit quand sa propre clé est refusée (arobase_libre.depuis_ci).

Secrets du dépôt : RAPIDAPI_KEY, GOOGLE_SERVICE_ACCOUNT_JSON. Code de sortie 1 si la clé manque ou si aucun @ n'a pu être lu.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

import arobase_libre as A  # noqa: E402
import instagram_rapidapi as I  # noqa: E402

FICHIER = Path(os.environ.get("SUIVI_FICHIER", "donnees_ci/instagram.json"))


def lire_json(fichier, defaut):
    try:
        return json.loads(Path(fichier).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def ecrire_json(fichier, donnees):
    f = Path(fichier)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")


async def main() -> int:
    import onboarding
    import paie_clics
    import pilotage
    if not I.CLE:
        print("RAPIDAPI_KEY manquant : ajoute le secret dans GitHub (Settings → Secrets and variables → Actions).")
        return 1
    I.configurer({"lire_json": lire_json, "ecrire_json": ecrire_json, "FICHIER": FICHIER})
    comptes = await onboarding.lire_comptes()
    dans_le_log = {A.norm(c.get("handle")) for c in comptes if c.get("handle")}
    cibles = A.cibles_ci(comptes)
    # 30/10 : des @ en plus, donnés au lancement à la main (entrée « arobases » du workflow), même hors des lignes à créer
    vus = {c["handle"] for c in cibles}
    for h in os.environ.get("AROBASES_EN_PLUS", "").replace(",", " ").split():
        if A.norm(h) and A.norm(h) not in vus:
            vus.add(A.norm(h))
            cibles.append({"handle": A.norm(h), "creatrice": "", "onglet": "", "ligne": "", "gerant": "en plus (lancement manuel)"})
    lignes, compte = [], {}
    for c in cibles:
        # jamais examen() ici : il relirait l'onglet de ce même contrôle et le daterait de maintenant
        ex = await A._examen_direct(c["handle"], c["creatrice"])
        variante = ""
        if ex.get("verdict") == A.PRIS and ex.get("profil_lu") and not ex.get("a_nous"):
            # pris (même tout neuf : le bot décide si c'est celui du clipper) : la première variante libre, pour le bot
            for v in A.variantes(c["handle"])[:A.VARIANTES_MAX]:
                if v not in dans_le_log and v not in vus and (await A._examen_direct(v, ""))["verdict"] == A.LIBRE:
                    variante = v
                    break
        ligne = A.ligne_ci(c, ex, datetime.now(timezone.utc), variante)
        if variante:                                                     # la variante a sa propre ligne : le bot la lit libre
            vus.add(variante)
            lignes.append(A.ligne_ci({**c, "handle": variante, "gerant": f"variante de {c['handle']}"}, {"verdict": A.LIBRE},
                                     datetime.now(timezone.utc)))
            compte["libre"] = compte.get("libre", 0) + 1
        compte[ligne[5]] = compte.get(ligne[5], 0) + 1
        lignes.append(ligne)
    ordre = {"existe": 0, "existe, profil illisible": 0, "pas lu": 1, "libre": 2}
    lignes.sort(key=lambda l: (ordre.get(l[5], 3), l[1], l[0]))
    classeur = await paie_clics._classeur_usage()
    if classeur:
        await pilotage._ecrire(classeur, A.ONGLET_CI, A.ENTETE_CI, lignes)
    print("Contrôle des @ :", len(cibles), "cible(s) ·", json.dumps(compte, ensure_ascii=False), "· requêtes :", I._jour["n"],
          "· quota restant :", I._jour["restant"])
    return 0 if any(l[5] != "pas lu" for l in lignes) or not lignes else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
