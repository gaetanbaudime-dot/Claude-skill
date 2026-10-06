/** Le bon dossier Drive du moment pour un clipper, en suivant la structure existante (jamais créée ici : c'est le bot
 *  et le script Drive de l'agence qui créent les dossiers) :
 *  Reels     → <Reels de sa créatrice> / 2026 ✅ / 10.Octobre / Semaine N   (semaine 1 = jours 1 à 7, 2 = 8 à 14, 3 = 15 à 21, 4 = 22 à 31)
 *  Photos    → <Photos de sa créatrice> / 2026 ✅ / 10. Octobre
 *  Top Reels → 🎬 Clippers / <Prénom du clipper> / TOP 20 Reels   (ses variantes uniques, déposées par le bot) ;
 *              sinon le « TOP 20 Reels » de la créatrice (Instagram / 📁 Reels / TOP 20 Reels) ; sinon son dossier personnel
 *  Stories   → le dossier Stories de sa créatrice (source du bot) ; sinon son dossier personnel
 *  Un mois ou une semaine pas encore créés font reculer au plus récent existant ; un niveau absent s'arrête au dernier
 *  dossier trouvé : la tuile ouvre toujours quelque chose d'utile, jamais une erreur. */
import { driveDossiers, driveParents, type Dossier } from "./google";
import { aujourdhuiParis, MOIS } from "./dates";
import { creatriceDe, sourcesDe, type Creatrice } from "./config";
import { normaliser, type Clipper } from "./clippers";

export type TypeTuile = "reels" | "photos" | "top" | "stories";
export const TUILES: TypeTuile[] = ["reels", "photos", "top", "stories"];
export type Cible = { type: TypeTuile; id: string; url: string; chemin: string[]; complet: boolean };

const cache = new Map<string, { expire: number; valeur: Cible }>();
const DIX_MINUTES = 10 * 60 * 1000;

function plat(t: string): string {
  return normaliser(t);
}

function trouverAnnee(dossiers: Dossier[], annee: number): Dossier | undefined {
  return dossiers.find((d) => new RegExp(`^\\s*${annee}\\b`).test(d.name));
}

/** Numéro du mois (1-12) lu dans un nom de dossier : « 10.Octobre », « 10. Octobre ✅ », « Octobre 2026 »… */
export function moisDuNom(nom: string): number | null {
  const n = nom.match(/^\s*(0?[1-9]|1[0-2])\s*[.\-_ ]/);
  if (n) return parseInt(n[1], 10);
  const i = MOIS.findIndex((m) => plat(nom).includes(plat(m)));
  return i >= 0 ? i + 1 : null;
}

/** Le dossier du mois demandé ; sinon le mois le plus récent déjà créé (jamais un mois futur). */
function trouverMois(dossiers: Dossier[], mois1: number): { d: Dossier; mois: number } | undefined {
  const candidats = dossiers.map((d) => ({ d, mois: moisDuNom(d.name) })).filter((x): x is { d: Dossier; mois: number } => x.mois !== null);
  const exact = candidats.find((x) => x.mois === mois1);
  if (exact) return exact;
  const passes = candidats.filter((x) => x.mois < mois1).sort((a, b) => b.mois - a.mois);
  return passes[0] || candidats.sort((a, b) => b.mois - a.mois)[0];
}

function numeroDeSemaine(nom: string): number | null {
  const m = plat(nom).match(/^\s*semaine\s*(\d+)\b/);
  return m ? parseInt(m[1], 10) : null;
}

/** La semaine demandée ; sinon la dernière semaine déjà créée avant elle. */
function trouverSemaine(dossiers: Dossier[], n: number): { d: Dossier; semaine: number } | undefined {
  const candidats = dossiers.map((d) => ({ d, semaine: numeroDeSemaine(d.name) })).filter((x): x is { d: Dossier; semaine: number } => x.semaine !== null);
  return candidats.find((x) => x.semaine === n) || candidats.filter((x) => x.semaine < n).sort((a, b) => b.semaine - a.semaine)[0] || candidats.sort((a, b) => b.semaine - a.semaine)[0];
}

export function numeroSemaine(jourDuMois: number): number {
  return Math.min(4, Math.floor((jourDuMois - 1) / 7) + 1);
}

const majuscule = (t: string) => t[0].toUpperCase() + t.slice(1);
const nomPropre = (t: string) => t.replace(/[✅❌⏳🔞📱📣📁🎬]/g, "").trim();

