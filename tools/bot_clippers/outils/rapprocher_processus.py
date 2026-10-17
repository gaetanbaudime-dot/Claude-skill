"""Import ADDITIF d'un rapprochement revu. Simulation par défaut, agrégats seulement.

Entrée JSON : [{uid, evidence, accounts:[{aliases:[...], status, evidence}]}].
Jamais une extraction brute du classeur présentée comme historique complet.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--reviewed-history', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Persister le rapprochement revu (aucune suppression)')
    args = parser.parse_args()
    entries = json.loads(args.reviewed_history.read_text())
    if not isinstance(entries, list):
        raise SystemExit('Historique attendu sous forme de liste')
    for e in entries:
        if not isinstance(e, dict) or not e.get('uid') or not e.get('evidence') or not isinstance(e.get('accounts'), list):
            raise SystemExit('Rapprochement incomplet : aucun import')
        if not e['accounts']:
            raise SystemExit('Zéro déclaré : utiliser la commande propriétaire !rapprocher-zero avec sauvegarde obligatoire')
    with tempfile.TemporaryDirectory() as tmp:
        simulation = Path(tmp)/'process.sqlite3'
        if args.database.exists():
            source = sqlite3.connect(f'file:{args.database}?mode=ro', uri=True)
            dest = sqlite3.connect(simulation)
            try: source.backup(dest)
            finally: source.close(); dest.close()
        store = Store(simulation)
        for e in entries:
            store.reconcile(str(e['uid']), e['accounts'], e['evidence'])
        if args.apply:
            store = Store(args.database)
            for e in entries:
                store.reconcile(str(e['uid']), e['accounts'], e['evidence'])
        print(json.dumps({'mode': 'applique' if args.apply else 'simulation', 'dossiers': len(entries),
                          'comptes': sum(len(e['accounts']) for e in entries)}))


if __name__ == '__main__':
    main()
