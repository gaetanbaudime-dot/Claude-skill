"""Historique Instagram durable sur le volume Railway. Aucune clé dans les fichiers."""

import json
from contextlib import closing
import sqlite3


CHAMPS = ("followers", "posts_total", "reels_hier", "reels_7j", "reels_lus", "couvre",
          "prive", "restreint", "ig_id", "serie_reels")


class HistoriqueReleves:
    def __init__(self, fichier):
        self.fichier = fichier

    def _connexion(self):
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(self.fichier, timeout=5)
        c.execute("CREATE TABLE IF NOT EXISTS releves (compte TEXT NOT NULL, collecte TEXT NOT NULL, "
                  "mesure TEXT NOT NULL, PRIMARY KEY(compte, collecte))")
        return c

    def enregistrer(self, mesures):
        # Le timestamp d'origine rend une relecture de cache idempotente.
        lignes = []
        for cle, m in mesures.items():
            if not m.get("lu") or not m.get("existe") or not m.get("collecte_iso"):
                continue
            propres = {k: m[k] for k in CHAMPS if k in m}
            lignes.append((cle, m["collecte_iso"], json.dumps(propres, ensure_ascii=False)))
        if not lignes:
            return
        with closing(self._connexion()) as c, c:
            c.executemany("INSERT OR IGNORE INTO releves(compte, collecte, mesure) VALUES (?, ?, ?)", lignes)
            c.execute("DELETE FROM releves WHERE datetime(collecte) < datetime('now', '-100 days')")

