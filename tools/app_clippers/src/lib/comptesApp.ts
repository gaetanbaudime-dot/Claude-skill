/** 12/10 (Gaëtan : « une application pour les team leaders… un onglet avec un lien direct vers Instagram pour voir les comptes de
 *  ses clippeurs… et dans l'app clippeur, un onglet où il peut mettre à jour le @ de ses 3 comptes Instagram »).
 *
 *  Le bot publie l'onglet « Comptes app » du tableur « App clippers · usage » (tools/bot_clippers/pilotage.py, toutes les 15 min) :
 *      Clé app | Prénom | Créatrice | N° | @ | ETAT | Followers | Reels 7 j | Vues 7 j (48 h) | Clé app TL | Prénom TL
 *  une ligne par compte, dans l'ordre du parcours ; la colonne « Team leader » du classeur décide du TL de chaque clipper.
 *  Un @ corrigé dans l'app est AJOUTÉ à l'onglet « Pseudos app » (Date | Clé app | N° | Nouveau @ | Statut | Détail) ; le bot
 *  l'applique avec la règle de `!pseudo` (classeur, fiche, scan) et écrit « fait » ou « refusé » avec la raison. L'app n'écrit
 *  jamais le classeur elle-même. */
import { ajouterLignes, assurerOnglet, lirePlage, maintenantParis, tableur } from "./usage";
import { lireJours } from "./activite";

export const ONGLET_COMPTES_APP = "Comptes app";
export const ONGLET_PSEUDOS = "Pseudos app";
const ENTETE_PSEUDOS = ["Date", "Clé app", "N°", "Nouveau @", "Statut", "Détail"];

/** `role` : colonne M « Rôle compte » publiée par le bot (« privé » = le compte au lien GAML, « croissance » sinon).
 *  `jours` : colonne N « Reels par jour (17 j) » (24/10), undefined tant que le bot ne la publie pas. */
export type CompteApp = { n: number; handle: string; etat: string; creatrice: string; followers: number | null; reels7: number | null; vues7: number | null; followersVerifiesLe?: string; role?: string; jours?: Record<string, number> };
export type MembreEquipe = { cle: string; prenom: string; creatrice: string; comptes: CompteApp[] };
export type Demande = { n: number; handle: string; statut: string; detail: string; date: string };

const nb = (x: string | undefined): number | null => {
  const t = String(x ?? "").replace(/\s/g, "").replace(",", ".");
  if (!t) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
};

type Ligne = { cle: string; prenom: string; compte: CompteApp | null; cleTl: string; prenomTl: string };
let cache: { t: number; lignes: Ligne[] } | null = null;

async function lignes(): Promise<Ligne[]> {
  if (cache && Date.now() - cache.t < 2 * 60 * 1000) return cache.lignes;
  // 31/10 (vérification de 14 apps d'affilée : quota Google Sheets dépassé, deux apps affichaient « UID:1471… » au lieu du
  // prénom) : une lecture refusée garde les dernières lignes connues plutôt que de tout perdre
  let tout: string[][];
  try { tout = await lirePlage(await tableur(), `'${ONGLET_COMPTES_APP}'!A1:N`); }
  catch (e) { if (cache) return cache.lignes; throw e; }
  // L'API Sheets coupe les cellules vides en fin de ligne : seul l'en-tête dit si la colonne N est publiée
  const avecJours = String(tout[0]?.[13] || "").startsWith("Reels par jour");
  const brut = tout.slice(1);
  const l = brut.filter((r) => (r[0] || "").trim()).map((r) => ({
    cle: (r[0] || "").trim(), prenom: (r[1] || "").trim(), cleTl: (r[9] || "").trim(), prenomTl: (r[10] || "").trim(),
    compte: (r[4] || "").trim() ? { n: parseInt(r[3] || "0", 10) || 0, handle: (r[4] || "").trim(), etat: (r[5] || "").trim(),
      creatrice: (r[2] || "").trim(), followers: nb(r[6]), reels7: nb(r[7]), vues7: nb(r[8]), followersVerifiesLe: (r[11] || "").trim(),
      role: (r[12] || "").trim(), jours: avecJours ? lireJours(r[13] || "") : undefined } : null,
  }));
  cache = { t: Date.now(), lignes: l };
  return l;
}

/** Clé d'app → prénom, tel que le bot l'écrit (colonne « Prénom »). Sert aux clés « uid:<id> » (lib/clippers, nommer). */
export async function prenomsDesCles(): Promise<Map<string, string>> {
  const m = new Map<string, string>();
  for (const x of await lignes()) if (x.cle && x.prenom && !m.has(x.cle)) m.set(x.cle, x.prenom);
  return m;
}

