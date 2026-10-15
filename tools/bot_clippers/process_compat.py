"""Sauvegarde locale additive avant activation ; aucun accès réseau ni import de dossiers."""
from pathlib import Path
import json
import os
import shutil
import sqlite3
import tempfile


def sauvegarder(dossier):
    dossier = Path(dossier)
    cible = dossier / 'sauvegarde-processus-20261015'
    if (cible / 'manifest.json').is_file():
        return cible
    temporaire = Path(tempfile.mkdtemp(prefix='.sauvegarde-processus-', dir=dossier))
    os.chmod(temporaire, 0o700)
    try:
        noms = []
        for source in sorted(dossier.glob('*.json')):
            if source.is_symlink() or not source.is_file():
                continue
            shutil.copyfile(source, temporaire / source.name)
            os.chmod(temporaire / source.name, 0o600)
            noms.append(source.name)
        db = dossier / 'process_clippeur.sqlite3'
        if db.is_file():
            source = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
            dest = sqlite3.connect(temporaire / db.name)
            try:
                source.backup(dest)
            finally:
                source.close()
                dest.close()
            os.chmod(temporaire / db.name, 0o600)
            noms.append(db.name)
        (temporaire / 'manifest.json').write_text(json.dumps({'version': 1, 'fichiers': noms}))
        os.chmod(temporaire / 'manifest.json', 0o600)
        # Aucun ancien snapshot écrasé ; un échec laisse les données source intactes.
        temporaire.rename(cible)
        return cible
    except BaseException:
        shutil.rmtree(temporaire)
        raise
