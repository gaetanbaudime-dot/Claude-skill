# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
"""OAuth WHOOP one-time. Lance : uv run --python 3.11 --script ~/.whoop-mcp/auth.py"""
import getpass, json, os, secrets, time, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import httpx

CRED = Path.home() / ".whoop-mcp" / "credentials.json"
PORT = 8788
REDIRECT = f"http://localhost:{PORT}/callback"
SCOPES = "offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement"

cid = input("WHOOP Client ID : ").strip()
csec = getpass.getpass("WHOOP Client Secret (saisie masquée) : ").strip()
state = secrets.token_urlsafe(16)
link = "https://api.prod.whoop.com/oauth/oauth2/auth?" + urllib.parse.urlencode({
    "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES, "state": state,
})
res = {}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        if q.path != "/callback":
            self.send_response(404); self.end_headers(); return
        p = urllib.parse.parse_qs(q.query)
        res["code"] = p.get("code", [None])[0]
        res["state"] = p.get("state", [None])[0]
        res["error"] = p.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>WHOOP connecté. Tu peux fermer cet onglet.</h2>".encode("utf-8"))
    def log_message(self, *a):
        pass

print("\nOuverture du navigateur. Si rien ne s'ouvre, colle ce lien :\n" + link + "\n")
try:
    webbrowser.open(link)
except Exception:
    pass

srv = HTTPServer(("localhost", PORT), H)
while "code" not in res and "error" not in res:
    srv.handle_request()

if res.get("error"):
    raise SystemExit("Erreur OAuth : " + res["error"])
if res.get("state") != state:
    raise SystemExit("State mismatch, on arrête.")

r = httpx.post("https://api.prod.whoop.com/oauth/oauth2/token", data={
    "grant_type": "authorization_code", "code": res["code"], "redirect_uri": REDIRECT,
    "client_id": cid, "client_secret": csec,
}, timeout=30)
r.raise_for_status()
t = r.json()

CRED.parent.mkdir(parents=True, exist_ok=True)
CRED.write_text(json.dumps({
    "client_id": cid, "client_secret": csec,
    "access_token": t["access_token"], "refresh_token": t["refresh_token"],
    "expires_at": time.time() + int(t.get("expires_in", 3600)), "scope": t.get("scope", SCOPES),
}, indent=2))
os.chmod(CRED, 0o600)
print("OK : tokens sauvegardés dans", CRED)
