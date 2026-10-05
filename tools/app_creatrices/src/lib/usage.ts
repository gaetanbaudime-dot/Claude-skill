/** Journal d'usage de l'app, pour Gaëtan uniquement : une ligne par événement (ouverture, onglet, période, tuile Drive)
 *  dans un tableur « App créatrices · usage » que l'app crée elle-même au premier événement avec le compte de service,
 *  dans le dossier interne de l'agence (« [A] G&M — Interne », à la racine du Drive, hors de portée des créatrices).
 *  Rien d'autre n'est collecté : ni adresse IP, ni appareil, ni navigateur. Toute erreur est avalée : le journal ne doit jamais gêner l'app. */
import { jetonGoogle } from "./google";
import { creatrices } from "./config";

const NOM_FEUILLE = "App créatrices · usage";
const DOSSIER_INTERNE = /\[A\]/;                                       // « 📁 [A] G&M — Interne »
const ONGLET = "Événements";
const ENTETE = ["Date", "Heure (Paris)", "Créatrice", "Événement", "Mode"];
let cache: { id: string; expire: number } | null = null;

async function appel(url: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  const jeton = await jetonGoogle();
  const r = await fetch(url, { ...init, headers: { Authorization: `Bearer ${jeton}`, "Content-Type": "application/json", ...(init.headers || {}) }, cache: "no-store" });
  if (!r.ok) throw new Error(`${url.split("?")[0]} ${r.status}`);
  return (await r.json()) as Record<string, unknown>;
}

async function chercher(): Promise<string | null> {
  const q = `name='${NOM_FEUILLE}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`;
  const d = await appel(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id)&pageSize=1`);
  const fichiers = (d.files as { id: string }[] | undefined) || [];
  return fichiers[0]?.id || null;
}

/** Le dossier interne de l'agence : on remonte depuis le dossier d'une créatrice jusqu'à la racine du Drive, puis on y cherche « [A] … ». */
async function dossierInterne(): Promise<string | null> {
  const premiere = Object.values(creatrices())[0];
  if (!premiere) return null;
  let id = premiere.racine;
  for (let i = 0; i < 6; i++) {
    const d = await appel(`https://www.googleapis.com/drive/v3/files/${id}?fields=id,parents&supportsAllDrives=true`);
    const parents = d.parents as string[] | undefined;
    if (!parents || !parents.length) break;
    id = parents[0];
  }
  const q = `'${id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'`;
  const l = await appel(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name)&pageSize=50&supportsAllDrives=true&includeItemsFromAllDrives=true`);
  const dossiers = (l.files as { id: string; name: string }[] | undefined) || [];
  return dossiers.find((x) => DOSSIER_INTERNE.test(x.name))?.id || null;
}

async function creer(): Promise<string> {
  const parent = await dossierInterne();
  const d = await appel("https://www.googleapis.com/drive/v3/files?supportsAllDrives=true", {
    method: "POST",
    body: JSON.stringify({ name: NOM_FEUILLE, mimeType: "application/vnd.google-apps.spreadsheet", ...(parent ? { parents: [parent] } : {}) }),
  });
  const id = d.id as string;
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}:batchUpdate`, {
    method: "POST",
    body: JSON.stringify({ requests: [
      { updateSpreadsheetProperties: { properties: { locale: "fr_FR", timeZone: "Europe/Paris" }, fields: "locale,timeZone" } },
      { updateSheetProperties: { properties: { sheetId: 0, title: ONGLET, gridProperties: { frozenRowCount: 1 } }, fields: "title,gridProperties.frozenRowCount" } },
    ] }),
  });
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(`${ONGLET}!A1:E1`)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: [ENTETE] }) });
  return id;
}

async function feuille(): Promise<string> {
  if (cache && cache.expire > Date.now()) return cache.id;
  const id = (await chercher()) || (await creer());
  cache = { id, expire: Date.now() + 6 * 60 * 60 * 1000 };
  return id;
}

function maintenantParis(): { date: string; heure: string } {
  const f = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const p = Object.fromEntries(f.formatToParts(new Date()).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, heure: `${p.hour}:${p.minute}:${p.second}` };
}

export async function enregistrer(prenom: string, evenement: string, mode: string): Promise<void> {
  try {
    const id = await feuille();
    const { date, heure } = maintenantParis();
    await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(`${ONGLET}!A:E`)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, {
      method: "POST", body: JSON.stringify({ values: [[date, heure, prenom, evenement, mode]] }),
    });
  } catch (e) {
    cache = null;                                                      // on recherchera la feuille au prochain événement
    console.warn("usage :", (e as Error).message);
  }
}