/** Reels ou Photos de la créatrice : même descente que l'app créatrices (année → mois → semaine pour les Reels). */
async function cibleCreatrice(c: Creatrice, type: "reels" | "photos", racineSecours?: string): Promise<{ id: string; chemin: string[]; complet: boolean }> {
  const aujourdhui = aujourdhuiParis();
  const annee = parseInt(aujourdhui.slice(0, 4), 10), mois = parseInt(aujourdhui.slice(5, 7), 10), jour = parseInt(aujourdhui.slice(8, 10), 10);
  let id = (type === "reels" ? c.reels : c.photos) || racineSecours || c.racine;
  const chemin: string[] = [];
  let complet = true;
  const descendre = async (chercher: (ds: Dossier[]) => { d: Dossier; libelle: string; exact: boolean } | undefined, deja?: Dossier[]) => {
    if (!complet) return;
    const r = chercher(deja || (await driveDossiers(id)));
    if (r) { id = r.d.id; chemin.push(r.libelle); if (!r.exact) complet = false; } else complet = false;
  };
  const niveauMois = (ds: Dossier[]) => { const r = trouverMois(ds, mois); return r && { d: r.d, libelle: majuscule(MOIS[r.mois - 1]), exact: r.mois === mois }; };
  const racine = await driveDossiers(id);
  const an = trouverAnnee(racine, annee);
  if (an) { id = an.id; chemin.push(String(annee)); await descendre(niveauMois); }
  else await descendre(niveauMois, racine);                            // pas de dossier d'année : les mois sont directement à la racine
  if (type === "reels") await descendre((ds) => { const r = trouverSemaine(ds, numeroSemaine(jour)); return r && { d: r.d, libelle: `Semaine ${r.semaine}`, exact: r.semaine === numeroSemaine(jour) }; });
  return { id, chemin, complet };
}

/** Le dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice (créé par le bot à l'onboarding), ou null. */
async function dossierClipper(clipper: Clipper): Promise<Dossier | null> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return null;
  const dossiers = await driveDossiers(s.parent);
  return dossiers.find((d) => plat(d.name) === clipper.cle) || dossiers.find((d) => plat(d.name).split(/\s+/)[0] === clipper.cle) || null;
}

/** Le « TOP 20 Reels » de la créatrice : au-dessus de « 🎬 Clippers », le dossier Instagram, puis « 📁 Reels », puis « TOP 20 Reels ». */
async function top20Creatrice(clipper: Clipper): Promise<Dossier | null> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return null;
  const parents = await driveParents(s.parent);
  if (!parents.length) return null;
  const reels = (await driveDossiers(parents[0])).find((d) => plat(d.name).includes("reels"));
  if (!reels) return null;
  return (await driveDossiers(reels.id)).find((d) => plat(d.name).includes("top")) || null;
}

export async function cibleClipper(clipper: Clipper, type: TypeTuile): Promise<Cible> {
  const cle = `${clipper.cle}:${type}`;
  const enCache = cache.get(cle);
  if (enCache && enCache.expire > Date.now()) return enCache.valeur;
  const c = creatriceDe(clipper.creatrice);
  const s = sourcesDe(clipper.creatrice);
  const source = (sous: string) => s?.sources.find((x) => plat(x.sous || "") === sous)?.id;
  let id = "", chemin: string[] = [], complet = true;

  if (type === "reels" || type === "photos") {
    const creatrice: Creatrice | null = c || (s ? { prenom: clipper.creatrice, racine: s.parent, reels: source("reels"), photos: source("photos") } : null);
    if (!creatrice) throw new Error(`créatrice inconnue : ${clipper.creatrice}`);
    const r = await cibleCreatrice(creatrice, type, source(type));
    id = r.id; chemin = r.chemin; complet = r.complet;
  } else if (type === "top") {
    const mien = await dossierClipper(clipper);
    const top = mien ? (await driveDossiers(mien.id)).find((d) => plat(d.name).includes("top") || plat(d.name).includes("unique")) : null;
    if (top) { id = top.id; chemin = [nomPropre(top.name)]; }
    else {
      const topC = await top20Creatrice(clipper).catch(() => null);
      if (topC) { id = topC.id; chemin = [`TOP 20 de ${clipper.creatrice}`]; complet = false; }
      else if (mien) { id = mien.id; chemin = ["Mon dossier"]; complet = false; }
      else throw new Error("pas de dossier TOP 20");
    }
  } else {
    const stories = source("stories");
    if (stories) { id = stories; chemin = ["Stories", clipper.creatrice]; }
    else {
      const mien = await dossierClipper(clipper);
      if (mien) { id = mien.id; chemin = ["Mon dossier"]; complet = false; }
      else throw new Error("pas de dossier Stories");
    }
  }
  const valeur: Cible = { type, id, url: `https://drive.google.com/drive/folders/${id}`, chemin, complet };
  cache.set(cle, { expire: Date.now() + DIX_MINUTES, valeur });
  return valeur;
}

/** Le repli de dernier recours d'une tuile : le dossier personnel du clipper (lisible par le lien), sinon le Drive. */
export async function urlDeSecours(clipper: Clipper): Promise<string> {
  try {
    const mien = await dossierClipper(clipper);
    if (mien) return `https://drive.google.com/drive/folders/${mien.id}`;
  } catch { /* on tombe sur le Drive */ }
  return "https://drive.google.com/";
}
