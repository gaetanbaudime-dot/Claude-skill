/** Journal d'usage de l'app, pour l'agence uniquement : une ligne par événement (ouverture, onglet, tuile Drive, copie du lien)
 *  dans un tableur nommé exactement « App clippers · usage », créé par Gaëtan dans son Drive (dossier « [A] G&M — Interne »)
 *  et partagé en modification avec le compte de service : un compte de service n'a pas de quota Drive, il ne peut pas posséder de fichier,
 *  mais il peut écrire dans un fichier qu'on lui partage. L'app trouve le tableur par son nom, prépare l'onglet « Événements » et y ajoute les lignes.
 *  Rien d'autre n'est collecté : ni adresse IP, ni appareil, ni navigateur. Toute erreur est avalée : le journal ne doit jamais gêner l'app.
 *  Mécanisme identique à celui de l'app créatrices (seul le nom du tableur et la colonne « Clipper » changent). */
import { jetonGoogle } from "./google";
import { creatrices } from "./config";

const NOM_FEUILLE = "App clippers · usage";
const DOSSIER_INTERNE = /\[A\]/;                                       // « 📁 [A] G&M — Interne »
const ONGLET = "Événements";
const ENTETE = ["Date", "Heure (Paris)", "Clipper", "Événement", "Mode"];
let cache: { id: string; expire: number } | null = null;

async function appel(url: string, init: RequestInit = {}): Promise<Record<string, unknown>> {
  const jeton = await jetonGoogle();
  const r = await fetch(url, { ...init, headers: { Authorization: `Bearer ${jeton}`, "Content-Type": "application/json", ...(init.headers || {}) }, cache: "no-store" });
  if (!r.ok) throw new Error(`${url.split("?")[0]} ${r.status} ${(await r.text()).slice(0, 300)}`);
  return (await r.json()) as Record<string, unknown>;
}

async function chercher(): Promise<string | null> {
  const q = `name='${NOM_FEUILLE}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`;
  const d = await appel(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id)&pageSize=1&supportsAllDrives=true&includeItemsFromAllDrives=true`);
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

/** Un tableur créé par Gaëtan n'a qu'un onglet « Feuille 1 » : on le renomme en « Événements » et on pose l'en-tête, une seule fois. */
async function preparer(id: string): Promise<void> {
  const meta = await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}?fields=sheets.properties(sheetId,title)`);
  const feuilles = ((meta.sheets as { properties: { sheetId: number; title: string } }[] | undefined) || []).map((s) => s.properties);
  if (feuilles.some((f) => f.title === ONGLET)) return;
  const premiere = feuilles[0];
  if (!premiere) throw new Error("tableur sans onglet");
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}:batchUpdate`, {
    method: "POST",
    body: JSON.stringify({ requests: [{ updateSheetProperties: { properties: { sheetId: premiere.sheetId, title: ONGLET, gridProperties: { frozenRowCount: 1 } }, fields: "title,gridProperties.frozenRowCount" } }] }),
  });
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(`${ONGLET}!A1:E1`)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: [ENTETE] }) });
}

/** Un onglet de plus dans le même tableur (ex. « Adresses USDC »), créé avec son en-tête s'il n'existe pas encore. */
export async function assurerOnglet(id: string, titre: string, entete: string[]): Promise<void> {
  const meta = await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}?fields=sheets.properties(sheetId,title)`);
  const feuilles = ((meta.sheets as { properties: { sheetId: number; title: string } }[] | undefined) || []).map((s) => s.properties);
  if (feuilles.some((f) => f.title === titre)) return;
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}:batchUpdate`, {
    method: "POST", body: JSON.stringify({ requests: [{ addSheet: { properties: { title: titre, gridProperties: { frozenRowCount: 1 } } } }] }),
  });
  const fin = String.fromCharCode(64 + entete.length);
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(`${titre}!A1:${fin}1`)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: [entete] }) });
}

/** Lecture et écriture brutes d'une plage du tableur (pour les onglets autres que le journal). */
export async function lirePlage(id: string, plage: string): Promise<string[][]> {
  const d = await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(plage)}`);
  return (d.values as string[][] | undefined) || [];
}
export async function ecrirePlage(id: string, plage: string, valeurs: string[][]): Promise<void> {
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(plage)}?valueInputOption=RAW`, { method: "PUT", body: JSON.stringify({ values: valeurs }) });
}
export async function ajouterLignes(id: string, plage: string, valeurs: string[][]): Promise<void> {
  await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(plage)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, { method: "POST", body: JSON.stringify({ values: valeurs }) });
}

let echecJusqua = 0;                                                   // après un échec (tableur absent, quota), on n'insiste pas pendant 10 minutes

/** L'identifiant du tableur « App clippers · usage » (cherché par son nom, en cache 6 h). */
export async function tableur(): Promise<string> {
  if (cache && cache.expire > Date.now()) return cache.id;
  if (echecJusqua > Date.now()) throw new Error("journal d'usage indisponible (nouvel essai dans 10 min)");
  try {
    const trouve = await chercher();
    const id = trouve || (await creer());                              // la création échoue tant que le tableur n'est pas créé par un humain (quota nul du compte de service)
    if (trouve) await preparer(id);
    cache = { id, expire: Date.now() + 6 * 60 * 60 * 1000 };
    return id;
  } catch (e) {
    echecJusqua = Date.now() + 10 * 60 * 1000;
    throw e;
  }
}

export function maintenantParis(): { date: string; heure: string } {
  const f = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const p = Object.fromEntries(f.formatToParts(new Date()).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, heure: `${p.hour}:${p.minute}:${p.second}` };
}

/** Renvoie null si la ligne est écrite, sinon le message d'erreur (journalisé, jamais montré au clipper). */
export async function enregistrer(prenom: string, evenement: string, mode: string): Promise<string | null> {
  try {
    const id = await tableur();
    const { date, heure } = maintenantParis();
    await appel(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values/${encodeURIComponent(`${ONGLET}!A:E`)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, {
      method: "POST", body: JSON.stringify({ values: [[date, heure, prenom, evenement, mode]] }),
    });
    return null;
  } catch (e) {
    cache = null;                                                      // on recherchera la feuille au prochain événement
    const message = (e as Error).message;
    console.warn("usage :", message);
    return message;
  }
}