export async function mesComptes(cle: string): Promise<{ comptes: CompteApp[]; tl: string }> {
  const l = (await lignes()).filter((x) => x.cle === cle);
  return { comptes: l.map((x) => x.compte).filter((c): c is CompteApp => !!c).sort((a, b) => a.n - b.n), tl: l[0]?.prenomTl || "" };
}

/** Les clippers dont `cle` est le TL (colonne « Team leader » du classeur, ou TL de la créatrice), avec leurs comptes. */
export async function monEquipe(cle: string): Promise<MembreEquipe[]> {
  const par = new Map<string, MembreEquipe>();
  for (const x of await lignes()) {
    if (!cle || x.cleTl !== cle || x.cle === cle) continue;
    const m = par.get(x.cle) || { cle: x.cle, prenom: x.prenom, creatrice: "", comptes: [] };
    if (x.compte) { m.comptes.push(x.compte); m.creatrice = m.creatrice || x.compte.creatrice; }
    par.set(x.cle, m);
  }
  return [...par.values()].map((m) => ({ ...m, comptes: m.comptes.sort((a, b) => a.n - b.n) })).sort((a, b) => a.prenom.localeCompare(b.prenom));
}

export async function estTl(cle: string): Promise<boolean> {
  try { return (await monEquipe(cle)).length > 0; } catch { return false; }
}

/** Les dernières demandes de changement de @ de ce clipper (la plus récente par compte). */
let cachePseudos: { t: number; brut: string[][] } | null = null;
/** « Pseudos app » relu au plus toutes les 30 secondes par instance (28/10 : quota Sheets) ; une demande envoyée vide le cache. */
export async function mesDemandes(cle: string): Promise<Demande[]> {
  let brut: string[][] = [];
  try {
    if (cachePseudos && Date.now() - cachePseudos.t < 30_000) brut = cachePseudos.brut;
    else { brut = await lirePlage(await tableur(), `'${ONGLET_PSEUDOS}'!A2:F`); cachePseudos = { t: Date.now(), brut }; }
  } catch { return []; }
  return demandesRecentes(brut, cle, Date.now());
}

/** 28/10 (audit : un refus du 12/10 s'affichait encore le 28/10, sur un autre compte depuis que les n° avaient bougé) : la plus
 *  récente par compte, en attente depuis moins de 24 h ou refusée depuis moins de 3 jours. Une demande faite ne s'affiche pas. Pur. */
export function demandesRecentes(brut: string[][], cle: string, maintenant: number): Demande[] {
  const par = new Map<number, Demande>();
  for (const r of brut) {
    if ((r[1] || "").trim() !== cle) continue;
    const n = parseInt(r[2] || "0", 10) || 0;
    par.set(n, { n, handle: (r[3] || "").trim(), statut: (r[4] || "").trim(), detail: (r[5] || "").trim(), date: (r[0] || "").trim() });
  }
  const age = (d: string) => {                                     // « 2026-10-12 15:09:56 », heure de Paris : à une heure près
    const t = Date.parse(d.replace(" ", "T") + "Z");
    return Number.isFinite(t) ? (maintenant - t) / 3_600_000 : Infinity;
  };
  return [...par.values()]
    .filter((d) => (!d.statut && age(d.date) < 24) || (d.statut === "refusé" && age(d.date) < 72))
    .sort((a, b) => a.n - b.n);
}

/** Un @ Instagram valide : lettres, chiffres, point, tiret bas ; 1 à 30 caractères ; pas de point au début ni à la fin. */
export function nettoyerHandle(brut: string): string | null {
  let h = String(brut || "").trim().toLowerCase();
  const m = /instagram\.com\/([^/?#\s]+)/.exec(h);
  if (m) h = m[1];
  h = h.replace(/^@+/, "");
  return /^(?!\.)(?!.*\.$)[a-z0-9._]{1,30}$/.test(h) ? h : null;
}

export async function demanderPseudo(cle: string, n: number, handle: string): Promise<void> {
  const id = await tableur();
  await assurerOnglet(id, ONGLET_PSEUDOS, ENTETE_PSEUDOS);
  const { date, heure } = maintenantParis();
  await ajouterLignes(id, `'${ONGLET_PSEUDOS}'!A:F`, [[`${date} ${heure}`, cle, String(n), handle, "", ""]]);
  cachePseudos = null;                                             // le clipper voit sa demande « en cours » tout de suite
}
