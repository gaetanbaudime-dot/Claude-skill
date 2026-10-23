"""Suivi Instagram lancé par GitHub Actions (22/10/2026, Gaëtan : « on pousse le scraper », Railway en panne).

Le même passage complet qu'`instagram_rapidapi.boucle` (profils, Reels, vues, top 20 des créatrices, onglets « IG · … »), mais
lancé par le cron du dépôt (.github/workflows/suivi-instagram.yml) : il tourne même quand Railway est arrêté. L'historique
(followers, Reels déjà vus) vit dans SUIVI_FICHIER, que le workflow garde d'un passage à l'autre (cache Actions).
Le passage au compte 2 / 3 reste au bot (il lit sa fiche parcours sur le volume Railway).

Secrets du dépôt : RAPIDAPI_KEY, GOOGLE_SERVICE_ACCOUNT_JSON. Code de sortie 1 si la clé manque ou si rien n'a pu être relu.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

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
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


async def main() -> int:
    import aiohttp
    if not I.CLE:
        print("RAPIDAPI_KEY manquant : ajoute le secret dans GitHub (Settings → Secrets and variables → Actions).")
        return 1
    I.configurer({"lire_json": lire_json, "ecrire_json": ecrire_json, "FICHIER": FICHIER})
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
        bilan = await I.passage_complet(session)
        # 22/10 : les @ « à créer » pris sur Instagram sont remplacés dans le LOG par une variante libre (pseudos_uniques)
        if not bilan.get("arret_temps") and not bilan.get("arret_quota"):
            try:
                import onboarding
                import pseudos_uniques
                store = lire_json(FICHIER, {})
                bp = await pseudos_uniques.passage(session, store, await onboarding.lire_comptes())
                ecrire_json(FICHIER, store)
                print("Pseudos :", json.dumps(bp, ensure_ascii=False))
            except Exception as erreur:                                 # noqa: BLE001 — le suivi est déjà écrit
                print("Pseudos non vérifiés :", type(erreur).__name__, str(erreur)[:200])
        # 23/10 : Public / Privé / Introuvable dans le LOG (colonne « Visibilité Insta ») et anomalies des comptes des clippers
        try:
            import visibilite_ig
            print("Visibilité :", json.dumps(await visibilite_ig.passage(lire_json(FICHIER, {})), ensure_ascii=False))
        except Exception as erreur:                                     # noqa: BLE001
            print("Visibilité non écrite :", type(erreur).__name__, str(erreur)[:200])
    print("Bilan :", json.dumps(bilan, ensure_ascii=False), "· requêtes :", I._jour["n"], "· quota restant :", I._jour["restant"])
    if I.RATTRAPAGE_J:
        print(f"Rattrapage {I.RATTRAPAGE_J} j : {bilan.get('rattrapage_restants', 0)} compte(s) restant(s), repris au passage suivant.")
    return 0 if bilan.get("profils") or bilan.get("reels") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
