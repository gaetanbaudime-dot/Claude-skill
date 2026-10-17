"""Rapport local depuis un instantané autorisé ; aucun réseau, aucun envoi.

python outils/mesurer_recrutement.py instantane.json --maintenant 2026-10-16T12:00:00Z
Entrée : pipeline, equipes, parcours, comptes, couverture_publications (bool).
La couverture doit être attestée par le lecteur serveur, jamais déduite d'un fichier vide.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recrutement_suivi as suivi


def rapport(snapshot, maintenant):
    manquantes = [cle for cle in ('pipeline','equipes','parcours','comptes') if cle not in snapshot]
    if manquantes:
        return dict(statut='non_mesure', sources_manquantes=manquantes, fuseau='UTC')
    pipeline, equipes, parcours, comptes = (snapshot[k] for k in ('pipeline','equipes','parcours','comptes'))
    if not all(isinstance(x,dict) for x in (pipeline,equipes,parcours)) or not isinstance(comptes,list):
        return dict(statut='non_mesure', raison='Schéma de source invalide', fuseau='UTC')
    dossiers = suivi.dossiers_depuis_sources(pipeline,equipes,parcours,comptes)
    publications = suivi.publications_attribuees(pipeline,parcours)
    resultat = suivi.mesurer(dossiers,publications,maintenant,
                            couverture=snapshot.get('couverture_publications') is True)
    resultat['premieres_reussites_quiz'] = suivi.premieres_reussites(pipeline)
    resultat['dossiers_source'] = dossiers
    resultat['volume'] = suivi.decision_volume(snapshot.get('mesures_volume') or {}, snapshot.get('seuils_volume') or {})
    return resultat


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instantane',type=Path)
    parser.add_argument('--maintenant',required=True,help='Instant avec fuseau, pour un résultat reproductible')
    args=parser.parse_args()
    maintenant=suivi.instant(args.maintenant)
    if maintenant is None:
        parser.error('Instant avec fuseau obligatoire')
    try:
        snapshot=json.loads(args.instantane.read_text())
        if not isinstance(snapshot,dict):
            raise ValueError('objet JSON attendu')
    except (OSError,ValueError):
        print(json.dumps(dict(statut='non_mesure',raison='Source illisible'),ensure_ascii=False))
        return 2
    print(json.dumps(rapport(snapshot,maintenant),ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
