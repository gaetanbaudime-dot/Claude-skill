"""Journal transactionnel du processus. Aucun appel réseau ni secret dans les erreurs.

SQLite sur le volume persistant du bot ; BEGIN IMMEDIATE arbitre aussi deux
processus partageant ce volume. Ne convient pas à des réplicas à disques séparés.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class Bloque(RuntimeError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS histories(uid TEXT PRIMARY KEY, evidence TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, uid TEXT NOT NULL,
                    status TEXT NOT NULL, evidence TEXT);
                CREATE TABLE IF NOT EXISTS aliases(handle TEXT PRIMARY KEY, account_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS resources(kind TEXT, value TEXT, owner TEXT NOT NULL,
                    PRIMARY KEY(kind,value));
                CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reconcile(self, uid, accounts, evidence):
        """Import explicite d'un historique complet revu ; jamais appelé implicitement.

        accounts : [{aliases: [...], status: created|reserved|unknown, evidence: ref}].
        Ne supprime jamais une identité déjà connue, ne diminue jamais un compteur.
        """
        if not str(evidence or '').strip():
            raise Bloque('Référence du rapprochement requise')
        with self.transaction() as db:
            for account in accounts:
                aliases = [str(h).lower().lstrip('@') for h in account['aliases']]
                if not aliases or account['status'] not in ('created', 'reserved', 'unknown'):
                    raise Bloque('Historique invalide')
                found = db.execute('SELECT a.id,a.uid,a.status FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?', (aliases[0],)).fetchone()
                if found and found[1] != str(uid):
                    raise Bloque('Identité déjà attribuée')
                ident = found[0] if found else str(uuid4())
                status = 'created' if found and found[2] == 'created' else account['status']
                db.execute('INSERT OR REPLACE INTO accounts VALUES(?,?,?,?)', (ident, str(uid), status, account.get('evidence') or evidence))
                for h in aliases:
                    prior = db.execute('SELECT account_id FROM aliases WHERE handle=?', (h,)).fetchone()
                    if prior and prior[0] != ident:
                        raise Bloque('Alias historique ambigu')
                    db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)', (h, ident))
            db.execute('INSERT OR REPLACE INTO histories VALUES(?,?)', (str(uid), evidence))

    def reserve(self, uid, handles):
        uid = str(uid)
        handles = sorted({str(h).lower().lstrip('@') for h in handles if h})
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM jobs WHERE key=?', ('sortie:' + uid,)).fetchone():
                raise Bloque('Départ enregistré : aucune nouvelle allocation')
            if not db.execute('SELECT 1 FROM histories WHERE uid=?', (uid,)).fetchone():
                raise Bloque('Historique à vie non rapproché : allocation bloquée')
            count = db.execute("SELECT COUNT(*) FROM accounts WHERE uid=? AND status IN ('created','reserved','unknown')", (uid,)).fetchone()[0]
            nouveaux = []
            for h in handles:
                found = db.execute('SELECT a.uid,a.status FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?', (h,)).fetchone()
                if found:
                    if found[0] != uid or found[1] == 'cancelled':
                        raise Bloque('Réattribution interdite')
                else:
                    nouveaux.append(h)
            if count + len(nouveaux) > 3:
                raise Bloque('Trois places à vie déjà créées, réservées ou incertaines')
            for h in nouveaux:
                ident = str(uuid4())
                db.execute('INSERT INTO accounts VALUES(?,?,?,NULL)', (ident, uid, 'reserved'))
                db.execute('INSERT INTO aliases VALUES(?,?)', (h, ident))

    def created(self, uid, handle, evidence):
        if not evidence:
            raise Bloque('Preuve de création requise')
        with self.transaction() as db:
            found = db.execute('SELECT a.id,a.uid,a.status FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?', (handle.lower().lstrip('@'),)).fetchone()
            if not found or found[1] != str(uid) or found[2] == 'cancelled':
                raise Bloque('Création sans réservation valide')
            db.execute("UPDATE accounts SET status='created',evidence=? WHERE id=?", (evidence, found[0]))

    def cancel(self, uid, handle, evidence):
        """Uniquement preuve explicite de non-création, jamais timeout, ban ou départ."""
        if not evidence:
            raise Bloque('Preuve de non-création requise')
        with self.transaction() as db:
            result = db.execute("UPDATE accounts SET status='cancelled',evidence=? WHERE uid=? AND status='reserved' AND id=(SELECT account_id FROM aliases WHERE handle=?)", (evidence, str(uid), handle.lower().lstrip('@')))
            if result.rowcount != 1:
                raise Bloque('Seule une réservation non créée peut être annulée')

    def rename(self, uid, old, new):
        with self.transaction() as db:
            found = db.execute('SELECT a.id FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE a.uid=? AND h.handle=?', (str(uid), old.lower().lstrip('@'))).fetchone()
            if not found:
                raise Bloque('Identité à rapprocher avant renommage')
            existing = db.execute('SELECT account_id FROM aliases WHERE handle=?', (new.lower().lstrip('@'),)).fetchone()
            if existing and existing[0] != found[0]:
                raise Bloque('Alias déjà attribué')
            db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)', (new.lower().lstrip('@'), found[0]))

    def counts(self, uid):
        with self.transaction() as db:
            return dict(db.execute('SELECT status,COUNT(*) FROM accounts WHERE uid=? GROUP BY status', (str(uid),)).fetchall())

    def get(self, key):
        with self.transaction() as db:
            row = db.execute('SELECT data FROM jobs WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else {}

    def put(self, key, data):
        with self.transaction() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)', (key, json.dumps(data)))

    def claim(self, owner, resources):
        """Tout le lot ou rien. Les destinations ne retournent jamais au pool au départ."""
        with self.transaction() as db:
            for kind, value in resources:
                prior = db.execute('SELECT owner FROM resources WHERE kind=? AND value=?', (kind, value)).fetchone()
                if prior and prior[0] != owner:
                    raise Bloque('Destination déjà réservée à un autre clippeur')
                db.execute('INSERT OR IGNORE INTO resources VALUES(?,?,?)', (kind, value, owner))

    @contextmanager
    def lock(self, key):
        """Verrou non bloquant interprocessus, libéré automatiquement après un crash."""
        import fcntl
        import hashlib
        path = self.path.parent / ('process-' + hashlib.sha256(key.encode()).hexdigest() + '.lock')
        with path.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Bloque('Opération déjà en cours, réessayer') from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def resource_owner(self, kind, value):
        with self.transaction() as db:
            row = db.execute('SELECT owner FROM resources WHERE kind=? AND value=?', (kind, value)).fetchone()
            return row[0] if row else None

    def claim_job(self, key, data):
        """Destinations et intention persistées dans la même transaction."""
        with self.transaction() as db:
            prior = db.execute('SELECT data FROM jobs WHERE key=?', (key,)).fetchone()
            if prior:
                return json.loads(prior[0])
            for kind in ('mym', 'of'):
                value = data[kind]
                owner = db.execute('SELECT owner FROM resources WHERE kind=? AND value=?', (kind, value)).fetchone()
                if owner and owner[0] != key:
                    raise Bloque('Destination déjà réservée à un autre clippeur')
                db.execute('INSERT OR IGNORE INTO resources VALUES(?,?,?)', (kind, value, key))
            db.execute('INSERT INTO jobs VALUES(?,?)', (key, json.dumps(data)))
            return data

    def owner_for_handle(self, handle):
        with self.transaction() as db:
            row = db.execute('SELECT a.uid FROM accounts a JOIN aliases h ON h.account_id=a.id WHERE h.handle=?',
                             (str(handle).lower().lstrip('@'),)).fetchone()
            return row[0] if row else None
