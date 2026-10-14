"""Mutualise les lectures Instagram, sans payer ni rafraîchir artificiellement les mesures."""

import asyncio
import copy
import logging
from datetime import datetime, timedelta, timezone


class CacheCollecte:
    def __init__(self, lire=None, ecrire=None, fichier=None, minutes=15):
        self.lire, self.ecrire, self.fichier = lire, ecrire, fichier
        self.minutes = max(0, minutes)
        self.verrou = asyncio.Lock()
        self.memoire = {}
        self.echecs = {}

    def _charger(self):
        if self.fichier and self.lire:
            try:
                d = self.lire(self.fichier, {})
                return d if isinstance(d, dict) else {}
            except (OSError, ValueError):
                # Un cache illisible ne doit pas déclencher un scraping payant.
                raise RuntimeError("Cache Apify illisible : collecte suspendue") from None
        return self.memoire

    async def obtenir(self, cles, scope, jour, collecter, forcer=False, maintenant=None):
        """Un seul appel en vol. Un scan plus complet peut servir un scan simple, jamais l'inverse.

        Seules les fiches vivantes lues sont conservées. Les dates et le scope d'origine restent
        attachés aux résultats : leur relecture ne devient pas un nouveau relevé.
        """
        async with self.verrou:
            now = maintenant or datetime.now(timezone.utc)
            d = self._charger()
            out, manquants = {}, []
            for cle in dict.fromkeys(cles):
                e = d.get(cle) or {}
                try:
                    t = datetime.fromisoformat(e.get("t", ""))
                    recent = timedelta(0) <= now - t < timedelta(minutes=self.minutes)
                except (ValueError, TypeError):
                    recent = False
                if not forcer and recent and e.get("jour") == jour and e.get("scope", -1) >= scope:
                    out[cle] = copy.deepcopy(e["mesure"])
                    out[cle]["cache_apify"] = True
                else:
                    manquants.append(cle)
            if manquants:
                if not forcer and any(self.echecs.get(cle, now) > now for cle in manquants):
                    return None
                try:
                    nouvelles = await collecter(manquants)
                except asyncio.CancelledError:
                    for cle in manquants:
                        self.echecs[cle] = (datetime.now(timezone.utc) if maintenant is None else now) + timedelta(minutes=5)
                    raise
                if nouvelles is None:
                    for cle in manquants:
                        self.echecs[cle] = (datetime.now(timezone.utc) if maintenant is None else now) + timedelta(minutes=5)
                    # Les appelants attendent tous les comptes demandés : une réponse partielle
                    # ne doit pas transformer les absents en journées non lues, puis en BAN.
                    return None
                t = (datetime.now(timezone.utc) if maintenant is None else now).isoformat(timespec="seconds")
                for cle, mesure in nouvelles.items():
                    m = copy.deepcopy(mesure)
                    m["collecte_iso"] = t
                    m["cache_apify"] = False
                    out[cle] = m
                    if m.get("lu") and m.get("existe") and not m.get("budget"):
                        d[cle] = {"t": t, "jour": jour, "scope": scope, "mesure": m}
                        self.echecs.pop(cle, None)
                    elif not m.get("lu") and not m.get("budget"):
                        self.echecs[cle] = (datetime.now(timezone.utc) if maintenant is None else now) + timedelta(minutes=5)
            # Supprime les données hors TTL plutôt que de conserver les bios indéfiniment.
            limites = now - timedelta(days=1)
            propres = {}
            for cle, e in d.items():
                try:
                    if datetime.fromisoformat(e["t"]) >= limites:
                        propres[cle] = e
                except (KeyError, ValueError, TypeError):
                    continue
            if self.fichier and self.ecrire:
                self.ecrire(self.fichier, propres)
            self.memoire = propres
            self.echecs = {cle: fin for cle, fin in self.echecs.items() if fin > now}
            logging.getLogger("etats_comptes").info("Apify mutualisé : %d comptes en cache, %d demandés",
                                                   len(out) - len(manquants), len(manquants))
            return out
