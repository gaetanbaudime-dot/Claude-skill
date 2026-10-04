/** Accès Google (Sheets, Drive) avec le compte de service de l'agence : jeton OAuth signé en RS256, mis en cache 50 minutes. */
import { createSign } from "crypto";

type Compte = { client_email: string; private_key: string };
let jetonCache: { valeur: string; expire: number } | null = null;

function compte(): Compte {
  const brut = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!brut) throw new Error("GOOGLE_SERVICE_ACCOUNT_JSON absent");
  return JSON.parse(brut) as Compte;
}

function b64url(s: string | Buffer): string {
  return Buffer.from(s).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function jetonGoogle(): Promise<string> {
  if (jetonCache && jetonCache.expire > Date.now()) return jetonCache.valeur;
  const c = compte();
  const maintenant = Math.floor(Date.now() / 1000);
  const entete = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const corps = b64url(JSON.stringify({
    iss: c.client_email, aud: "https://oauth2.googleapis.com/token", iat: maintenant, exp: maintenant + 3600,
    scope: "https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly",
  }));
  const signeur = createSign("RSA-SHA256");
  signeur.update(`${entete}.${corps}`);
  const signature = b64url(signeur.sign(c.private_key));
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${entete}.${corps}.${signature}` }),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`Google OAuth ${r.status}`);
  const d = (await r.json()) as { access_token: string; expires_in: number };
  jetonCache = { valeur: d.access_token, expire: Date.now() + Math.min(d.expires_in - 120, 3000) * 1000 };
  return d.access_token;
}

export async function sheetsLire(id: string, plage: string): Promise<(string | number)[][]> {
  const jeton = await jetonGoogle();
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(plage)}?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=SERIAL_NUMBER`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (!r.ok) throw new Error(`Sheets ${r.status}`);
  const d = (await r.json()) as { values?: (string | number)[][] };
  return d.values || [];
}

export type Dossier = { id: string; name: string };

export async function driveDossiers(parent: string): Promise<Dossier[]> {
  const jeton = await jetonGoogle();
  const q = `'${parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'`;
  const url = `https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name)&pageSize=100&supportsAllDrives=true&includeItemsFromAllDrives=true`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (!r.ok) throw new Error(`Drive ${r.status}`);
  const d = (await r.json()) as { files?: Dossier[] };
  return d.files || [];
}
